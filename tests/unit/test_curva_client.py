import json
from pathlib import Path
import httpx
import pytest
import respx
from curva_agent.curva_client.client import CurvaClient

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_get_categories():
    respx.get(f"{BASE}/categories").mock(return_value=httpx.Response(200, json=_read("categories_ar.json")))
    async with CurvaClient(base_url=BASE) as c:
        cats = await c.get_categories(locale="ar")
    assert len(cats.data) >= 5


@pytest.mark.asyncio
@respx.mock
async def test_search_products_posts_with_body():
    route = respx.post(f"{BASE}/products").mock(
        return_value=httpx.Response(200, json=_read("products_zamalek.json"))
    )
    async with CurvaClient(base_url=BASE) as c:
        r = await c.search_products({"club_id": 26, "limit": 5, "page": 1})
    assert route.called
    sent_body = json.loads(route.calls[0].request.content)
    assert sent_body == {"club_id": 26, "limit": 5, "page": 1}
    assert r.data.total >= 1


@pytest.mark.asyncio
@respx.mock
async def test_get_product():
    respx.get(f"{BASE}/product/10307").mock(return_value=httpx.Response(200, json=_read("product_10307.json")))
    async with CurvaClient(base_url=BASE) as c:
        r = await c.get_product(10307)
    assert r.data.product.id == 10307


@pytest.mark.asyncio
@respx.mock
async def test_get_offers_uses_query_params():
    route = respx.get(f"{BASE}/offers").mock(
        return_value=httpx.Response(200, json=_read("offers_p1.json"))
    )
    async with CurvaClient(base_url=BASE) as c:
        await c.get_offers(page=1, limit=5)
    assert dict(route.calls[0].request.url.params) == {"page": "1", "limit": "5"}


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_5xx():
    route = respx.get(f"{BASE}/categories").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=_read("categories_ar.json"))]
    )
    async with CurvaClient(base_url=BASE) as c:
        r = await c.get_categories()
    assert route.call_count == 2
    assert r.status is True


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_warning_threshold():
    respx.get(f"{BASE}/categories").mock(
        return_value=httpx.Response(
            200,
            json=_read("categories_ar.json"),
            headers={"X-RateLimit-Limit": "100", "X-RateLimit-Remaining": "10"},
        )
    )
    warnings: list = []
    async with CurvaClient(base_url=BASE, rate_limit_warn_at=20, on_rate_limit_low=warnings.append) as c:
        await c.get_categories()
    assert warnings == [10]


@pytest.mark.asyncio
@respx.mock
async def test_sends_user_agent_and_accept_language():
    route = respx.get(f"{BASE}/categories").mock(return_value=httpx.Response(200, json=_read("categories_ar.json")))
    async with CurvaClient(base_url=BASE, user_agent="CurvaCSAgent/1.0") as c:
        await c.get_categories(locale="ar")
    req = route.calls[0].request
    assert req.headers["user-agent"] == "CurvaCSAgent/1.0"
    assert req.headers["accept-language"] == "ar"