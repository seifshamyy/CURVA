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