import json
from pathlib import Path
import httpx
import pytest
import respx
from curva_agent.curva_client.client import CurvaClient
from curva_agent.sync.taxonomy import sync_taxonomy, SyncResult
from tests.unit.test_taxonomy_repo import StubSupabase
from curva_agent.supabase_client.taxonomy import TaxonomyRepository

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_sync_taxonomy_full_run_populates_snapshot():
    respx.get(f"{BASE}/categories").mock(return_value=httpx.Response(200, json=_read("categories_ar.json")))
    respx.get(f"{BASE}/seasons").mock(return_value=httpx.Response(200, json=_read("seasons.json")))
    respx.get(f"{BASE}/branches").mock(return_value=httpx.Response(200, json=_read("branches.json")))
    respx.post(f"{BASE}/clubs").mock(return_value=httpx.Response(200, json=_read("clubs.json")))
    respx.post(f"{BASE}/brands").mock(return_value=httpx.Response(200, json=_read("brands.json")))
    respx.get(f"{BASE}/categories").mock(return_value=httpx.Response(200, json=_read("categories_ar.json")))

    sup = StubSupabase()
    repo = TaxonomyRepository(sup)

    async with CurvaClient(base_url=BASE) as c:
        result: SyncResult = await sync_taxonomy(curva=c, repo=repo)

    snap = await repo.load_snapshot()
    assert len(snap.categories) >= 5
    assert len(snap.clubs) >= 1
    assert len(snap.brands) >= 1
    assert any(s.name == "2026/27" for s in snap.seasons)
    assert result.ok is True
    assert result.counts["clubs"] == len(snap.clubs)


@pytest.mark.asyncio
@respx.mock
async def test_sync_taxonomy_reports_partial_failure():
    respx.get(f"{BASE}/categories").mock(return_value=httpx.Response(503))
    respx.get(f"{BASE}/seasons").mock(return_value=httpx.Response(200, json=_read("seasons.json")))
    respx.get(f"{BASE}/branches").mock(return_value=httpx.Response(200, json=_read("branches.json")))
    respx.post(f"{BASE}/clubs").mock(return_value=httpx.Response(200, json=_read("clubs.json")))
    respx.post(f"{BASE}/brands").mock(return_value=httpx.Response(200, json=_read("brands.json")))

    sup = StubSupabase()
    repo = TaxonomyRepository(sup)
    async with CurvaClient(base_url=BASE, timeout=5) as c:
        result = await sync_taxonomy(curva=c, repo=repo)

    assert result.ok is False
    assert "categories" in (result.error or "")