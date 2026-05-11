"""The agent's tool-use loop."""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
import orjson
from curva_agent.llm.client import LLMClient, LLMMessage, LLMResponse, LLMToolCall
from curva_agent.observability.logging import get_logger
from curva_agent.tools.base import Tool

log = get_logger("tool_loop")


class LoopExceeded(Exception):
    """The agent exceeded its tool-iteration safety cap."""


class ToolError(Exception):
    """A tool raised during execution (recoverable — reported to LLM)."""


@dataclass
class ToolLoopResult:
    final_text: str
    final_tool_calls: list[LLMToolCall]
    tool_calls_made: list[dict[str, Any]]
    iterations: int
    total_usage: dict[str, int] = field(default_factory=dict)


async def run_tool_loop(
    *,
    llm: LLMClient,
    system_blocks: list[dict[str, Any]],
    user_message: str,
    tools: dict[str, Tool],
    max_iterations: int = 12,
    locale: str = "ar",
    context_block: str | None = None,
    finalize_tool_name: str | None = None,
    finalize_tool_spec: dict[str, Any] | None = None,
) -> ToolLoopResult:
    messages: list[LLMMessage] = []
    if context_block:
        messages.append(LLMMessage(role="user", content=context_block))
    messages.append(LLMMessage(role="user", content=user_message))

    tool_specs = [t.tool_spec() for t in tools.values()]
    if finalize_tool_spec and finalize_tool_name:
        tool_specs.append(finalize_tool_spec)
    observability: list[dict[str, Any]] = []
    totals: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}

    for iteration in range(1, max_iterations + 1):
        resp: LLMResponse = await llm.complete(
            system_blocks=system_blocks, messages=messages, tools=tool_specs
        )
        for k in totals:
            totals[k] += resp.usage.get(k, 0)

        if finalize_tool_name and any(tc.name == finalize_tool_name for tc in resp.tool_calls):
            return ToolLoopResult(
                final_text=resp.text,
                final_tool_calls=resp.tool_calls,
                tool_calls_made=observability,
                iterations=iteration,
                total_usage=totals,
            )

        if not resp.tool_calls:
            return ToolLoopResult(
                final_text=resp.text,
                final_tool_calls=[],
                tool_calls_made=observability,
                iterations=iteration,
                total_usage=totals,
            )

        messages.append(
            LLMMessage(
                role="assistant",
                content=resp.text or None,
                tool_calls=[LLMClient.serialize_tool_call(tc) for tc in resp.tool_calls],
            )
        )

        results = await asyncio.gather(
            *[_invoke_tool(tools, tc, locale=locale) for tc in resp.tool_calls],
            return_exceptions=False,
        )
        for tc, (payload, obs) in zip(resp.tool_calls, results, strict=True):
            observability.append(obs)
            messages.append(LLMMessage(role="tool", tool_call_id=tc.id, name=tc.name, content=payload))

    raise LoopExceeded(f"loop exceeded {max_iterations} iterations")


async def _invoke_tool(
    tools: dict[str, Tool], tc: LLMToolCall, *, locale: str
) -> tuple[str, dict[str, Any]]:
    started = time.perf_counter()
    obs: dict[str, Any] = {"name": tc.name, "args": tc.arguments, "ok": False, "latency_ms": 0}
    tool = tools.get(tc.name)
    if tool is None:
        obs["error"] = f"unknown tool: {tc.name}"
        obs["latency_ms"] = int((time.perf_counter() - started) * 1000)
        return _err_payload(obs["error"]), obs
    try:
        validated = tool.input_model.model_validate(tc.arguments)
    except ValidationError as e:
        obs["error"] = f"invalid arguments: {e}"
        obs["latency_ms"] = int((time.perf_counter() - started) * 1000)
        return _err_payload(obs["error"]), obs
    try:
        out = await tool.run(validated, locale=locale)
        obs["ok"] = True
        obs["latency_ms"] = int((time.perf_counter() - started) * 1000)
        return orjson.dumps(out.model_dump()).decode(), obs
    except Exception as e:
        obs["error"] = f"{type(e).__name__}: {e}"
        obs["latency_ms"] = int((time.perf_counter() - started) * 1000)
        log.warning("tool_error", tool=tc.name, error=obs["error"])
        return _err_payload(obs["error"]), obs


def _err_payload(msg: str) -> str:
    return orjson.dumps({"error": msg}).decode()