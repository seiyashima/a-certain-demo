from __future__ import annotations

import asyncio
import hmac
import logging
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status

from app import auth as auth_utils
from app.config import ACLPolicy, Settings, get_settings
from app.connectors import SaaSSearchConnector, build_connectors
from app.etl import ETLPipeline, build_etl_pipeline
from app.models import (
    ACLCheckRequest,
    ACLCheckResponse,
    AuthContext,
    ETLRunRequest,
    ETLRunResponse,
    ETLSystemResultResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)

logger = logging.getLogger(__name__)
app = FastAPI(title="Federated SaaS Search API")


def get_api_key(
    x_api_key: Annotated[Optional[str], Header()] = None,
    settings: Settings = Depends(get_settings),
) -> str:
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")
    return x_api_key


def get_connectors(settings: Settings = Depends(get_settings)) -> list[SaaSSearchConnector]:
    return build_connectors(settings.providers, settings.request_timeout_seconds)


def get_etl_pipeline(settings: Settings = Depends(get_settings)) -> ETLPipeline:
    return build_etl_pipeline(settings)


def get_client_id(
    x_client_id: Annotated[Optional[str], Header()] = None,
    settings: Settings = Depends(get_settings),
) -> Optional[str]:
    if settings.acl_enabled and not x_client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing X-Client-Id header for ACL enforcement",
        )
    return x_client_id


def _split_csv_header(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def _normalize_metadata_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip().lower() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        normalized: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip().lower()
            if text:
                normalized.append(text)
        return normalized
    return [str(value).strip().lower()] if str(value).strip() else []


def get_auth_context(
    authorization: Annotated[Optional[str], Header()] = None,
    x_user_sub: Annotated[Optional[str], Header()] = None,
    x_user_groups: Annotated[Optional[str], Header()] = None,
    x_user_department: Annotated[Optional[str], Header()] = None,
    x_user_region: Annotated[Optional[str], Header()] = None,
    x_user_position: Annotated[Optional[str], Header()] = None,
    x_user_manager_id: Annotated[Optional[str], Header()] = None,
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    bearer_token = auth_utils.extract_bearer_token(authorization)
    if settings.okta_auth_enabled and bearer_token:
        return auth_utils.decode_okta_access_token(bearer_token, settings)

    return AuthContext(
        sub=x_user_sub.strip().lower() if x_user_sub else None,
        groups=_split_csv_header(x_user_groups),
        department=x_user_department.strip().lower() if x_user_department else None,
        region=x_user_region.strip().lower() if x_user_region else None,
        position=x_user_position.strip().lower() if x_user_position else None,
        manager_id=x_user_manager_id.strip().lower() if x_user_manager_id else None,
    )


def _resolve_acl_policy(settings: Settings, principal: Optional[str]) -> Optional[ACLPolicy]:
    if not settings.acl_enabled:
        return None

    normalized_principal = (principal or "").strip().lower()
    for policy in settings.acl_policies:
        if policy.principal == normalized_principal:
            return policy

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ACL denied for principal")


def _evaluate_acl(
    settings: Settings,
    principal: Optional[str],
    auth_context: AuthContext,
    requested_providers: set[str],
    query_length: int,
) -> tuple[Optional[ACLPolicy], set[str], int, int, list[str], list[str], list[str]]:
    policy = _resolve_acl_policy(settings, principal)
    reasons: list[str] = []
    denied_providers: list[str] = []
    matched_groups: list[str] = []

    if not policy:
        return (
            None,
            set(),
            settings.max_query_length,
            settings.max_results_per_provider,
            denied_providers,
            reasons,
            matched_groups,
        )

    allowed_providers = set(policy.allowed_providers)
    if requested_providers:
        denied_providers = sorted(requested_providers - allowed_providers)
        if denied_providers:
            reasons.append(f"providers not allowed by ACL: {', '.join(denied_providers)}")

    if policy.allowed_groups:
        matched_groups = sorted(set(auth_context.groups) & set(policy.allowed_groups))
        if not matched_groups:
            reasons.append("no required group matched")

    if policy.allowed_departments and auth_context.department not in set(policy.allowed_departments):
        reasons.append("department not allowed by ACL")

    if policy.allowed_regions and auth_context.region not in set(policy.allowed_regions):
        reasons.append("region not allowed by ACL")

    if policy.allowed_positions and auth_context.position not in set(policy.allowed_positions):
        reasons.append("position not allowed by ACL")

    if policy.require_manager and not auth_context.manager_id:
        reasons.append("manager context required by ACL")

    effective_max_query_length = min(
        settings.max_query_length,
        policy.max_query_length or settings.max_query_length,
    )
    if query_length > effective_max_query_length:
        reasons.append(f"query length exceeds ACL limit ({effective_max_query_length})")

    effective_max_results = min(
        settings.max_results_per_provider,
        policy.max_results_per_provider or settings.max_results_per_provider,
    )

    return (
        policy,
        allowed_providers,
        effective_max_query_length,
        effective_max_results,
        denied_providers,
        reasons,
        matched_groups,
    )


def _result_matches_auth_context(result: SearchResult, auth_context: AuthContext) -> bool:
    metadata = result.metadata

    allowed_groups = _normalize_metadata_list(metadata.get("allowed_groups") or metadata.get("allowed_roles"))
    if allowed_groups and not set(auth_context.groups).intersection(allowed_groups):
        return False

    allowed_departments = _normalize_metadata_list(metadata.get("allowed_departments"))
    if allowed_departments and auth_context.department not in allowed_departments:
        return False

    allowed_regions = _normalize_metadata_list(metadata.get("allowed_regions"))
    if allowed_regions and auth_context.region not in allowed_regions:
        return False

    allowed_positions = _normalize_metadata_list(metadata.get("allowed_positions"))
    if allowed_positions and auth_context.position not in allowed_positions:
        return False

    allowed_manager_ids = _normalize_metadata_list(metadata.get("allowed_manager_ids"))
    if allowed_manager_ids and auth_context.sub not in allowed_manager_ids:
        return False

    allowed_user_subs = _normalize_metadata_list(metadata.get("allowed_user_subs"))
    if allowed_user_subs and auth_context.sub not in allowed_user_subs:
        return False

    return True


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse)
async def search(
    payload: SearchRequest,
    _: str = Depends(get_api_key),
    client_id: Optional[str] = Depends(get_client_id),
    auth_context: AuthContext = Depends(get_auth_context),
    settings: Settings = Depends(get_settings),
    connectors: list[SaaSSearchConnector] = Depends(get_connectors),
) -> SearchResponse:
    query = payload.query.strip()
    selected_providers = {provider.strip().lower() for provider in (payload.providers or []) if provider.strip()}
    _, allowed_by_acl, acl_max_query_length, acl_max_results, denied_providers, acl_reasons, _ = _evaluate_acl(
        settings=settings,
        principal=client_id,
        auth_context=auth_context,
        requested_providers=selected_providers,
        query_length=len(query),
    )

    if denied_providers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"providers not allowed by ACL: {', '.join(denied_providers)}",
        )

    if len(query) > acl_max_query_length:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"query must be <= {acl_max_query_length} characters",
        )

    if acl_reasons:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="; ".join(acl_reasons))

    active_connectors = [
        connector
        for connector in connectors
        if (
            (not selected_providers or connector.provider.name.strip().lower() in selected_providers)
            and (not allowed_by_acl or connector.provider.name.strip().lower() in allowed_by_acl)
        )
    ]
    if not active_connectors:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no providers matched")

    results = await asyncio.gather(
        *[connector.search(query, acl_max_results) for connector in active_connectors],
        return_exceptions=True,
    )

    merged_results: list[SearchResult] = []
    failed_providers: list[str] = []
    for connector, result in zip(active_connectors, results):
        if isinstance(result, Exception):
            failed_providers.append(connector.provider.name)
            logger.warning("provider search failed", extra={"provider": connector.provider.name})
            continue
        merged_results.extend(result)

    filtered_results = [result for result in merged_results if _result_matches_auth_context(result, auth_context)]

    if failed_providers and not filtered_results:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"all providers failed: {', '.join(failed_providers)}",
        )

    return SearchResponse(query=query, results=filtered_results, failed_providers=failed_providers)


@app.post("/acl/check", response_model=ACLCheckResponse)
async def check_acl(
    payload: ACLCheckRequest,
    _: str = Depends(get_api_key),
    settings: Settings = Depends(get_settings),
) -> ACLCheckResponse:
    requested_providers = {provider.strip().lower() for provider in (payload.providers or []) if provider.strip()}
    auth_context = AuthContext(
        sub=payload.sub.strip().lower() if payload.sub else None,
        groups=[group.strip().lower() for group in (payload.groups or []) if group.strip()],
        department=payload.department.strip().lower() if payload.department else None,
        region=payload.region.strip().lower() if payload.region else None,
        position=payload.position.strip().lower() if payload.position else None,
        manager_id=payload.manager_id.strip().lower() if payload.manager_id else None,
    )
    _, allowed_providers, acl_max_query_length, acl_max_results, denied_providers, reasons, matched_groups = _evaluate_acl(
        settings=settings,
        principal=payload.principal,
        auth_context=auth_context,
        requested_providers=requested_providers,
        query_length=payload.query_length,
    )

    return ACLCheckResponse(
        allowed=not reasons,
        principal=payload.principal.strip().lower(),
        allowed_providers=sorted(allowed_providers),
        matched_groups=matched_groups,
        effective_max_query_length=acl_max_query_length,
        effective_max_results_per_provider=acl_max_results,
        denied_providers=denied_providers,
        reasons=reasons,
    )


@app.post("/etl/run", response_model=ETLRunResponse)
async def run_etl(
    payload: ETLRunRequest,
    _: str = Depends(get_api_key),
    settings: Settings = Depends(get_settings),
    pipeline: ETLPipeline = Depends(get_etl_pipeline),
) -> ETLRunResponse:
    if not settings.etl_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="ETL is disabled")

    try:
        results = await pipeline.run(systems=payload.systems, dry_run=payload.dry_run)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return ETLRunResponse(
        dry_run=payload.dry_run,
        systems=[
            ETLSystemResultResponse(
                system=item.system,
                extracted_records=item.extracted_records,
                transformed_documents=item.transformed_documents,
                loaded_documents=item.loaded_documents,
            )
            for item in results
        ],
    )
