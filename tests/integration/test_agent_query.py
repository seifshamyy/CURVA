"""Integration test: drives /agent/query with a scripted LLM and real tools
backed by respx-mocked Curva API."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from curva_agent.llm.client import LLMResponse, LLMToolCall
from curva_agent.deps import reset_singletons_for_tests

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.fixture(autouse=True)
def _reset():
    reset_singletons_for_tests()
    yield
    reset_singletons_for_tests()


@pytest.mark.asyncio
@respx.mock
async def test_agent_query_invokes_search_and_finalizes():
    respx.post(f"{BASE}/products").mock(return_value=httpx.Response(200, json=_read("products_zamalek.json")))
    from curva_agent.supabase_client.taxonomy import (
        TaxonomySnapshot, CategoryRow, ClubRow, BrandRow, SeasonRow, BranchRow,
    )
    snap = TaxonomySnapshot(
        categories=[CategoryRow(id=1, name_ar="ملابس", name_en="Wear", image=None)],
        subcategories=[],
        clubs=[ClubRow(id=26, name_ar="الزمالك", name_en="Zamalek", type="club", supplier=None, image=None, orders_count=0)],
        brands=[], seasons=[], branches=[],
    )
    from curva_agent import deps
    deps.load_taxonomy_snapshot = AsyncMock(return_value=snap)

    public_args = {
        "reply_text": "عندنا قمصان زمالك",
        "products": [],
        "follow_up_suggestions": [],
        "intent": "search",
    }
    session_args = {"focus_product_ids": [10307], "last_filters": {"club_id": 26}, "conversation_summary": "asked about Zamalek"}
    from curva_agent.llm import client as llm_mod
    fake_llm = AsyncMock()
    fake_llm.complete = AsyncMock(side_effect=[
        LLMResponse(text="", tool_calls=[LLMToolCall(id="c1", name="search_products", arguments={"club_id": 26, "limit": 5, "page": 1})], finish_reason="tool_calls", usage={"prompt_tokens": 10}),
        LLMResponse(text="", tool_calls=[LLMToolCall(id="c2", name="finalize_response", arguments={"public": public_args, "next_session_state": session_args})], finish_reason="tool_calls", usage={"prompt_tokens": 12}),
    ])
    deps.build_llm_client = lambda: fake_llm

    from curva_agent.main import app
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


def test_agent_query_rejects_missing_api_key():
    from curva_agent.main import app
    client = TestClient(app)
    r = client.post("/agent/query", json={"session_id": "x", "user_message": "hi"})
    assert r.status_code == 401