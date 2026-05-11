"""Integration test: drives /agent/query with a scripted LLM and real tools
backed by respx-mocked Curva API."""
import json
from pathlib import Path
from unittest.mock import AsyncMock
import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from curva_agent.llm.client import LLMResponse, LLMToolCall
from curva_agent.deps import reset_singletons_for_tests, get_orchestrator, get_session_repo, get_logs_repo
from curva_agent.supabase_client.logs import AgentLogsRepository
from curva_agent.supabase_client.sessions import SessionRepository
from curva_agent.orchestrator.orchestrator import Orchestrator
from curva_agent.supabase_client.taxonomy import (
    TaxonomySnapshot, CategoryRow, ClubRow, BrandRow, SeasonRow, BranchRow,
)
from tests.unit.test_session_repo import StubSupabase as _SessionStubSupabase
from tests.unit.test_logs_repo import StubSupabase as _LogsStubSupabase

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


def _snap():
    return TaxonomySnapshot(
        categories=[CategoryRow(id=1, name_ar="ملابس", name_en="Wear", image=None)],
        subcategories=[],
        clubs=[ClubRow(id=26, name_ar="الزمالك", name_en="Zamalek", type="club", supplier=None, image=None, orders_count=0)],
        brands=[BrandRow(id=8, name_ar="نايكي", name_en="Nike", image=None, orders_count=0)],
        seasons=[SeasonRow(id=40, name="2026/27")],
        branches=[BranchRow(id=3, name="test", phones=["010"], sort=1)],
    )


@pytest.fixture(autouse=True)
def _reset():
    reset_singletons_for_tests()
    yield
    reset_singletons_for_tests()


@pytest.mark.asyncio
@respx.mock
async def test_agent_query_invokes_search_and_finalizes():
    respx.post(f"{BASE}/products").mock(return_value=httpx.Response(200, json=_read("products_zamalek.json")))

    snap = _snap()
    stub_session_repo = SessionRepository(_SessionStubSupabase())
    stub_logs_repo = AgentLogsRepository(_LogsStubSupabase())

    fake_llm = AsyncMock()
    finalize_args = {
        "reply_text": "عندنا قمصان زمالك",
        "products": [],
        "follow_up_suggestions": [],
        "intent": "search",
        "focus_product_ids": [10307],
        "last_filters": {"club_id": 26},
        "conversation_summary": "asked about Zamalek",
    }
    fake_llm.complete = AsyncMock(side_effect=[
        LLMResponse(text="", tool_calls=[LLMToolCall(id="c1", name="search_products", arguments={"club_id": 26, "limit": 5, "page": 1})], finish_reason="tool_calls", usage={"prompt_tokens": 10}),
        LLMResponse(text="", tool_calls=[LLMToolCall(id="c2", name="finalize_response", arguments=finalize_args)], finish_reason="tool_calls", usage={"prompt_tokens": 12}),
    ])

    stub_orchestrator = Orchestrator(
        llm=fake_llm,
        tools={},
        snapshot_loader=AsyncMock(return_value=snap),
        model_name="test-model",
    )

    from curva_agent.main import app

    app.dependency_overrides[get_orchestrator] = lambda: stub_orchestrator
    app.dependency_overrides[get_session_repo] = lambda: stub_session_repo
    app.dependency_overrides[get_logs_repo] = lambda: stub_logs_repo

    try:
        client = TestClient(app)
        r = client.post(
            "/agent/query",
            headers={"X-API-Key": "test-agent-key"},
            json={"session_id": "20100", "user_message": "عندكوا زمالك؟", "locale": "ar"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["intent"] == "search"
        assert body["reply_text"]
        assert body["diagnostics"]["tool_calls"] >= 1
        assert body["diagnostics"]["iterations"] >= 2
    finally:
        app.dependency_overrides.clear()


def test_agent_query_rejects_missing_api_key():
    from curva_agent.main import app
    client = TestClient(app)
    r = client.post("/agent/query", json={"session_id": "x", "user_message": "hi"})
    assert r.status_code == 401