import json
from pathlib import Path
import httpx
import pytest
import respx
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.tools.get_product import GetProductTool
from curva_agent.schemas.tools import GetProductInput

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_get_product_returns_flattened_variants():
    respx.get(f"{BASE}/product/10307").mock(return_value=httpx.Response(200, json=_read("product_10307.json")))
    async with CurvaClient(base_url=BASE) as c:
        tool = GetProductTool(curva=c, cache=AsyncTTLCache(maxsize=64, ttl=60))
        out = await tool.run(GetProductInput(product_id=10307))
    assert out.id == 10307
    assert out.primary_image.startswith("https://")
    assert len(out.images) >= 1
    assert len(out.variants) >= 1
    v = out.variants[0]
    assert v.size and v.size_id > 0
    assert v.available is True
    c0 = v.colors[0]
    assert c0.quantity >= 0
    assert c0.barcode.startswith(f"{out.id}-")
    assert out.url == f"https://curvaegypt.com/product/{out.id}"


@pytest.mark.asyncio
@respx.mock
async def test_variant_available_flag_reflects_stock():
    fixture = _read("product_10307.json")
    fixture["data"]["product"]["sizes"][0]["colors"][0]["quantity"] = "0"
    fixture["data"]["product"]["sizes"][0]["colors"] = [fixture["data"]["product"]["sizes"][0]["colors"][0]]
    respx.get(f"{BASE}/product/10307").mock(return_value=httpx.Response(200, json=fixture))
    async with CurvaClient(base_url=BASE) as c:
        tool = GetProductTool(curva=c, cache=AsyncTTLCache(maxsize=64, ttl=60))
        out = await tool.run(GetProductInput(product_id=10307))
    assert out.variants[0].available is False


@pytest.mark.asyncio
@respx.mock
async def test_get_product_is_cached():
    route = respx.get(f"{BASE}/product/10307").mock(return_value=httpx.Response(200, json=_read("product_10307.json")))
    cache = AsyncTTLCache(maxsize=64, ttl=60)
    async with CurvaClient(base_url=BASE) as c:
        tool = GetProductTool(curva=c, cache=cache)
        await tool.run(GetProductInput(product_id=10307))
        await tool.run(GetProductInput(product_id=10307))
    assert route.call_count == 1
    assert cache.metrics()["hits"] == 1