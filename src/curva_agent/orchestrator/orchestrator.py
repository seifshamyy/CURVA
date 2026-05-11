"""Master orchestrator: composes LLM + tools + taxonomy."""
import time
from collections.abc import Awaitable, Callable
from typing import Any
from pydantic import ValidationError
from curva_agent.llm.client import LLMClient
from curva_agent.llm.prompts import build_system_blocks, build_user_context_block
from curva_agent.llm.tool_loop import LoopExceeded, run_tool_loop
from curva_agent.observability.logging import get_logger
from curva_agent.orchestrator.finalize import FINALIZE_TOOL_NAME, FINALIZE_TOOL_SPEC
from curva_agent.schemas.api import (
    AgentQueryRequest,
    AgentQueryResponse,
    Diagnostics,
    FinalizeArgs,
    NextSessionState,
)
from curva_agent.supabase_client.taxonomy import TaxonomySnapshot
from curva_agent.tools.base import Tool

log = get_logger("orchestrator")


class Orchestrator:
    def __init__(
        self,
        *,
        llm: LLMClient,
        tools: dict[str, Tool],
        snapshot_loader: Callable[[], Awaitable[TaxonomySnapshot]],
        model_name: str,
        max_iterations: int = 12,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._load_snapshot = snapshot_loader
        self._model_name = model_name
        self._max_iterations = max_iterations

    async def handle(
        self,
        req: AgentQueryRequest,
        *,
        session_context: dict[str, Any] | None,
    ) -> tuple[AgentQueryResponse, NextSessionState]:
        started = time.perf_counter()
        snapshot = await self._load_snapshot()
        system_blocks = build_system_blocks(snapshot=snapshot, locale=req.locale)

        context_block = build_user_context_block(
            session_summary=(session_context or {}).get("conversation_summary"),
            focus_product_ids=(session_context or {}).get("focus_product_ids", []),
            conversation_history=[t.model_dump() for t in req.conversation_history] or None,
        )

        try:
            loop_result = await run_tool_loop(
                llm=self._llm,
                system_blocks=system_blocks,
                user_message=req.user_message,
                tools=self._tools,
                max_iterations=self._max_iterations,
                locale=req.locale,
                context_block=context_block,
                finalize_tool_name=FINALIZE_TOOL_NAME,
                finalize_tool_spec=FINALIZE_TOOL_SPEC,
            )
        except LoopExceeded:
            log.warning("loop_exceeded", session_id=req.session_id)
            return self._handoff_fallback("loop exceeded"), NextSessionState()

        latency_ms = int((time.perf_counter() - started) * 1000)

        final_call = next(
            (tc for tc in loop_result.final_tool_calls if tc.name == FINALIZE_TOOL_NAME), None
        )
        if final_call is None:
            return self._wrap_freeform(loop_result.final_text), NextSessionState()

        try:
            args = FinalizeArgs.model_validate(final_call.arguments)
        except ValidationError as e:
            log.error("finalize_invalid", error=str(e), args=final_call.arguments)
            return self._handoff_fallback(f"invalid finalize args: {e}"), NextSessionState()

        if not args.reply_text:
            log.warning("finalize_empty_reply", args=final_call.arguments)
            return self._wrap_freeform(loop_result.final_text), NextSessionState()

        response = args.to_response()
        response.diagnostics = Diagnostics(
            tool_calls=len(loop_result.tool_calls_made),
            synthesizer_invoked=any(
                c["name"] == "product_synthesizer" for c in loop_result.tool_calls_made
            ),
            latency_ms=latency_ms,
            model=self._model_name,
            cache_hits=sum(1 for c in loop_result.tool_calls_made if c.get("cache_hit")),
            iterations=loop_result.iterations,
            tool_calls_detail=loop_result.tool_calls_made,
            prompt_tokens=loop_result.total_usage.get("prompt_tokens", 0),
            completion_tokens=loop_result.total_usage.get("completion_tokens", 0),
            cached_tokens=loop_result.total_usage.get("cached_tokens", 0),
        )
        return response, args.to_session_state()

    def _wrap_freeform(self, text: str) -> AgentQueryResponse:
        return AgentQueryResponse(
            reply_text=text or "آسف، حصل خطأ. هاسأل حد من الفريق يساعدك.",
            products=[],
            follow_up_suggestions=[],
            intent="handoff",
        )

    def _handoff_fallback(self, reason: str) -> AgentQueryResponse:
        log.warning("handoff_fallback", reason=reason)
        return AgentQueryResponse(
            reply_text="آسف، مش قادر أساعدك دلوقتي. هاسأل حد من الفريق يكلمك.",
            products=[],
            follow_up_suggestions=[],
            intent="handoff",
        )