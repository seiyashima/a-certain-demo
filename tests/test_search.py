import asyncio

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.config import Settings, get_settings
from app.config import SaaSProvider
from app.connectors import SaaSSearchConnector
from app.main import app, auth_utils, get_connectors
from app.models import AuthContext, SearchResult


class StubConnector:
    def __init__(self, name: str, results: list[SearchResult], expected_limit: int = 3) -> None:
        self.provider = type("Provider", (), {"name": name})()
        self._results = results
        self._expected_limit = expected_limit

    async def search(self, query: str, limit: int) -> list[SearchResult]:
        assert query
        assert limit == self._expected_limit
        return self._results


def create_client() -> TestClient:
    settings = Settings(
        api_key="1234567890abcdef",
        max_results_per_provider=3,
        allowed_provider_hosts="docs.example.com",
        providers=[
            {
                "name": "docs",
                "base_url": "https://docs.example.com",
                "bearer_token": "docs-token",
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_connectors] = lambda: [
        StubConnector(
            "docs",
            [
                SearchResult(
                    provider="docs",
                    id="1",
                    title="Escalation playbook",
                    url="https://docs.example.com/playbook",
                    snippet="How to handle customer escalations.",
                )
            ],
        )
    ]
    return TestClient(app)


def teardown_module() -> None:
    app.dependency_overrides.clear()


def test_search_requires_api_key() -> None:
    client = create_client()

    response = client.post("/search", json={"query": "customer escalation"})

    assert response.status_code == 401


def test_search_returns_federated_results() -> None:
    client = create_client()

    response = client.post(
        "/search",
        headers={"x-api-key": "1234567890abcdef"},
        json={"query": "customer escalation"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "query": "customer escalation",
        "results": [
            {
                "provider": "docs",
                "id": "1",
                "title": "Escalation playbook",
                "url": "https://docs.example.com/playbook",
                "snippet": "How to handle customer escalations.",
                "metadata": {},
            }
        ],
        "failed_providers": [],
    }


def test_search_rejects_too_long_queries() -> None:
    client = create_client()

    response = client.post(
        "/search",
        headers={"x-api-key": "1234567890abcdef"},
        json={"query": "x" * 121},
    )

    assert response.status_code == 422


def test_search_requires_client_id_when_acl_enabled() -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        max_results_per_provider=3,
        allowed_provider_hosts="docs.example.com",
        providers=[
            {
                "name": "docs",
                "base_url": "https://docs.example.com",
                "bearer_token": "docs-token",
            }
        ],
        acl_enabled=True,
        acl_policies=[
            {
                "principal": "web-client",
                "allowed_providers": ["docs"],
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_connectors] = lambda: [
        StubConnector(
            "docs",
            [
                SearchResult(
                    provider="docs",
                    id="1",
                    title="Escalation playbook",
                    url="https://docs.example.com/playbook",
                    snippet="How to handle customer escalations.",
                )
            ],
        )
    ]
    client = TestClient(app)

    response = client.post(
        "/search",
        headers={"x-api-key": "1234567890abcdef"},
        json={"query": "customer escalation"},
    )

    assert response.status_code == 401


def test_search_denies_provider_outside_acl() -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        max_results_per_provider=3,
        allowed_provider_hosts="docs.example.com,tickets.example.com",
        providers=[
            {
                "name": "docs",
                "base_url": "https://docs.example.com",
                "bearer_token": "docs-token",
            },
            {
                "name": "tickets",
                "base_url": "https://tickets.example.com",
                "bearer_token": "tickets-token",
            },
        ],
        acl_enabled=True,
        acl_policies=[
            {
                "principal": "web-client",
                "allowed_providers": ["docs"],
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_connectors] = lambda: [
        StubConnector("docs", []),
        StubConnector("tickets", []),
    ]
    client = TestClient(app)

    response = client.post(
        "/search",
        headers={"x-api-key": "1234567890abcdef", "x-client-id": "web-client"},
        json={"query": "customer escalation", "providers": ["tickets"]},
    )

    assert response.status_code == 403


def test_acl_check_endpoint_reports_acl_limits() -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        max_query_length=120,
        max_results_per_provider=10,
        allowed_provider_hosts="docs.example.com,tickets.example.com",
        providers=[
            {
                "name": "docs",
                "base_url": "https://docs.example.com",
                "bearer_token": "docs-token",
            },
            {
                "name": "tickets",
                "base_url": "https://tickets.example.com",
                "bearer_token": "tickets-token",
            },
        ],
        acl_enabled=True,
        acl_policies=[
            {
                "principal": "web-client",
                "allowed_providers": ["docs"],
                "max_query_length": 80,
                "max_results_per_provider": 5,
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_connectors] = lambda: [
        StubConnector("docs", []),
        StubConnector("tickets", []),
    ]
    client = TestClient(app)

    response = client.post(
        "/acl/check",
        headers={"x-api-key": "1234567890abcdef"},
        json={
            "principal": "web-client",
            "providers": ["docs", "tickets"],
            "query_length": 90,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "allowed": False,
        "principal": "web-client",
        "allowed_providers": ["docs"],
        "matched_groups": [],
        "effective_max_query_length": 80,
        "effective_max_results_per_provider": 5,
        "denied_providers": ["tickets"],
        "reasons": [
            "providers not allowed by ACL: tickets",
            "query length exceeds ACL limit (80)",
        ],
    }


def test_search_denies_department_region_and_position_outside_acl() -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        max_results_per_provider=3,
        allowed_provider_hosts="docs.example.com",
        providers=[
            {
                "name": "docs",
                "base_url": "https://docs.example.com",
                "bearer_token": "docs-token",
            }
        ],
        acl_enabled=True,
        acl_policies=[
            {
                "principal": "hr-client",
                "allowed_providers": ["docs"],
                "allowed_departments": ["hr"],
                "allowed_regions": ["emea"],
                "allowed_positions": ["manager"],
                "require_manager": True,
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_connectors] = lambda: [StubConnector("docs", [])]
    client = TestClient(app)

    response = client.post(
        "/search",
        headers={
            "x-api-key": "1234567890abcdef",
            "x-client-id": "hr-client",
            "x-user-department": "trading",
            "x-user-region": "apac",
            "x-user-position": "individual-contributor",
        },
        json={"query": "termination process"},
    )

    assert response.status_code == 403
    assert "department not allowed by ACL" in response.json()["detail"]


def test_search_allows_abac_matched_context() -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        max_results_per_provider=3,
        allowed_provider_hosts="docs.example.com",
        providers=[
            {
                "name": "docs",
                "base_url": "https://docs.example.com",
                "bearer_token": "docs-token",
            }
        ],
        acl_enabled=True,
        acl_policies=[
            {
                "principal": "compliance-client",
                "allowed_providers": ["docs"],
                "allowed_groups": ["compliance-officer", "internal-audit"],
                "allowed_departments": ["compliance"],
                "allowed_regions": ["emea", "apac"],
                "allowed_positions": ["manager", "individual-contributor"],
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_connectors] = lambda: [
        StubConnector(
            "docs",
            [
                SearchResult(
                    provider="docs",
                    id="1",
                    title="Trading violation playbook",
                    url="https://docs.example.com/violations",
                    snippet="Compliance escalation procedure.",
                )
            ],
        )
    ]
    client = TestClient(app)

    response = client.post(
        "/search",
        headers={
            "x-api-key": "1234567890abcdef",
            "x-client-id": "compliance-client",
            "x-user-groups": "compliance-officer,emea-reviewers",
            "x-user-department": "compliance",
            "x-user-region": "emea",
            "x-user-position": "manager",
        },
        json={"query": "trading violations"},
    )

    assert response.status_code == 200


def test_acl_check_endpoint_reports_abac_reasons() -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        max_query_length=120,
        max_results_per_provider=10,
        allowed_provider_hosts="docs.example.com",
        providers=[
            {
                "name": "docs",
                "base_url": "https://docs.example.com",
                "bearer_token": "docs-token",
            }
        ],
        acl_enabled=True,
        acl_policies=[
            {
                "principal": "trader-client",
                "allowed_providers": ["docs"],
                "allowed_groups": ["trader"],
                "allowed_departments": ["markets"],
                "allowed_regions": ["apac"],
                "allowed_positions": ["manager"],
                "require_manager": True,
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_connectors] = lambda: [StubConnector("docs", [])]
    client = TestClient(app)

    response = client.post(
        "/acl/check",
        headers={"x-api-key": "1234567890abcdef"},
        json={
            "principal": "trader-client",
            "providers": ["docs"],
            "query_length": 20,
            "groups": ["guest"],
            "department": "hr",
            "region": "emea",
            "position": "individual-contributor",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "allowed": False,
        "principal": "trader-client",
        "allowed_providers": ["docs"],
        "matched_groups": [],
        "effective_max_query_length": 120,
        "effective_max_results_per_provider": 10,
        "denied_providers": [],
        "reasons": [
            "no required group matched",
            "department not allowed by ACL",
            "region not allowed by ACL",
            "position not allowed by ACL",
            "manager context required by ACL",
        ],
    }


def test_search_filters_results_by_document_region_and_department_metadata() -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        max_results_per_provider=3,
        allowed_provider_hosts="docs.example.com",
        providers=[
            {
                "name": "docs",
                "base_url": "https://docs.example.com",
                "bearer_token": "docs-token",


            }
        ],
        acl_enabled=True,
        acl_policies=[
            {
                "principal": "trader-client",
                "allowed_providers": ["docs"],
                "allowed_groups": ["trader"],
                "allowed_departments": ["markets"],
                "allowed_regions": ["apac"],
                "allowed_positions": ["individual-contributor"],
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_connectors] = lambda: [
        StubConnector(
            "docs",
            [
                SearchResult(
                    provider="docs",
                    id="1",
                    title="APAC Trading Rule",
                    url="https://docs.example.com/apac-rule",
                    metadata={
                        "allowed_groups": ["trader"],
                        "allowed_departments": ["markets"],
                        "allowed_regions": ["apac"],
                    },
                ),
                SearchResult(
                    provider="docs",
                    id="2",
                    title="EMEA HR Policy",
                    url="https://docs.example.com/emea-hr",
                    metadata={
                        "allowed_departments": ["hr"],
                        "allowed_regions": ["emea"],
                    },
                ),
            ],
        )
    ]
    client = TestClient(app)

    response = client.post(
        "/search",
        headers={
            "x-api-key": "1234567890abcdef",
            "x-client-id": "trader-client",
            "x-user-sub": "u-123",
            "x-user-groups": "trader",
            "x-user-department": "markets",
            "x-user-region": "apac",
            "x-user-position": "individual-contributor",
        },
        json={"query": "policy"},
    )

    assert response.status_code == 200
    assert response.json()["results"] == [
        {
            "provider": "docs",
            "id": "1",
            "title": "APAC Trading Rule",
            "url": "https://docs.example.com/apac-rule",
            "snippet": None,
            "metadata": {
                "allowed_groups": ["trader"],
                "allowed_departments": ["markets"],
                "allowed_regions": ["apac"],
            },
        }
    ]


def test_search_filters_results_by_direct_manager_metadata() -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        max_results_per_provider=3,
        allowed_provider_hosts="docs.example.com",
        providers=[
            {
                "name": "docs",
                "base_url": "https://docs.example.com",
                "bearer_token": "docs-token",
            }
        ],
        acl_enabled=True,
        acl_policies=[
            {
                "principal": "hr-client",
                "allowed_providers": ["docs"],
                "allowed_departments": ["hr"],
                "allowed_regions": ["emea"],
                "allowed_positions": ["manager"],
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_connectors] = lambda: [
        StubConnector(
            "docs",
            [
                SearchResult(
                    provider="docs",
                    id="1",
                    title="Termination Process - John Smith",
                    url="https://docs.example.com/john-smith",
                    metadata={"allowed_manager_ids": ["mgr-001"]},
                ),
                SearchResult(
                    provider="docs",
                    id="2",
                    title="Termination Process - Another Employee",
                    url="https://docs.example.com/another-employee",
                    metadata={"allowed_manager_ids": ["mgr-999"]},
                ),
            ],
        )
    ]
    client = TestClient(app)

    response = client.post(
        "/search",
        headers={
            "x-api-key": "1234567890abcdef",
            "x-client-id": "hr-client",
            "x-user-sub": "mgr-001",
            "x-user-department": "hr",
            "x-user-region": "emea",
            "x-user-position": "manager",
        },
        json={"query": "termination process"},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["results"]] == ["1"]


def test_search_uses_okta_bearer_claims_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        okta_auth_enabled=True,
        okta_issuer="https://example.okta.com/oauth2/default",
        okta_audience="api://search",
        max_results_per_provider=3,
        allowed_provider_hosts="docs.example.com",
        providers=[
            {
                "name": "docs",
                "base_url": "https://docs.example.com",
                "bearer_token": "docs-token",
            }
        ],
        acl_enabled=True,
        acl_policies=[
            {
                "principal": "compliance-client",
                "allowed_providers": ["docs"],
                "allowed_groups": ["compliance-officer"],
                "allowed_departments": ["compliance"],
                "allowed_regions": ["emea"],
                "allowed_positions": ["manager"],
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_connectors] = lambda: [
        StubConnector(
            "docs",
            [
                SearchResult(
                    provider="docs",
                    id="1",
                    title="Trading violation playbook",
                    url="https://docs.example.com/violations",
                    snippet="Compliance escalation procedure.",
                )
            ],
        )
    ]

    def fake_decode_okta_access_token(token: str, resolved_settings: Settings) -> AuthContext:
        assert token == "fake-token"
        assert resolved_settings.okta_audience == "api://search"
        return AuthContext(
            sub="user-123",
            groups=["compliance-officer"],
            department="compliance",
            region="emea",
            position="manager",
        )

    monkeypatch.setattr(auth_utils, "decode_okta_access_token", fake_decode_okta_access_token)
    client = TestClient(app)

    response = client.post(
        "/search",
        headers={
            "x-api-key": "1234567890abcdef",
            "x-client-id": "compliance-client",
            "authorization": "Bearer fake-token",
        },
        json={"query": "trading violations"},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == "1"


def test_search_rejects_invalid_okta_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        api_key="1234567890abcdef",
        okta_auth_enabled=True,
        okta_issuer="https://example.okta.com/oauth2/default",
        okta_audience="api://search",
        max_results_per_provider=3,
        allowed_provider_hosts="docs.example.com",
        providers=[
            {
                "name": "docs",
                "base_url": "https://docs.example.com",
                "bearer_token": "docs-token",
            }
        ],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_connectors] = lambda: [StubConnector("docs", [])]

    def fake_decode_okta_access_token(token: str, resolved_settings: Settings) -> AuthContext:
        raise HTTPException(status_code=401, detail="invalid Okta token: bad signature")

    monkeypatch.setattr(auth_utils, "decode_okta_access_token", fake_decode_okta_access_token)
    client = TestClient(app)

    response = client.post(
        "/search",
        headers={
            "x-api-key": "1234567890abcdef",
            "authorization": "Bearer fake-token",
        },
        json={"query": "anything"},
    )

    assert response.status_code == 401


def test_saas_search_connector_uses_configured_bearer_token(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"items": []}

    class _Client:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params=None, headers=None):
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            return _Response()

    monkeypatch.setattr("app.connectors.httpx.AsyncClient", _Client)

    connector = SaaSSearchConnector(
        SaaSProvider(
            name="docs",
            base_url="https://docs.example.com",
            bearer_token="docs-token",
        ),
        timeout=1.0,
    )

    results = asyncio.run(connector.search("hello", 10))

    assert results == []
    assert captured["url"] == "https://docs.example.com/search"
    assert captured["params"] == {"q": "hello", "limit": 10}
    assert captured["headers"] == {"Authorization": "Bearer docs-token"}
