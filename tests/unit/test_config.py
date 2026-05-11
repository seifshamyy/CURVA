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
    assert s.llm_model == "anthropic/claude-sonnet-4.6"
    assert s.llm_max_tool_iterations == 12
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