from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app, get_connectors
from app.models import SearchResult


class StubConnector:
    def __init__(self, name: str, results: list[SearchResult]) -> None:
        self.provider = type("Provider", (), {"name": name})()
        self._results = results

    async def search(self, query: str, limit: int) -> list[SearchResult]:
        assert query == "customer escalation"
        assert limit == 3
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
    }


def test_search_rejects_too_long_queries() -> None:
    client = create_client()

    response = client.post(
        "/search",
        headers={"x-api-key": "1234567890abcdef"},
        json={"query": "x" * 121},
    )

    assert response.status_code == 422
