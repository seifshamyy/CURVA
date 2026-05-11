import json
from pathlib import Path
import httpx
import pytest
import respx
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.tools.search_products import SearchProductsTool, SearchProductsInput

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_search_returns_summaries():
    respx.post(f"{BASE}/products").mock(return_value=httpx.Response(200, json=_read("products_zamalek.json")))
    async with CurvaClient(base_url=BASE) as c:
        tool = SearchProductsTool(curva=c, cache=AsyncTTLCache(maxsize=64, ttl=60))
        out = await tool.run(SearchProductsInput(club_id=26, limit=5, page=1))
    assert out.total >= 1
    assert out.items[0].id > 0
    assert out.items[0].url.startswith("https://curvaegypt.com/product/")


@pytest.mark.asyncio
@respx.mock
async def test_search_results_are_cached_per_filter():
    route = respx.post(f"{BASE}/products").mock(return_value=httpx.Response(200, json=_read("products_zamalek.json")))
    cache = AsyncTTLCache(maxsize=64, ttl=60)
    async with CurvaClient(base_url=BASE) as c:
        tool = SearchProductsTool(curva=c, cache=cache)
        await tool.run(SearchProductsInput(club_id=26, limit=5, page=1))
        await tool.run(SearchProductsInput(club_id=26, limit=5, page=1))
        await tool.run(SearchProductsInput(club_id=26, limit=10, page=1))
    assert route.call_count == 2
    assert cache.metrics()["hits"] == 1


def test_search_input_is_jsonable_for_tool_use():
    schema = SearchProductsInput.model_json_schema()
    club_id = schema["properties"]["club_id"]
    assert "category_id" in schema["properties"]
    assert club_id.get("anyOf") or club_id.get("type")


@pytest.mark.asyncio
@respx.mock
async def test_locale_is_propagated():
    route = respx.post(f"{BASE}/products").mock(return_value=httpx.Response(200, json=_read("products_zamalek.json")))
    async with CurvaClient(base_url=BASE) as c:
        tool = SearchProductsTool(curva=c, cache=AsyncTTLCache(maxsize=64, ttl=60))
        await tool.run(SearchProductsInput(club_id=26, limit=5), locale="en")
    assert route.calls[0].request.headers["accept-language"] == "en"