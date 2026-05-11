"""Parallel product detail fetch helper used by the Synthesizer."""
import asyncio
from typing import Any
from curva_agent.observability.logging import get_logger
from curva_agent.schemas.tools import GetProductInput

log = get_logger("tools.parallel")


async def fetch_products_parallel(tool: Any, product_ids: list[int], *, locale: str) -> list[Any]:
    async def _one(pid: int) -> Any | Exception:
        try:
            return await tool.run(GetProductInput(product_id=pid), locale=locale)
        except Exception as e:
            log.warning("synthesizer_fetch_failed", product_id=pid, error=str(e))
            return e

    raw = await asyncio.gather(*(_one(p) for p in product_ids))
    return [r for r in raw if not isinstance(r, Exception)]