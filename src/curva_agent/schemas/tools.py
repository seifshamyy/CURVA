"""Tool I/O schemas — shared between the orchestrator (LLM tool catalog),
the tools themselves, and the response contract.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- search_products ----------
class SearchProductsInput(_Base):
    category_id: int | None = Field(default=None, description="Filter by category (see taxonomy.categories)")
    subcategory_id: int | None = Field(default=None, description="Filter by subcategory")
    club_id: int | None = Field(default=None, description="Filter by club/nation (see taxonomy.clubs)")
    brand_id: int | None = Field(default=None, description="Filter by brand (see taxonomy.brands)")
    season_id: int | None = Field(default=None, description="Filter by season")
    search: str | None = Field(default=None, description="Free-text product name search (works AR or EN)")
    min_price: int | None = Field(default=None, ge=0)
    max_price: int | None = Field(default=None, ge=0)
    sort: Literal["id", "init_price", "views", "orders", "created_at"] | None = None
    limit: int = Field(default=30, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class ProductCardItem(_Base):
    id: int
    name: str
    init_price: int
    offer_price: int | None
    offer_ratio: str | None
    availability: str
    image: str
    url: str


class SearchProductsOutput(_Base):
    items: list[ProductCardItem]
    total: int
    page: int
    last_page: int


# ---------- get_product ----------
class GetProductInput(_Base):
    product_id: int = Field(..., ge=1)


class ColorOption(_Base):
    name: str
    hex: str | None
    quantity: int
    barcode: str
    image: str


class VariantBySize(_Base):
    size: str
    size_id: int
    price: int
    offer_price: int | None
    available: bool
    colors: list[ColorOption]


class GetProductOutput(_Base):
    id: int
    name: str
    init_price: int
    offer_price: int | None
    availability: str
    description_html: str
    url: str
    images: list[str]
    primary_image: str
    variants: list[VariantBySize]
    club: dict | None
    brand: dict | None
    season: str | None
    category: str | None
    subcategory: str | None


# ---------- get_offers ----------
class GetOffersInput(_Base):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=30, ge=1, le=100)


class GetOffersOutput(_Base):
    items: list[ProductCardItem]
    total: int
    page: int
    last_page: int


# ---------- list_branches ----------
class ListBranchesInput(_Base):
    pass


class BranchInfo(_Base):
    id: int
    name: str
    phones: list[str]


class ListBranchesOutput(_Base):
    branches: list[BranchInfo]


# ---------- product_synthesizer ----------
class ProductSynthesizerInput(_Base):
    product_ids: list[int] = Field(..., min_length=1, max_length=10)
    constraint: str | None = Field(default=None, description="User constraint to rank by (e.g. 'size M', 'under 400 EGP')")


class SynthesizedCandidate(_Base):
    id: int
    name: str
    price: int
    offer_price: int | None
    primary_image: str
    images: list[str]
    best_variants: list[VariantBySize]
    url: str
    rationale: str = Field(..., description="One-line 'why this matches' in the customer's locale")


class ProductSynthesizerOutput(_Base):
    candidates: list[SynthesizedCandidate]