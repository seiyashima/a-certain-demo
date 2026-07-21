from fastapi.testclient import TestClient

from app.main import app


def test_root_returns_landing_page():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "a-certain-demo" in response.text
    assert "/healthz" in response.text
