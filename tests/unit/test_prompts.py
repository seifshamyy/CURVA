from curva_agent.llm.prompts import build_system_blocks, build_user_context_block
from curva_agent.supabase_client.taxonomy import (
    BranchRow,
    BrandRow,
    CategoryRow,
    ClubRow,
    SeasonRow,
    SubcategoryRow,
    TaxonomySnapshot,
)


def _sample_snapshot() -> TaxonomySnapshot:
    return TaxonomySnapshot(
        categories=[CategoryRow(id=1, name_ar="ملابس", name_en="Wear", image=None)],
        subcategories=[SubcategoryRow(id=3, category_id=1, name_ar="قمصان", name_en="Jerseys")],
        clubs=[ClubRow(id=26, name_ar="الزمالك", name_en="Zamalek", type="club", supplier=None, image=None, orders_count=0)],
        brands=[BrandRow(id=8, name_ar="نايكي", name_en="Nike", image=None, orders_count=0)],
        seasons=[SeasonRow(id=40, name="2026/27")],
        branches=[BranchRow(id=3, name="مدينة نصر", phones=["01097613728"], sort=1)],
    )


def test_system_blocks_have_two_blocks_stable_prefix_cached():
    blocks = build_system_blocks(snapshot=_sample_snapshot(), locale="ar")
    assert len(blocks) == 2
    assert blocks[0]["type"] == "text"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "Curva" in blocks[0]["text"]
    assert "Zamalek" in blocks[0]["text"]
    assert '"id": 26' in blocks[0]["text"]
    assert "cache_control" not in blocks[1]
    assert "Arabic" in blocks[1]["text"] or "ar" in blocks[1]["text"]


def test_system_blocks_locale_switches_dynamic_block():
    ar = build_system_blocks(snapshot=_sample_snapshot(), locale="ar")
    en = build_system_blocks(snapshot=_sample_snapshot(), locale="en")
    assert ar[0]["text"] == en[0]["text"]
    assert ar[1]["text"] != en[1]["text"]


def test_user_context_block_includes_session_summary():
    block = build_user_context_block(
        session_summary="Customer asked about Real Madrid jerseys size M.",
        focus_product_ids=[10307, 10306],
        conversation_history=[{"role": "user", "content": "I want the red one"}],
    )
    assert "Real Madrid" in block
    assert "10307" in block
    assert "I want the red one" in block