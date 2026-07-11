from typing import Any, Iterable, List

import httpx

from app.config import SaaSProvider
from app.models import SearchResult


class SaaSSearchConnector:
    def __init__(self, provider: SaaSProvider, timeout: float) -> None:
        self.provider = provider
        self.timeout = timeout

    async def search(self, query: str, limit: int) -> List[SearchResult]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.provider.base_url}{self.provider.search_path}",
                params={"q": query, "limit": min(limit, self.provider.result_limit)},
                headers={"Authorization": f"******"},
            )
            response.raise_for_status()
            payload = response.json()
        items = payload.get("items", [])
        return [self._normalize(item) for item in items]

    def _normalize(self, item: dict[str, Any]) -> SearchResult:
        return SearchResult(
            provider=self.provider.name,
            id=str(item.get("id", "")),
            title=str(item.get("title", "")),
            url=str(item.get("url", "")),
            snippet=item.get("snippet"),
            metadata={
                key: value
                for key, value in item.items()
                if key not in {"id", "title", "url", "snippet"}
            },
        )


def build_connectors(providers: Iterable[SaaSProvider], timeout: float) -> list[SaaSSearchConnector]:
    return [SaaSSearchConnector(provider=provider, timeout=timeout) for provider in providers]
