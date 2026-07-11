from app import create_app
from fastapi.testclient import TestClient


def test_healthz_returns_ok():
    app = create_app()
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_rejects_empty_query():
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/search", json={"subject": "admin-user", "query": "   ", "target_system": "all"})

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "subject and query are required"


def test_search_returns_routed_results_for_admin_subject():
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/search", json={"subject": "admin-user", "query": "runbook policy incident", "target_system": "all"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["target_system"] == "all"
    assert len(body["results"]) == 5
    assert any(result["key"] == "confluence" for result in body["results"])
    assert "request_id" in body
    assert "elapsed_ms" in body


def test_search_denies_unauthorized_target():
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/search", json={"subject": "guest-user", "query": "payroll", "target_system": "workday"})

    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "access denied"
    assert body["denied_targets"] == ["workday"]


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
    assert body["connector_count"] == 5
    assert "uptime_ms" in body


def test_connectors_endpoint_returns_catalog():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/connectors")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert len(body["connectors"]) == 5
