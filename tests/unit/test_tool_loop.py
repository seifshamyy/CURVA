"""Tests for the tool-use loop with a stub LLM client."""
from unittest.mock import AsyncMock
import pytest
from pydantic import BaseModel
from curva_agent.llm.client import LLMResponse, LLMToolCall
from curva_agent.llm.tool_loop import run_tool_loop, LoopExceeded
from curva_agent.tools.base import Tool


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    echoed: str


class EchoTool(Tool[EchoInput, EchoOutput]):
    name = "echo"
    description = "Echo the input text"
    input_model = EchoInput

    async def run(self, args: EchoInput, *, locale: str = "ar") -> EchoOutput:
        return EchoOutput(echoed=args.text.upper())


@pytest.mark.asyncio
async def test_loop_calls_tool_then_finalizes():
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=[
        LLMResponse(text="", tool_calls=[LLMToolCall(id="c1", name="echo", arguments={"text": "hello"})], finish_reason="tool_calls", usage={"prompt_tokens": 5}),
        LLMResponse(text="Done", tool_calls=[], finish_reason="stop", usage={"prompt_tokens": 8}),
    ])

    result = await run_tool_loop(
        llm=llm,
        system_blocks=[],
        user_message="say hello",
        tools={EchoTool().name: EchoTool()},
        max_iterations=5,
        locale="en",
    )
    assert result.final_text == "Done"
    assert len(result.tool_calls_made) == 1
    assert result.tool_calls_made[0]["name"] == "echo"
    assert result.tool_calls_made[0]["ok"] is True


@pytest.mark.asyncio
async def test_loop_handles_parallel_tool_calls():
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=[
        LLMResponse(text="", tool_calls=[
            LLMToolCall(id="c1", name="echo", arguments={"text": "a"}),
            LLMToolCall(id="c2", name="echo", arguments={"text": "b"}),
        ], finish_reason="tool_calls", usage={"prompt_tokens": 5}),
        LLMResponse(text="ok", tool_calls=[], finish_reason="stop", usage={"prompt_tokens": 8}),
    ])
    result = await run_tool_loop(
        llm=llm, system_blocks=[], user_message="run both",
        tools={EchoTool().name: EchoTool()}, max_iterations=5, locale="en",
    )
    assert len(result.tool_calls_made) == 2


@pytest.mark.asyncio
async def test_loop_raises_when_cap_exceeded():
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        text="", tool_calls=[LLMToolCall(id="c", name="echo", arguments={"text": "x"})],
        finish_reason="tool_calls", usage={},
    ))
    with pytest.raises(LoopExceeded):
        await run_tool_loop(
            llm=llm, system_blocks=[], user_message="forever",
            tools={EchoTool().name: EchoTool()}, max_iterations=3, locale="en",
        )


@pytest.mark.asyncio
async def test_tool_error_surfaces_as_tool_message_to_llm():
    class FailingTool(Tool):
        name = "fail"; description = "always fails"; input_model = EchoInput
        async def run(self, args, *, locale="ar"):
            raise RuntimeError("kaboom")

    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=[
        LLMResponse(text="", tool_calls=[LLMToolCall(id="c1", name="fail", arguments={"text": "x"})], finish_reason="tool_calls", usage={}),
        LLMResponse(text="sorry", tool_calls=[], finish_reason="stop", usage={}),
    ])
    result = await run_tool_loop(
        llm=llm, system_blocks=[], user_message="x",
        tools={FailingTool().name: FailingTool()}, max_iterations=5, locale="en",
    )
    assert result.tool_calls_made[0]["ok"] is False
    assert "kaboom" in result.tool_calls_made[0]["error"]


@pytest.mark.asyncio
async def test_unknown_tool_returns_error_to_llm():
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=[
        LLMResponse(text="", tool_calls=[LLMToolCall(id="c1", name="nonexistent", arguments={})], finish_reason="tool_calls", usage={}),
        LLMResponse(text="ok", tool_calls=[], finish_reason="stop", usage={}),
    ])
    result = await run_tool_loop(
        llm=llm, system_blocks=[], user_message="x",
        tools={EchoTool().name: EchoTool()}, max_iterations=5, locale="en",
    )
    assert result.tool_calls_made[0]["ok"] is False
    assert "unknown tool" in result.tool_calls_made[0]["error"].lower()


@pytest.mark.asyncio
async def test_invalid_tool_arguments_returns_structured_error():
    """When the model sends args that fail Pydantic validation, the loop must
    report a structured tool error back to the LLM rather than crashing."""
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=[
        LLMResponse(
            text="",
            tool_calls=[LLMToolCall(id="c1", name="echo", arguments={})],
            finish_reason="tool_calls",
            usage={},
        ),
        LLMResponse(text="ok", tool_calls=[], finish_reason="stop", usage={}),
    ])
    result = await run_tool_loop(
        llm=llm,
        system_blocks=[],
        user_message="x",
        tools={EchoTool().name: EchoTool()},
        max_iterations=5,
        locale="en",
    )
    assert result.tool_calls_made[0]["ok"] is False
    assert "invalid arguments" in result.tool_calls_made[0]["error"].lower()