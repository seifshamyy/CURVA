import asyncio
import pytest
from curva_agent.tools._parallel import fetch_products_parallel
from curva_agent.schemas.tools import GetProductInput


class StubGetProductTool:
    def __init__(self):
        self.calls = []

    async def run(self, args, *, locale="ar"):
        self.calls.append(args.product_id)
        await asyncio.sleep(0.01)
        return type("Out", (), {"id": args.product_id, "name": f"P{args.product_id}"})()


@pytest.mark.asyncio
async def test_fetches_in_parallel_and_preserves_order():
    tool = StubGetProductTool()
    out = await fetch_products_parallel(tool, [3, 1, 4, 1, 5], locale="ar")
    assert [p.id for p in out] == [3, 1, 4, 1, 5]


@pytest.mark.asyncio
async def test_partial_failures_dropped_with_warning():
    class FlakyTool:
        async def run(self, args, *, locale="ar"):
            if args.product_id == 2:
                raise RuntimeError("boom")
            return type("Out", (), {"id": args.product_id, "name": f"P{args.product_id}"})()

    out = await fetch_products_parallel(FlakyTool(), [1, 2, 3], locale="ar")
    assert [p.id for p in out] == [1, 3]