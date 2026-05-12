"""Pydantic models matching the curvaegypt.com upstream API responses."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ---------- Categories ----------
class Subcategory(_Base):
    id: int
    name: str
    category_id: int


class Category(_Base):
    id: int
    name: str
    image: str | None = None
    sub_category: list[Subcategory] = Field(default_factory=list)


class CategoryListResponse(_Base):
    status: bool
    message: str | None = None
    data: list[Category]


# ---------- Seasons ----------
class Season(_Base):
    id: int
    name: str


class SeasonListResponse(_Base):
    status: bool
    message: str | None = None
    data: list[Season]


# ---------- Branches ----------
class Branch(_Base):
    id: int
    name: str
    phones: list[str] = Field(default_factory=list)
    phone: str | None = None
    sort: int | None = None


class BranchListResponse(_Base):
    status: bool
    message: str | None = None
    data: list[Branch]


# ---------- Pagination envelope ----------
class _PaginatedEnvelope(_Base):
    current_page: int
    last_page: int
    per_page: int
    total: int
    from_: int | None = Field(default=None, alias="from")
    to: int | None = None


# ---------- Clubs ----------
class ClubSummary(_Base):
    id: int
    name: str
    image: str | None = None
    orders: int = 0
    type: str | None = None
    supplier: str | None = None
    brand: dict[str, Any] | None = None


class ClubListPage(_PaginatedEnvelope):
    data: list[ClubSummary]


class ClubListResponse(_Base):
    status: bool
    message: str | None = None
    data: ClubListPage


# ---------- Brands ----------
class BrandSummary(_Base):
    id: int
    name: str
    image: str | None = None
    orders: int = 0


class BrandListPage(_PaginatedEnvelope):
    data: list[BrandSummary]


class BrandListResponse(_Base):
    status: bool
    message: str | None = None
    data: BrandListPage


# ---------- Products (list) ----------
class ProductSummary(_Base):
    id: int
    name: str
    init_price: int
    offer_ratio: str | None = None
    availability: str = "available"
    tags: str | None = None
    image: str
    offer_price: int | None = None
    in_wishlist: bool = False
    in_cart: bool = False


class ProductListPage(_PaginatedEnvelope):
    data: list[ProductSummary]


class ProductListResponse(_Base):
    status: bool
    message: str | None = None
    data: ProductListPage


# ---------- Offers ----------
class OffersListResponse(_Base):
    status: bool
    message: str | None = None
    data: ProductListPage


# ---------- Product detail ----------
class SizeRef(_Base):
    id: int
    name: str


class ColorRef(_Base):
    id: int
    name: str
    color: str | None = None


class ProductColorVariant(_Base):
    id: int
    barcode: str
    size_id: int
    color_id: int
    product_id: int
    product_size_id: int
    quantity: str | int
    image: str
    color: ColorRef


class ProductSize(_Base):
    id: int
    price: str
    sort: int | None = None
    size_id: int
    product_id: int
    final_price: int
    offer_price: int | None = None
    size: SizeRef
    colors: list[ProductColorVariant] = Field(default_factory=list)


class ProductImage(_Base):
    id: int
    image: str
    sort: int
    product_id: int


class ProductRef(_Base):
    id: int
    name: str
    supplier: str | None = None
    brand: dict[str, Any] | None = None


class ProductDetail(_Base):
    id: int
    name: str
    init_price: int
    offer_ratio: str | None = None
    offer_price: int | None = None
    brand_id: int | None = None
    club_id: int | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    season_id: int | None = None
    availability: str
    desc: str = ""
    views: int = 0
    season: Season | None = None
    brand: BrandSummary | None = None
    club: ProductRef | None = None
    category: dict[str, Any] | None = None
    subcategory: dict[str, Any] | None = None
    sizes: list[ProductSize] = Field(default_factory=list)
    images: list[ProductImage] = Field(default_factory=list)


class ProductDetailData(_Base):
    product: ProductDetail
    offers: list[ProductSummary] = Field(default_factory=list)


class ProductDetailResponse(_Base):
    status: bool
    message: str | None = None
    data: ProductDetailData