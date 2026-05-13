"""Verify the FastAPI lifespan closes shared HTTP clients on shutdown."""
from unittest.mock import AsyncMock
import pytest
from curva_agent import deps
from curva_agent.main import app, lifespan


@pytest.mark.asyncio
async def test_lifespan_closes_curva_and_llm_clients():
    deps.reset_singletons_for_tests()
    fake_curva = AsyncMock()
    fake_llm = AsyncMock()
    deps._curva_client = fake_curva
    deps._llm = fake_llm
    try:
        async with lifespan(app):
            pass
        fake_curva.aclose.assert_awaited_once()
        fake_llm.aclose.assert_awaited_once()
        assert deps._curva_client is None
        assert deps._llm is None
    finally:
        deps.reset_singletons_for_tests()


@pytest.mark.asyncio
async def test_lifespan_shutdown_is_safe_when_no_singletons_initialized():
    deps.reset_singletons_for_tests()
    try:
        async with lifespan(app):
            pass
    finally:
        deps.reset_singletons_for_tests()
