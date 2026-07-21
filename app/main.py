from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import auth as auth_utils
from app.config import ACLPolicy, Settings, get_settings
from app.connectors import SaaSSearchConnector, build_connectors
from app.etl import ETLPipeline, build_etl_pipeline
from app.etl.mock_data import MOCK_ETL_RECORDS, build_mock_access_token, get_mock_secret
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
started_at = time.time()
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
MOCK_TEMPLATE_PATH = TEMPLATES_DIR / "index.html"

DEMO_MODES: list[dict[str, str]] = [
    {
        "key": "mock",
        "label": "Gemini Enterprise Mock",
        "description": "Profile-driven chat demo that mirrors the test data coverage",
    },
    {
        "key": "status",
        "label": "Cloud Run Status Check",
        "description": "Current app: runtime checks plus connector search demo",
    },
]

DEMO_PROFILES: dict[str, dict[str, object]] = {
    "john-smith": {
        "id": "john-smith",
        "label": "John Smith (Employee / Sales)",
        "description": "General employee profile. Cannot access confidential HR records for John Smith.",
        "subject": "john-smith",
        "coverage_ids": ["sn-kb-3301", "cf-misc-7021", "sp-gift-9202"],
        "suggested_queries": [
            "How do I reset my password?",
            "Where is the team handbook?",
            "Can I see my performance review?",
        ],
        "default_target_system": "all",
    },
    "carol-tanaka": {
        "id": "carol-tanaka",
        "label": "Carol Tanaka (HR Manager / JP)",
        "description": "HR manager profile. Can access John Smith HR documents.",
        "subject": "hr-manager",
        "coverage_ids": ["wd-hr-5501", "wd-hr-5502", "wd-hr-7701", "wd-pay-3001"],
        "suggested_queries": [
            "Who approved the termination process for John Smith?",
            "Show the performance review for John Smith.",
            "What HR file is available for this direct report?",
        ],
        "default_target_system": "workday",
    },
    "emma-sato": {
        "id": "emma-sato",
        "label": "Emma Sato (Compliance Officer / Risk)",
        "description": "Compliance reviewer for exception approvals and audit logs.",
        "subject": "compliance-head",
        "coverage_ids": ["sn-exc-2409", "cmp-audit-8801", "cmp-gift-7710", "sn-chat-7781"],
        "suggested_queries": [
            "Who approved the exception for the Smith account?",
            "Show the audit log for trading violations.",
            "Open the named access memo for client gift exceptions.",
        ],
        "default_target_system": "all",
    },
    "ryo-kobayashi": {
        "id": "ryo-kobayashi",
        "label": "Ryo Kobayashi (Trader / Markets JP)",
        "description": "Trading floor profile for gift policy and Chinese wall scenarios.",
        "subject": "trader-user",
        "coverage_ids": ["sp-gift-9201", "sn-chat-7781", "wd-acc-3410"],
        "suggested_queries": [
            "Where is the policy on client gift limits?",
            "What is the process for requesting trading system access?",
            "Show the Chinese wall related trading communication.",
        ],
        "default_target_system": "all",
    },
    "ken-ito": {
        "id": "ken-ito",
        "label": "Ken Ito (IT Support / Operations)",
        "description": "Support profile for password reset and operational runbooks.",
        "subject": "it-support",
        "coverage_ids": ["sn-kb-3301", "wd-admin-9101", "cf-page-6001", "cf-page-6002", "cf-misc-7021"],
        "suggested_queries": [
            "How do I reset a password?",
            "Is there a Workday admin password reset guide?",
            "Find the search gateway runbook.",
        ],
        "default_target_system": "all",
    },
    "sophie-dupont": {
        "id": "sophie-dupont",
        "label": "Sophie Dupont (EU Privacy Lead)",
        "description": "GDPR profile for EU personal-data and payroll exception controls.",
        "subject": "privacy-lead",
        "coverage_ids": ["sp-gdpr-6601", "wd-pay-3001"],
        "suggested_queries": [
            "How is EU employee personal data handled?",
            "Show the payroll exception policy.",
        ],
        "default_target_system": "all",
    },
}

DEMO_DOCUMENTS: list[dict[str, str]] = [
    {
        "id": "sp-gift-9201",
        "title": "Client gift limits policy (Trading Division)",
        "source": "sharepoint",
        "answer": "The Trading Division client gift policy is in SharePoint under sp-gift-9201.",
        "keywords": "client gift,gift limits,trading division,trading policy",
    },
    {
        "id": "sp-gift-9202",
        "title": "Client gift limits policy (Investment Banking)",
        "source": "sharepoint",
        "answer": "The banking-side policy is stored separately as sp-gift-9202.",
        "keywords": "client gift,gift limits,investment banking,coverage teams",
    },
    {
        "id": "sn-exc-2409",
        "title": "Smith account exception approval ticket (2024)",
        "source": "servicenow",
        "answer": "Mary Johnson approved the Smith account exception on 2024-09-18.",
        "keywords": "smith,exception,approval,mary johnson",
    },
    {
        "id": "wd-acc-3410",
        "title": "Role Enablement request flow",
        "source": "workday",
        "answer": "Request trading system access via Workday > Internal Mobility > Role Enablement.",
        "keywords": "trading system access,role enablement,internal mobility",
    },
    {
        "id": "sn-chat-7781",
        "title": "Trading floor communication: Client Orion block trade",
        "source": "servicenow",
        "answer": "This document is a Chinese-wall-restricted trading communication for Client Orion.",
        "keywords": "chinese wall,client orion,block trade,trading floor",
    },
    {
        "id": "cmp-audit-8801",
        "title": "Audit log: trading violations Q2",
        "source": "compliance-system",
        "answer": "The audit log for trading violations is cmp-audit-8801.",
        "keywords": "audit,trading violations,who accessed what",
    },
    {
        "id": "sp-gdpr-6601",
        "title": "EU employee personal data handling standard",
        "source": "sharepoint",
        "answer": "EU employee personal data is handled in sp-gdpr-6601.",
        "keywords": "gdpr,personal data,eu employee",
    },
    {
        "id": "sn-kb-3301",
        "title": "Password reset knowledge article for IT support",
        "source": "servicenow",
        "answer": "Password reset for employees is documented in ServiceNow as sn-kb-3301.",
        "keywords": "password reset,it support,knowledge article",
    },
    {
        "id": "wd-admin-9101",
        "title": "Workday admin password reset procedure",
        "source": "workday",
        "answer": "Workday admin password reset is handled by wd-admin-9101.",
        "keywords": "workday admin,password reset,tenant administrator",
    },
    {
        "id": "cmp-gift-7710",
        "title": "Specific access list: client gift review board memo",
        "source": "compliance-system",
        "answer": "This memo is limited to the named users defined in cmp-gift-7710.",
        "keywords": "specific access,named users,client gift exceptions",
    },
    {
        "id": "wd-pay-3001",
        "title": "Payroll exception policy",
        "source": "workday",
        "answer": "The payroll exception policy is wd-pay-3001 and is EU-scoped.",
        "keywords": "payroll exception,gdpr,eu",
    },
    {
        "id": "wd-hr-5501",
        "title": "Termination process for John Smith",
        "source": "workday",
        "answer": "The termination process for John Smith is documented in Workday as wd-hr-5501.",
        "keywords": "termination,john smith,direct report",
    },
    {
        "id": "wd-hr-5502",
        "title": "Performance review: John Smith",
        "source": "workday",
        "answer": "The performance review for John Smith is available only to the direct manager and HR.",
        "keywords": "performance review,john smith,direct manager",
    },
    {
        "id": "wd-hr-7701",
        "title": "HR cross-team confidential package",
        "source": "workday",
        "answer": "This package is restricted and requires matching HR manager scope.",
        "keywords": "hr confidential,restricted package,manager scope",
    },
    {
        "id": "cf-page-6001",
        "title": "Runbook: search gateway failover",
        "source": "confluence",
        "answer": "The search gateway failover runbook is stored in Confluence as cf-page-6001.",
        "keywords": "runbook,failover,search gateway",
    },
    {
        "id": "cf-page-6002",
        "title": "Postmortem template",
        "source": "confluence",
        "answer": "The postmortem template is cf-page-6002.",
        "keywords": "postmortem,template,action item",
    },
    {
        "id": "cf-misc-7021",
        "title": "Confluence team handbook",
        "source": "confluence",
        "answer": "General team handbook is available in cf-misc-7021.",
        "keywords": "team handbook,operations notes,general guide",
    },
]

DEMO_DOCUMENT_INDEX = {document["id"]: document for document in DEMO_DOCUMENTS}
DEMO_TARGET_SYSTEMS = {"servicenow", "workday", "compliance-system", "sharepoint", "confluence"}
DEMO_SOURCE_SAMPLES: dict[str, dict[str, object]] = {
    "servicenow": {
        "file": "data/source_samples/servicenow_sample.json",
        "sample": {
            "system": "servicenow",
            "records": [
                {"id": "SN-001", "title": "Smith account exception approval", "type": "ticket", "status": "approved"}
            ],
        },
    },
    "workday": {
        "file": "data/source_samples/workday_sample.json",
        "sample": {
            "system": "workday",
            "records": [
                {"id": "WD-001", "title": "Role Enablement request flow", "category": "internal_mobility", "status": "active"}
            ],
        },
    },
    "compliance-system": {
        "file": "data/source_samples/compliance_system_sample.json",
        "sample": {
            "system": "compliance-system",
            "records": [
                {"id": "CMP-001", "title": "Audit log: trading violations Q2", "classification": "compliance", "status": "retained"}
            ],
        },
    },
    "sharepoint": {
        "file": "data/source_samples/sharepoint_sample.json",
        "sample": {
            "system": "sharepoint",
            "records": [
                {"id": "SP-001", "title": "Client gift limits policy", "format": "pdf", "status": "published"}
            ],
        },
    },
    "confluence": {
        "file": "data/source_samples/confluence_sample.json",
        "sample": {
            "system": "confluence",
            "records": [
                {"id": "CF-001", "title": "Runbook: search gateway failover", "space": "OPS", "status": "current"}
            ],
        },
    },
}


class DemoMockChatRequest(BaseModel):
    profile_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    target_system: str = Field(default="all")
    target_systems: list[str] = Field(default_factory=list)


def _profile_summary(profile: dict[str, object]) -> dict[str, object]:
    coverage_ids = list(profile["coverage_ids"])
    label = str(profile["label"])
    display_name = label.split("(")[0].strip()
    return {
        "id": profile["id"],
        "label": label,
        "display_name": display_name,
        "description": profile["description"],
        "subject": profile["subject"],
        "coverage_ids": coverage_ids,
        "suggested_queries": profile["suggested_queries"],
        "default_target_system": profile["default_target_system"],
        "coverage_titles": [DEMO_DOCUMENT_INDEX[document_id]["title"] for document_id in coverage_ids if document_id in DEMO_DOCUMENT_INDEX],
    }


def _document_summary(document: dict[str, str], visible: bool) -> dict[str, object]:
    return {
        "id": document["id"],
        "title": document["title"],
        "source": document["source"],
        "summary": document["answer"],
        "visible": visible,
    }


def _find_mock_documents(query: str, selected_systems: set[str]) -> list[dict[str, str]]:
    query_lower = query.lower()
    matched: list[dict[str, str]] = []
    for document in DEMO_DOCUMENTS:
        if selected_systems and document["source"] not in selected_systems:
            continue
        keywords = [item.strip() for item in document["keywords"].split(",") if item.strip()]
        if any(keyword in query_lower for keyword in keywords):
            matched.append(document)
    return matched


def _build_mock_answer(profile: dict[str, object], query: str, selected_systems: set[str]) -> dict[str, object]:
    matched_documents = _find_mock_documents(query, selected_systems)
    visible_documents = [document for document in matched_documents if document["id"] in profile["coverage_ids"]]
    blocked_documents = [document for document in matched_documents if document["id"] not in profile["coverage_ids"]]

    if not selected_systems:
        selected_systems = set(DEMO_TARGET_SYSTEMS)

    if visible_documents:
        reply = " ".join(document["answer"] for document in visible_documents)
    elif matched_documents:
        reply = f"{profile['label']} does not have access to the matched document(s) for this query."
    else:
        reply = f"No matching test document was found for '{query}'."

    return {
        "status": "ok",
        "mode": "mock",
        "profile": _profile_summary(profile),
        "query": query,
        "target_system": "all" if len(selected_systems) != 1 else next(iter(selected_systems)),
        "target_systems": sorted(selected_systems),
        "reply": reply,
        "citations": [_document_summary(document, True) for document in visible_documents],
        "blocked_documents": [_document_summary(document, False) for document in blocked_documents],
        "matched_documents": [_document_summary(document, document in visible_documents) for document in matched_documents],
        "source_samples": [
            {
                "system": system,
                "source_sample_file": DEMO_SOURCE_SAMPLES[system]["file"],
                "route": f"/api/demo/source-samples/{system}",
            }
            for system in sorted(selected_systems)
            if system in DEMO_SOURCE_SAMPLES
        ],
        "suggested_queries": profile["suggested_queries"],
        "elapsed_ms": 0,
    }
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


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


@app.get("/api/runtime")
async def runtime() -> dict[str, object]:
    return {
        "status": "ok",
        "service": os.getenv("K_SERVICE", "local"),
        "revision": os.getenv("K_REVISION", "local"),
        "configuration": os.getenv("K_CONFIGURATION", "local"),
        "project": os.getenv("GOOGLE_CLOUD_PROJECT", "local"),
        "environment": os.getenv("APP_ENV", "development"),
        "demo_mode": os.getenv("DEMO_MODE", "echo"),
        "connector_count": len(DEMO_TARGET_SYSTEMS),
        "uptime_ms": int((time.time() - started_at) * 1000),
    }


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
        return HTMLResponse(
                """
                <!doctype html>
                <html lang="ja">
                    <head>
                        <meta charset="UTF-8" />
                        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                        <title>a-certain-demo</title>
                        <style>
                            body { font-family: Arial, sans-serif; margin: 0; padding: 3rem; background: #0f172a; color: #e2e8f0; }
                            main { max-width: 720px; margin: 0 auto; }
                            h1 { margin: 0 0 1rem; font-size: 2rem; }
                            p { line-height: 1.7; color: #cbd5e1; }
                            .card { margin-top: 1.5rem; padding: 1.25rem; border-radius: 16px; background: #111827; border: 1px solid #334155; }
                            a { color: #93c5fd; }
                            code { background: #1e293b; padding: 0.15rem 0.35rem; border-radius: 6px; }
                        </style>
                    </head>
                    <body>
                        <main>
                            <h1>a-certain-demo</h1>
                            <p>Cloud Run の API ゲートウェイです。検索や ETL の確認は API から行えます。</p>
                            <div class="card">
                                <p><a href="/docs">API ドキュメント</a></p>
                                <p><a href="/healthz">Health check</a></p>
                                <p><a href="/api/runtime">Runtime metadata</a></p>
                                <p><a href="/mock">Gemini Enterprise mock</a></p>
                                <p><a href="/api/demo/source-samples">5 systems sample JSON catalog</a></p>
                            </div>
                            <p>起動確認は <code>/healthz</code>、モック画面は <code>/mock</code> を参照してください。</p>
                        </main>
                    </body>
                </html>
                """.strip()
        )


@app.get("/mock", response_class=HTMLResponse)
async def gemini_mock() -> HTMLResponse:
    if not MOCK_TEMPLATE_PATH.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mock template not found")
    return HTMLResponse(MOCK_TEMPLATE_PATH.read_text(encoding="utf-8"))


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


@app.get("/mock/systems/{system_name}/records")
async def mock_system_records(system_name: str) -> dict[str, object]:
    system = system_name.strip().lower()
    if system not in MOCK_ETL_RECORDS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown mock system")

    return {
        "system": system,
        "items": MOCK_ETL_RECORDS[system],
    }


@app.post("/mock/idp/{identity_provider}/token")
async def mock_identity_token(identity_provider: str, system: str) -> dict[str, object]:
    provider = identity_provider.strip().lower()
    if provider not in {"okta", "entra_id", "okta_ldap_agent"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported identity provider")

    return {
        "token_type": "Bearer",
        "access_token": build_mock_access_token(system.strip().lower(), provider),
        "expires_in": 3600,
    }


@app.get("/mock/secrets/{secret_name}")
async def mock_secret(secret_name: str) -> dict[str, str]:
    try:
        value = get_mock_secret(secret_name)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mock secret not found") from error

    return {"name": secret_name, "value": value}


@app.get("/mock/ldap/bind/{system_name}")
async def mock_ldap_bind(system_name: str) -> dict[str, str]:
    system = system_name.strip().lower()
    if system != "compliance-system":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mock bind info not found")

    return {
        "system": system,
        "username": get_mock_secret("SEARCH_APP_ETL_SECRET_COMPLIANCE_LDAP_USERNAME"),
        "password": get_mock_secret("SEARCH_APP_ETL_SECRET_COMPLIANCE_LDAP_PASSWORD"),
    }


@app.get("/api/demo/config")
async def demo_config() -> dict[str, object]:
    return {
        "status": "ok",
        "modes": DEMO_MODES,
        "default_mode": "mock",
        "profiles": [_profile_summary(profile) for profile in DEMO_PROFILES.values()],
    }


@app.get("/api/demo/source-samples")
async def demo_source_samples() -> dict[str, object]:
    return {
        "status": "ok",
        "systems": [
            {
                "system": system,
                "source_sample_file": payload["file"],
                "route": f"/api/demo/source-samples/{system}",
            }
            for system, payload in DEMO_SOURCE_SAMPLES.items()
        ],
    }


@app.get("/api/demo/source-samples/{system_name}")
async def demo_source_sample_detail(system_name: str) -> dict[str, object]:
    system = system_name.strip().lower()
    if system not in DEMO_SOURCE_SAMPLES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown demo source system")

    payload = DEMO_SOURCE_SAMPLES[system]
    pretty = json.dumps(payload["sample"], ensure_ascii=False, indent=2)
    return {
        "status": "ok",
        "system": system,
        "source_sample_file": payload["file"],
        "sample": payload["sample"],
        "sample_pretty_json": pretty,
    }


@app.post("/api/demo/mock/chat")
async def demo_mock_chat(request: DemoMockChatRequest) -> dict[str, object]:
    profile_key = request.profile_id.strip().lower()
    if profile_key not in DEMO_PROFILES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "unknown demo profile"})

    selected_systems = {item.strip().lower() for item in request.target_systems if item.strip()}

    target_system = request.target_system.strip().lower() or "all"
    if target_system != "all":
        selected_systems.add(target_system)

    if not selected_systems:
        selected_systems = set(DEMO_TARGET_SYSTEMS)

    invalid_systems = [system for system in selected_systems if system not in DEMO_TARGET_SYSTEMS]
    if invalid_systems:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "target_system is invalid"})

    started = time.time()
    response = _build_mock_answer(DEMO_PROFILES[profile_key], request.query.strip(), selected_systems)
    response["elapsed_ms"] = int((time.time() - started) * 1000)
    return response
