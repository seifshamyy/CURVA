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