"""Fetch full product detail: sizes, colors, stock, images, description."""
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.schemas.tools import (
    ColorOption,
    GetProductInput,
    GetProductOutput,
    VariantBySize,
)
from curva_agent.tools.base import Tool

STOREFRONT_URL = "https://curvaegypt.com/product/{id}"


class GetProductTool(Tool[GetProductInput, GetProductOutput]):
    name = "get_product"
    description = (
        "Get complete details for one product by ID — all sizes and color "
        "variants with stock quantities, full image gallery, description HTML, "
        "and category/club/brand/season metadata. Use after search_products "
        "to inspect a specific product."
    )
    input_model = GetProductInput

    def __init__(self, *, curva: CurvaClient, cache: AsyncTTLCache) -> None:
        self._curva = curva
        self._cache = cache

    async def run(self, args: GetProductInput, *, locale: str = "ar") -> GetProductOutput:
        key = f"get_product:{locale}:{args.product_id}"

        async def load() -> GetProductOutput:
            r = await self._curva.get_product(args.product_id, locale=locale)
            p = r.data.product
            variants = []
            for size_block in p.sizes:
                colors = [
                    ColorOption(
                        name=cv.color.name,
                        hex=cv.color.color,
                        quantity=int(cv.quantity) if cv.quantity.isdigit() else 0,
                        barcode=cv.barcode,
                        image=cv.image,
                    )
                    for cv in size_block.colors
                ]
                variants.append(
                    VariantBySize(
                        size=size_block.size.name,
                        size_id=size_block.size.id,
                        price=size_block.final_price,
                        offer_price=size_block.offer_price,
                        available=any(c.quantity > 0 for c in colors),
                        colors=colors,
                    )
                )
            images = [im.image for im in sorted(p.images, key=lambda x: x.sort)]
            primary_image = images[0] if images else ""

            return GetProductOutput(
                id=p.id,
                name=p.name,
                init_price=p.init_price,
                offer_price=p.offer_price,
                availability=p.availability,
                description_html=p.desc,
                url=STOREFRONT_URL.format(id=p.id),
                images=images,
                primary_image=primary_image,
                variants=variants,
                club={"id": p.club.id, "name": p.club.name} if p.club else None,
                brand={"id": p.brand.id, "name": p.brand.name} if p.brand else None,
                season=p.season.name if p.season else None,
                category=p.category.get("name") if p.category else None,
                subcategory=p.subcategory.get("name") if p.subcategory else None,
            )

        return await self._cache.get_or_load(key, load)