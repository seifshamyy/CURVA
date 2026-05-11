"""List currently discounted products."""
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.schemas.tools import (
    GetOffersInput,
    GetOffersOutput,
    ProductCardItem,
)
from curva_agent.tools.base import Tool

STOREFRONT_URL = "https://curvaegypt.com/product/{id}"


class GetOffersTool(Tool[GetOffersInput, GetOffersOutput]):
    name = "get_offers"
    description = "List products currently on discount. Use when customer asks about deals, sales, or offers."
    input_model = GetOffersInput

    def __init__(self, *, curva: CurvaClient, cache: AsyncTTLCache) -> None:
        self._curva = curva
        self._cache = cache

    async def run(self, args: GetOffersInput, *, locale: str = "ar") -> GetOffersOutput:
        key = f"get_offers:{locale}:{args.page}:{args.limit}"

        async def load() -> GetOffersOutput:
            r = await self._curva.get_offers(page=args.page, limit=args.limit, locale=locale)
            return GetOffersOutput(
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