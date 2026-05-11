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