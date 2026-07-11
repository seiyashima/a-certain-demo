from app import create_app
from fastapi.testclient import TestClient


def test_healthz_returns_ok():
    app = create_app()
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_rejects_empty_message():
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "message is required"


def test_chat_returns_echo_reply():
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Echo: hello"
    assert "request_id" in body
    assert "elapsed_ms" in body


def test_runtime_endpoint_returns_metadata():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/runtime")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "service" in body
    assert "revision" in body
    assert "project" in body
    assert "environment" in body
    assert "demo_mode" in body
    assert "uptime_ms" in body
