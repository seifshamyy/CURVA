"""Taxonomy repository — reads and writes reference tables in Supabase.

Accepts any Supabase-like client with a `table(name).upsert(...).execute()` /
`select(...).execute()` interface so we can unit-test against a stub.
"""
from dataclasses import asdict, dataclass
from typing import Any, Protocol


@dataclass
class CategoryRow:
    id: int
    name_ar: str
    name_en: str
    image: str | None = None


@dataclass
class SubcategoryRow:
    id: int
    category_id: int
    name_ar: str
    name_en: str


@dataclass
class ClubRow:
    id: int
    name_ar: str
    name_en: str | None
    type: str | None
    supplier: str | None
    image: str | None
    orders_count: int = 0


@dataclass
class BrandRow:
    id: int
    name_ar: str
    name_en: str | None
    image: str | None
    orders_count: int = 0


@dataclass
class SeasonRow:
    id: int
    name: str


@dataclass
class BranchRow:
    id: int
    name: str
    phones: list[str]
    sort: int | None


@dataclass
class TaxonomySnapshot:
    categories: list[CategoryRow]
    subcategories: list[SubcategoryRow]
    clubs: list[ClubRow]
    brands: list[BrandRow]
    seasons: list[SeasonRow]
    branches: list[BranchRow]

    def to_llm_json(self) -> dict[str, Any]:
        return {
            "categories": [{"id": c.id, "name_ar": c.name_ar, "name_en": c.name_en} for c in self.categories],
            "subcategories": [
                {"id": s.id, "category_id": s.category_id, "name_ar": s.name_ar, "name_en": s.name_en}
                for s in self.subcategories
            ],
            "clubs": [
                {"id": c.id, "name_ar": c.name_ar, "name_en": c.name_en, "type": c.type}
                for c in self.clubs
            ],
            "brands": [
                {"id": b.id, "name_ar": b.name_ar, "name_en": b.name_en}
                for b in self.brands
            ],
            "seasons": [{"id": s.id, "name": s.name} for s in self.seasons],
            "branches": [
                {"id": br.id, "name": br.name, "phones": br.phones}
                for br in self.branches
            ],
        }


class _SupabaseLike(Protocol):
    def table(self, name: str) -> Any: ...


class TaxonomyRepository:
    def __init__(self, client: _SupabaseLike) -> None:
        self._c = client

    async def upsert_categories(self, rows: list[CategoryRow]) -> None:
        if not rows:
            return
        await self._c.table("categories").upsert([asdict(r) for r in rows], on_conflict="id").execute()

    async def upsert_subcategories(self, rows: list[SubcategoryRow]) -> None:
        if not rows:
            return
        await self._c.table("subcategories").upsert([asdict(r) for r in rows], on_conflict="id").execute()

    async def upsert_clubs(self, rows: list[ClubRow]) -> None:
        if not rows:
            return
        await self._c.table("clubs").upsert([asdict(r) for r in rows], on_conflict="id").execute()

    async def upsert_brands(self, rows: list[BrandRow]) -> None:
        if not rows:
            return
        await self._c.table("brands").upsert([asdict(r) for r in rows], on_conflict="id").execute()

    async def upsert_seasons(self, rows: list[SeasonRow]) -> None:
        if not rows:
            return
        await self._c.table("seasons").upsert([asdict(r) for r in rows], on_conflict="id").execute()

    async def upsert_branches(self, rows: list[BranchRow]) -> None:
        if not rows:
            return
        await self._c.table("branches").upsert([asdict(r) for r in rows], on_conflict="id").execute()

    async def load_snapshot(self) -> TaxonomySnapshot:
        cats_r = await self._c.table("categories").select("*").order("id").execute()
        subs_r = await self._c.table("subcategories").select("*").order("id").execute()
        clubs_r = await self._c.table("clubs").select("*").order("orders_count", desc=True).execute()
        brands_r = await self._c.table("brands").select("*").order("orders_count", desc=True).execute()
        seasons_r = await self._c.table("seasons").select("*").order("id", desc=True).execute()
        branches_r = await self._c.table("branches").select("*").order("sort").execute()
        return TaxonomySnapshot(
            categories=[CategoryRow(**_pick(r, CategoryRow)) for r in cats_r.data],
            subcategories=[SubcategoryRow(**_pick(r, SubcategoryRow)) for r in subs_r.data],
            clubs=[ClubRow(**_pick(r, ClubRow)) for r in clubs_r.data],
            brands=[BrandRow(**_pick(r, BrandRow)) for r in brands_r.data],
            seasons=[SeasonRow(**_pick(r, SeasonRow)) for r in seasons_r.data],
            branches=[BranchRow(**_pick(r, BranchRow)) for r in branches_r.data],
        )


def _pick(row: dict, cls: type) -> dict:
    fields = {f for f in cls.__dataclass_fields__}
    return {k: v for k, v in row.items() if k in fields}