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
    fake_result = type("R", (), {"ok": True, "counts": {"clubs": 4, "brands": 4}, "error": None})()
    with patch("curva_agent.main.sync_taxonomy", new=AsyncMock(return_value=fake_result)) as mock_sync, \
         patch("curva_agent.main.get_curva_client") as mock_curva, \
         patch("curva_agent.main.get_taxonomy_repo") as mock_repo:
        mock_curva.return_value = AsyncMock(aclose=AsyncMock())
        mock_repo.return_value = AsyncMock()
        client = TestClient(app)
        r = client.post("/admin/sync-taxonomy", headers={"X-API-Key": "test-agent-key"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["counts"]["clubs"] == 4
    mock_sync.assert_awaited_once()