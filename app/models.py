from typing import Any, List

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    providers: List[str] | None = None


class SearchResult(BaseModel):
    provider: str
    id: str
    title: str
    url: str
    snippet: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
