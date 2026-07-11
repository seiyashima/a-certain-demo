import asyncio
import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status

from app.config import Settings, get_settings
from app.connectors import SaaSSearchConnector, build_connectors
from app.models import SearchRequest, SearchResponse, SearchResult

logger = logging.getLogger(__name__)
app = FastAPI(title="Federated SaaS Search API")


def get_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> str:
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")
    return x_api_key


def get_connectors(settings: Settings = Depends(get_settings)) -> list[SaaSSearchConnector]:
    return build_connectors(settings.providers, settings.request_timeout_seconds)


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    _: str = Depends(get_api_key),
    settings: Settings = Depends(get_settings),
    connectors: list[SaaSSearchConnector] = Depends(get_connectors),
) -> SearchResponse:
    query = payload.query.strip()
    if len(query) > settings.max_query_length:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"query must be <= {settings.max_query_length} characters",
        )

    selected_providers = set(payload.providers or [])
    active_connectors = [
        connector
        for connector in connectors
        if not selected_providers or connector.provider.name in selected_providers
    ]
    if not active_connectors:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no providers matched")

    results = await asyncio.gather(
        *[connector.search(query, settings.max_results_per_provider) for connector in active_connectors],
        return_exceptions=True,
    )

    merged_results: list[SearchResult] = []
    failed_providers: list[str] = []
    for connector, result in zip(active_connectors, results, strict=True):
        if isinstance(result, Exception):
            failed_providers.append(connector.provider.name)
            logger.warning("provider search failed", extra={"provider": connector.provider.name})
            continue
        merged_results.extend(result)

    if failed_providers and not merged_results:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"all providers failed: {', '.join(failed_providers)}",
        )

    return SearchResponse(query=query, results=merged_results)
