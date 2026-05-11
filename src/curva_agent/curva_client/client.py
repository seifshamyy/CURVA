"""Async HTTP client for the curvaegypt.com upstream API."""
from collections.abc import Callable
from typing import Any
import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from curva_agent.observability.logging import get_logger
from curva_agent.schemas.curva import (
    BranchListResponse,
    BrandListResponse,
    CategoryListResponse,
    ClubListResponse,
    OffersListResponse,
    ProductDetailResponse,
    ProductListResponse,
    SeasonListResponse,
)

log = get_logger("curva_client")


class CurvaAPIError(Exception):
    """Upstream Curva API returned an error."""


class CurvaRateLimited(CurvaAPIError):
    """Upstream returned 429 / rate limit indicator."""


class CurvaClient:
    """Async client for the public curvaegypt.com endpoints."""

    def __init__(
        self,
        base_url: str,
        *,
        user_agent: str = "CurvaCSAgent/1.0",
        rate_limit_warn_at: int = 20,
        on_rate_limit_low: Callable[[int], None] | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._warn_at = rate_limit_warn_at
        self._on_low = on_rate_limit_low
        self._client = httpx.AsyncClient(
            base_url=self._base,
            timeout=timeout,
            http2=True,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )

    async def __aenter__(self) -> "CurvaClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._client.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        locale: str = "ar",
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Accept-Language": locale}
        if json is not None:
            headers["Content-Type"] = "application/json"

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(2),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
            retry=retry_if_exception_type((httpx.TransportError, CurvaAPIError)),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.request(
                    method, path, headers=headers, json=json, params=params
                )
                self._inspect_rate_limit(resp)
                if resp.status_code == 429:
                    raise CurvaRateLimited(f"429 on {path}")
                if 500 <= resp.status_code < 600:
                    raise CurvaAPIError(f"{resp.status_code} on {path}")
                resp.raise_for_status()
                return resp.json()
        raise CurvaAPIError(f"request failed: {method} {path}")

    def _inspect_rate_limit(self, resp: httpx.Response) -> None:
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining is None:
            return
        try:
            n = int(remaining)
        except ValueError:
            return
        if n <= self._warn_at:
            log.warning("curva_rate_limit_low", remaining=n)
            if self._on_low is not None:
                self._on_low(n)

    async def get_categories(self, *, locale: str = "ar") -> CategoryListResponse:
        return CategoryListResponse.model_validate(await self._request("GET", "/categories", locale=locale))

    async def get_seasons(self, *, locale: str = "ar") -> SeasonListResponse:
        return SeasonListResponse.model_validate(await self._request("GET", "/seasons", locale=locale))

    async def get_branches(self, *, locale: str = "ar") -> BranchListResponse:
        return BranchListResponse.model_validate(await self._request("GET", "/branches", locale=locale))

    async def get_clubs(self, *, limit: int = 200, page: int = 1, locale: str = "ar") -> ClubListResponse:
        return ClubListResponse.model_validate(
            await self._request("POST", "/clubs", locale=locale, json={"limit": limit, "page": page})
        )

    async def get_brands(self, *, limit: int = 200, page: int = 1, locale: str = "ar") -> BrandListResponse:
        return BrandListResponse.model_validate(
            await self._request("POST", "/brands", locale=locale, json={"limit": limit, "page": page})
        )

    async def search_products(self, filters: dict[str, Any], *, locale: str = "ar") -> ProductListResponse:
        return ProductListResponse.model_validate(
            await self._request("POST", "/products", locale=locale, json=filters)
        )

    async def get_product(self, product_id: int, *, locale: str = "ar") -> ProductDetailResponse:
        return ProductDetailResponse.model_validate(
            await self._request("GET", f"/product/{product_id}", locale=locale)
        )

    async def get_offers(self, *, page: int = 1, limit: int = 30, locale: str = "ar") -> OffersListResponse:
        return OffersListResponse.model_validate(
            await self._request("GET", "/offers", locale=locale, params={"page": page, "limit": limit})
        )