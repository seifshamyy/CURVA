import json
from pathlib import Path
from curva_agent.schemas.curva import (
    CategoryListResponse,
    SeasonListResponse,
    BranchListResponse,
    ClubListResponse,
    BrandListResponse,
    ProductListResponse,
    ProductDetailResponse,
    OffersListResponse,
)

FIX = Path(__file__).parent.parent / "fixtures" / "curva"


def _load(name: str):
    return json.loads((FIX / name).read_text())


def test_categories_parses():
    r = CategoryListResponse.model_validate(_load("categories_ar.json"))
    assert r.status is True
    assert len(r.data) >= 5
    assert r.data[0].id > 0
    assert any(s.category_id == r.data[0].id for s in r.data[0].sub_category)


def test_seasons_parses():
    r = SeasonListResponse.model_validate(_load("seasons.json"))
    assert r.status is True
    assert any(s.name == "2026/27" for s in r.data)


def test_branches_parses():
    r = BranchListResponse.model_validate(_load("branches.json"))
    assert r.status is True
    assert r.data[0].phones


def test_clubs_parses():
    r = ClubListResponse.model_validate(_load("clubs.json"))
    assert r.status is True
    assert r.data.total >= 1
    assert any(c.id == 26 for c in r.data.data)


def test_brands_parses():
    r = BrandListResponse.model_validate(_load("brands.json"))
    assert r.status is True
    assert any(b.id == 8 for b in r.data.data)


def test_product_list_parses():
    r = ProductListResponse.model_validate(_load("products_zamalek.json"))
    assert r.status is True
    assert len(r.data.data) >= 1
    p = r.data.data[0]
    assert p.id > 0
    assert p.availability in ("available", "unavailable")
    assert p.image.startswith("https://")


def test_product_detail_parses_sizes_and_colors():
    r = ProductDetailResponse.model_validate(_load("product_10307.json"))
    p = r.data.product
    assert p.id == 10307
    assert p.club is not None and p.club.id == 26
    assert len(p.sizes) >= 1
    size = p.sizes[0]
    assert size.size.name
    assert len(size.colors) >= 1
    c = size.colors[0]
    assert c.barcode == f"{p.id}-{size.size.id}-{c.color_id}"
    assert int(c.quantity) >= 0


def test_offers_parses():
    r = OffersListResponse.model_validate(_load("offers_p1.json"))
    assert r.status is True
    assert r.data.data[0].offer_price is not None or r.data.data[0].offer_ratio is not None