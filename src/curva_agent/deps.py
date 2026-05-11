"""FastAPI dependency providers."""
from collections.abc import AsyncIterator
from fastapi import Depends, Header, HTTPException, status
from curva_agent.cache.lru import AsyncTTLCache
from curva_agent.config import Settings, get_settings
from curva_agent.curva_client.client import CurvaClient
from curva_agent.llm.client import LLMClient
from curva_agent.orchestrator.orchestrator import Orchestrator
from curva_agent.supabase_client.client import get_supabase_client
from curva_agent.supabase_client.logs import AgentLogsRepository
from curva_agent.supabase_client.sessions import SessionRepository
from curva_agent.supabase_client.taxonomy import TaxonomyRepository, TaxonomySnapshot
from curva_agent.tools.base import Tool
from curva_agent.tools.get_offers import GetOffersTool
from curva_agent.tools.get_product import GetProductTool
from curva_agent.tools.list_branches import ListBranchesTool
from curva_agent.tools.product_synthesizer import ProductSynthesizerTool
from curva_agent.tools.search_products import SearchProductsTool


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


async def get_session_repo() -> SessionRepository:
    client = await get_supabase_client()
    return SessionRepository(client)


async def get_logs_repo() -> AgentLogsRepository:
    client = await get_supabase_client()
    return AgentLogsRepository(client)


def reset_singletons_for_tests() -> None:
    global _curva_client, _caches, _tools_by_name, _llm
    _curva_client = None
    _caches = {}
    _tools_by_name = None
    _llm = None