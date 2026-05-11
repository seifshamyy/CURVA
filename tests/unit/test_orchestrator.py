import pytest
from unittest.mock import AsyncMock
from curva_agent.llm.client import LLMResponse, LLMToolCall
from curva_agent.orchestrator.orchestrator import Orchestrator
from curva_agent.schemas.api import AgentQueryRequest, AgentQueryResponse
from curva_agent.supabase_client.taxonomy import (
    BrandRow, CategoryRow, ClubRow, SeasonRow, SubcategoryRow, BranchRow, TaxonomySnapshot,
)


def _snap() -> TaxonomySnapshot:
    return TaxonomySnapshot(
        categories=[CategoryRow(id=1, name_ar="ملابس", name_en="Wear", image=None)],
        subcategories=[SubcategoryRow(id=3, category_id=1, name_ar="قمصان", name_en="Jerseys")],
        clubs=[ClubRow(id=26, name_ar="الزمالك", name_en="Zamalek", type="club", supplier=None, image=None, orders_count=0)],
        brands=[BrandRow(id=8, name_ar="نايكي", name_en="Nike", image=None, orders_count=0)],
        seasons=[SeasonRow(id=40, name="2026/27")],
        branches=[BranchRow(id=3, name="مدينة نصر", phones=["010"], sort=1)],
    )


def _finalize_call(**kwargs) -> LLMToolCall:
    defaults = {
        "reply_text": "",
        "products": [],
        "follow_up_suggestions": [],
        "intent": "search",
        "focus_product_ids": [],
        "last_filters": None,
        "conversation_summary": "",
    }
    defaults.update(kwargs)
    return LLMToolCall(
        id="final_1", name="finalize_response",
        arguments=defaults,
    )


@pytest.mark.asyncio
async def test_orchestrator_returns_validated_response_from_finalize():
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        text="", tool_calls=[_finalize_call(
            reply_text="تمام", intent="smalltalk", conversation_summary="hi",
        )], finish_reason="tool_calls", usage={},
    ))

    orch = Orchestrator(llm=llm, tools={}, snapshot_loader=AsyncMock(return_value=_snap()), model_name="test-model")
    req = AgentQueryRequest(session_id="x", user_message="hi", locale="ar")
    resp, next_state = await orch.handle(req, session_context=None)

    assert isinstance(resp, AgentQueryResponse)
    assert resp.intent == "smalltalk"
    assert resp.diagnostics.model == "test-model"
    assert next_state.conversation_summary == "hi"


@pytest.mark.asyncio
async def test_orchestrator_handles_missing_finalize_gracefully():
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        text="freeform reply", tool_calls=[], finish_reason="stop", usage={},
    ))

    orch = Orchestrator(llm=llm, tools={}, snapshot_loader=AsyncMock(return_value=_snap()), model_name="test")
    req = AgentQueryRequest(session_id="x", user_message="hi", locale="ar")
    resp, next_state = await orch.handle(req, session_context=None)
    assert resp.reply_text == "freeform reply"
    assert resp.intent == "handoff"