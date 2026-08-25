from fastapi.testclient import TestClient

from app.main import app


def test_chat_returns_mock_reply() -> None:
    response = TestClient(app).post("/api/chat", json={"message": "안녕 자비스"})
    assert response.status_code == 200
    assert response.json()["reply"]
    assert response.json()["tool_calls"] == []


def test_chat_returns_time_tool_metadata() -> None:
    response = TestClient(app).post("/api/chat", json={"message": "\ud604\uc7ac \uc2dc\uac04 \uc54c\ub824\uc918"})
    assert response.status_code == 200
    assert response.json()["tool_calls"] == [{"name": "get_current_time", "success": True}]
