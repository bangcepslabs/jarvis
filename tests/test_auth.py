from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_health_remains_public_when_auth_enabled(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "client_token", "test-token")
    assert TestClient(app).get("/health").status_code == 200


def test_client_routes_require_valid_bearer_token(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "client_token", "test-token")
    client = TestClient(app)

    assert client.post("/api/chat", json={"message": "hello"}).status_code == 401
    assert client.post("/api/chat", headers={"Authorization": "Bearer wrong"}, json={"message": "hello"}).status_code == 401
    assert client.post("/api/chat", headers={"Authorization": "Bearer test-token"}, json={"message": "hello"}).status_code != 401


def test_auth_disabled_preserves_local_development_behavior(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "client_token", None)
    assert TestClient(app).post("/api/chat", json={"message": "hello"}).status_code != 401
