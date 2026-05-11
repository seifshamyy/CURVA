import json
from pathlib import Path
import httpx
import pytest
import respx
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.tools.get_offers import GetOffersTool
from curva_agent.tools.list_branches import ListBranchesTool
from curva_agent.schemas.tools import GetOffersInput, ListBranchesInput

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_get_offers_returns_discounted_items():
    respx.get(f"{BASE}/offers").mock(return_value=httpx.Response(200, json=_read("offers_p1.json")))
    async with CurvaClient(base_url=BASE) as c:
        tool = GetOffersTool(curva=c, cache=AsyncTTLCache(maxsize=64, ttl=60))
        out = await tool.run(GetOffersInput(page=1, limit=5))
    assert out.total >= 1
    assert out.items[0].url.startswith("https://curvaegypt.com/product/")


@pytest.mark.asyncio
@respx.mock
async def test_list_branches_returns_phones():
    respx.get(f"{BASE}/branches").mock(return_value=httpx.Response(200, json=_read("branches.json")))
    async with CurvaClient(base_url=BASE) as c:
        tool = ListBranchesTool(curva=c, cache=AsyncTTLCache(maxsize=8, ttl=86400))
        out = await tool.run(ListBranchesInput())
    assert len(out.branches) >= 1
    assert out.branches[0].phones


@pytest.mark.asyncio
@respx.mock
async def test_list_branches_cached_for_24h():
    route = respx.get(f"{BASE}/branches").mock(return_value=httpx.Response(200, json=_read("branches.json")))
    cache = AsyncTTLCache(maxsize=8, ttl=86400)
    async with CurvaClient(base_url=BASE) as c:
        tool = ListBranchesTool(curva=c, cache=cache)
        await tool.run(ListBranchesInput())
        await tool.run(ListBranchesInput())
        await tool.run(ListBranchesInput())
    assert route.call_count == 1
    assert cache.metrics()["hits"] == 2