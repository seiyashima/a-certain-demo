from fastapi.testclient import TestClient

from app.main import app


def test_root_returns_landing_page():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "a-certain-demo" in response.text
    assert "/healthz" in response.text
    assert "/mock" in response.text


def test_runtime_metadata_returns_ok():
    client = TestClient(app)

    response = client.get("/api/runtime")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "service" in body
    assert "uptime_ms" in body


def test_mock_entrypoint_returns_landing_page():
    client = TestClient(app)

    response = client.get("/mock")

    assert response.status_code == 200
    assert "Gemini Enterprise" in response.text
    assert "Cloud Runステータスチェック" in response.text


def test_demo_config_exposes_expected_test_users():
    client = TestClient(app)

    response = client.get("/api/demo/config")

    assert response.status_code == 200
    body = response.json()
    profile_ids = {profile["id"] for profile in body["profiles"]}
    assert {
        "trader-jp",
        "investment-banking-jp",
        "compliance-officer",
        "hr-manager-jp",
        "it-support",
        "eu-privacy",
    }.issubset(profile_ids)


def test_demo_source_sample_catalog_contains_five_systems():
    client = TestClient(app)

    response = client.get("/api/demo/source-samples")

    assert response.status_code == 200
    body = response.json()
    systems = {item["system"] for item in body["systems"]}
    assert systems == {"servicenow", "workday", "compliance-system", "sharepoint", "confluence"}


def test_demo_source_sample_detail_returns_json_payload():
    client = TestClient(app)

    response = client.get("/api/demo/source-samples/confluence")

    assert response.status_code == 200
    body = response.json()
    assert body["system"] == "confluence"
    assert "sample" in body
    assert "sample_pretty_json" in body


def test_demo_mock_chat_can_retrieve_confluence_document_for_it_support():
    client = TestClient(app)

    response = client.post(
        "/api/demo/mock/chat",
        json={
            "profile_id": "it-support",
            "query": "Find the search gateway runbook",
            "target_system": "confluence",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert any(item["source"] == "confluence" for item in body["citations"])
    assert any(item["system"] == "confluence" for item in body["source_samples"])


def test_demo_mock_chat_honors_multiple_selected_connectors():
    client = TestClient(app)

    response = client.post(
        "/api/demo/mock/chat",
        json={
            "profile_id": "it-support",
            "query": "Find the search gateway runbook and password reset",
            "target_systems": ["confluence", "servicenow"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["target_systems"] == ["confluence", "servicenow"]
    cited_sources = {item["source"] for item in body["citations"]}
    assert "confluence" in cited_sources or "servicenow" in cited_sources
    linked_systems = {item["system"] for item in body["source_samples"]}
    assert linked_systems == {"confluence", "servicenow"}
