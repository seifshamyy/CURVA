"""Sync taxonomy from upstream Curva API into Supabase."""
from dataclasses import dataclass, field
from typing import Any
from curva_agent.curva_client.client import CurvaAPIError, CurvaClient
from curva_agent.observability.logging import get_logger
from curva_agent.supabase_client.taxonomy import (
    BranchRow,
    BrandRow,
    CategoryRow,
    ClubRow,
    SeasonRow,
    SubcategoryRow,
    TaxonomyRepository,
)

log = get_logger("sync.taxonomy")


@dataclass
class SyncResult:
    ok: bool
    counts: dict[str, int] = field(default_factory=dict)
    error: str | None = None


async def sync_taxonomy(*, curva: CurvaClient, repo: TaxonomyRepository) -> SyncResult:
    counts: dict[str, int] = {}
    errors: list[str] = []

    try:
        cats_ar = await curva.get_categories(locale="ar")
        cats_en = await curva.get_categories(locale="en")
        en_by_id = {c.id: c.name for c in cats_en.data}
        en_sub_by_id = {s.id: s.name for c in cats_en.data for s in c.sub_category}

        cat_rows = [
            CategoryRow(id=c.id, name_ar=c.name, name_en=en_by_id.get(c.id, c.name), image=c.image)
            for c in cats_ar.data
        ]
        sub_rows = [
            SubcategoryRow(
                id=s.id, category_id=s.category_id, name_ar=s.name, name_en=en_sub_by_id.get(s.id, s.name)
            )
            for c in cats_ar.data
            for s in c.sub_category
        ]
        await repo.upsert_categories(cat_rows)
        await repo.upsert_subcategories(sub_rows)
        counts["categories"] = len(cat_rows)
        counts["subcategories"] = len(sub_rows)
    except CurvaAPIError as e:
        errors.append(f"categories: {e}")
        log.error("sync_categories_failed", error=str(e))

    try:
        clubs_ar = await curva.get_clubs(limit=200, page=1, locale="ar")
        clubs_en = await curva.get_clubs(limit=200, page=1, locale="en")
        en_by_id = {c.id: c.name for c in clubs_en.data.data}
        club_rows = [
            ClubRow(
                id=c.id,
                name_ar=c.name,
                name_en=en_by_id.get(c.id),
                type=c.type,
                supplier=c.supplier,
                image=c.image,
                orders_count=c.orders,
            )
            for c in clubs_ar.data.data
        ]
        await repo.upsert_clubs(club_rows)
        counts["clubs"] = len(club_rows)
    except CurvaAPIError as e:
        errors.append(f"clubs: {e}")
        log.error("sync_clubs_failed", error=str(e))

    try:
        brands_ar = await curva.get_brands(limit=200, page=1, locale="ar")
        brands_en = await curva.get_brands(limit=200, page=1, locale="en")
        en_by_id = {b.id: b.name for b in brands_en.data.data}
        brand_rows = [
            BrandRow(
                id=b.id,
                name_ar=b.name,
                name_en=en_by_id.get(b.id),
                image=b.image,
                orders_count=b.orders,
            )
            for b in brands_ar.data.data
        ]
        await repo.upsert_brands(brand_rows)
        counts["brands"] = len(brand_rows)
    except CurvaAPIError as e:
        errors.append(f"brands: {e}")
        log.error("sync_brands_failed", error=str(e))

    try:
        seasons = await curva.get_seasons()
        season_rows = [SeasonRow(id=s.id, name=s.name) for s in seasons.data]
        await repo.upsert_seasons(season_rows)
        counts["seasons"] = len(season_rows)
    except CurvaAPIError as e:
        errors.append(f"seasons: {e}")
        log.error("sync_seasons_failed", error=str(e))

    try:
        branches = await curva.get_branches()
        branch_rows = [
            BranchRow(id=b.id, name=b.name, phones=b.phones, sort=b.sort) for b in branches.data
        ]
        await repo.upsert_branches(branch_rows)
        counts["branches"] = len(branch_rows)
    except CurvaAPIError as e:
        errors.append(f"branches: {e}")
        log.error("sync_branches_failed", error=str(e))

    return SyncResult(ok=not errors, counts=counts, error="; ".join(errors) if errors else None)


async def record_sync_run(supabase: Any, started_at: str, result: SyncResult) -> None:
    await supabase.table("taxonomy_sync_runs").insert(
        {
            "started_at": started_at,
            "finished_at": "now()",
            "ok": result.ok,
            "delta_summary": result.counts,
            "error": result.error,
        }
    ).execute()