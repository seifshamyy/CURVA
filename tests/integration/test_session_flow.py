"""Multi-turn integration test: turn 1 sets focus, turn 2 reads it."""
from unittest.mock import AsyncMock
import pytest
from curva_agent.llm.client import LLMResponse, LLMToolCall
from curva_agent.orchestrator.orchestrator import Orchestrator
from curva_agent.schemas.api import AgentQueryRequest
from curva_agent.supabase_client.sessions import SessionRepository, SessionRow
from curva_agent.supabase_client.taxonomy import (
    BranchRow, BrandRow, CategoryRow, ClubRow, SeasonRow, SubcategoryRow, TaxonomySnapshot,
)
from tests.unit.test_session_repo import StubSupabase


def _snap():
    return TaxonomySnapshot(
        categories=[CategoryRow(id=1, name_ar="ملابس", name_en="Wear", image=None)],
        subcategories=[],
        clubs=[ClubRow(id=26, name_ar="الزمالك", name_en="Zamalek", type="club", supplier=None, image=None, orders_count=0)],
        brands=[], seasons=[], branches=[],
    )


def _finalize(reply_text, intent, *, focus_product_ids=None, last_filters=None, conversation_summary=""):
    return LLMToolCall(id="f", name="finalize_response", arguments={
        "reply_text": reply_text,
        "products": [],
        "follow_up_suggestions": [],
        "intent": intent,
        "focus_product_ids": focus_product_ids or [],
        "last_filters": last_filters,
        "conversation_summary": conversation_summary,
    })


@pytest.mark.asyncio
async def test_session_focus_carries_across_turns():
    sup = StubSupabase()
    sessions = SessionRepository(sup)

    # Turn 1: LLM finalizes with focus_product_ids=[10307]
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        text="", tool_calls=[_finalize(
            "ها هو", "search",
            focus_product_ids=[10307],
            last_filters={"club_id": 26},
            conversation_summary="Showed Zamalek jersey",
        )], finish_reason="tool_calls", usage={},
    ))

    orch = Orchestrator(llm=llm, tools={}, snapshot_loader=AsyncMock(return_value=_snap()), model_name="t")
    captured_context: list = []

    # Wrap orchestrator.handle to capture session context per turn
    original_handle = orch.handle

    async def spy_handle(req, *, session_context):
        captured_context.append(session_context)
        return await original_handle(req, session_context=session_context)

    orch.handle = spy_handle

    # Turn 1
    req1 = AgentQueryRequest(session_id="20100", user_message="عندكوا زمالك؟", locale="ar")
    existing = await sessions.load("20100")
    ctx1 = _to_context(existing)
    resp1, next_state1 = await orch.handle(req1, session_context=ctx1)
    await sessions.save(_row_from_state("20100", "ar", next_state1, locale_for_new="ar"))

    # Turn 2: ensure the orchestrator now sees focus_product_ids=[10307]
    llm.complete = AsyncMock(return_value=LLMResponse(
        text="", tool_calls=[_finalize(
            "اللون أحمر متاح", "detail",
            focus_product_ids=[10307],
            conversation_summary="Confirmed red color in stock",
        )], finish_reason="tool_calls", usage={},
    ))
    req2 = AgentQueryRequest(session_id="20100", user_message="الأحمر متاح؟", locale="ar")
    existing2 = await sessions.load("20100")
    ctx2 = _to_context(existing2)
    resp2, _ = await orch.handle(req2, session_context=ctx2)

    assert captured_context[1] is not None
    assert captured_context[1]["focus_product_ids"] == [10307]
    assert "Zamalek" in captured_context[1]["conversation_summary"]


def _to_context(row: SessionRow | None) -> dict | None:
    if row is None:
        return None
    return {
        "focus_product_ids": row.focus_product_ids,
        "conversation_summary": row.conversation_summary,
        "last_filters": row.last_filters,
    }


def _row_from_state(sid, locale, state, locale_for_new):
    return SessionRow(
        session_id=sid, locale=locale or locale_for_new,
        focus_product_ids=state.focus_product_ids,
        last_filters=state.last_filters,
        conversation_summary=state.conversation_summary,
    )