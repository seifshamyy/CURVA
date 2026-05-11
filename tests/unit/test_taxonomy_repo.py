from typing import Any
import pytest
from curva_agent.supabase_client.taxonomy import (
    TaxonomyRepository,
    CategoryRow,
    SubcategoryRow,
    ClubRow,
    BrandRow,
    SeasonRow,
    BranchRow,
    TaxonomySnapshot,
)


class StubTable:
    def __init__(self, store: dict, table_name: str):
        self.store = store
        self.name = table_name
        self._select_filter: tuple | None = None

    def upsert(self, rows: list[dict], on_conflict: str = "id"):
        for row in rows:
            self.store.setdefault(self.name, {})[row["id"]] = row
        return self

    def select(self, _cols: str = "*"):
        return self

    def order(self, *_args, **_kwargs):
        return self

    async def execute(self):
        return type("R", (), {"data": list(self.store.get(self.name, {}).values())})()


class StubSupabase:
    def __init__(self):
        self.store: dict[str, dict[int, dict[str, Any]]] = {}

    def table(self, name: str) -> StubTable:
        return StubTable(self.store, name)


@pytest.mark.asyncio
async def test_upsert_and_load_full_snapshot():
    stub = StubSupabase()
    repo = TaxonomyRepository(stub)

    await repo.upsert_categories([CategoryRow(id=1, name_ar="ملابس", name_en="Wear", image=None)])
    await repo.upsert_subcategories([SubcategoryRow(id=3, category_id=1, name_ar="قمصان", name_en="Jerseys")])
    await repo.upsert_clubs([ClubRow(id=26, name_ar="الزمالك", name_en="Zamalek", type="club", supplier="", image=None, orders_count=2274)])
    await repo.upsert_brands([BrandRow(id=8, name_ar="نايكي", name_en="Nike", image=None, orders_count=6446)])
    await repo.upsert_seasons([SeasonRow(id=40, name="2026/27")])
    await repo.upsert_branches([BranchRow(id=3, name="مدينة نصر", phones=["01097613728"], sort=1)])

    snap = await repo.load_snapshot()
    assert isinstance(snap, TaxonomySnapshot)
    assert snap.categories[0].name_en == "Wear"
    assert snap.subcategories[0].category_id == 1
    assert snap.clubs[0].id == 26
    assert snap.brands[0].name_en == "Nike"
    assert snap.seasons[0].name == "2026/27"
    assert snap.branches[0].phones == ["01097613728"]


@pytest.mark.asyncio
async def test_snapshot_to_llm_json_is_compact():
    stub = StubSupabase()
    repo = TaxonomyRepository(stub)
    await repo.upsert_categories([CategoryRow(id=1, name_ar="ملابس", name_en="Wear", image=None)])
    await repo.upsert_clubs([ClubRow(id=26, name_ar="الزمالك", name_en="Zamalek", type="club", supplier="", image=None, orders_count=0)])

    snap = await repo.load_snapshot()
    j = snap.to_llm_json()
    assert "categories" in j and "clubs" in j
    assert j["clubs"][0] == {"id": 26, "name_ar": "الزمالك", "name_en": "Zamalek", "type": "club"}
    assert "image" not in j["clubs"][0]