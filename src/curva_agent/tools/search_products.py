"""Search products by structured filters."""
import hashlib
import json
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.schemas.tools import (
    ProductCardItem,
    SearchProductsInput,
    SearchProductsOutput,
)
from curva_agent.tools.base import Tool

STOREFRONT_URL = "https://curvaegypt.com/product/{id}"


class SearchProductsTool(Tool[SearchProductsInput, SearchProductsOutput]):
    name = "search_products"
    description = (
        "Search the Curva catalog with structured filters. Combine any of "
        "category_id, subcategory_id, club_id, brand_id, season_id, price range, "
        "free-text search, sort, and pagination. Returns product summaries "
        "(card-level: name, price, availability, image) — call get_product for "
        "full sizes/colors/stock."
    )
    input_model = SearchProductsInput

    def __init__(self, *, curva: CurvaClient, cache: AsyncTTLCache) -> None:
        self._curva = curva
        self._cache = cache

    async def run(self, args: SearchProductsInput, *, locale: str = "ar") -> SearchProductsOutput:
        filters = args.model_dump(exclude_none=True)
        key = _cache_key("search_products", locale, filters)

        async def load() -> SearchProductsOutput:
            r = await self._curva.search_products(filters, locale=locale)
            return SearchProductsOutput(
                items=[
                    ProductCardItem(
                        id=p.id,
                        name=p.name,
                        init_price=p.init_price,
                        offer_price=p.offer_price,
                        offer_ratio=p.offer_ratio,
                        availability=p.availability,
                        image=p.image,
                        url=STOREFRONT_URL.format(id=p.id),
                    )
                    for p in r.data.data
                ],
                total=r.data.total,
                page=r.data.current_page,
                last_page=r.data.last_page,
            )

        return await self._cache.get_or_load(key, load)


def _cache_key(prefix: str, locale: str, payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha256(body.encode()).hexdigest()[:16]
    return f"{prefix}:{locale}:{h}"