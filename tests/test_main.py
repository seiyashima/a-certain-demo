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
    assert "ログインユーザ" in response.text


def test_demo_config_exposes_expected_test_users():
    client = TestClient(app)

    response = client.get("/api/demo/config")

    assert response.status_code == 200
    body = response.json()
    profile_ids = {profile["id"] for profile in body["profiles"]}
    assert {
        "john-smith",
        "carol-tanaka",
        "david-lee",
        "emma-sato",
        "ryo-kobayashi",
        "ken-ito",
        "sophie-dupont",
    }.issubset(profile_ids)


def test_hr_manager_answer_contains_approval_detail_for_termination_question():
    client = TestClient(app)

    response = client.post(
        "/api/demo/mock/chat",
        json={
            "profile_id": "carol-tanaka",
            "query": "Who approved the termination process for John Smith?",
            "target_system": "workday",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "David Lee" in body["reply"]
    assert "Carol Tanaka" in body["reply"]
    assert any(item["id"] == "wd-hr-5501" for item in body["citations"])


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
            "profile_id": "ken-ito",
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
            "profile_id": "ken-ito",
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


def test_john_smith_cannot_read_john_smith_hr_documents():
    client = TestClient(app)

    response = client.post(
        "/api/demo/mock/chat",
        json={
            "profile_id": "john-smith",
            "query": "Show the performance review for John Smith",
            "target_system": "workday",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert len(body["citations"]) == 0
    assert any(item["id"] == "wd-hr-5502" for item in body["blocked_documents"])
