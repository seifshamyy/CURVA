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