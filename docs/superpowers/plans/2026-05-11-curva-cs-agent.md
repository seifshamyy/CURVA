# Curva CS Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a WhatsApp-facing customer service agent for curvaegypt.com — a single FastAPI endpoint backed by Claude Sonnet 4.6 (via OpenRouter) that searches the catalog, answers questions, sends product photos, and signals order intent.

**Architecture:** Python/FastAPI service deployed as a long-lived container. A master LLM orchestrator runs an agent loop over 4 deterministic tools (catalog search, product detail, offers, branches) plus 1 specialist sub-agent (Product Synthesizer). Supabase holds the reference taxonomy (synced weekly via Edge Function), session memory keyed by WhatsApp phone, and operational logs. Live upstream Curva API is the source of truth for products.

**Tech Stack:** Python 3.12, FastAPI, `httpx` (async), Pydantic v2, `openai` SDK pointed at OpenRouter, Supabase (Postgres + Edge Functions), `cachetools`, `tenacity`, `structlog`, `pytest` + `respx`.

**Spec:** [docs/superpowers/specs/2026-05-11-curva-cs-agent-design.md](../specs/2026-05-11-curva-cs-agent-design.md)

---

## Phase 0 — Bootstrap

### Task 1: Initialize repo and Python project

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/curva_agent/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize git repo**

Run:
```bash
cd /Users/seifelshamy/Downloads/0
git init
git config user.name "Seif Elshamy"
git config user.email "seize.shikabala@gmail.com"
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.env
.env.local
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/
dist/
build/
*.log
.DS_Store
.vscode/
.idea/
supabase/.branches
supabase/.temp
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[project]
name = "curva-cs-agent"
version = "0.1.0"
description = "WhatsApp customer service agent for curvaegypt.com"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "httpx[http2]>=0.27",
  "pydantic>=2.9",
  "pydantic-settings>=2.6",
  "openai>=1.55",
  "supabase>=2.10",
  "cachetools>=5.5",
  "tenacity>=9.0",
  "structlog>=24.4",
  "python-dotenv>=1.0",
  "orjson>=3.10",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "respx>=0.21",
  "ruff>=0.7",
  "mypy>=1.13",
  "freezegun>=1.5",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/curva_agent"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "ASYNC"]

[tool.mypy]
python_version = "3.12"
strict = true
mypy_path = "src"
```

- [ ] **Step 4: Create `.env.example`**

```env
# OpenRouter (LLM provider)
OPENROUTER_API_KEY=
LLM_MODEL=anthropic/claude-sonnet-4.6
LLM_MAX_TOOL_ITERATIONS=12

# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=

# Curva upstream API
CURVA_API_BASE=https://octane.curvaegypt.com/api
CURVA_RATE_LIMIT_WARN_AT=20
CURVA_USER_AGENT=CurvaCSAgent/1.0

# Agent service auth (n8n -> service)
AGENT_API_KEY=

# Cache TTLs (seconds)
CACHE_PRODUCTS_TTL_SEC=600
CACHE_PRODUCT_TTL_SEC=900
CACHE_OFFERS_TTL_SEC=600
CACHE_BRANCHES_TTL_SEC=86400

# Session
SESSION_TTL_DAYS=30
SESSION_RATE_LIMIT_PER_MIN=30

# Logging
LOG_LEVEL=INFO
```

- [ ] **Step 5: Create empty `__init__.py` files and conftest**

`src/curva_agent/__init__.py`:
```python
"""Curva CS Agent — WhatsApp customer service agent."""
__version__ = "0.1.0"
```

`tests/__init__.py`: (empty)

`tests/conftest.py`:
```python
"""Shared pytest fixtures."""
import asyncio
import os
import pytest

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("AGENT_API_KEY", "test-agent-key")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

- [ ] **Step 6: Install dependencies and verify**

Run:
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest --collect-only
```

Expected: `pytest --collect-only` exits cleanly with "no tests ran" (no tests yet).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore .env.example src/ tests/
git commit -m "chore: initialize Python project with FastAPI dependencies"
```

---

### Task 2: Config loader with Pydantic Settings

**Files:**
- Create: `src/curva_agent/config.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_config.py`:
```python
import os
import pytest
from curva_agent.config import Settings, get_settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "key-123")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc-key")
    monkeypatch.setenv("AGENT_API_KEY", "agent-key")
    get_settings.cache_clear()

    s = get_settings()
    assert s.openrouter_api_key == "key-123"
    assert s.supabase_url == "https://example.supabase.co"
    assert s.llm_model == "anthropic/claude-sonnet-4.6"  # default
    assert s.llm_max_tool_iterations == 12  # default
    assert s.curva_api_base == "https://octane.curvaegypt.com/api"


def test_settings_is_cached():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_settings_missing_required_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(Exception):
        Settings(_env_file=None)
```

- [ ] **Step 2: Run test to confirm failure**

Run: `pytest tests/unit/test_config.py -v`
Expected: ImportError on `curva_agent.config`.

- [ ] **Step 3: Implement `config.py`**

`src/curva_agent/config.py`:
```python
"""Application configuration loaded from environment variables."""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    openrouter_api_key: str = Field(...)
    llm_model: str = "anthropic/claude-sonnet-4.6"
    llm_max_tool_iterations: int = 12

    # Supabase
    supabase_url: str = Field(...)
    supabase_service_role_key: str = Field(...)

    # Curva upstream
    curva_api_base: str = "https://octane.curvaegypt.com/api"
    curva_rate_limit_warn_at: int = 20
    curva_user_agent: str = "CurvaCSAgent/1.0"

    # Service auth
    agent_api_key: str = Field(...)

    # Cache TTLs
    cache_products_ttl_sec: int = 600
    cache_product_ttl_sec: int = 900
    cache_offers_ttl_sec: int = 600
    cache_branches_ttl_sec: int = 86400

    # Session
    session_ttl_days: int = 30
    session_rate_limit_per_min: int = 30

    # Logging
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run test to confirm pass**

Run: `pytest tests/unit/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/curva_agent/config.py tests/unit/
git commit -m "feat(config): add Settings loader with env-driven configuration"
```

---

### Task 3: FastAPI skeleton with /healthz

**Files:**
- Create: `src/curva_agent/main.py`
- Create: `tests/unit/test_main.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_main.py`:
```python
from fastapi.testclient import TestClient
from curva_agent.main import app


def test_healthz_returns_200():
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_root_returns_service_metadata():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "curva-cs-agent"
    assert "version" in data
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/unit/test_main.py -v`
Expected: ImportError on `curva_agent.main`.

- [ ] **Step 3: Implement `main.py`**

`src/curva_agent/main.py`:
```python
"""FastAPI application entry point."""
from fastapi import FastAPI
from curva_agent import __version__

app = FastAPI(title="Curva CS Agent", version=__version__)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "curva-cs-agent", "version": __version__}
```

- [ ] **Step 4: Run to confirm pass**

Run: `pytest tests/unit/test_main.py -v`
Expected: 2 passed.

- [ ] **Step 5: Smoke test the server**

Run:
```bash
uvicorn curva_agent.main:app --port 8000 &
sleep 1
curl -s http://localhost:8000/healthz
kill %1
```
Expected output: `{"status":"ok"}`

- [ ] **Step 6: Commit**

```bash
git add src/curva_agent/main.py tests/unit/test_main.py
git commit -m "feat(api): add FastAPI app with /healthz endpoint"
```

---

### Task 4: Dockerfile + structured logging setup

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `src/curva_agent/observability/__init__.py`
- Create: `src/curva_agent/observability/logging.py`
- Create: `tests/unit/test_logging.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_logging.py`:
```python
import json
import logging
import structlog
from curva_agent.observability.logging import configure_logging, get_logger


def test_configure_logging_sets_json_renderer(capsys):
    configure_logging("INFO")
    log = get_logger("test")
    log.info("hello", session_id="20100", tool="search_products")
    captured = capsys.readouterr()
    line = captured.out.strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["event"] == "hello"
    assert parsed["session_id"] == "20100"
    assert parsed["tool"] == "search_products"
    assert parsed["level"] == "info"


def test_get_logger_returns_bound_logger():
    log = get_logger("test").bind(session_id="abc")
    assert hasattr(log, "info")
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/unit/test_logging.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `logging.py`**

`src/curva_agent/observability/__init__.py`: (empty)

`src/curva_agent/observability/logging.py`:
```python
"""Structured JSON logging configuration."""
import logging
import sys
import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog with JSON output to stdout."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
```

- [ ] **Step 4: Wire logging into FastAPI startup**

Modify `src/curva_agent/main.py`:
```python
"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from curva_agent import __version__
from curva_agent.config import get_settings
from curva_agent.observability.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("startup")
    log.info("service_starting", version=__version__, model=settings.llm_model)
    yield
    log.info("service_stopping")


app = FastAPI(title="Curva CS Agent", version=__version__, lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "curva-cs-agent", "version": __version__}
```

- [ ] **Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: all green (5 passed).

- [ ] **Step 6: Create Dockerfile**

`Dockerfile`:
```dockerfile
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

FROM base AS builder
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --upgrade pip && pip install --prefix=/install -e .

FROM base AS runtime
COPY --from=builder /install /usr/local
COPY --from=builder /app/src /app/src
ENV PYTHONPATH=/app/src
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)"
CMD ["uvicorn", "curva_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`.dockerignore`:
```
.venv/
__pycache__/
*.pyc
.git/
tests/
docs/
.env
.env.local
```

- [ ] **Step 7: Build and verify**

Run:
```bash
docker build -t curva-cs-agent:dev .
docker run --rm -d -p 8001:8000 --name curva-test \
  -e OPENROUTER_API_KEY=x -e SUPABASE_URL=x -e SUPABASE_SERVICE_ROLE_KEY=x -e AGENT_API_KEY=x \
  curva-cs-agent:dev
sleep 2
curl -s http://localhost:8001/healthz
docker stop curva-test
```
Expected: `{"status":"ok"}`

- [ ] **Step 8: Commit**

```bash
git add Dockerfile .dockerignore src/curva_agent/observability/ src/curva_agent/main.py tests/unit/test_logging.py
git commit -m "feat(observability): structured logging + Docker image"
```

---

## Phase 1 — Curva HTTP Client

### Task 5: Pydantic models for Curva API responses + recorded fixtures

**Files:**
- Create: `src/curva_agent/schemas/__init__.py`
- Create: `src/curva_agent/schemas/curva.py`
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/curva/` (directory of recorded JSON)
- Create: `tests/unit/test_curva_schemas.py`

- [ ] **Step 1: Record live fixtures from upstream**

Run:
```bash
mkdir -p tests/fixtures/curva
curl -s 'https://octane.curvaegypt.com/api/categories' -H 'accept-language: ar' > tests/fixtures/curva/categories_ar.json
curl -s 'https://octane.curvaegypt.com/api/seasons' > tests/fixtures/curva/seasons.json
curl -s 'https://octane.curvaegypt.com/api/branches' > tests/fixtures/curva/branches.json
curl -s -X POST -H 'content-type: application/json' --data '{"limit":200,"page":1}' 'https://octane.curvaegypt.com/api/clubs' > tests/fixtures/curva/clubs.json
curl -s -X POST -H 'content-type: application/json' --data '{"limit":200,"page":1}' 'https://octane.curvaegypt.com/api/brands' > tests/fixtures/curva/brands.json
curl -s -X POST -H 'content-type: application/json' --data '{"limit":5,"page":1,"club_id":26}' 'https://octane.curvaegypt.com/api/products' > tests/fixtures/curva/products_zamalek.json
curl -s 'https://octane.curvaegypt.com/api/product/10307' > tests/fixtures/curva/product_10307.json
curl -s 'https://octane.curvaegypt.com/api/offers?limit=5&page=1' > tests/fixtures/curva/offers_p1.json
ls -la tests/fixtures/curva/
```

Expected: 8 JSON files, each non-empty.

- [ ] **Step 2: Write the failing test**

`tests/unit/test_curva_schemas.py`:
```python
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
    assert r.data.total >= 100
    assert any(c.id == 26 for c in r.data.data)  # Zamalek


def test_brands_parses():
    r = BrandListResponse.model_validate(_load("brands.json"))
    assert r.status is True
    assert any(b.id == 8 for b in r.data.data)  # Nike


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
```

- [ ] **Step 3: Implement `curva.py` schemas**

`src/curva_agent/schemas/__init__.py`: (empty)

`src/curva_agent/schemas/curva.py`:
```python
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
    availability: str
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
    color: str | None = None  # hex


class ProductColorVariant(_Base):
    id: int
    barcode: str
    size_id: int
    color_id: int
    product_id: int
    product_size_id: int
    quantity: str
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
    brand_id: int
    club_id: int
    category_id: int
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
```

- [ ] **Step 4: Run schema tests**

Run: `pytest tests/unit/test_curva_schemas.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/curva_agent/schemas/ tests/fixtures/ tests/unit/test_curva_schemas.py
git commit -m "feat(schemas): Pydantic models for Curva API responses + recorded fixtures"
```

---

### Task 6: Async Curva HTTP client

**Files:**
- Create: `src/curva_agent/curva_client/__init__.py`
- Create: `src/curva_agent/curva_client/client.py`
- Create: `tests/unit/test_curva_client.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_curva_client.py`:
```python
import json
from pathlib import Path
import httpx
import pytest
import respx
from curva_agent.curva_client.client import CurvaClient

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_get_categories():
    respx.get(f"{BASE}/categories").mock(return_value=httpx.Response(200, json=_read("categories_ar.json")))
    async with CurvaClient(base_url=BASE) as c:
        cats = await c.get_categories(locale="ar")
    assert len(cats.data) >= 5


@pytest.mark.asyncio
@respx.mock
async def test_search_products_posts_with_body():
    route = respx.post(f"{BASE}/products").mock(
        return_value=httpx.Response(200, json=_read("products_zamalek.json"))
    )
    async with CurvaClient(base_url=BASE) as c:
        r = await c.search_products({"club_id": 26, "limit": 5, "page": 1})
    assert route.called
    sent_body = json.loads(route.calls[0].request.content)
    assert sent_body == {"club_id": 26, "limit": 5, "page": 1}
    assert r.data.total >= 1


@pytest.mark.asyncio
@respx.mock
async def test_get_product():
    respx.get(f"{BASE}/product/10307").mock(return_value=httpx.Response(200, json=_read("product_10307.json")))
    async with CurvaClient(base_url=BASE) as c:
        r = await c.get_product(10307)
    assert r.data.product.id == 10307


@pytest.mark.asyncio
@respx.mock
async def test_get_offers_uses_query_params():
    route = respx.get(f"{BASE}/offers").mock(
        return_value=httpx.Response(200, json=_read("offers_p1.json"))
    )
    async with CurvaClient(base_url=BASE) as c:
        await c.get_offers(page=1, limit=5)
    assert dict(route.calls[0].request.url.params) == {"page": "1", "limit": "5"}


@pytest.mark.asyncio
@respx.mock
async def test_retry_on_5xx(caplog):
    route = respx.get(f"{BASE}/categories").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=_read("categories_ar.json"))]
    )
    async with CurvaClient(base_url=BASE) as c:
        r = await c.get_categories()
    assert route.call_count == 2
    assert r.status is True


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_warning_threshold(caplog):
    respx.get(f"{BASE}/categories").mock(
        return_value=httpx.Response(
            200,
            json=_read("categories_ar.json"),
            headers={"X-RateLimit-Limit": "100", "X-RateLimit-Remaining": "10"},
        )
    )
    warnings: list = []
    async with CurvaClient(base_url=BASE, rate_limit_warn_at=20, on_rate_limit_low=warnings.append) as c:
        await c.get_categories()
    assert warnings == [10]


@pytest.mark.asyncio
@respx.mock
async def test_sends_user_agent_and_accept_language():
    route = respx.get(f"{BASE}/categories").mock(return_value=httpx.Response(200, json=_read("categories_ar.json")))
    async with CurvaClient(base_url=BASE, user_agent="CurvaCSAgent/1.0") as c:
        await c.get_categories(locale="ar")
    req = route.calls[0].request
    assert req.headers["user-agent"] == "CurvaCSAgent/1.0"
    assert req.headers["accept-language"] == "ar"
```

- [ ] **Step 2: Run to confirm failure**

Run: `pytest tests/unit/test_curva_client.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `client.py`**

`src/curva_agent/curva_client/__init__.py`:
```python
from curva_agent.curva_client.client import CurvaClient

__all__ = ["CurvaClient"]
```

`src/curva_agent/curva_client/client.py`:
```python
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
    """Async client for the public curvaegypt.com endpoints.

    Public API — see docs/curva-api-docs.md for full schema.
    """

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

    # ----- low-level request with retries -----
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
        raise CurvaAPIError(f"request failed: {method} {path}")  # unreachable

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

    # ----- typed endpoint methods -----
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_curva_client.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/curva_agent/curva_client/ tests/unit/test_curva_client.py
git commit -m "feat(curva): async HTTP client with retries and rate-limit awareness"
```

---

## Phase 2 — Supabase Schema and Taxonomy Sync

### Task 7: Supabase reference table migrations

**Files:**
- Create: `supabase/config.toml`
- Create: `supabase/migrations/20260511000001_reference_tables.sql`
- Create: `supabase/migrations/20260511000002_taxonomy_sync_runs.sql`

- [ ] **Step 1: Initialize Supabase project**

Run:
```bash
npx supabase init --workdir /Users/seifelshamy/Downloads/0
```

Expected: creates `supabase/config.toml`.

- [ ] **Step 2: Create reference tables migration**

`supabase/migrations/20260511000001_reference_tables.sql`:
```sql
-- Reference data mirrored from curvaegypt.com weekly via Edge Function.

create table if not exists categories (
  id          int primary key,
  name_ar     text not null,
  name_en     text not null,
  image       text,
  updated_at  timestamptz not null default now()
);

create table if not exists subcategories (
  id          int primary key,
  category_id int not null references categories(id) on delete cascade,
  name_ar     text not null,
  name_en     text not null,
  updated_at  timestamptz not null default now()
);
create index if not exists subcategories_category_id_idx on subcategories(category_id);

create table if not exists clubs (
  id            int primary key,
  name_ar       text not null,
  name_en       text,
  type          text,
  supplier      text,
  image         text,
  orders_count  int not null default 0,
  updated_at    timestamptz not null default now()
);

create table if not exists brands (
  id            int primary key,
  name_ar       text not null,
  name_en       text,
  image         text,
  orders_count  int not null default 0,
  updated_at    timestamptz not null default now()
);

create table if not exists seasons (
  id          int primary key,
  name        text not null,
  updated_at  timestamptz not null default now()
);

create table if not exists branches (
  id          int primary key,
  name        text not null,
  phones      text[] not null default '{}',
  sort        int,
  updated_at  timestamptz not null default now()
);
```

- [ ] **Step 3: Create taxonomy_sync_runs migration**

`supabase/migrations/20260511000002_taxonomy_sync_runs.sql`:
```sql
create table if not exists taxonomy_sync_runs (
  id             bigserial primary key,
  started_at     timestamptz not null,
  finished_at    timestamptz,
  ok             boolean,
  delta_summary  jsonb,
  error          text
);
create index if not exists taxonomy_sync_runs_started_at_idx
  on taxonomy_sync_runs(started_at desc);
```

- [ ] **Step 4: Apply migrations locally**

Run:
```bash
npx supabase start
npx supabase db reset
```

Expected: tables created, no errors. Verify with:
```bash
npx supabase db diff
```

- [ ] **Step 5: Commit**

```bash
git add supabase/config.toml supabase/migrations/
git commit -m "feat(db): reference tables + taxonomy_sync_runs migrations"
```

---

### Task 8: Supabase client wrapper + taxonomy repository

**Files:**
- Create: `src/curva_agent/supabase_client/__init__.py`
- Create: `src/curva_agent/supabase_client/client.py`
- Create: `src/curva_agent/supabase_client/taxonomy.py`
- Create: `tests/unit/test_taxonomy_repo.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_taxonomy_repo.py`:
```python
"""Unit tests for the taxonomy repository.

These use a stub SupabaseClient — integration against a real Supabase project
runs separately in Task 9's manual smoke test.
"""
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
    assert "image" not in j["clubs"][0]  # stripped for compactness
```

- [ ] **Step 2: Implement Supabase client wrapper**

`src/curva_agent/supabase_client/__init__.py`:
```python
from curva_agent.supabase_client.client import get_supabase_client

__all__ = ["get_supabase_client"]
```

`src/curva_agent/supabase_client/client.py`:
```python
"""Async Supabase client factory."""
from functools import lru_cache
from supabase import acreate_client, AsyncClient
from curva_agent.config import get_settings


_client: AsyncClient | None = None


async def get_supabase_client() -> AsyncClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = await acreate_client(s.supabase_url, s.supabase_service_role_key)
    return _client


def reset_supabase_client_for_tests() -> None:
    global _client
    _client = None
```

- [ ] **Step 3: Implement taxonomy repository**

`src/curva_agent/supabase_client/taxonomy.py`:
```python
"""Taxonomy repository — reads and writes reference tables in Supabase.

Accepts any Supabase-like client with a `table(name).upsert(...).execute()` /
`select(...).execute()` interface so we can unit-test against a stub.
"""
from dataclasses import asdict, dataclass
from typing import Any, Protocol


# ---- Row types -----------------------------------------------------
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
        """Compact JSON for inclusion in the orchestrator system prompt.

        Strips images and noisy fields. Keeps everything the LLM needs to
        resolve customer references (names + IDs + category/club type).
        """
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


# ---- Repository ----------------------------------------------------
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_taxonomy_repo.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/curva_agent/supabase_client/ tests/unit/test_taxonomy_repo.py
git commit -m "feat(db): Supabase client + taxonomy repository with snapshot loader"
```

---

### Task 9: Taxonomy sync service

**Files:**
- Create: `src/curva_agent/sync/__init__.py`
- Create: `src/curva_agent/sync/taxonomy.py`
- Create: `tests/unit/test_taxonomy_sync.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_taxonomy_sync.py`:
```python
import json
from pathlib import Path
import httpx
import pytest
import respx
from curva_agent.curva_client.client import CurvaClient
from curva_agent.sync.taxonomy import sync_taxonomy, SyncResult
from tests.unit.test_taxonomy_repo import StubSupabase
from curva_agent.supabase_client.taxonomy import TaxonomyRepository

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_sync_taxonomy_full_run_populates_snapshot():
    respx.get(f"{BASE}/categories").mock(return_value=httpx.Response(200, json=_read("categories_ar.json")))
    respx.get(f"{BASE}/seasons").mock(return_value=httpx.Response(200, json=_read("seasons.json")))
    respx.get(f"{BASE}/branches").mock(return_value=httpx.Response(200, json=_read("branches.json")))
    respx.post(f"{BASE}/clubs").mock(return_value=httpx.Response(200, json=_read("clubs.json")))
    respx.post(f"{BASE}/brands").mock(return_value=httpx.Response(200, json=_read("brands.json")))
    # English passes for name_en
    respx.get(f"{BASE}/categories").mock(return_value=httpx.Response(200, json=_read("categories_ar.json")))

    sup = StubSupabase()
    repo = TaxonomyRepository(sup)

    async with CurvaClient(base_url=BASE) as c:
        result: SyncResult = await sync_taxonomy(curva=c, repo=repo)

    snap = await repo.load_snapshot()
    assert len(snap.categories) >= 5
    assert len(snap.clubs) >= 100
    assert len(snap.brands) >= 50
    assert any(s.name == "2026/27" for s in snap.seasons)
    assert result.ok is True
    assert result.counts["clubs"] == len(snap.clubs)


@pytest.mark.asyncio
@respx.mock
async def test_sync_taxonomy_reports_partial_failure():
    respx.get(f"{BASE}/categories").mock(return_value=httpx.Response(503))
    respx.get(f"{BASE}/seasons").mock(return_value=httpx.Response(200, json=_read("seasons.json")))
    respx.get(f"{BASE}/branches").mock(return_value=httpx.Response(200, json=_read("branches.json")))
    respx.post(f"{BASE}/clubs").mock(return_value=httpx.Response(200, json=_read("clubs.json")))
    respx.post(f"{BASE}/brands").mock(return_value=httpx.Response(200, json=_read("brands.json")))

    sup = StubSupabase()
    repo = TaxonomyRepository(sup)
    async with CurvaClient(base_url=BASE, timeout=5) as c:
        result = await sync_taxonomy(curva=c, repo=repo)

    assert result.ok is False
    assert "categories" in (result.error or "")
```

- [ ] **Step 2: Implement sync service**

`src/curva_agent/sync/__init__.py`: (empty)

`src/curva_agent/sync/taxonomy.py`:
```python
"""Sync taxonomy from upstream Curva API into Supabase.

Strategy: fetch each reference endpoint in both `ar` and `en` locales (to get
bilingual names), upsert into Supabase. Continue on per-resource failures and
report a per-resource result so callers can decide how to handle partial syncs.
"""
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

    # Categories + subcategories (needs both locales)
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

    # Clubs
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

    # Brands
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

    # Seasons
    try:
        seasons = await curva.get_seasons()
        season_rows = [SeasonRow(id=s.id, name=s.name) for s in seasons.data]
        await repo.upsert_seasons(season_rows)
        counts["seasons"] = len(season_rows)
    except CurvaAPIError as e:
        errors.append(f"seasons: {e}")
        log.error("sync_seasons_failed", error=str(e))

    # Branches
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
    """Append a row to taxonomy_sync_runs."""
    await supabase.table("taxonomy_sync_runs").insert(
        {
            "started_at": started_at,
            "finished_at": "now()",
            "ok": result.ok,
            "delta_summary": result.counts,
            "error": result.error,
        }
    ).execute()
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_taxonomy_sync.py -v`
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add src/curva_agent/sync/ tests/unit/test_taxonomy_sync.py
git commit -m "feat(sync): bilingual taxonomy sync from Curva → Supabase"
```

---

### Task 10: `POST /admin/sync-taxonomy` endpoint

**Files:**
- Create: `src/curva_agent/deps.py`
- Modify: `src/curva_agent/main.py`
- Create: `tests/unit/test_admin_routes.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_admin_routes.py`:
```python
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from curva_agent.main import app


def test_sync_taxonomy_requires_api_key():
    client = TestClient(app)
    r = client.post("/admin/sync-taxonomy")
    assert r.status_code == 401


def test_sync_taxonomy_rejects_wrong_key():
    client = TestClient(app)
    r = client.post("/admin/sync-taxonomy", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_sync_taxonomy_runs_and_returns_counts():
    fake_result = type("R", (), {"ok": True, "counts": {"clubs": 117, "brands": 76}, "error": None})()
    with patch("curva_agent.main.sync_taxonomy", new=AsyncMock(return_value=fake_result)) as mock_sync, \
         patch("curva_agent.main.get_curva_client") as mock_curva, \
         patch("curva_agent.main.get_taxonomy_repo") as mock_repo:
        mock_curva.return_value = AsyncMock()
        mock_repo.return_value = AsyncMock()
        client = TestClient(app)
        r = client.post("/admin/sync-taxonomy", headers={"X-API-Key": "test-agent-key"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["counts"]["clubs"] == 117
    mock_sync.assert_awaited_once()
```

- [ ] **Step 2: Implement deps + admin route**

`src/curva_agent/deps.py`:
```python
"""FastAPI dependency providers."""
from fastapi import Depends, Header, HTTPException, status
from curva_agent.config import Settings, get_settings
from curva_agent.curva_client.client import CurvaClient
from curva_agent.supabase_client.client import get_supabase_client
from curva_agent.supabase_client.taxonomy import TaxonomyRepository


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_api_key or x_api_key != settings.agent_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid or missing api key")


async def get_curva_client(settings: Settings = Depends(get_settings)) -> CurvaClient:
    return CurvaClient(
        base_url=settings.curva_api_base,
        user_agent=settings.curva_user_agent,
        rate_limit_warn_at=settings.curva_rate_limit_warn_at,
    )


async def get_taxonomy_repo() -> TaxonomyRepository:
    client = await get_supabase_client()
    return TaxonomyRepository(client)
```

Modify `src/curva_agent/main.py` — add admin route:
```python
"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import Depends, FastAPI
from curva_agent import __version__
from curva_agent.config import get_settings
from curva_agent.curva_client.client import CurvaClient
from curva_agent.deps import get_curva_client, get_taxonomy_repo, require_api_key
from curva_agent.observability.logging import configure_logging, get_logger
from curva_agent.supabase_client.taxonomy import TaxonomyRepository
from curva_agent.sync.taxonomy import sync_taxonomy


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger("startup")
    log.info("service_starting", version=__version__, model=settings.llm_model)
    yield
    log.info("service_stopping")


app = FastAPI(title="Curva CS Agent", version=__version__, lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "curva-cs-agent", "version": __version__}


@app.post("/admin/sync-taxonomy", dependencies=[Depends(require_api_key)])
async def admin_sync_taxonomy(
    curva: CurvaClient = Depends(get_curva_client),
    repo: TaxonomyRepository = Depends(get_taxonomy_repo),
) -> dict:
    log = get_logger("admin.sync")
    started_at = datetime.now(timezone.utc).isoformat()
    log.info("sync_taxonomy_started", started_at=started_at)
    try:
        result = await sync_taxonomy(curva=curva, repo=repo)
    finally:
        await curva.aclose()
    log.info("sync_taxonomy_finished", ok=result.ok, counts=result.counts, error=result.error)
    return {"ok": result.ok, "counts": result.counts, "error": result.error, "started_at": started_at}
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_admin_routes.py tests/unit/test_main.py -v`
Expected: all green.

- [ ] **Step 4: Manual integration smoke test (optional, requires real Supabase)**

Run (with real `.env`):
```bash
uvicorn curva_agent.main:app --port 8000 &
sleep 1
curl -s -X POST -H "X-API-Key: $AGENT_API_KEY" http://localhost:8000/admin/sync-taxonomy | jq
kill %1
```
Expected: `{"ok": true, "counts": {"categories": 7, "subcategories": 70, "clubs": 117, "brands": 76, "seasons": 40, "branches": 8}, ...}`

- [ ] **Step 5: Commit**

```bash
git add src/curva_agent/deps.py src/curva_agent/main.py tests/unit/test_admin_routes.py
git commit -m "feat(api): POST /admin/sync-taxonomy with shared-secret auth"
```

---

### Task 11: Supabase Edge Function for weekly cron

**Files:**
- Create: `supabase/functions/sync-taxonomy/index.ts`
- Create: `supabase/functions/sync-taxonomy/deno.json`
- Create: `supabase/migrations/20260511000003_cron_sync_taxonomy.sql`

- [ ] **Step 1: Create Edge Function source**

`supabase/functions/sync-taxonomy/deno.json`:
```json
{
  "imports": {}
}
```

`supabase/functions/sync-taxonomy/index.ts`:
```typescript
// Weekly cron: triggers the agent service's /admin/sync-taxonomy endpoint.
// Configured to run Sundays 03:00 Cairo time via pg_cron (see migration).
//
// Env (set in Supabase dashboard):
//   AGENT_SERVICE_URL  https://curva-cs-agent.example.com
//   AGENT_API_KEY      shared secret
Deno.serve(async (_req) => {
  const url = Deno.env.get("AGENT_SERVICE_URL");
  const key = Deno.env.get("AGENT_API_KEY");
  if (!url || !key) {
    return new Response(
      JSON.stringify({ ok: false, error: "missing AGENT_SERVICE_URL or AGENT_API_KEY" }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
  const startedAt = new Date().toISOString();
  const r = await fetch(`${url}/admin/sync-taxonomy`, {
    method: "POST",
    headers: { "X-API-Key": key, "Content-Type": "application/json" },
  });
  const body = await r.text();
  return new Response(
    JSON.stringify({ triggered_at: startedAt, status: r.status, body }),
    { status: r.ok ? 200 : 502, headers: { "Content-Type": "application/json" } },
  );
});
```

- [ ] **Step 2: Create pg_cron migration**

`supabase/migrations/20260511000003_cron_sync_taxonomy.sql`:
```sql
-- Schedule the sync-taxonomy Edge Function weekly on Sunday at 01:00 UTC (03:00 Cairo, no DST).
create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Replace these placeholders during one-time setup in your Supabase dashboard:
-- :supabase_url:  -- e.g. https://xxxxx.supabase.co
-- :anon_key:      -- service role key
do $$
begin
  perform cron.schedule(
    'sync-taxonomy-weekly',
    '0 1 * * 0',
    $cron$
    select net.http_post(
      url := current_setting('app.supabase_url') || '/functions/v1/sync-taxonomy',
      headers := jsonb_build_object('Authorization', 'Bearer ' || current_setting('app.anon_key'))
    ) as request_id;
    $cron$
  );
exception when others then
  raise notice 'cron.schedule skipped (already exists or pg_cron unavailable): %', sqlerrm;
end$$;
```

- [ ] **Step 3: Local smoke test of Edge Function**

Run:
```bash
npx supabase functions serve sync-taxonomy --env-file .env.local &
sleep 2
curl -sX POST http://localhost:54321/functions/v1/sync-taxonomy
kill %1
```
Expected: response with `triggered_at` and forwarded status (since AGENT_SERVICE_URL points at local instance).

- [ ] **Step 4: Commit**

```bash
git add supabase/functions/ supabase/migrations/20260511000003_cron_sync_taxonomy.sql
git commit -m "feat(cron): weekly Edge Function to trigger taxonomy sync"
```

---

## Phase 3 — In-Memory Cache

### Task 12: TTL LRU cache with single-flight

**Files:**
- Create: `src/curva_agent/cache/__init__.py`
- Create: `src/curva_agent/cache/lru.py`
- Create: `tests/unit/test_cache.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_cache.py`:
```python
import asyncio
import pytest
from curva_agent.cache.lru import AsyncTTLCache


@pytest.mark.asyncio
async def test_cache_miss_calls_loader_once():
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        return {"value": 42}

    c = AsyncTTLCache(maxsize=10, ttl=60)
    v1 = await c.get_or_load("k", loader)
    v2 = await c.get_or_load("k", loader)
    assert v1 == v2 == {"value": 42}
    assert calls == 1


@pytest.mark.asyncio
async def test_single_flight_dedupes_concurrent_calls():
    calls = 0

    async def slow_loader():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return "v"

    c = AsyncTTLCache(maxsize=10, ttl=60)
    results = await asyncio.gather(*[c.get_or_load("same_key", slow_loader) for _ in range(8)])
    assert results == ["v"] * 8
    assert calls == 1  # only ONE loader invocation


@pytest.mark.asyncio
async def test_ttl_expiry_triggers_reload():
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        return calls

    c = AsyncTTLCache(maxsize=10, ttl=0.05)
    v1 = await c.get_or_load("k", loader)
    await asyncio.sleep(0.1)
    v2 = await c.get_or_load("k", loader)
    assert v1 == 1
    assert v2 == 2


@pytest.mark.asyncio
async def test_different_keys_isolated():
    c = AsyncTTLCache(maxsize=10, ttl=60)
    assert await c.get_or_load("a", lambda: _async_value(1)) == 1
    assert await c.get_or_load("b", lambda: _async_value(2)) == 2


async def _async_value(v):
    return v


@pytest.mark.asyncio
async def test_metrics_reports_hits_and_misses():
    c = AsyncTTLCache(maxsize=10, ttl=60)
    await c.get_or_load("k", lambda: _async_value("x"))  # miss
    await c.get_or_load("k", lambda: _async_value("x"))  # hit
    await c.get_or_load("k", lambda: _async_value("x"))  # hit
    assert c.metrics() == {"hits": 2, "misses": 1, "size": 1}
```

- [ ] **Step 2: Implement cache**

`src/curva_agent/cache/__init__.py`:
```python
from curva_agent.cache.lru import AsyncTTLCache

__all__ = ["AsyncTTLCache"]
```

`src/curva_agent/cache/lru.py`:
```python
"""TTL-bounded LRU cache with single-flight semantics for async loaders.

Why single-flight: when 5 concurrent requests miss the cache for the same key
(common: 5 customers all asking about Zamalek jerseys simultaneously), only ONE
upstream call fires; siblings await the same future. Prevents thundering herd.
"""
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from cachetools import TTLCache


class AsyncTTLCache:
    def __init__(self, *, maxsize: int, ttl: float) -> None:
        self._store: TTLCache[str, Any] = TTLCache(maxsize=maxsize, ttl=ttl)
        self._inflight: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get_or_load(self, key: str, loader: Callable[[], Awaitable[Any]]) -> Any:
        # Fast path: cached value
        try:
            v = self._store[key]
            self._hits += 1
            return v
        except KeyError:
            pass

        # Coordinate concurrent misses
        async with self._lock:
            try:
                v = self._store[key]
                self._hits += 1
                return v
            except KeyError:
                pass
            if key in self._inflight:
                fut = self._inflight[key]
            else:
                fut = asyncio.get_running_loop().create_future()
                self._inflight[key] = fut
                asyncio.create_task(self._fill(key, loader, fut))

        self._misses += 1
        return await fut

    async def _fill(
        self,
        key: str,
        loader: Callable[[], Awaitable[Any]],
        fut: asyncio.Future,
    ) -> None:
        try:
            v = await loader()
            self._store[key] = v
            fut.set_result(v)
        except Exception as e:
            fut.set_exception(e)
        finally:
            async with self._lock:
                self._inflight.pop(key, None)

    def metrics(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses, "size": len(self._store)}

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_cache.py -v`
Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add src/curva_agent/cache/ tests/unit/test_cache.py
git commit -m "feat(cache): async TTL LRU cache with single-flight loader"
```

---

## Phase 4 — Agent Tools

### Task 13: Tool framework + `search_products`

**Files:**
- Create: `src/curva_agent/schemas/tools.py`
- Create: `src/curva_agent/tools/__init__.py`
- Create: `src/curva_agent/tools/base.py`
- Create: `src/curva_agent/tools/search_products.py`
- Create: `tests/unit/test_search_products_tool.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_search_products_tool.py`:
```python
import json
from pathlib import Path
import httpx
import pytest
import respx
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.tools.search_products import SearchProductsTool, SearchProductsInput

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_search_returns_summaries():
    respx.post(f"{BASE}/products").mock(return_value=httpx.Response(200, json=_read("products_zamalek.json")))
    async with CurvaClient(base_url=BASE) as c:
        tool = SearchProductsTool(curva=c, cache=AsyncTTLCache(maxsize=64, ttl=60))
        out = await tool.run(SearchProductsInput(club_id=26, limit=5, page=1))
    assert out.total >= 1
    assert out.items[0].id > 0
    assert out.items[0].url.startswith("https://curvaegypt.com/product/")


@pytest.mark.asyncio
@respx.mock
async def test_search_results_are_cached_per_filter():
    route = respx.post(f"{BASE}/products").mock(return_value=httpx.Response(200, json=_read("products_zamalek.json")))
    cache = AsyncTTLCache(maxsize=64, ttl=60)
    async with CurvaClient(base_url=BASE) as c:
        tool = SearchProductsTool(curva=c, cache=cache)
        await tool.run(SearchProductsInput(club_id=26, limit=5, page=1))
        await tool.run(SearchProductsInput(club_id=26, limit=5, page=1))  # cache hit
        await tool.run(SearchProductsInput(club_id=26, limit=10, page=1))  # cache miss (different filter)
    assert route.call_count == 2
    assert cache.metrics()["hits"] == 1


def test_search_input_is_jsonable_for_tool_use():
    schema = SearchProductsInput.model_json_schema()
    assert schema["properties"]["club_id"]["type"] in ("integer", ["integer", "null"])
    assert "category_id" in schema["properties"]


@pytest.mark.asyncio
@respx.mock
async def test_locale_is_propagated():
    route = respx.post(f"{BASE}/products").mock(return_value=httpx.Response(200, json=_read("products_zamalek.json")))
    async with CurvaClient(base_url=BASE) as c:
        tool = SearchProductsTool(curva=c, cache=AsyncTTLCache(maxsize=64, ttl=60))
        await tool.run(SearchProductsInput(club_id=26, limit=5), locale="en")
    assert route.calls[0].request.headers["accept-language"] == "en"
```

- [ ] **Step 2: Implement tools framework**

`src/curva_agent/schemas/tools.py`:
```python
"""Tool I/O schemas — shared between the orchestrator (LLM tool catalog),
the tools themselves, and the response contract.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- search_products ----------
class SearchProductsInput(_Base):
    """Filter-based catalog search. All filters optional; combine freely."""

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
```

`src/curva_agent/tools/__init__.py`: (empty)

`src/curva_agent/tools/base.py`:
```python
"""Shared base class for tools.

Each tool encapsulates: input schema, output schema, a `run` coroutine,
and a `tool_spec()` that the LLM client uses to register the tool.
"""
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from pydantic import BaseModel

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


class Tool(ABC, Generic[I, O]):
    name: str = ""
    description: str = ""
    input_model: type[BaseModel]

    @abstractmethod
    async def run(self, args: I, *, locale: str = "ar") -> O: ...

    def tool_spec(self) -> dict[str, Any]:
        """OpenAI-format tool spec; OpenRouter normalizes to provider native."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }
```

`src/curva_agent/tools/search_products.py`:
```python
"""Search products by structured filters."""
import hashlib
import json
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.schemas.tools import (
    ProductCardItem,
    SearchProductsInput,
    SearchProductsOutput,
)
from curva_agent.tools.base import Tool

STOREFRONT_URL = "https://curvaegypt.com/product/{id}"


class SearchProductsTool(Tool[SearchProductsInput, SearchProductsOutput]):
    name = "search_products"
    description = (
        "Search the Curva catalog with structured filters. Combine any of "
        "category_id, subcategory_id, club_id, brand_id, season_id, price range, "
        "free-text search, sort, and pagination. Returns product summaries "
        "(card-level: name, price, availability, image) — call get_product for "
        "full sizes/colors/stock."
    )
    input_model = SearchProductsInput

    def __init__(self, *, curva: CurvaClient, cache: AsyncTTLCache) -> None:
        self._curva = curva
        self._cache = cache

    async def run(self, args: SearchProductsInput, *, locale: str = "ar") -> SearchProductsOutput:
        filters = args.model_dump(exclude_none=True)
        key = _cache_key("search_products", locale, filters)

        async def load() -> SearchProductsOutput:
            r = await self._curva.search_products(filters, locale=locale)
            return SearchProductsOutput(
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


def _cache_key(prefix: str, locale: str, payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha256(body.encode()).hexdigest()[:16]
    return f"{prefix}:{locale}:{h}"
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_search_products_tool.py -v`
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add src/curva_agent/schemas/tools.py src/curva_agent/tools/ tests/unit/test_search_products_tool.py
git commit -m "feat(tools): Tool base + search_products with caching"
```

---

### Task 14: `get_product` tool

**Files:**
- Create: `src/curva_agent/tools/get_product.py`
- Create: `tests/unit/test_get_product_tool.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_get_product_tool.py`:
```python
import json
from pathlib import Path
import httpx
import pytest
import respx
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.tools.get_product import GetProductTool
from curva_agent.schemas.tools import GetProductInput

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_get_product_returns_flattened_variants():
    respx.get(f"{BASE}/product/10307").mock(return_value=httpx.Response(200, json=_read("product_10307.json")))
    async with CurvaClient(base_url=BASE) as c:
        tool = GetProductTool(curva=c, cache=AsyncTTLCache(maxsize=64, ttl=60))
        out = await tool.run(GetProductInput(product_id=10307))
    assert out.id == 10307
    assert out.primary_image.startswith("https://")
    assert len(out.images) >= 1
    assert len(out.variants) >= 1
    v = out.variants[0]
    assert v.size and v.size_id > 0
    assert v.available is True
    c0 = v.colors[0]
    assert c0.quantity >= 0
    assert c0.barcode.startswith(f"{out.id}-")
    assert out.url == f"https://curvaegypt.com/product/{out.id}"


@pytest.mark.asyncio
@respx.mock
async def test_variant_available_flag_reflects_stock():
    fixture = _read("product_10307.json")
    fixture["data"]["product"]["sizes"][0]["colors"][0]["quantity"] = "0"
    fixture["data"]["product"]["sizes"][0]["colors"] = [fixture["data"]["product"]["sizes"][0]["colors"][0]]
    respx.get(f"{BASE}/product/10307").mock(return_value=httpx.Response(200, json=fixture))
    async with CurvaClient(base_url=BASE) as c:
        tool = GetProductTool(curva=c, cache=AsyncTTLCache(maxsize=64, ttl=60))
        out = await tool.run(GetProductInput(product_id=10307))
    assert out.variants[0].available is False


@pytest.mark.asyncio
@respx.mock
async def test_get_product_is_cached():
    route = respx.get(f"{BASE}/product/10307").mock(return_value=httpx.Response(200, json=_read("product_10307.json")))
    cache = AsyncTTLCache(maxsize=64, ttl=60)
    async with CurvaClient(base_url=BASE) as c:
        tool = GetProductTool(curva=c, cache=cache)
        await tool.run(GetProductInput(product_id=10307))
        await tool.run(GetProductInput(product_id=10307))
    assert route.call_count == 1
    assert cache.metrics()["hits"] == 1
```

- [ ] **Step 2: Implement `get_product.py`**

`src/curva_agent/tools/get_product.py`:
```python
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
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_get_product_tool.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add src/curva_agent/tools/get_product.py tests/unit/test_get_product_tool.py
git commit -m "feat(tools): get_product with variant flattening and caching"
```

---

### Task 15: `get_offers` and `list_branches` tools

**Files:**
- Create: `src/curva_agent/tools/get_offers.py`
- Create: `src/curva_agent/tools/list_branches.py`
- Create: `tests/unit/test_offers_branches_tools.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_offers_branches_tools.py`:
```python
import json
from pathlib import Path
import httpx
import pytest
import respx
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.tools.get_offers import GetOffersTool
from curva_agent.tools.list_branches import ListBranchesTool
from curva_agent.schemas.tools import GetOffersInput, ListBranchesInput

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_get_offers_returns_discounted_items():
    respx.get(f"{BASE}/offers").mock(return_value=httpx.Response(200, json=_read("offers_p1.json")))
    async with CurvaClient(base_url=BASE) as c:
        tool = GetOffersTool(curva=c, cache=AsyncTTLCache(maxsize=64, ttl=60))
        out = await tool.run(GetOffersInput(page=1, limit=5))
    assert out.total >= 1
    assert out.items[0].url.startswith("https://curvaegypt.com/product/")


@pytest.mark.asyncio
@respx.mock
async def test_list_branches_returns_phones():
    respx.get(f"{BASE}/branches").mock(return_value=httpx.Response(200, json=_read("branches.json")))
    async with CurvaClient(base_url=BASE) as c:
        tool = ListBranchesTool(curva=c, cache=AsyncTTLCache(maxsize=8, ttl=86400))
        out = await tool.run(ListBranchesInput())
    assert len(out.branches) >= 1
    assert out.branches[0].phones


@pytest.mark.asyncio
@respx.mock
async def test_list_branches_cached_for_24h():
    route = respx.get(f"{BASE}/branches").mock(return_value=httpx.Response(200, json=_read("branches.json")))
    cache = AsyncTTLCache(maxsize=8, ttl=86400)
    async with CurvaClient(base_url=BASE) as c:
        tool = ListBranchesTool(curva=c, cache=cache)
        await tool.run(ListBranchesInput())
        await tool.run(ListBranchesInput())
        await tool.run(ListBranchesInput())
    assert route.call_count == 1
    assert cache.metrics()["hits"] == 2
```

- [ ] **Step 2: Implement `get_offers.py`**

`src/curva_agent/tools/get_offers.py`:
```python
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
```

- [ ] **Step 3: Implement `list_branches.py`**

`src/curva_agent/tools/list_branches.py`:
```python
"""List physical store branches."""
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.schemas.tools import (
    BranchInfo,
    ListBranchesInput,
    ListBranchesOutput,
)
from curva_agent.tools.base import Tool


class ListBranchesTool(Tool[ListBranchesInput, ListBranchesOutput]):
    name = "list_branches"
    description = (
        "List Curva physical store branches with phone numbers. Use when "
        "customer asks about pickup, store locations, or contact phones."
    )
    input_model = ListBranchesInput

    def __init__(self, *, curva: CurvaClient, cache: AsyncTTLCache) -> None:
        self._curva = curva
        self._cache = cache

    async def run(self, args: ListBranchesInput, *, locale: str = "ar") -> ListBranchesOutput:
        key = f"list_branches:{locale}"

        async def load() -> ListBranchesOutput:
            r = await self._curva.get_branches(locale=locale)
            return ListBranchesOutput(
                branches=[BranchInfo(id=b.id, name=b.name, phones=b.phones) for b in r.data]
            )

        return await self._cache.get_or_load(key, load)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_offers_branches_tools.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/curva_agent/tools/get_offers.py src/curva_agent/tools/list_branches.py tests/unit/test_offers_branches_tools.py
git commit -m "feat(tools): get_offers and list_branches with caching"
```

---

## Phase 5 — LLM Layer

### Task 16: OpenRouter LLM client (provider-neutral)

**Files:**
- Create: `src/curva_agent/llm/__init__.py`
- Create: `src/curva_agent/llm/client.py`
- Create: `tests/unit/test_llm_client.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_llm_client.py`:
```python
from unittest.mock import AsyncMock, MagicMock
import pytest
from curva_agent.llm.client import LLMClient, LLMMessage, LLMToolCall, LLMResponse


@pytest.mark.asyncio
async def test_complete_translates_openai_response_to_LLMResponse():
    fake_choice = MagicMock()
    fake_choice.message.content = "hello"
    fake_choice.message.tool_calls = None
    fake_choice.finish_reason = "stop"
    fake_completion = MagicMock(choices=[fake_choice], usage=MagicMock(prompt_tokens=10, completion_tokens=2))
    underlying = MagicMock()
    underlying.chat.completions.create = AsyncMock(return_value=fake_completion)

    client = LLMClient(api_key="x", model="anthropic/claude-sonnet-4.6", _client=underlying)
    resp = await client.complete(
        system_blocks=[{"type": "text", "text": "you are…", "cache_control": {"type": "ephemeral"}}],
        messages=[LLMMessage(role="user", content="hi")],
        tools=[],
    )
    assert isinstance(resp, LLMResponse)
    assert resp.text == "hello"
    assert resp.tool_calls == []
    assert resp.finish_reason == "stop"
    assert resp.usage["prompt_tokens"] == 10


@pytest.mark.asyncio
async def test_complete_extracts_tool_calls():
    tc = MagicMock()
    tc.id = "call_1"
    tc.function.name = "search_products"
    tc.function.arguments = '{"club_id": 26}'
    fake_choice = MagicMock()
    fake_choice.message.content = None
    fake_choice.message.tool_calls = [tc]
    fake_choice.finish_reason = "tool_calls"
    fake_completion = MagicMock(choices=[fake_choice], usage=MagicMock(prompt_tokens=20, completion_tokens=5))
    underlying = MagicMock()
    underlying.chat.completions.create = AsyncMock(return_value=fake_completion)

    client = LLMClient(api_key="x", model="anthropic/claude-sonnet-4.6", _client=underlying)
    resp = await client.complete(system_blocks=[], messages=[LLMMessage(role="user", content="x")], tools=[])
    assert resp.tool_calls == [LLMToolCall(id="call_1", name="search_products", arguments={"club_id": 26})]


@pytest.mark.asyncio
async def test_complete_sends_cache_control_in_system():
    captured: dict = {}

    async def capture(**kwargs):
        captured.update(kwargs)
        fc = MagicMock()
        fc.message.content = ""
        fc.message.tool_calls = None
        fc.finish_reason = "stop"
        return MagicMock(choices=[fc], usage=MagicMock(prompt_tokens=0, completion_tokens=0))

    underlying = MagicMock()
    underlying.chat.completions.create = capture

    client = LLMClient(api_key="x", model="anthropic/claude-sonnet-4.6", _client=underlying)
    await client.complete(
        system_blocks=[
            {"type": "text", "text": "stable prefix", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "dynamic per-turn"},
        ],
        messages=[LLMMessage(role="user", content="hi")],
        tools=[],
    )
    system_msg = captured["messages"][0]
    assert system_msg["role"] == "system"
    assert system_msg["content"][0]["cache_control"] == {"type": "ephemeral"}
```

- [ ] **Step 2: Implement `client.py`**

`src/curva_agent/llm/__init__.py`:
```python
from curva_agent.llm.client import LLMClient, LLMMessage, LLMResponse, LLMToolCall

__all__ = ["LLMClient", "LLMMessage", "LLMResponse", "LLMToolCall"]
```

`src/curva_agent/llm/client.py`:
```python
"""Provider-neutral LLM client backed by the OpenAI SDK pointed at OpenRouter.

OpenRouter accepts OpenAI's chat-completions schema and normalizes to whatever
backend model is named. For Anthropic models, OpenRouter passes through the
`cache_control: {"type": "ephemeral"}` extension on system/content blocks for
prompt caching.

Why this abstraction:
- Swap `anthropic/claude-sonnet-4.6` ↔ `openai/gpt-5` by env var (LLM_MODEL).
- The rest of the codebase never imports the OpenAI SDK directly.
"""
import json
from dataclasses import dataclass, field
from typing import Any
import orjson
from openai import AsyncOpenAI


@dataclass
class LLMMessage:
    role: str  # "user" | "assistant" | "tool"
    content: str | list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    name: str | None = None


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    finish_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)


class LLMClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        _client: AsyncOpenAI | None = None,
    ) -> None:
        self._model = model
        self._client = _client or AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "HTTP-Referer": "https://curvaegypt.com",
                "X-Title": "Curva CS Agent",
            },
        )

    async def complete(
        self,
        *,
        system_blocks: list[dict[str, Any]],
        messages: list[LLMMessage],
        tools: list[dict[str, Any]],
        tool_choice: str | dict | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        # System message: content as an array of text blocks; OpenRouter passes
        # cache_control through for Anthropic models.
        openai_messages: list[dict[str, Any]] = []
        if system_blocks:
            openai_messages.append({"role": "system", "content": system_blocks})
        for m in messages:
            msg: dict[str, Any] = {"role": m.role}
            if m.content is not None:
                msg["content"] = m.content
            if m.tool_call_id is not None:
                msg["tool_call_id"] = m.tool_call_id
            if m.tool_calls is not None:
                msg["tool_calls"] = m.tool_calls
            if m.name is not None:
                msg["name"] = m.name
            openai_messages.append(msg)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        completion = await self._client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        tool_calls: list[LLMToolCall] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(LLMToolCall(id=tc.id, name=tc.function.name, arguments=args))
        usage = {}
        if completion.usage is not None:
            usage = {
                "prompt_tokens": getattr(completion.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(completion.usage, "completion_tokens", 0),
            }
            # OpenRouter exposes cached tokens for Anthropic models via the
            # `prompt_tokens_details` extension when available.
            details = getattr(completion.usage, "prompt_tokens_details", None)
            if details is not None:
                cached = getattr(details, "cached_tokens", 0)
                usage["cached_tokens"] = cached or 0
        return LLMResponse(
            text=choice.message.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "",
            usage=usage,
        )

    @staticmethod
    def serialize_tool_call(tc: LLMToolCall) -> dict[str, Any]:
        """Build the assistant message's `tool_calls` entry for the next turn."""
        return {
            "id": tc.id,
            "type": "function",
            "function": {"name": tc.name, "arguments": orjson.dumps(tc.arguments).decode()},
        }
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_llm_client.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add src/curva_agent/llm/__init__.py src/curva_agent/llm/client.py tests/unit/test_llm_client.py
git commit -m "feat(llm): provider-neutral LLM client via OpenRouter"
```

---

### Task 17: System prompt builder with cached taxonomy block

**Files:**
- Create: `src/curva_agent/llm/prompts.py`
- Create: `tests/unit/test_prompts.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_prompts.py`:
```python
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
    # Block 0: stable prefix (role + taxonomy) — cached
    assert blocks[0]["type"] == "text"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "Curva" in blocks[0]["text"]
    assert "Zamalek" in blocks[0]["text"]
    assert '"id": 26' in blocks[0]["text"]
    # Block 1: dynamic per-turn (locale + response rules) — NOT cached
    assert "cache_control" not in blocks[1]
    assert "Arabic" in blocks[1]["text"] or "ar" in blocks[1]["text"]


def test_system_blocks_locale_switches_dynamic_block():
    ar = build_system_blocks(snapshot=_sample_snapshot(), locale="ar")
    en = build_system_blocks(snapshot=_sample_snapshot(), locale="en")
    assert ar[0]["text"] == en[0]["text"]  # cached prefix identical
    assert ar[1]["text"] != en[1]["text"]  # dynamic differs


def test_user_context_block_includes_session_summary():
    block = build_user_context_block(
        session_summary="Customer asked about Real Madrid jerseys size M.",
        focus_product_ids=[10307, 10306],
        conversation_history=[{"role": "user", "content": "I want the red one"}],
    )
    assert "Real Madrid" in block
    assert "10307" in block
    assert "I want the red one" in block
```

- [ ] **Step 2: Implement `prompts.py`**

`src/curva_agent/llm/prompts.py`:
```python
"""System prompt builder for the master orchestrator.

The system prompt is split into TWO blocks so the LLM provider can cache the
stable prefix and re-bill only the dynamic tail:

  Block 0 (cached):   role + voice + taxonomy snapshot + tool catalog hints
  Block 1 (dynamic):  locale rules + response-format reminder

The user-context block (session summary + conversation history) is sent as a
user message so it doesn't pollute the cached prefix.
"""
from typing import Any
import orjson
from curva_agent.supabase_client.taxonomy import TaxonomySnapshot


_ROLE_PREFIX = """\
You are the customer service agent for Curva Egypt — a football merchandise
retailer (curvaegypt.com). You speak to customers over WhatsApp.

Your job:
- Search the catalog and surface relevant products with photos.
- Answer questions about sizes, colors, prices, and stock availability.
- Recognize order intent and signal it (do NOT try to place orders yourself).
- Be concise, friendly, and accurate. Never invent products, prices, or stock.

Working method:
1. Read the session context (focus_product_ids, last_filters, conversation_summary)
   to understand whether this turn is a follow-up.
2. Resolve customer references (club, brand, season, category) to IDs by
   consulting the catalog taxonomy below. The customer may mix Arabic and
   English; both are fine.
3. Call tools to gather data. You may call multiple tools in parallel
   (e.g. comparing brands → two search_products calls in one turn).
4. When you have enough information, call `finalize_response` with the
   structured public reply AND updated session state. This MUST be your
   final tool call of the turn.

Rules:
- Prefer structured filters over keyword `search` when intent is clear.
- If a query is too broad (>50 results), refine before showing.
- If a query yields 0 results, suggest closest alternatives — never silently
  return nothing.
- For ambiguous queries (e.g. "a nice jersey"), ask a clarifying question
  instead of guessing. Use intent="clarification" in that case.
- Always include image URLs in product cards.
- conversation_summary you emit must be ≤500 tokens, in English, third-person.

Catalog taxonomy (taxonomy.json — current):
"""


_DYNAMIC_TEMPLATE_AR = """\
Locale: Arabic. Speak Egyptian Arabic (عامية مصرية), not MSA. Keep replies
short — WhatsApp users skim. Prices in EGP. When you list products, the
customer sees product cards rendered from your `products` array — don't
repeat all product info in `reply_text`.
"""

_DYNAMIC_TEMPLATE_EN = """\
Locale: English. Keep replies short — WhatsApp users skim. Prices in EGP.
When you list products, the customer sees product cards rendered from your
`products` array — don't repeat all product info in `reply_text`.
"""


def build_system_blocks(
    *,
    snapshot: TaxonomySnapshot,
    locale: str,
) -> list[dict[str, Any]]:
    """Build the two-block system message (cached prefix + dynamic tail)."""
    taxonomy_json = orjson.dumps(snapshot.to_llm_json(), option=orjson.OPT_INDENT_2).decode()
    cached_prefix = _ROLE_PREFIX + taxonomy_json
    dynamic = _DYNAMIC_TEMPLATE_AR if locale == "ar" else _DYNAMIC_TEMPLATE_EN
    return [
        {"type": "text", "text": cached_prefix, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic},
    ]


def build_user_context_block(
    *,
    session_summary: str | None,
    focus_product_ids: list[int],
    conversation_history: list[dict[str, str]] | None,
) -> str:
    parts: list[str] = ["<session_context>"]
    if session_summary:
        parts.append(f"summary: {session_summary}")
    if focus_product_ids:
        parts.append(f"focus_product_ids: {focus_product_ids}")
    if conversation_history:
        parts.append("recent_history:")
        for turn in conversation_history[-6:]:
            parts.append(f"  {turn.get('role')}: {turn.get('content')}")
    parts.append("</session_context>")
    return "\n".join(parts)
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_prompts.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add src/curva_agent/llm/prompts.py tests/unit/test_prompts.py
git commit -m "feat(llm): system prompt builder with cached taxonomy block"
```

---

### Task 18: Tool-use agent loop

**Files:**
- Create: `src/curva_agent/llm/tool_loop.py`
- Create: `tests/unit/test_tool_loop.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_tool_loop.py`:
```python
"""Tests for the tool-use loop with a stub LLM client.

The stub returns scripted responses so we can exercise multi-step loops
without real provider calls.
"""
from unittest.mock import AsyncMock
import pytest
from pydantic import BaseModel
from curva_agent.llm.client import LLMResponse, LLMToolCall
from curva_agent.llm.tool_loop import run_tool_loop, LoopExceeded, ToolError
from curva_agent.tools.base import Tool


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    echoed: str


class EchoTool(Tool[EchoInput, EchoOutput]):
    name = "echo"
    description = "Echo the input text"
    input_model = EchoInput

    async def run(self, args: EchoInput, *, locale: str = "ar") -> EchoOutput:
        return EchoOutput(echoed=args.text.upper())


@pytest.mark.asyncio
async def test_loop_calls_tool_then_finalizes():
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=[
        LLMResponse(text="", tool_calls=[LLMToolCall(id="c1", name="echo", arguments={"text": "hello"})], finish_reason="tool_calls", usage={"prompt_tokens": 5}),
        LLMResponse(text="Done", tool_calls=[], finish_reason="stop", usage={"prompt_tokens": 8}),
    ])

    result = await run_tool_loop(
        llm=llm,
        system_blocks=[],
        user_message="say hello",
        tools={EchoTool().name: EchoTool()},
        max_iterations=5,
        locale="en",
    )
    assert result.final_text == "Done"
    assert len(result.tool_calls_made) == 1
    assert result.tool_calls_made[0]["name"] == "echo"
    assert result.tool_calls_made[0]["ok"] is True


@pytest.mark.asyncio
async def test_loop_handles_parallel_tool_calls():
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=[
        LLMResponse(text="", tool_calls=[
            LLMToolCall(id="c1", name="echo", arguments={"text": "a"}),
            LLMToolCall(id="c2", name="echo", arguments={"text": "b"}),
        ], finish_reason="tool_calls", usage={"prompt_tokens": 5}),
        LLMResponse(text="ok", tool_calls=[], finish_reason="stop", usage={"prompt_tokens": 8}),
    ])
    result = await run_tool_loop(
        llm=llm, system_blocks=[], user_message="run both",
        tools={EchoTool().name: EchoTool()}, max_iterations=5, locale="en",
    )
    assert len(result.tool_calls_made) == 2


@pytest.mark.asyncio
async def test_loop_raises_when_cap_exceeded():
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        text="", tool_calls=[LLMToolCall(id="c", name="echo", arguments={"text": "x"})],
        finish_reason="tool_calls", usage={},
    ))
    with pytest.raises(LoopExceeded):
        await run_tool_loop(
            llm=llm, system_blocks=[], user_message="forever",
            tools={EchoTool().name: EchoTool()}, max_iterations=3, locale="en",
        )


@pytest.mark.asyncio
async def test_tool_error_surfaces_as_tool_message_to_llm():
    class FailingTool(Tool):
        name = "fail"; description = "always fails"; input_model = EchoInput
        async def run(self, args, *, locale="ar"):
            raise RuntimeError("kaboom")

    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=[
        LLMResponse(text="", tool_calls=[LLMToolCall(id="c1", name="fail", arguments={"text": "x"})], finish_reason="tool_calls", usage={}),
        LLMResponse(text="sorry", tool_calls=[], finish_reason="stop", usage={}),
    ])
    result = await run_tool_loop(
        llm=llm, system_blocks=[], user_message="x",
        tools={FailingTool().name: FailingTool()}, max_iterations=5, locale="en",
    )
    assert result.tool_calls_made[0]["ok"] is False
    assert "kaboom" in result.tool_calls_made[0]["error"]
    # Final assistant turn happened after the tool error was reported.
    assert result.final_text == "sorry"


@pytest.mark.asyncio
async def test_unknown_tool_returns_error_to_llm():
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=[
        LLMResponse(text="", tool_calls=[LLMToolCall(id="c1", name="nonexistent", arguments={})], finish_reason="tool_calls", usage={}),
        LLMResponse(text="ok", tool_calls=[], finish_reason="stop", usage={}),
    ])
    result = await run_tool_loop(
        llm=llm, system_blocks=[], user_message="x",
        tools={EchoTool().name: EchoTool()}, max_iterations=5, locale="en",
    )
    assert result.tool_calls_made[0]["ok"] is False
    assert "unknown tool" in result.tool_calls_made[0]["error"].lower()
```

- [ ] **Step 2: Implement `tool_loop.py`**

`src/curva_agent/llm/tool_loop.py`:
```python
"""The agent's tool-use loop.

Algorithm:
  1. Send system + user (+ accumulated history) to the LLM.
  2. If the response has tool_calls: execute each (in parallel within a turn,
     since the protocol allows multiple tool_use blocks), append a tool message
     per call, loop.
  3. If the response has only text (or `finish_reason == "stop"`), return it.
  4. If iterations exceed `max_iterations`, raise LoopExceeded.

Tool errors are NOT raised back up — they become tool-result messages so the
LLM can apologize / retry / pivot. This is critical for graceful degradation.
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
import orjson
from pydantic import ValidationError
from curva_agent.llm.client import LLMClient, LLMMessage, LLMResponse, LLMToolCall
from curva_agent.observability.logging import get_logger
from curva_agent.tools.base import Tool

log = get_logger("tool_loop")


class LoopExceeded(Exception):
    """The agent exceeded its tool-iteration safety cap."""


class ToolError(Exception):
    """A tool raised during execution (recoverable — reported to LLM)."""


@dataclass
class ToolLoopResult:
    final_text: str
    final_tool_calls: list[LLMToolCall]      # tool calls in the FINAL assistant turn (e.g. finalize_response)
    tool_calls_made: list[dict[str, Any]]    # observability: name, args, ok, error, latency_ms
    iterations: int
    total_usage: dict[str, int] = field(default_factory=dict)


async def run_tool_loop(
    *,
    llm: LLMClient,
    system_blocks: list[dict[str, Any]],
    user_message: str,
    tools: dict[str, Tool],
    max_iterations: int = 12,
    locale: str = "ar",
    context_block: str | None = None,
    finalize_tool_name: str | None = None,
) -> ToolLoopResult:
    """Run the orchestrator's agent loop.

    If `finalize_tool_name` is set, the loop ALSO stops when the LLM calls it
    (returning its arguments in `final_tool_calls`). Useful for the master
    orchestrator's structured-response gate.
    """
    messages: list[LLMMessage] = []
    if context_block:
        messages.append(LLMMessage(role="user", content=context_block))
    messages.append(LLMMessage(role="user", content=user_message))

    tool_specs = [t.tool_spec() for t in tools.values()]
    observability: list[dict[str, Any]] = []
    totals: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}

    for iteration in range(1, max_iterations + 1):
        resp: LLMResponse = await llm.complete(
            system_blocks=system_blocks, messages=messages, tools=tool_specs
        )
        for k in totals:
            totals[k] += resp.usage.get(k, 0)

        # Did the LLM call the special finalize tool? Stop here.
        if finalize_tool_name and any(tc.name == finalize_tool_name for tc in resp.tool_calls):
            return ToolLoopResult(
                final_text=resp.text,
                final_tool_calls=resp.tool_calls,
                tool_calls_made=observability,
                iterations=iteration,
                total_usage=totals,
            )

        # No tool calls → we're done (text-only finish).
        if not resp.tool_calls:
            return ToolLoopResult(
                final_text=resp.text,
                final_tool_calls=[],
                tool_calls_made=observability,
                iterations=iteration,
                total_usage=totals,
            )

        # Append assistant message with the tool calls.
        messages.append(
            LLMMessage(
                role="assistant",
                content=resp.text or None,
                tool_calls=[LLMClient.serialize_tool_call(tc) for tc in resp.tool_calls],
            )
        )

        # Execute tools in parallel.
        results = await asyncio.gather(
            *[_invoke_tool(tools, tc, locale=locale) for tc in resp.tool_calls],
            return_exceptions=False,
        )
        for tc, (payload, obs) in zip(resp.tool_calls, results, strict=True):
            observability.append(obs)
            messages.append(LLMMessage(role="tool", tool_call_id=tc.id, name=tc.name, content=payload))

    raise LoopExceeded(f"loop exceeded {max_iterations} iterations")


async def _invoke_tool(
    tools: dict[str, Tool], tc: LLMToolCall, *, locale: str
) -> tuple[str, dict[str, Any]]:
    started = time.perf_counter()
    obs: dict[str, Any] = {"name": tc.name, "args": tc.arguments, "ok": False, "latency_ms": 0}
    tool = tools.get(tc.name)
    if tool is None:
        obs["error"] = f"unknown tool: {tc.name}"
        obs["latency_ms"] = int((time.perf_counter() - started) * 1000)
        return _err_payload(obs["error"]), obs
    try:
        validated = tool.input_model.model_validate(tc.arguments)
    except ValidationError as e:
        obs["error"] = f"invalid arguments: {e}"
        obs["latency_ms"] = int((time.perf_counter() - started) * 1000)
        return _err_payload(obs["error"]), obs
    try:
        out = await tool.run(validated, locale=locale)
        obs["ok"] = True
        obs["latency_ms"] = int((time.perf_counter() - started) * 1000)
        return orjson.dumps(out.model_dump()).decode(), obs
    except Exception as e:  # noqa: BLE001 — surface to LLM
        obs["error"] = f"{type(e).__name__}: {e}"
        obs["latency_ms"] = int((time.perf_counter() - started) * 1000)
        log.warning("tool_error", tool=tc.name, error=obs["error"])
        return _err_payload(obs["error"]), obs


def _err_payload(msg: str) -> str:
    return orjson.dumps({"error": msg}).decode()
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_tool_loop.py -v`
Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add src/curva_agent/llm/tool_loop.py tests/unit/test_tool_loop.py
git commit -m "feat(llm): tool-use agent loop with parallel calls and error pass-through"
```

---

## Phase 6 — Orchestrator MVP (no session, no synthesizer)

### Task 19: `finalize_response` schema and synthetic tool

**Files:**
- Create: `src/curva_agent/schemas/api.py`
- Create: `src/curva_agent/orchestrator/__init__.py`
- Create: `src/curva_agent/orchestrator/finalize.py`
- Create: `tests/unit/test_finalize_schema.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_finalize_schema.py`:
```python
import pytest
from pydantic import ValidationError
from curva_agent.schemas.api import (
    AgentQueryRequest,
    AgentQueryResponse,
    ProductCard,
    FinalizeArgs,
    NextSessionState,
)


def test_agent_query_request_required_fields():
    r = AgentQueryRequest(session_id="2010", user_message="hi")
    assert r.locale == "ar"  # default
    with pytest.raises(ValidationError):
        AgentQueryRequest(user_message="hi")  # missing session_id


def test_agent_query_response_minimal():
    r = AgentQueryResponse(reply_text="hi", products=[], intent="smalltalk")
    assert r.diagnostics is None


def test_product_card_url_and_images():
    card = ProductCard(
        id=10307,
        name_ar="..", name_en="..",
        price=295, offer_price=None, offer_ratio=None,
        availability="available",
        url="https://curvaegypt.com/product/10307",
        images=["https://x/y.webp"],
        primary_image="https://x/y.webp",
        variants=[], club=None, brand=None,
        season=None, category=None, subcategory=None,
    )
    assert card.id == 10307


def test_finalize_args_round_trip():
    args = FinalizeArgs(
        public=AgentQueryResponse(reply_text="hi", products=[], intent="search"),
        next_session_state=NextSessionState(
            focus_product_ids=[1, 2], last_filters={"club_id": 26},
            conversation_summary="asked about Zamalek",
        ),
    )
    j = args.model_dump_json()
    parsed = FinalizeArgs.model_validate_json(j)
    assert parsed.public.intent == "search"
    assert parsed.next_session_state.focus_product_ids == [1, 2]
```

- [ ] **Step 2: Implement API schemas**

`src/curva_agent/schemas/api.py`:
```python
"""Public endpoint contract + orchestrator's `finalize_response` tool args."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field
from curva_agent.schemas.tools import VariantBySize


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ---------- Request ----------
class HistoryTurn(_Base):
    role: Literal["user", "assistant"]
    content: str


class RequestMetadata(_Base):
    customer_name: str | None = None
    customer_phone: str | None = None
    channel: str | None = None


class AgentQueryRequest(_Base):
    session_id: str = Field(..., min_length=1)
    user_message: str = Field(..., min_length=1)
    locale: Literal["ar", "en"] = "ar"
    conversation_history: list[HistoryTurn] = Field(default_factory=list)
    metadata: RequestMetadata | None = None


# ---------- Response ----------
class ProductCard(_Base):
    id: int
    name_ar: str
    name_en: str
    price: int
    offer_price: int | None
    offer_ratio: str | None
    availability: str
    url: str
    images: list[str]
    primary_image: str
    variants: list[VariantBySize]
    club: dict[str, Any] | None
    brand: dict[str, Any] | None
    season: str | None
    category: str | None
    subcategory: str | None


Intent = Literal[
    "search", "detail", "availability", "order_intent",
    "smalltalk", "handoff", "clarification",
]


class Diagnostics(_Base):
    tool_calls: int
    synthesizer_invoked: bool = False
    latency_ms: int = 0
    model: str = ""
    cache_hits: int = 0
    iterations: int = 0
    # Per-call observability — used by agent_logs writer.
    tool_calls_detail: list[dict[str, Any]] = Field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0


class AgentQueryResponse(_Base):
    reply_text: str
    products: list[ProductCard] = Field(default_factory=list)
    follow_up_suggestions: list[str] = Field(default_factory=list)
    intent: Intent
    diagnostics: Diagnostics | None = None


# ---------- finalize_response tool args ----------
class NextSessionState(_Base):
    focus_product_ids: list[int] = Field(default_factory=list)
    last_filters: dict[str, Any] | None = None
    conversation_summary: str = ""


class FinalizeArgs(_Base):
    """Arguments the orchestrator MUST emit via finalize_response."""

    public: AgentQueryResponse
    next_session_state: NextSessionState
```

- [ ] **Step 3: Implement finalize tool spec**

`src/curva_agent/orchestrator/__init__.py`: (empty)

`src/curva_agent/orchestrator/finalize.py`:
```python
"""The synthetic `finalize_response` tool — the orchestrator's exit gate.

This is NOT a real Tool subclass (it doesn't `run`). It only contributes a
`tool_spec` to the LLM's tool catalog. When the LLM calls it, the tool-loop
recognizes the special name and stops, surfacing the args as the structured
response.
"""
from curva_agent.schemas.api import FinalizeArgs

FINALIZE_TOOL_NAME = "finalize_response"

FINALIZE_TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": FINALIZE_TOOL_NAME,
        "description": (
            "REQUIRED final tool call. Emits the structured response to the customer "
            "and the updated session state. After calling this you MUST stop — do "
            "not call any further tools."
        ),
        "parameters": FinalizeArgs.model_json_schema(),
    },
}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_finalize_schema.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/curva_agent/schemas/api.py src/curva_agent/orchestrator/__init__.py src/curva_agent/orchestrator/finalize.py tests/unit/test_finalize_schema.py
git commit -m "feat(orchestrator): finalize_response synthetic tool + API schemas"
```

---

### Task 20: Orchestrator core (stateless, no session)

**Files:**
- Create: `src/curva_agent/orchestrator/orchestrator.py`
- Create: `tests/unit/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_orchestrator.py`:
```python
"""Orchestrator unit tests — drive the orchestrator with a scripted LLM stub
and verify it correctly returns a validated AgentQueryResponse.
"""
from unittest.mock import AsyncMock
import pytest
from curva_agent.llm.client import LLMResponse, LLMToolCall
from curva_agent.orchestrator.orchestrator import Orchestrator
from curva_agent.schemas.api import AgentQueryRequest, AgentQueryResponse
from curva_agent.supabase_client.taxonomy import (
    BrandRow, CategoryRow, ClubRow, SeasonRow, SubcategoryRow, BranchRow, TaxonomySnapshot,
)


def _snap() -> TaxonomySnapshot:
    return TaxonomySnapshot(
        categories=[CategoryRow(id=1, name_ar="ملابس", name_en="Wear", image=None)],
        subcategories=[SubcategoryRow(id=3, category_id=1, name_ar="قمصان", name_en="Jerseys")],
        clubs=[ClubRow(id=26, name_ar="الزمالك", name_en="Zamalek", type="club", supplier=None, image=None, orders_count=0)],
        brands=[BrandRow(id=8, name_ar="نايكي", name_en="Nike", image=None, orders_count=0)],
        seasons=[SeasonRow(id=40, name="2026/27")],
        branches=[BranchRow(id=3, name="مدينة نصر", phones=["010"], sort=1)],
    )


def _finalize_call(public: dict, session: dict) -> LLMToolCall:
    return LLMToolCall(
        id="final_1", name="finalize_response",
        arguments={"public": public, "next_session_state": session},
    )


@pytest.mark.asyncio
async def test_orchestrator_returns_validated_response_from_finalize():
    llm = AsyncMock()
    public = {
        "reply_text": "تمام", "products": [], "follow_up_suggestions": [], "intent": "smalltalk",
    }
    session = {"focus_product_ids": [], "last_filters": None, "conversation_summary": "hi"}
    llm.complete = AsyncMock(return_value=LLMResponse(
        text="", tool_calls=[_finalize_call(public, session)], finish_reason="tool_calls", usage={},
    ))

    orch = Orchestrator(llm=llm, tools={}, snapshot_loader=AsyncMock(return_value=_snap()), model_name="test-model")
    req = AgentQueryRequest(session_id="x", user_message="hi", locale="ar")
    resp, next_state = await orch.handle(req, session_context=None)

    assert isinstance(resp, AgentQueryResponse)
    assert resp.intent == "smalltalk"
    assert resp.diagnostics.model == "test-model"
    assert next_state.conversation_summary == "hi"


@pytest.mark.asyncio
async def test_orchestrator_handles_missing_finalize_gracefully():
    """If the LLM stops without calling finalize_response, the orchestrator
    wraps its text into a fallback response with intent=handoff."""
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        text="freeform reply", tool_calls=[], finish_reason="stop", usage={},
    ))

    orch = Orchestrator(llm=llm, tools={}, snapshot_loader=AsyncMock(return_value=_snap()), model_name="test")
    req = AgentQueryRequest(session_id="x", user_message="hi", locale="ar")
    resp, next_state = await orch.handle(req, session_context=None)
    assert resp.reply_text == "freeform reply"
    assert resp.intent == "handoff"
```

- [ ] **Step 2: Implement orchestrator**

`src/curva_agent/orchestrator/orchestrator.py`:
```python
"""Master orchestrator: composes LLM + tools + taxonomy into a single
`handle(request) → response` operation.

This phase is STATELESS — session memory is added in Phase 8. The orchestrator
accepts a `session_context` argument but does nothing with it yet.
"""
import time
from collections.abc import Awaitable, Callable
from typing import Any
from pydantic import ValidationError
from curva_agent.llm.client import LLMClient
from curva_agent.llm.prompts import build_system_blocks, build_user_context_block
from curva_agent.llm.tool_loop import LoopExceeded, run_tool_loop
from curva_agent.observability.logging import get_logger
from curva_agent.orchestrator.finalize import FINALIZE_TOOL_NAME, FINALIZE_TOOL_SPEC
from curva_agent.schemas.api import (
    AgentQueryRequest,
    AgentQueryResponse,
    Diagnostics,
    FinalizeArgs,
    NextSessionState,
)
from curva_agent.supabase_client.taxonomy import TaxonomySnapshot
from curva_agent.tools.base import Tool

log = get_logger("orchestrator")


class Orchestrator:
    def __init__(
        self,
        *,
        llm: LLMClient,
        tools: dict[str, Tool],
        snapshot_loader: Callable[[], Awaitable[TaxonomySnapshot]],
        model_name: str,
        max_iterations: int = 12,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._load_snapshot = snapshot_loader
        self._model_name = model_name
        self._max_iterations = max_iterations

    async def handle(
        self,
        req: AgentQueryRequest,
        *,
        session_context: dict[str, Any] | None,
    ) -> tuple[AgentQueryResponse, NextSessionState]:
        started = time.perf_counter()
        snapshot = await self._load_snapshot()
        system_blocks = build_system_blocks(snapshot=snapshot, locale=req.locale)

        context_block = build_user_context_block(
            session_summary=(session_context or {}).get("conversation_summary"),
            focus_product_ids=(session_context or {}).get("focus_product_ids", []),
            conversation_history=[t.model_dump() for t in req.conversation_history] or None,
        )

        # Tool catalog = real tools + the synthetic finalize tool.
        tool_specs = {t.name: t.tool_spec() for t in self._tools.values()}
        tool_specs[FINALIZE_TOOL_NAME] = FINALIZE_TOOL_SPEC

        # Run loop. Tools dict that the loop dispatches to does NOT include
        # finalize (it's handled specially by `finalize_tool_name`).
        try:
            loop_result = await run_tool_loop(
                llm=self._llm,
                system_blocks=system_blocks,
                user_message=req.user_message,
                tools=self._tools,
                max_iterations=self._max_iterations,
                locale=req.locale,
                context_block=context_block,
                finalize_tool_name=FINALIZE_TOOL_NAME,
            )
        except LoopExceeded:
            log.warning("loop_exceeded", session_id=req.session_id)
            return self._handoff_fallback("loop exceeded"), NextSessionState()

        latency_ms = int((time.perf_counter() - started) * 1000)

        # Extract finalize_response arguments.
        final_call = next(
            (tc for tc in loop_result.final_tool_calls if tc.name == FINALIZE_TOOL_NAME), None
        )
        if final_call is None:
            # The loop exited without calling finalize. Wrap the LLM's free text
            # as a handoff response so n8n still gets a valid payload.
            return self._wrap_freeform(loop_result.final_text), NextSessionState()

        try:
            args = FinalizeArgs.model_validate(final_call.arguments)
        except ValidationError as e:
            log.error("finalize_invalid", error=str(e), args=final_call.arguments)
            return self._handoff_fallback(f"invalid finalize args: {e}"), NextSessionState()

        response = args.public
        response.diagnostics = Diagnostics(
            tool_calls=len(loop_result.tool_calls_made),
            synthesizer_invoked=any(
                c["name"] == "product_synthesizer" for c in loop_result.tool_calls_made
            ),
            latency_ms=latency_ms,
            model=self._model_name,
            cache_hits=sum(1 for c in loop_result.tool_calls_made if c.get("cache_hit")),
            iterations=loop_result.iterations,
            tool_calls_detail=loop_result.tool_calls_made,
            prompt_tokens=loop_result.total_usage.get("prompt_tokens", 0),
            completion_tokens=loop_result.total_usage.get("completion_tokens", 0),
            cached_tokens=loop_result.total_usage.get("cached_tokens", 0),
        )
        return response, args.next_session_state

    def _wrap_freeform(self, text: str) -> AgentQueryResponse:
        return AgentQueryResponse(
            reply_text=text or "آسف، حصل خطأ. هاسأل حد من الفريق يساعدك.",
            products=[],
            follow_up_suggestions=[],
            intent="handoff",
        )

    def _handoff_fallback(self, reason: str) -> AgentQueryResponse:
        log.warning("handoff_fallback", reason=reason)
        return AgentQueryResponse(
            reply_text="آسف، مش قادر أساعدك دلوقتي. هاسأل حد من الفريق يكلمك.",
            products=[],
            follow_up_suggestions=[],
            intent="handoff",
        )
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_orchestrator.py -v`
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add src/curva_agent/orchestrator/orchestrator.py tests/unit/test_orchestrator.py
git commit -m "feat(orchestrator): stateless master orchestrator with handoff fallback"
```

---

### Task 21: `POST /agent/query` endpoint wiring

**Files:**
- Modify: `src/curva_agent/deps.py`
- Modify: `src/curva_agent/main.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_agent_query.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_agent_query.py`:
```python
"""Integration test: drives /agent/query with a scripted LLM and real tools
backed by respx-mocked Curva API. Verifies the end-to-end FastAPI handler.
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock
import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from curva_agent.llm.client import LLMResponse, LLMToolCall

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_agent_query_invokes_search_and_finalizes(monkeypatch):
    # Mock upstream
    respx.post(f"{BASE}/products").mock(return_value=httpx.Response(200, json=_read("products_zamalek.json")))
    # Mock the taxonomy snapshot loader to bypass Supabase
    from curva_agent.supabase_client.taxonomy import (
        TaxonomySnapshot, CategoryRow, SubcategoryRow, ClubRow, BrandRow, SeasonRow, BranchRow,
    )
    snap = TaxonomySnapshot(
        categories=[CategoryRow(id=1, name_ar="ملابس", name_en="Wear", image=None)],
        subcategories=[],
        clubs=[ClubRow(id=26, name_ar="الزمالك", name_en="Zamalek", type="club", supplier=None, image=None, orders_count=0)],
        brands=[], seasons=[], branches=[],
    )
    from curva_agent import deps
    monkeypatch.setattr(deps, "load_taxonomy_snapshot", AsyncMock(return_value=snap))

    # Mock the LLM: 1st turn calls search_products; 2nd turn calls finalize.
    public_args = {
        "reply_text": "عندنا قمصان زمالك",
        "products": [],
        "follow_up_suggestions": [],
        "intent": "search",
    }
    session_args = {"focus_product_ids": [10307], "last_filters": {"club_id": 26}, "conversation_summary": "asked about Zamalek"}
    from curva_agent.llm import client as llm_mod
    fake_llm = AsyncMock()
    fake_llm.complete = AsyncMock(side_effect=[
        LLMResponse(text="", tool_calls=[LLMToolCall(id="c1", name="search_products", arguments={"club_id": 26, "limit": 5, "page": 1})], finish_reason="tool_calls", usage={"prompt_tokens": 10}),
        LLMResponse(text="", tool_calls=[LLMToolCall(id="c2", name="finalize_response", arguments={"public": public_args, "next_session_state": session_args})], finish_reason="tool_calls", usage={"prompt_tokens": 12}),
    ])
    monkeypatch.setattr(deps, "build_llm_client", lambda: fake_llm)

    from curva_agent.main import app
    client = TestClient(app)
    r = client.post(
        "/agent/query",
        headers={"X-API-Key": "test-agent-key"},
        json={"session_id": "20100", "user_message": "عندكوا زمالك؟", "locale": "ar"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "search"
    assert body["reply_text"]
    assert body["diagnostics"]["tool_calls"] >= 1
    assert body["diagnostics"]["iterations"] >= 2


def test_agent_query_rejects_missing_api_key():
    from curva_agent.main import app
    client = TestClient(app)
    r = client.post("/agent/query", json={"session_id": "x", "user_message": "hi"})
    assert r.status_code == 401
```

- [ ] **Step 2: Modify `deps.py` to wire orchestrator dependencies**

`src/curva_agent/deps.py` — REPLACE WHOLE FILE:
```python
"""FastAPI dependency providers."""
from collections.abc import AsyncIterator
from fastapi import Depends, Header, HTTPException, status
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.config import Settings, get_settings
from curva_agent.curva_client.client import CurvaClient
from curva_agent.llm.client import LLMClient
from curva_agent.orchestrator.orchestrator import Orchestrator
from curva_agent.supabase_client.client import get_supabase_client
from curva_agent.supabase_client.taxonomy import TaxonomyRepository, TaxonomySnapshot
from curva_agent.tools.base import Tool
from curva_agent.tools.get_offers import GetOffersTool
from curva_agent.tools.get_product import GetProductTool
from curva_agent.tools.list_branches import ListBranchesTool
from curva_agent.tools.search_products import SearchProductsTool


# Module-level singletons (one container = one process).
_curva_client: CurvaClient | None = None
_caches: dict[str, AsyncTTLCache] = {}
_tools_by_name: dict[str, Tool] | None = None
_llm: LLMClient | None = None


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_api_key or x_api_key != settings.agent_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid or missing api key")


def _build_caches(settings: Settings) -> dict[str, AsyncTTLCache]:
    return {
        "products": AsyncTTLCache(maxsize=512, ttl=settings.cache_products_ttl_sec),
        "product": AsyncTTLCache(maxsize=512, ttl=settings.cache_product_ttl_sec),
        "offers": AsyncTTLCache(maxsize=64, ttl=settings.cache_offers_ttl_sec),
        "branches": AsyncTTLCache(maxsize=4, ttl=settings.cache_branches_ttl_sec),
    }


async def get_curva_client(settings: Settings = Depends(get_settings)) -> CurvaClient:
    global _curva_client
    if _curva_client is None:
        _curva_client = CurvaClient(
            base_url=settings.curva_api_base,
            user_agent=settings.curva_user_agent,
            rate_limit_warn_at=settings.curva_rate_limit_warn_at,
        )
    return _curva_client


async def get_taxonomy_repo() -> TaxonomyRepository:
    client = await get_supabase_client()
    return TaxonomyRepository(client)


async def load_taxonomy_snapshot() -> TaxonomySnapshot:
    repo = await get_taxonomy_repo()
    return await repo.load_snapshot()


def build_llm_client() -> LLMClient:
    global _llm
    if _llm is None:
        s = get_settings()
        _llm = LLMClient(api_key=s.openrouter_api_key, model=s.llm_model)
    return _llm


async def get_tools(
    curva: CurvaClient = Depends(get_curva_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, Tool]:
    global _tools_by_name, _caches
    if _tools_by_name is None:
        _caches = _build_caches(settings)
        instances: list[Tool] = [
            SearchProductsTool(curva=curva, cache=_caches["products"]),
            GetProductTool(curva=curva, cache=_caches["product"]),
            GetOffersTool(curva=curva, cache=_caches["offers"]),
            ListBranchesTool(curva=curva, cache=_caches["branches"]),
        ]
        _tools_by_name = {t.name: t for t in instances}
    return _tools_by_name


async def get_orchestrator(
    tools: dict[str, Tool] = Depends(get_tools),
    settings: Settings = Depends(get_settings),
) -> Orchestrator:
    return Orchestrator(
        llm=build_llm_client(),
        tools=tools,
        snapshot_loader=load_taxonomy_snapshot,
        model_name=settings.llm_model,
        max_iterations=settings.llm_max_tool_iterations,
    )


def reset_singletons_for_tests() -> None:
    global _curva_client, _caches, _tools_by_name, _llm
    _curva_client = None
    _caches = {}
    _tools_by_name = None
    _llm = None
```

- [ ] **Step 3: Wire `/agent/query` route**

Modify `src/curva_agent/main.py` — append:
```python
from curva_agent.deps import get_orchestrator
from curva_agent.orchestrator.orchestrator import Orchestrator
from curva_agent.schemas.api import AgentQueryRequest, AgentQueryResponse


@app.post(
    "/agent/query",
    response_model=AgentQueryResponse,
    dependencies=[Depends(require_api_key)],
)
async def agent_query(
    req: AgentQueryRequest,
    orch: Orchestrator = Depends(get_orchestrator),
) -> AgentQueryResponse:
    log = get_logger("agent_query").bind(session_id=req.session_id, locale=req.locale)
    log.info("turn_started", message_len=len(req.user_message))
    response, _next_state = await orch.handle(req, session_context=None)
    log.info("turn_finished", intent=response.intent, tool_calls=response.diagnostics.tool_calls if response.diagnostics else 0)
    return response
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_agent_query.py tests/unit/ -v`
Expected: all green.

- [ ] **Step 5: Manual smoke test against real OpenRouter (optional)**

Run (with real `.env`):
```bash
uvicorn curva_agent.main:app --port 8000 &
sleep 1
curl -sX POST http://localhost:8000/agent/query \
  -H "X-API-Key: $AGENT_API_KEY" -H "Content-Type: application/json" \
  -d '{"session_id":"test","user_message":"عندكوا قميص زمالك؟","locale":"ar"}' | jq
kill %1
```
Expected: structured JSON with `reply_text`, `products`, `intent`.

- [ ] **Step 6: Commit**

```bash
git add src/curva_agent/deps.py src/curva_agent/main.py tests/integration/
git commit -m "feat(api): POST /agent/query wires orchestrator end-to-end"
```

---

## Phase 7 — Product Synthesizer Sub-Agent

### Task 22: Parallel detail fetch helper

**Files:**
- Create: `src/curva_agent/tools/_parallel.py`
- Create: `tests/unit/test_parallel_fetch.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_parallel_fetch.py`:
```python
import asyncio
import pytest
from curva_agent.tools._parallel import fetch_products_parallel


class StubGetProductTool:
    def __init__(self):
        self.calls = []

    async def run(self, args, *, locale="ar"):
        self.calls.append(args.product_id)
        await asyncio.sleep(0.01)
        return type("Out", (), {"id": args.product_id, "name": f"P{args.product_id}"})()


@pytest.mark.asyncio
async def test_fetches_in_parallel_and_preserves_order():
    tool = StubGetProductTool()
    out = await fetch_products_parallel(tool, [3, 1, 4, 1, 5], locale="ar")
    assert [p.id for p in out] == [3, 1, 4, 1, 5]


@pytest.mark.asyncio
async def test_partial_failures_dropped_with_warning(caplog):
    class FlakyTool:
        async def run(self, args, *, locale="ar"):
            if args.product_id == 2:
                raise RuntimeError("boom")
            return type("Out", (), {"id": args.product_id, "name": f"P{args.product_id}"})()

    out = await fetch_products_parallel(FlakyTool(), [1, 2, 3], locale="ar")
    assert [p.id for p in out] == [1, 3]
```

- [ ] **Step 2: Implement parallel fetch**

`src/curva_agent/tools/_parallel.py`:
```python
"""Parallel product detail fetch helper used by the Synthesizer."""
import asyncio
from typing import Any
from curva_agent.observability.logging import get_logger
from curva_agent.schemas.tools import GetProductInput

log = get_logger("tools.parallel")


async def fetch_products_parallel(tool: Any, product_ids: list[int], *, locale: str) -> list[Any]:
    """Fetch full product details for a list of IDs in parallel.

    Returns details in the same order as input IDs. Failures are logged and
    dropped rather than failing the whole batch.
    """
    async def _one(pid: int) -> Any | Exception:
        try:
            return await tool.run(GetProductInput(product_id=pid), locale=locale)
        except Exception as e:  # noqa: BLE001
            log.warning("synthesizer_fetch_failed", product_id=pid, error=str(e))
            return e

    raw = await asyncio.gather(*(_one(p) for p in product_ids))
    return [r for r in raw if not isinstance(r, Exception)]
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_parallel_fetch.py -v`
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add src/curva_agent/tools/_parallel.py tests/unit/test_parallel_fetch.py
git commit -m "feat(tools): parallel fetch helper for the Synthesizer"
```

---

### Task 23: `product_synthesizer` sub-agent tool

**Files:**
- Create: `src/curva_agent/tools/product_synthesizer.py`
- Create: `tests/unit/test_product_synthesizer.py`
- Modify: `src/curva_agent/deps.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_product_synthesizer.py`:
```python
import json
from pathlib import Path
from unittest.mock import AsyncMock
import httpx
import pytest
import respx
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.curva_client.client import CurvaClient
from curva_agent.llm.client import LLMResponse, LLMToolCall
from curva_agent.tools.get_product import GetProductTool
from curva_agent.tools.product_synthesizer import ProductSynthesizerTool
from curva_agent.schemas.tools import ProductSynthesizerInput

FIX = Path(__file__).parent.parent / "fixtures" / "curva"
BASE = "https://octane.curvaegypt.com/api"


def _read(name: str) -> dict:
    return json.loads((FIX / name).read_text())


@pytest.mark.asyncio
@respx.mock
async def test_synthesizer_ranks_candidates_via_llm():
    respx.get(f"{BASE}/product/10307").mock(return_value=httpx.Response(200, json=_read("product_10307.json")))

    # LLM stub: returns one ranked candidate in JSON.
    fake_llm = AsyncMock()
    fake_llm.complete = AsyncMock(return_value=LLMResponse(
        text='{"candidates":[{"id":10307,"rationale":"size M in stock"}]}',
        tool_calls=[], finish_reason="stop", usage={"prompt_tokens": 50, "completion_tokens": 20},
    ))

    async with CurvaClient(base_url=BASE) as curva:
        gp = GetProductTool(curva=curva, cache=AsyncTTLCache(maxsize=8, ttl=60))
        synth = ProductSynthesizerTool(get_product=gp, llm=fake_llm)
        out = await synth.run(ProductSynthesizerInput(product_ids=[10307], constraint="size M"))

    assert len(out.candidates) == 1
    c = out.candidates[0]
    assert c.id == 10307
    assert c.rationale == "size M in stock"
    assert c.primary_image.startswith("https://")
    assert any(v.size == "M" for v in c.best_variants)
    assert c.url == "https://curvaegypt.com/product/10307"


@pytest.mark.asyncio
@respx.mock
async def test_synthesizer_drops_missing_products():
    respx.get(f"{BASE}/product/10307").mock(return_value=httpx.Response(200, json=_read("product_10307.json")))
    respx.get(f"{BASE}/product/99999").mock(return_value=httpx.Response(404, json={"status": False}))

    fake_llm = AsyncMock()
    fake_llm.complete = AsyncMock(return_value=LLMResponse(
        text='{"candidates":[{"id":10307,"rationale":"only one available"}]}',
        tool_calls=[], finish_reason="stop", usage={},
    ))

    async with CurvaClient(base_url=BASE) as curva:
        gp = GetProductTool(curva=curva, cache=AsyncTTLCache(maxsize=8, ttl=60))
        synth = ProductSynthesizerTool(get_product=gp, llm=fake_llm)
        out = await synth.run(ProductSynthesizerInput(product_ids=[10307, 99999], constraint=None))

    assert [c.id for c in out.candidates] == [10307]


@pytest.mark.asyncio
async def test_synthesizer_handles_llm_returning_invalid_json():
    fake_llm = AsyncMock()
    fake_llm.complete = AsyncMock(return_value=LLMResponse(
        text="not json at all", tool_calls=[], finish_reason="stop", usage={},
    ))

    class StubGP:
        async def run(self, args, *, locale="ar"):
            return type("P", (), {
                "id": args.product_id, "name": f"P{args.product_id}", "init_price": 100,
                "offer_price": None, "primary_image": "https://x/y.webp", "images": [],
                "variants": [], "url": f"https://curvaegypt.com/product/{args.product_id}",
            })()

    synth = ProductSynthesizerTool(get_product=StubGP(), llm=fake_llm)
    out = await synth.run(ProductSynthesizerInput(product_ids=[1, 2], constraint=None))
    # Fallback: returns candidates in input order with empty rationales.
    assert [c.id for c in out.candidates] == [1, 2]
    assert all(c.rationale == "" for c in out.candidates)
```

- [ ] **Step 2: Implement the synthesizer**

`src/curva_agent/tools/product_synthesizer.py`:
```python
"""The Product Synthesizer sub-agent.

Given 1–10 candidate product IDs and an optional user constraint, this tool:
  1. Fetches full product details in parallel.
  2. Calls a focused LLM with the constraint and a compact summary of each
     candidate, asking for ranking + a one-line "why this matches" rationale.
  3. Returns a structured list of SynthesizedCandidate.

Why this is a sub-agent and not a deterministic ranker: ranking, dedup, and
"what to emphasize" need judgment that's brittle to encode as rules.
"""
import json
from typing import Any
from curva_agent.llm.client import LLMClient, LLMMessage
from curva_agent.observability.logging import get_logger
from curva_agent.schemas.tools import (
    ProductSynthesizerInput,
    ProductSynthesizerOutput,
    SynthesizedCandidate,
    GetProductOutput,
)
from curva_agent.tools._parallel import fetch_products_parallel
from curva_agent.tools.base import Tool

log = get_logger("synthesizer")

_SYS_PROMPT = """\
You are a ranking sub-agent for the Curva CS bot. You are NOT talking to the
customer — only the master agent reads your output.

Input: a list of candidate products (full details) and a customer constraint.
Output: a JSON object {"candidates":[{"id":N,"rationale":"..."}, ...]} ranking
the candidates by how well they match the constraint. Drop near-duplicates.
Cap output at 5 candidates. If no constraint, rank by stock availability and
recency (favor available, higher-stock variants).

Rationale: ONE short line in the requested locale, ≤80 chars, explaining the
match (e.g. "Size M available, on sale", "Closest color match").

Return ONLY the JSON object. No prose.
"""


class ProductSynthesizerTool(Tool[ProductSynthesizerInput, ProductSynthesizerOutput]):
    name = "product_synthesizer"
    description = (
        "Given 1-10 candidate product IDs and an optional user constraint, "
        "fetch full details for each in parallel and return a ranked, deduped "
        "list of the best matches with photos, variants, and one-line "
        "rationales. Use after search_products to drill into candidates."
    )
    input_model = ProductSynthesizerInput

    def __init__(self, *, get_product: Any, llm: LLMClient) -> None:
        self._get_product = get_product
        self._llm = llm

    async def run(
        self, args: ProductSynthesizerInput, *, locale: str = "ar"
    ) -> ProductSynthesizerOutput:
        details: list[GetProductOutput] = await fetch_products_parallel(
            self._get_product, args.product_ids, locale=locale
        )
        if not details:
            return ProductSynthesizerOutput(candidates=[])

        # Build compact summary for the ranker LLM.
        compact = [
            {
                "id": d.id,
                "name": d.name,
                "price": d.init_price,
                "offer_price": d.offer_price,
                "availability": d.availability,
                "variants": [
                    {
                        "size": v.size,
                        "available": v.available,
                        "colors": [
                            {"name": c.name, "qty": c.quantity} for c in v.colors
                        ],
                    }
                    for v in d.variants
                ],
            }
            for d in details
        ]
        user_msg = json.dumps(
            {"constraint": args.constraint, "locale": locale, "candidates": compact},
            ensure_ascii=False,
        )

        resp = await self._llm.complete(
            system_blocks=[{"type": "text", "text": _SYS_PROMPT}],
            messages=[LLMMessage(role="user", content=user_msg)],
            tools=[],
            temperature=0.1,
            max_tokens=1024,
        )

        rankings = _parse_rankings(resp.text)
        by_id = {d.id: d for d in details}
        candidates: list[SynthesizedCandidate] = []
        seen: set[int] = set()
        # Use ranker order when available; fall back to input order for the rest.
        order = [r["id"] for r in rankings if r["id"] in by_id]
        for pid in order + [d.id for d in details if d.id not in order]:
            if pid in seen:
                continue
            seen.add(pid)
            d = by_id[pid]
            rationale = next((r["rationale"] for r in rankings if r["id"] == pid), "")
            candidates.append(
                SynthesizedCandidate(
                    id=d.id,
                    name=d.name,
                    price=d.init_price,
                    offer_price=d.offer_price,
                    primary_image=d.primary_image,
                    images=d.images[:3],
                    best_variants=[v for v in d.variants if v.available][:3] or d.variants[:3],
                    url=d.url,
                    rationale=rationale,
                )
            )
            if len(candidates) >= 5:
                break
        return ProductSynthesizerOutput(candidates=candidates)


def _parse_rankings(text: str) -> list[dict[str, Any]]:
    """Best-effort JSON parsing of the ranker output."""
    if not text:
        return []
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract a JSON object substring.
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            log.warning("synthesizer_invalid_json", text=text[:200])
            return []
        try:
            obj = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            log.warning("synthesizer_invalid_json", text=text[:200])
            return []
    cands = obj.get("candidates") if isinstance(obj, dict) else None
    if not isinstance(cands, list):
        return []
    out: list[dict[str, Any]] = []
    for c in cands:
        if isinstance(c, dict) and isinstance(c.get("id"), int):
            out.append({"id": c["id"], "rationale": str(c.get("rationale") or "")})
    return out
```

- [ ] **Step 3: Wire the synthesizer in `deps.py`**

Modify `src/curva_agent/deps.py` — inside `get_tools`, add to the instances list:
```python
from curva_agent.tools.product_synthesizer import ProductSynthesizerTool

# ... inside get_tools() after creating gp = GetProductTool(...):
async def get_tools(
    curva: CurvaClient = Depends(get_curva_client),
    settings: Settings = Depends(get_settings),
) -> dict[str, Tool]:
    global _tools_by_name, _caches
    if _tools_by_name is None:
        _caches = _build_caches(settings)
        gp = GetProductTool(curva=curva, cache=_caches["product"])
        instances: list[Tool] = [
            SearchProductsTool(curva=curva, cache=_caches["products"]),
            gp,
            GetOffersTool(curva=curva, cache=_caches["offers"]),
            ListBranchesTool(curva=curva, cache=_caches["branches"]),
            ProductSynthesizerTool(get_product=gp, llm=build_llm_client()),
        ]
        _tools_by_name = {t.name: t for t in instances}
    return _tools_by_name
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_product_synthesizer.py tests/integration/ -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/curva_agent/tools/product_synthesizer.py src/curva_agent/deps.py tests/unit/test_product_synthesizer.py
git commit -m "feat(tools): Product Synthesizer sub-agent with parallel fetch and LLM ranking"
```

---

## Phase 8 — Session Memory

### Task 24: `agent_sessions` migration

**Files:**
- Create: `supabase/migrations/20260511000004_agent_sessions.sql`

- [ ] **Step 1: Create migration**

`supabase/migrations/20260511000004_agent_sessions.sql`:
```sql
create table if not exists agent_sessions (
  session_id            text primary key,
  locale                text not null default 'ar',
  customer_name         text,
  focus_product_ids     int[] not null default '{}',
  last_filters          jsonb,
  conversation_summary  text default '',
  turn_count            int not null default 0,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  last_active_at        timestamptz not null default now()
);

create index if not exists agent_sessions_last_active_at_idx
  on agent_sessions(last_active_at);

-- Daily cleanup of inactive sessions (>30d). Uses pg_cron.
create extension if not exists pg_cron;
do $$
begin
  perform cron.schedule(
    'agent-sessions-gc-daily',
    '15 2 * * *',
    $cron$
    delete from agent_sessions
    where last_active_at < now() - interval '30 days';
    $cron$
  );
exception when others then
  raise notice 'cron.schedule skipped: %', sqlerrm;
end$$;
```

- [ ] **Step 2: Apply migration locally**

Run:
```bash
npx supabase db reset
psql "postgresql://postgres:postgres@localhost:54322/postgres" -c "\d agent_sessions"
```
Expected: shows the table with all columns.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260511000004_agent_sessions.sql
git commit -m "feat(db): agent_sessions table + 30-day GC cron"
```

---

### Task 25: Session repository

**Files:**
- Create: `src/curva_agent/supabase_client/sessions.py`
- Create: `tests/unit/test_session_repo.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_session_repo.py`:
```python
from typing import Any
import pytest
from curva_agent.supabase_client.sessions import SessionRepository, SessionRow


class StubTable:
    def __init__(self, store: dict, name: str):
        self.store = store
        self.name = name
        self._filter: tuple | None = None

    def select(self, _cols: str = "*"):
        return self

    def eq(self, col: str, val: Any):
        self._filter = (col, val)
        return self

    def upsert(self, payload: dict, on_conflict: str = "session_id"):
        self.store.setdefault(self.name, {})[payload["session_id"]] = payload
        return self

    def maybe_single(self):
        return self

    async def execute(self):
        if self._filter is not None:
            col, val = self._filter
            row = self.store.get(self.name, {}).get(val) if col == "session_id" else None
            return type("R", (), {"data": row})()
        return type("R", (), {"data": list(self.store.get(self.name, {}).values())})()


class StubSupabase:
    def __init__(self):
        self.store: dict[str, dict[str, Any]] = {}

    def table(self, name: str) -> StubTable:
        return StubTable(self.store, name)


@pytest.mark.asyncio
async def test_load_returns_none_for_missing_session():
    repo = SessionRepository(StubSupabase())
    assert await repo.load("nonexistent") is None


@pytest.mark.asyncio
async def test_save_then_load_round_trip():
    sup = StubSupabase()
    repo = SessionRepository(sup)
    row = SessionRow(
        session_id="20100",
        locale="ar",
        customer_name="Ahmed",
        focus_product_ids=[10307],
        last_filters={"club_id": 26},
        conversation_summary="asked Zamalek",
        turn_count=1,
    )
    await repo.save(row)
    loaded = await repo.load("20100")
    assert loaded is not None
    assert loaded.session_id == "20100"
    assert loaded.focus_product_ids == [10307]
    assert loaded.last_filters == {"club_id": 26}
    assert loaded.turn_count == 1


@pytest.mark.asyncio
async def test_save_increments_turn_count_for_existing_session():
    sup = StubSupabase()
    repo = SessionRepository(sup)
    await repo.save(SessionRow(session_id="x", locale="ar"))
    await repo.save(SessionRow(session_id="x", locale="ar"))
    loaded = await repo.load("x")
    assert loaded.turn_count == 2
```

- [ ] **Step 2: Implement sessions repository**

`src/curva_agent/supabase_client/sessions.py`:
```python
"""Session memory repository."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass
class SessionRow:
    session_id: str
    locale: str = "ar"
    customer_name: str | None = None
    focus_product_ids: list[int] = field(default_factory=list)
    last_filters: dict[str, Any] | None = None
    conversation_summary: str = ""
    turn_count: int = 0


class _SupabaseLike(Protocol):
    def table(self, name: str) -> Any: ...


class SessionRepository:
    TABLE = "agent_sessions"

    def __init__(self, client: _SupabaseLike) -> None:
        self._c = client

    async def load(self, session_id: str) -> SessionRow | None:
        r = await self._c.table(self.TABLE).select("*").eq("session_id", session_id).maybe_single().execute()
        if not getattr(r, "data", None):
            return None
        data = r.data
        return SessionRow(
            session_id=data["session_id"],
            locale=data.get("locale", "ar"),
            customer_name=data.get("customer_name"),
            focus_product_ids=data.get("focus_product_ids") or [],
            last_filters=data.get("last_filters"),
            conversation_summary=data.get("conversation_summary") or "",
            turn_count=data.get("turn_count") or 0,
        )

    async def save(self, row: SessionRow) -> None:
        # Increment turn_count for existing sessions.
        existing = await self.load(row.session_id)
        new_turn_count = (existing.turn_count + 1) if existing else max(row.turn_count, 1)
        now = datetime.now(timezone.utc).isoformat()
        payload = asdict(row)
        payload["turn_count"] = new_turn_count
        payload["updated_at"] = now
        payload["last_active_at"] = now
        if existing is None:
            payload["created_at"] = now
        await self._c.table(self.TABLE).upsert(payload, on_conflict="session_id").execute()
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_session_repo.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add src/curva_agent/supabase_client/sessions.py tests/unit/test_session_repo.py
git commit -m "feat(db): session repository with load/save + turn count"
```

---

### Task 26: Integrate session into orchestrator + endpoint

**Files:**
- Modify: `src/curva_agent/orchestrator/orchestrator.py`
- Modify: `src/curva_agent/deps.py`
- Modify: `src/curva_agent/main.py`
- Create: `tests/integration/test_session_flow.py`

- [ ] **Step 1: Write the failing test**

`tests/integration/test_session_flow.py`:
```python
"""Multi-turn integration test: turn 1 sets focus, turn 2 reads it."""
from unittest.mock import AsyncMock
import pytest
from curva_agent.llm.client import LLMResponse, LLMToolCall
from curva_agent.orchestrator.orchestrator import Orchestrator
from curva_agent.schemas.api import AgentQueryRequest
from curva_agent.supabase_client.sessions import SessionRepository, SessionRow
from curva_agent.supabase_client.taxonomy import (
    BranchRow, BrandRow, CategoryRow, ClubRow, SeasonRow, SubcategoryRow, TaxonomySnapshot,
)
from tests.unit.test_session_repo import StubSupabase


def _snap():
    return TaxonomySnapshot(
        categories=[CategoryRow(id=1, name_ar="ملابس", name_en="Wear", image=None)],
        subcategories=[],
        clubs=[ClubRow(id=26, name_ar="الزمالك", name_en="Zamalek", type="club", supplier=None, image=None, orders_count=0)],
        brands=[], seasons=[], branches=[],
    )


def _finalize(public, session):
    return LLMToolCall(id="f", name="finalize_response", arguments={"public": public, "next_session_state": session})


@pytest.mark.asyncio
async def test_session_focus_carries_across_turns():
    sup = StubSupabase()
    sessions = SessionRepository(sup)

    # Turn 1: LLM finalizes with focus_product_ids=[10307]
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=LLMResponse(
        text="", tool_calls=[_finalize(
            public={"reply_text": "ها هو", "products": [], "follow_up_suggestions": [], "intent": "search"},
            session={"focus_product_ids": [10307], "last_filters": {"club_id": 26}, "conversation_summary": "Showed Zamalek jersey"},
        )], finish_reason="tool_calls", usage={},
    ))

    orch = Orchestrator(llm=llm, tools={}, snapshot_loader=AsyncMock(return_value=_snap()), model_name="t")
    captured_context: list = []

    # Wrap orchestrator.handle to capture session context per turn
    original_handle = orch.handle

    async def spy_handle(req, *, session_context):
        captured_context.append(session_context)
        return await original_handle(req, session_context=session_context)

    orch.handle = spy_handle

    # Turn 1
    req1 = AgentQueryRequest(session_id="20100", user_message="عندكوا زمالك؟", locale="ar")
    existing = await sessions.load("20100")
    ctx1 = _to_context(existing)
    resp1, next_state1 = await orch.handle(req1, session_context=ctx1)
    await sessions.save(_row_from_state("20100", "ar", next_state1, locale_for_new="ar"))

    # Turn 2: ensure the orchestrator now sees focus_product_ids=[10307]
    llm.complete = AsyncMock(return_value=LLMResponse(
        text="", tool_calls=[_finalize(
            public={"reply_text": "اللون أحمر متاح", "products": [], "follow_up_suggestions": [], "intent": "detail"},
            session={"focus_product_ids": [10307], "last_filters": None, "conversation_summary": "Confirmed red color in stock"},
        )], finish_reason="tool_calls", usage={},
    ))
    req2 = AgentQueryRequest(session_id="20100", user_message="الأول بالأحمر متاح؟", locale="ar")
    existing2 = await sessions.load("20100")
    ctx2 = _to_context(existing2)
    resp2, _ = await orch.handle(req2, session_context=ctx2)

    assert captured_context[1] is not None
    assert captured_context[1]["focus_product_ids"] == [10307]
    assert "Zamalek" in captured_context[1]["conversation_summary"]


def _to_context(row: SessionRow | None) -> dict | None:
    if row is None:
        return None
    return {
        "focus_product_ids": row.focus_product_ids,
        "conversation_summary": row.conversation_summary,
        "last_filters": row.last_filters,
    }


def _row_from_state(sid, locale, state, locale_for_new):
    return SessionRow(
        session_id=sid, locale=locale or locale_for_new,
        focus_product_ids=state.focus_product_ids,
        last_filters=state.last_filters,
        conversation_summary=state.conversation_summary,
    )
```

- [ ] **Step 2: Modify `deps.py` to expose the session repo**

Append to `src/curva_agent/deps.py`:
```python
from curva_agent.supabase_client.sessions import SessionRepository


async def get_session_repo() -> SessionRepository:
    client = await get_supabase_client()
    return SessionRepository(client)
```

- [ ] **Step 3: Update the `/agent/query` handler to load + save sessions**

Modify `src/curva_agent/main.py` — replace the existing `agent_query` handler:
```python
from curva_agent.deps import get_orchestrator, get_session_repo
from curva_agent.supabase_client.sessions import SessionRepository, SessionRow


@app.post(
    "/agent/query",
    response_model=AgentQueryResponse,
    dependencies=[Depends(require_api_key)],
)
async def agent_query(
    req: AgentQueryRequest,
    orch: Orchestrator = Depends(get_orchestrator),
    sessions: SessionRepository = Depends(get_session_repo),
) -> AgentQueryResponse:
    log = get_logger("agent_query").bind(session_id=req.session_id, locale=req.locale)
    log.info("turn_started", message_len=len(req.user_message))

    existing = await sessions.load(req.session_id)
    session_context = None
    if existing is not None:
        session_context = {
            "focus_product_ids": existing.focus_product_ids,
            "conversation_summary": existing.conversation_summary,
            "last_filters": existing.last_filters,
        }

    response, next_state = await orch.handle(req, session_context=session_context)

    await sessions.save(SessionRow(
        session_id=req.session_id,
        locale=req.locale,
        customer_name=(req.metadata.customer_name if req.metadata else None),
        focus_product_ids=next_state.focus_product_ids,
        last_filters=next_state.last_filters,
        conversation_summary=next_state.conversation_summary,
    ))

    log.info(
        "turn_finished",
        intent=response.intent,
        tool_calls=response.diagnostics.tool_calls if response.diagnostics else 0,
        latency_ms=response.diagnostics.latency_ms if response.diagnostics else 0,
    )
    return response
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_session_flow.py tests/integration/test_agent_query.py -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/curva_agent/deps.py src/curva_agent/main.py tests/integration/test_session_flow.py
git commit -m "feat(session): per-phone session memory with focus + summary carry-over"
```

---

## Phase 9 — Operational Logging

### Task 27: `agent_logs` migration

**Files:**
- Create: `supabase/migrations/20260511000005_agent_logs.sql`

- [ ] **Step 1: Create migration**

`supabase/migrations/20260511000005_agent_logs.sql`:
```sql
create table if not exists agent_logs (
  id                bigserial primary key,
  session_id        text not null,
  user_message      text not null,
  reply_text        text,
  intent            text,
  tool_calls        jsonb,
  product_ids       int[],
  model             text,
  prompt_tokens     int,
  completion_tokens int,
  cached_tokens     int,
  latency_ms        int,
  ok                boolean not null,
  error             text,
  created_at        timestamptz not null default now()
);

create index if not exists agent_logs_session_created_idx
  on agent_logs(session_id, created_at desc);
create index if not exists agent_logs_created_idx
  on agent_logs(created_at desc);
create index if not exists agent_logs_failures_idx
  on agent_logs(created_at desc) where ok = false;
```

- [ ] **Step 2: Apply**

Run: `npx supabase db reset`
Expected: clean migration.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260511000005_agent_logs.sql
git commit -m "feat(db): agent_logs table with per-turn observability"
```

---

### Task 28: Logs repository + write integration

**Files:**
- Create: `src/curva_agent/supabase_client/logs.py`
- Create: `tests/unit/test_logs_repo.py`
- Modify: `src/curva_agent/main.py`
- Modify: `src/curva_agent/deps.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_logs_repo.py`:
```python
from typing import Any
import pytest
from curva_agent.supabase_client.logs import AgentLogsRepository, AgentLogRow


class StubTable:
    def __init__(self, store: dict, name: str):
        self.store = store
        self.name = name

    def insert(self, payload: dict):
        self._payload = payload
        return self

    async def execute(self):
        self.store.setdefault(self.name, []).append(self._payload)
        return type("R", (), {"data": [self._payload]})()


class StubSupabase:
    def __init__(self):
        self.store: dict[str, list[dict[str, Any]]] = {}

    def table(self, name: str) -> StubTable:
        return StubTable(self.store, name)


@pytest.mark.asyncio
async def test_write_log_row_inserts_into_table():
    sup = StubSupabase()
    repo = AgentLogsRepository(sup)
    await repo.write(AgentLogRow(
        session_id="20100",
        user_message="hi",
        reply_text="hello",
        intent="smalltalk",
        tool_calls=[{"name": "echo", "ok": True}],
        product_ids=[10307],
        model="anthropic/claude-sonnet-4.6",
        prompt_tokens=100, completion_tokens=20, cached_tokens=50,
        latency_ms=1200, ok=True, error=None,
    ))
    rows = sup.store["agent_logs"]
    assert len(rows) == 1
    assert rows[0]["session_id"] == "20100"
    assert rows[0]["tool_calls"][0]["name"] == "echo"
    assert rows[0]["ok"] is True
```

- [ ] **Step 2: Implement logs repository**

`src/curva_agent/supabase_client/logs.py`:
```python
"""Append-only operational log of every agent turn."""
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass
class AgentLogRow:
    session_id: str
    user_message: str
    reply_text: str | None
    intent: str | None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    product_ids: list[int] = field(default_factory=list)
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    latency_ms: int = 0
    ok: bool = True
    error: str | None = None


class _SupabaseLike(Protocol):
    def table(self, name: str) -> Any: ...


class AgentLogsRepository:
    TABLE = "agent_logs"

    def __init__(self, client: _SupabaseLike) -> None:
        self._c = client

    async def write(self, row: AgentLogRow) -> None:
        await self._c.table(self.TABLE).insert(asdict(row)).execute()
```

- [ ] **Step 3: Wire logs in `deps.py`**

Append:
```python
from curva_agent.supabase_client.logs import AgentLogsRepository


async def get_logs_repo() -> AgentLogsRepository:
    client = await get_supabase_client()
    return AgentLogsRepository(client)
```

- [ ] **Step 4: Update `/agent/query` to write a log row per turn**

Modify `src/curva_agent/main.py` — `agent_query` becomes:
```python
import time
from curva_agent.deps import get_logs_repo
from curva_agent.supabase_client.logs import AgentLogRow, AgentLogsRepository


@app.post(
    "/agent/query",
    response_model=AgentQueryResponse,
    dependencies=[Depends(require_api_key)],
)
async def agent_query(
    req: AgentQueryRequest,
    orch: Orchestrator = Depends(get_orchestrator),
    sessions: SessionRepository = Depends(get_session_repo),
    logs: AgentLogsRepository = Depends(get_logs_repo),
) -> AgentQueryResponse:
    log = get_logger("agent_query").bind(session_id=req.session_id, locale=req.locale)
    log.info("turn_started", message_len=len(req.user_message))
    started = time.perf_counter()
    ok = True
    error: str | None = None
    response: AgentQueryResponse | None = None
    next_state = None
    try:
        existing = await sessions.load(req.session_id)
        session_context = None
        if existing is not None:
            session_context = {
                "focus_product_ids": existing.focus_product_ids,
                "conversation_summary": existing.conversation_summary,
                "last_filters": existing.last_filters,
            }
        response, next_state = await orch.handle(req, session_context=session_context)
        await sessions.save(SessionRow(
            session_id=req.session_id,
            locale=req.locale,
            customer_name=(req.metadata.customer_name if req.metadata else None),
            focus_product_ids=next_state.focus_product_ids,
            last_filters=next_state.last_filters,
            conversation_summary=next_state.conversation_summary,
        ))
    except Exception as e:  # noqa: BLE001
        ok = False
        error = f"{type(e).__name__}: {e}"
        log.exception("turn_failed")
        raise
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            d = response.diagnostics if response and response.diagnostics else None
            await logs.write(AgentLogRow(
                session_id=req.session_id,
                user_message=req.user_message,
                reply_text=(response.reply_text if response else None),
                intent=(response.intent if response else None),
                tool_calls=(d.tool_calls_detail if d else []),
                product_ids=[p.id for p in (response.products if response else [])],
                model=(d.model if d else None),
                prompt_tokens=(d.prompt_tokens if d else 0),
                completion_tokens=(d.completion_tokens if d else 0),
                cached_tokens=(d.cached_tokens if d else 0),
                latency_ms=latency_ms,
                ok=ok,
                error=error,
            ))
        except Exception as logerr:  # noqa: BLE001
            log.warning("log_write_failed", error=str(logerr))

    log.info(
        "turn_finished",
        intent=response.intent if response else None,
        tool_calls=response.diagnostics.tool_calls if response and response.diagnostics else 0,
        latency_ms=latency_ms,
    )
    return response  # type: ignore[return-value]
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/ -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/curva_agent/supabase_client/logs.py src/curva_agent/deps.py src/curva_agent/main.py tests/unit/test_logs_repo.py
git commit -m "feat(observability): write agent_logs row per turn"
```

---

## Phase 10 — Hardening

### Task 29: Per-session in-memory rate limiter

**Files:**
- Create: `src/curva_agent/observability/rate_limit.py`
- Create: `tests/unit/test_rate_limit.py`
- Modify: `src/curva_agent/main.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_rate_limit.py`:
```python
import asyncio
import pytest
from curva_agent.observability.rate_limit import SlidingWindowRateLimiter


@pytest.mark.asyncio
async def test_allows_up_to_limit_then_blocks():
    rl = SlidingWindowRateLimiter(max_events=3, window_seconds=60)
    assert await rl.try_acquire("k") is True
    assert await rl.try_acquire("k") is True
    assert await rl.try_acquire("k") is True
    assert await rl.try_acquire("k") is False


@pytest.mark.asyncio
async def test_isolated_per_key():
    rl = SlidingWindowRateLimiter(max_events=1, window_seconds=60)
    assert await rl.try_acquire("a") is True
    assert await rl.try_acquire("b") is True


@pytest.mark.asyncio
async def test_window_slides_to_allow_new_events():
    rl = SlidingWindowRateLimiter(max_events=2, window_seconds=0.1)
    assert await rl.try_acquire("k") is True
    assert await rl.try_acquire("k") is True
    assert await rl.try_acquire("k") is False
    await asyncio.sleep(0.12)
    assert await rl.try_acquire("k") is True
```

- [ ] **Step 2: Implement rate limiter**

`src/curva_agent/observability/rate_limit.py`:
```python
"""Sliding-window per-key rate limiter (in-memory).

Suitable for single-container deployments. If we scale beyond one replica, swap
this for a Redis-backed implementation — interface stays the same.
"""
import asyncio
import time
from collections import deque


class SlidingWindowRateLimiter:
    def __init__(self, *, max_events: int, window_seconds: float) -> None:
        self._max = max_events
        self._window = window_seconds
        self._events: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def try_acquire(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            buf = self._events.setdefault(key, deque())
            cutoff = now - self._window
            while buf and buf[0] < cutoff:
                buf.popleft()
            if len(buf) >= self._max:
                return False
            buf.append(now)
            return True
```

- [ ] **Step 3: Apply to `/agent/query`**

Modify `src/curva_agent/main.py` — add a module-level limiter and a check:
```python
from curva_agent.observability.rate_limit import SlidingWindowRateLimiter

_session_limiter: SlidingWindowRateLimiter | None = None


def _get_session_limiter() -> SlidingWindowRateLimiter:
    global _session_limiter
    if _session_limiter is None:
        s = get_settings()
        _session_limiter = SlidingWindowRateLimiter(
            max_events=s.session_rate_limit_per_min, window_seconds=60.0
        )
    return _session_limiter
```

Then inside `agent_query` (at the top, after `log = ...`):
```python
    if not await _get_session_limiter().try_acquire(req.session_id):
        log.warning("session_rate_limited")
        raise HTTPException(status_code=429, detail="too many turns; slow down")
```

Add the import: `from fastapi import HTTPException`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_rate_limit.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/curva_agent/observability/rate_limit.py src/curva_agent/main.py tests/unit/test_rate_limit.py
git commit -m "feat(hardening): per-session sliding-window rate limit"
```

---

### Task 30: Supabase RLS policies

**Files:**
- Create: `supabase/migrations/20260511000006_rls_policies.sql`

- [ ] **Step 1: Create migration**

`supabase/migrations/20260511000006_rls_policies.sql`:
```sql
-- Lock down all tables to service role only. The agent service uses the
-- service role key; nothing else should read or write.

alter table agent_sessions enable row level security;
alter table agent_logs enable row level security;
alter table taxonomy_sync_runs enable row level security;
alter table categories enable row level security;
alter table subcategories enable row level security;
alter table clubs enable row level security;
alter table brands enable row level security;
alter table seasons enable row level security;
alter table branches enable row level security;

-- Service-role-only policies (deny by default; service role bypasses RLS,
-- but we explicitly add the policy for clarity and forward-compat).
do $$ declare t text;
begin
  for t in select unnest(array[
    'agent_sessions','agent_logs','taxonomy_sync_runs',
    'categories','subcategories','clubs','brands','seasons','branches'
  ]) loop
    execute format(
      'create policy %I on %I for all using (auth.role() = ''service_role'') with check (auth.role() = ''service_role'')',
      t || '_service_role_only', t
    );
  end loop;
end$$;
```

- [ ] **Step 2: Apply locally**

Run:
```bash
npx supabase db reset
psql "postgresql://postgres:postgres@localhost:54322/postgres" -c "select tablename, rowsecurity from pg_tables where schemaname='public'"
```
Expected: all listed tables show `rowsecurity = t`.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260511000006_rls_policies.sql
git commit -m "feat(security): enable RLS service-role-only on all tables"
```

---

### Task 31: Future-embedding tables (reserved) + README + n8n integration docs

**Files:**
- Create: `supabase/migrations/20260511000007_future_embeddings.sql`
- Create: `README.md`
- Create: `docs/n8n-integration.md`

- [ ] **Step 1: Reserved embedding tables migration**

`supabase/migrations/20260511000007_future_embeddings.sql`:
```sql
-- Reserved for future use. Populated when vector text search or SigLip2 image
-- search is added. Empty for now — schema only.

create extension if not exists vector;

create table if not exists product_embeddings (
  product_id  int primary key,
  embedding   vector(1024),
  name_concat text,
  updated_at  timestamptz default now()
);

create table if not exists product_image_embeddings (
  image_id    int primary key,
  product_id  int not null,
  embedding   vector(768),
  image_url   text not null,
  updated_at  timestamptz default now()
);
create index if not exists product_image_embeddings_product_idx
  on product_image_embeddings(product_id);
```

- [ ] **Step 2: README**

`README.md`:
```markdown
# Curva CS Agent

WhatsApp customer service agent for [curvaegypt.com](https://curvaegypt.com).
Single FastAPI endpoint backed by Claude Sonnet 4.6 (via OpenRouter), Supabase,
and live upstream Curva API calls.

## Quick start

1. Copy `.env.example` → `.env` and fill in keys.
2. Start Supabase locally: `npx supabase start`
3. Apply migrations: `npx supabase db reset`
4. Run: `uvicorn curva_agent.main:app --reload --port 8000`
5. Seed taxonomy: `curl -sX POST -H "X-API-Key: $AGENT_API_KEY" http://localhost:8000/admin/sync-taxonomy`

## Endpoints

- `POST /agent/query` — primary agent endpoint (auth: `X-API-Key`)
- `POST /admin/sync-taxonomy` — manual taxonomy refresh (auth: `X-API-Key`)
- `GET /healthz` — liveness

## Tests

```bash
pytest -v
```

## Deploy

Single container. See `Dockerfile`. Deploy to Cloud Run or Fly.io. Required env
vars are in `.env.example`.

## Architecture

See [docs/superpowers/specs/2026-05-11-curva-cs-agent-design.md](docs/superpowers/specs/2026-05-11-curva-cs-agent-design.md).
```

- [ ] **Step 3: n8n integration guide**

`docs/n8n-integration.md`:
```markdown
# n8n Integration Guide

The Curva CS Agent exposes ONE endpoint that n8n calls for every incoming
WhatsApp message.

## Request

```http
POST {AGENT_URL}/agent/query
X-API-Key: {AGENT_API_KEY}
Content-Type: application/json

{
  "session_id": "{{ $json.from }}",
  "user_message": "{{ $json.text }}",
  "locale": "ar",
  "conversation_history": [],
  "metadata": {
    "customer_name": "{{ $json.profile.name }}",
    "customer_phone": "{{ $json.from }}",
    "channel": "whatsapp"
  }
}
```

## Response

```json
{
  "reply_text": "string — render as WhatsApp text message",
  "products": [{ "id": ..., "primary_image": "url", "images": [...], ... }],
  "follow_up_suggestions": ["string", "string"],
  "intent": "search | detail | availability | order_intent | smalltalk | handoff | clarification",
  "diagnostics": { ... }
}
```

## Rendering products

For each product in `products`:
1. Send `primary_image` as a WhatsApp media message with a short caption
   (name + price).
2. Optionally send 2–3 more images from `images` for the same product.

For each `follow_up_suggestion`, render as a WhatsApp quick-reply button.

## Intent routing

- `order_intent` — route the conversation context to the CRM workflow.
- `handoff` — escalate to a human CS rep (notify ops channel).
- All other intents — just reply.

## Error handling

- `401` — bad/missing API key. Check `X-API-Key` header.
- `429` — session rate-limited (>30 turns/minute). Throttle in n8n.
- `5xx` — service issue. Fall back to a static "I'll get a human" message.
```

- [ ] **Step 4: Apply migration**

Run: `npx supabase db reset`

- [ ] **Step 5: Final test sweep**

Run: `pytest -v`
Expected: all green.

- [ ] **Step 6: Final commit**

```bash
git add supabase/migrations/20260511000007_future_embeddings.sql README.md docs/n8n-integration.md
git commit -m "docs: README + n8n integration guide; reserve embedding tables"
```

---

## Done

The plan covers all 7 spec phases across 31 tasks. Each task ends in a green test sweep and a commit. Subagent-Driven execution is recommended for the long tail of tool/orchestrator tasks (Phases 4-8).








