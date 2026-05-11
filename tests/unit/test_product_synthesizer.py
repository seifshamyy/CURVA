import json
from pathlib import Path
from unittest.mock import AsyncMock
import httpx
import pytest
import respx
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.llm.client import LLMResponse, LLMToolCall
from curva_agent.tools.get_product import GetProductTool
from curva_agent.tools.product_synthesizer import ProductSynthesizerTool
from curva_agent.schemas.tools import ProductSynthesizerInput

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_synthesizer_ranks_candidates_via_llm():
    respx.get(f"{BASE}/product/10307").mock(return_value=httpx.Response(200, json=_read("product_10307.json")))

    fake_llm = AsyncMock()
    fake_llm.complete = AsyncMock(return_value=LLMResponse(
        text='{"candidates":[{"id":10307,"rationale":"size M in stock"}]}',
        tool_calls=[], finish_reason="stop", usage={"prompt_tokens": 50, "completion_tokens": 20},
    ))

    async with CurvaClient(base_url=BASE) as curva:
        gp = GetProductTool(curva=curva, cache=AsyncTTLCache(maxsize=8, ttl=60))
        synth = ProductSynthesizerTool(get_product=gp, llm=fake_llm)
        out = await synth.run(ProductSynthesizerInput(product_ids=[10307], constraint="size M"))

    assert len(out.candidates) == 1
    c = out.candidates[0]
    assert c.id == 10307
    assert c.rationale == "size M in stock"
    assert c.primary_image.startswith("https://")
    assert any(v.size == "M" for v in c.best_variants)
    assert c.url == "https://curvaegypt.com/product/10307"


@pytest.mark.asyncio
@respx.mock
async def test_synthesizer_drops_missing_products():
    respx.get(f"{BASE}/product/10307").mock(return_value=httpx.Response(200, json=_read("product_10307.json")))
    respx.get(f"{BASE}/product/99999").mock(return_value=httpx.Response(404, json={"status": False}))

    fake_llm = AsyncMock()
    fake_llm.complete = AsyncMock(return_value=LLMResponse(
        text='{"candidates":[{"id":10307,"rationale":"only one available"}]}',
        tool_calls=[], finish_reason="stop", usage={},
    ))

    async with CurvaClient(base_url=BASE) as curva:
        gp = GetProductTool(curva=curva, cache=AsyncTTLCache(maxsize=8, ttl=60))
        synth = ProductSynthesizerTool(get_product=gp, llm=fake_llm)
        out = await synth.run(ProductSynthesizerInput(product_ids=[10307, 99999], constraint=None))

    assert [c.id for c in out.candidates] == [10307]


@pytest.mark.asyncio
async def test_synthesizer_handles_llm_returning_invalid_json():
    fake_llm = AsyncMock()
    fake_llm.complete = AsyncMock(return_value=LLMResponse(
        text="not json at all", tool_calls=[], finish_reason="stop", usage={},
    ))

    class StubGP:
        async def run(self, args, *, locale="ar"):
            return type("P", (), {
                "id": args.product_id, "name": f"P{args.product_id}", "init_price": 100,
                "offer_price": None, "availability": "available", "primary_image": "https://x/y.webp", "images": [],
                "variants": [], "url": f"https://curvaegypt.com/product/{args.product_id}",
            })()

    synth = ProductSynthesizerTool(get_product=StubGP(), llm=fake_llm)
    out = await synth.run(ProductSynthesizerInput(product_ids=[1, 2], constraint=None))
    assert [c.id for c in out.candidates] == [1, 2]
    assert all(c.rationale == "" for c in out.candidates)