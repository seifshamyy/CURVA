from unittest.mock import AsyncMock, MagicMock
import pytest
from curva_agent.llm.client import LLMClient, LLMMessage, LLMToolCall, LLMResponse


@pytest.mark.asyncio
async def test_complete_translates_openai_response_to_LLMResponse():
    fake_choice = MagicMock()
    fake_choice.message.content = "hello"
    fake_choice.message.tool_calls = None
    fake_choice.finish_reason = "stop"
    fake_completion = MagicMock(choices=[fake_choice], usage=MagicMock(prompt_tokens=10, completion_tokens=2))
    underlying = MagicMock()
    underlying.chat.completions.create = AsyncMock(return_value=fake_completion)

    client = LLMClient(api_key="x", model="anthropic/claude-sonnet-4.6", _client=underlying)
    resp = await client.complete(
        system_blocks=[{"type": "text", "text": "you are…", "cache_control": {"type": "ephemeral"}}],
        messages=[LLMMessage(role="user", content="hi")],
        tools=[],
    )
    assert isinstance(resp, LLMResponse)
    assert resp.text == "hello"
    assert resp.tool_calls == []
    assert resp.finish_reason == "stop"
    assert resp.usage["prompt_tokens"] == 10


@pytest.mark.asyncio
async def test_complete_extracts_tool_calls():
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = "search_products"
    tc.function.arguments = '{"club_id": 26}'
    fake_choice = MagicMock()
    fake_choice.message.content = None
    fake_choice.message.tool_calls = [tc]
    fake_choice.finish_reason = "tool_calls"
    fake_completion = MagicMock(choices=[fake_choice], usage=MagicMock(prompt_tokens=20, completion_tokens=5))
    underlying = MagicMock()
    underlying.chat.completions.create = AsyncMock(return_value=fake_completion)

    client = LLMClient(api_key="x", model="anthropic/claude-sonnet-4.6", _client=underlying)
    resp = await client.complete(system_blocks=[], messages=[LLMMessage(role="user", content="x")], tools=[])
    assert resp.tool_calls == [LLMToolCall(id="call_1", name="search_products", arguments={"club_id": 26})]


@pytest.mark.asyncio
async def test_complete_sends_cache_control_in_system():
    captured: dict = {}

    async def capture(**kwargs):
        captured.update(kwargs)
        fc = MagicMock()
        fc.message.content = ""
        fc.message.tool_calls = None
        fc.finish_reason = "stop"
        return MagicMock(choices=[fc], usage=MagicMock(prompt_tokens=0, completion_tokens=0))

    underlying = MagicMock()
    underlying.chat.completions.create = capture

    client = LLMClient(api_key="x", model="anthropic/claude-sonnet-4.6", _client=underlying)
    await client.complete(
        system_blocks=[
            {"type": "text", "text": "stable prefix", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "dynamic per-turn"},
        ],
        messages=[LLMMessage(role="user", content="hi")],
        tools=[],
    )
    system_msg = captured["messages"][0]
    assert system_msg["role"] == "system"
    assert system_msg["content"][0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_aclose_closes_underlying_openai_client():
    from unittest.mock import AsyncMock
    from curva_agent.llm.client import LLMClient

    fake_openai = AsyncMock()
    llm = LLMClient(api_key="k", model="m", _client=fake_openai)
    await llm.aclose()
    fake_openai.close.assert_awaited_once()