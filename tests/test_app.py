from app import create_app


def test_healthz_returns_ok():
    app = create_app()
    app.testing = True
    client = app.test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_chat_rejects_empty_message():
    app = create_app()
    app.testing = True
    client = app.test_client()

    response = client.post("/api/chat", json={"message": "   "})

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "message is required"


def test_chat_returns_echo_reply():
    app = create_app()
    app.testing = True
    client = app.test_client()

    response = client.post("/api/chat", json={"message": "hello"})

    assert response.status_code == 200
    body = response.get_json()
    assert body["reply"] == "Echo: hello"
    assert "request_id" in body
    assert "elapsed_ms" in body
