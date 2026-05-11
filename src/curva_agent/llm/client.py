"""Provider-neutral LLM client backed by the OpenAI SDK pointed at OpenRouter."""
import json
from dataclasses import dataclass, field
from typing import Any
import orjson
from openai import AsyncOpenAI


@dataclass
class LLMMessage:
    role: str
    content: str | list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    name: str | None = None


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    finish_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        _client: AsyncOpenAI | None = None,
    ) -> None:
        self._model = model
        self._client = _client or AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "HTTP-Referer": "https://curvaegypt.com",
                "X-Title": "Curva CS Agent",
            },
        )

    async def complete(
        self,
        *,
        system_blocks: list[dict[str, Any]],
        messages: list[LLMMessage],
        tools: list[dict[str, Any]],
        tool_choice: str | dict | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        openai_messages: list[dict[str, Any]] = []
        if system_blocks:
            openai_messages.append({"role": "system", "content": system_blocks})
        for m in messages:
            msg: dict[str, Any] = {"role": m.role}
            if m.content is not None:
                msg["content"] = m.content
            if m.tool_call_id is not None:
                msg["tool_call_id"] = m.tool_call_id
            if m.tool_calls is not None:
                msg["tool_calls"] = m.tool_calls
            if m.name is not None:
                msg["name"] = m.name
            openai_messages.append(msg)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        completion = await self._client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        tool_calls: list[LLMToolCall] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(LLMToolCall(id=tc.id, name=tc.function.name, arguments=args))
        usage = {}
        if completion.usage is not None:
            usage = {
                "prompt_tokens": getattr(completion.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(completion.usage, "completion_tokens", 0),
            }
            details = getattr(completion.usage, "prompt_tokens_details", None)
            if details is not None:
                cached = getattr(details, "cached_tokens", 0)
                usage["cached_tokens"] = cached or 0
        return LLMResponse(
            text=choice.message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "",
            usage=usage,
        )

    @staticmethod
    def serialize_tool_call(tc: LLMToolCall) -> dict[str, Any]:
        return {
            "id": tc.id,
            "type": "function",
            "function": {"name": tc.name, "arguments": orjson.dumps(tc.arguments).decode()},
        }