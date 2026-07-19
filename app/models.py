from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    providers: Optional[List[str]] = None


class SearchResult(BaseModel):
    provider: str
    id: str
    title: str
    url: str
    snippet: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    failed_providers: List[str] = Field(default_factory=list)


class AuthContext(BaseModel):
    sub: Optional[str] = None
    groups: List[str] = Field(default_factory=list)
    department: Optional[str] = None
    region: Optional[str] = None
    position: Optional[str] = None
    manager_id: Optional[str] = None


class ACLCheckRequest(BaseModel):
    principal: str = Field(min_length=1)
    providers: Optional[List[str]] = None
    query_length: int = Field(default=1, ge=0, le=500)
    sub: Optional[str] = None
    groups: Optional[List[str]] = None
    department: Optional[str] = None
    region: Optional[str] = None
    position: Optional[str] = None
    manager_id: Optional[str] = None


class ACLCheckResponse(BaseModel):
    allowed: bool
    principal: str
    allowed_providers: List[str] = Field(default_factory=list)
    matched_groups: List[str] = Field(default_factory=list)
    effective_max_query_length: int
    effective_max_results_per_provider: int
    denied_providers: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class ETLRunRequest(BaseModel):
    systems: Optional[List[str]] = None
    dry_run: bool = False


class ETLSystemResultResponse(BaseModel):
    system: str
    extracted_records: int
    transformed_documents: int
    loaded_documents: int


class ETLRunResponse(BaseModel):
    status: str = "ok"
    dry_run: bool
    systems: List[ETLSystemResultResponse] = Field(default_factory=list)
