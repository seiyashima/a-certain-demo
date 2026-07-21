import logging
import os
import re
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field


CONNECTORS: dict[str, dict[str, Any]] = {
    "servicenow": {
        "label": "ServiceNow",
        "description": "Incidents, requests, and operational workflows",
        "keywords": ["incident", "ticket", "request", "change", "ops"],
        "documents": [
            {
                "title": "INC-2048 VPN outage follow-up",
                "snippet": "Incident response notes and remediation steps for the VPN outage.",
                "tags": ["incident", "ops"],
            },
            {
                "title": "CHG-3311 maintenance window",
                "snippet": "Approved change record for the monthly maintenance window.",
                "tags": ["change", "request"],
            },
        ],
    },
    "workday": {
        "label": "Workday",
        "description": "Employee records, payroll, and HR workflows",
        "keywords": ["payroll", "pto", "employee", "benefits", "hr"],
        "documents": [
            {
                "title": "Payroll adjustment guide",
                "snippet": "Steps for correcting payroll entries with manager approval.",
                "tags": ["payroll", "hr"],
            },
            {
                "title": "PTO request policy",
                "snippet": "Vacation request guidance and approval routing.",
                "tags": ["pto", "policy"],
            },
        ],
    },
    "compliance-system": {
        "label": "Compliance System",
        "description": "Reviews, policies, and audit evidence",
        "keywords": ["compliance", "policy", "audit", "review", "violation"],
        "documents": [
            {
                "title": "Policy exception review",
                "snippet": "Compliance review notes for a policy exception request.",
                "tags": ["review", "policy"],
            },
            {
                "title": "Audit evidence checklist",
                "snippet": "Required evidence for internal and external audits.",
                "tags": ["audit", "evidence"],
            },
        ],
    },
    "sharepoint": {
        "label": "SharePoint",
        "description": "Documents, templates, and shared folders",
        "keywords": ["document", "template", "folder", "policy", "sharepoint"],
        "documents": [
            {
                "title": "New joiner checklist",
                "snippet": "Shared onboarding checklist for hiring managers.",
                "tags": ["document", "template"],
            },
            {
                "title": "Policy template library",
                "snippet": "Centralized templates for team-owned policy drafts.",
                "tags": ["policy", "template"],
            },
        ],
    },
    "confluence": {
        "label": "Confluence",
        "description": "Runbooks, design notes, and knowledge pages",
        "keywords": ["runbook", "design", "knowledge", "adr", "confluence"],
        "documents": [
            {
                "title": "Search gateway runbook",
                "snippet": "Operational notes for the Cloud Run search gateway.",
                "tags": ["runbook", "ops"],
            },
            {
                "title": "Connector ADR digest",
                "snippet": "Architecture notes for connector routing and ACL checks.",
                "tags": ["adr", "design"],
            },
        ],
    },
}

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

DEMO_PROFILES: dict[str, dict[str, Any]] = {
    "trader-jp": {
        "id": "trader-jp",
        "label": "Trader / JP",
        "description": "Trading floor user in Japan covering client gift and Chinese wall scenarios.",
        "subject": "trader-user",
        "attributes": {
            "sub": "okta|trader.jp",
            "groups": ["trading_floor"],
            "department": "markets",
            "region": "jp",
            "position": "trader",
            "manager_id": "mgr-trade-001",
        },
        "coverage_ids": ["sp-gift-9201", "sn-chat-7781", "wd-acc-3410"],
        "suggested_queries": [
            "Where is the policy on client gift limits?",
            "What is the process for requesting trading system access?",
            "Show the Chinese wall related trading communication.",
        ],
        "default_target_system": "all",
    },
    "investment-banking-jp": {
        "id": "investment-banking-jp",
        "label": "Investment Banking / JP",
        "description": "Coverage team for the banking-side gift policy negative case.",
        "subject": "ib-user",
        "attributes": {
            "sub": "okta|ib.jp",
            "groups": ["investment_banking"],
            "department": "ibd",
            "region": "jp",
            "position": "banker",
            "manager_id": "mgr-ib-001",
        },
        "coverage_ids": ["sp-gift-9202"],
        "suggested_queries": [
            "Where is the policy on client gift limits?",
            "Do I see the trading division version of the policy?",
        ],
        "default_target_system": "sharepoint",
    },
    "compliance-officer": {
        "id": "compliance-officer",
        "label": "Compliance Officer",
        "description": "Reviewer role for exception, audit, and named-access memo scenarios.",
        "subject": "compliance-head",
        "attributes": {
            "sub": "okta|compliance.head",
            "groups": ["compliance", "compliance_officer"],
            "department": "risk",
            "region": "jp",
            "position": "officer",
            "manager_id": "mgr-compliance-001",
        },
        "coverage_ids": ["sn-exc-2409", "cmp-audit-8801", "cmp-gift-7710", "sn-chat-7781"],
        "suggested_queries": [
            "Who approved the exception for the Smith account?",
            "Show the audit log for trading violations.",
            "Open the named access memo for client gift exceptions.",
        ],
        "default_target_system": "all",
    },
    "hr-manager-jp": {
        "id": "hr-manager-jp",
        "label": "HR Manager / JP",
        "description": "Direct-manager HR profile for confidential employee records.",
        "subject": "hr-manager",
        "attributes": {
            "sub": "entra|carol",
            "groups": ["hr", "hr_manager"],
            "department": "hr",
            "region": "jp",
            "position": "manager",
            "manager_id": "mgr-john-001",
        },
        "coverage_ids": ["wd-hr-5501", "wd-hr-5502", "wd-hr-7701"],
        "suggested_queries": [
            "Who approved the termination process for John Smith?",
            "Show the performance review for John Smith.",
            "What HR file is available for this direct report?",
        ],
        "default_target_system": "workday",
    },
    "it-support": {
        "id": "it-support",
        "label": "IT Support",
        "description": "Support profile for password reset and general ops content.",
        "subject": "it-support",
        "attributes": {
            "sub": "okta|it.support",
            "groups": ["it_support", "ops"],
            "department": "it",
            "region": "jp",
            "position": "specialist",
            "manager_id": "mgr-it-001",
        },
        "coverage_ids": ["sn-kb-3301", "wd-admin-9101", "cf-page-6001", "cf-page-6002", "cf-misc-7021"],
        "suggested_queries": [
            "How do I reset a password?",
            "Is there a Workday admin password reset guide?",
            "Find the search gateway runbook.",
        ],
        "default_target_system": "all",
    },
    "eu-privacy": {
        "id": "eu-privacy",
        "label": "EU Privacy",
        "description": "GDPR profile for regional personal-data access.",
        "subject": "privacy-lead",
        "attributes": {
            "sub": "entra|privacy.eu",
            "groups": ["hr", "privacy", "compliance"],
            "department": "hr",
            "region": "eu",
            "position": "officer",
            "manager_id": "mgr-privacy-001",
        },
        "coverage_ids": ["sp-gdpr-6601", "wd-pay-3001"],
        "suggested_queries": [
            "How is EU employee personal data handled?",
            "Show the payroll exception policy.",
        ],
        "default_target_system": "all",
    },
}

DEMO_DOCUMENTS: list[dict[str, Any]] = [
    {
        "id": "sp-gift-9201",
        "title": "Client gift limits policy (Trading Division)",
        "source": "sharepoint",
        "classification": "compliance",
        "keywords": ["client gift", "gift limits", "trading division", "trading policy"],
        "summary": "Large SharePoint PDF with the trading division policy.",
        "answer": "The Trading Division client gift policy is in SharePoint under sp-gift-9201.",
    },
    {
        "id": "sp-gift-9202",
        "title": "Client gift limits policy (Investment Banking)",
        "source": "sharepoint",
        "classification": "compliance",
        "keywords": ["client gift", "gift limits", "investment banking", "coverage teams"],
        "summary": "Investment banking specific gift policy.",
        "answer": "The banking-side policy is stored separately as sp-gift-9202.",
    },
    {
        "id": "sn-exc-2409",
        "title": "Smith account exception approval ticket (2024)",
        "source": "servicenow",
        "classification": "compliance",
        "keywords": ["smith", "exception", "approval", "mary johnson"],
        "summary": "Exception approval record for the Smith account.",
        "answer": "Mary Johnson approved the Smith account exception on 2024-09-18.",
    },
    {
        "id": "wd-acc-3410",
        "title": "Role Enablement request flow (Internal Mobility > Role Enablement)",
        "source": "workday",
        "classification": "standard",
        "keywords": ["trading system access", "role enablement", "internal mobility"],
        "summary": "Non-intuitive Workday category for trading system access.",
        "answer": "Request trading system access via Workday > Internal Mobility > Role Enablement.",
    },
    {
        "id": "sn-chat-7781",
        "title": "Trading floor communication: Client Orion block trade",
        "source": "servicenow",
        "classification": "compliance",
        "keywords": ["chinese wall", "client orion", "block trade", "trading floor"],
        "summary": "Restricted trading-floor communication around a block trade.",
        "answer": "This document is a Chinese-wall-restricted trading communication for Client Orion.",
    },
    {
        "id": "wd-hr-5501",
        "title": "Termination process for John Smith",
        "source": "workday",
        "classification": "compliance",
        "keywords": ["termination", "john smith", "direct report"],
        "summary": "HR termination checklist and legal steps.",
        "answer": "The termination process for John Smith is documented in Workday as wd-hr-5501.",
    },
    {
        "id": "wd-hr-5502",
        "title": "Performance review: John Smith",
        "source": "workday",
        "classification": "compliance",
        "keywords": ["performance review", "john smith", "direct manager"],
        "summary": "Confidential performance review notes.",
        "answer": "The performance review for John Smith is available only to the direct manager and HR.",
    },
    {
        "id": "cmp-audit-8801",
        "title": "Audit log: trading violations Q2",
        "source": "compliance_system",
        "classification": "compliance",
        "keywords": ["audit", "trading violations", "who accessed what"],
        "summary": "Audit trail of a trading violations investigation.",
        "answer": "The audit log for trading violations is cmp-audit-8801.",
    },
    {
        "id": "sp-gdpr-6601",
        "title": "EU employee personal data handling standard",
        "source": "sharepoint",
        "classification": "gdpr",
        "keywords": ["gdpr", "personal data", "eu employee"],
        "summary": "EU-only handling standard for personal data.",
        "answer": "EU employee personal data is handled in sp-gdpr-6601.",
    },
    {
        "id": "sn-kb-3301",
        "title": "Password reset knowledge article for IT support",
        "source": "servicenow",
        "classification": "standard",
        "keywords": ["password reset", "it support", "knowledge article"],
        "summary": "IT support workflow for employee password resets.",
        "answer": "Password reset for employees is documented in ServiceNow as sn-kb-3301.",
    },
    {
        "id": "wd-admin-9101",
        "title": "Workday admin password reset procedure",
        "source": "workday",
        "classification": "standard",
        "keywords": ["workday admin", "password reset", "tenant administrator"],
        "summary": "Administrative password reset for Workday administrators.",
        "answer": "Workday admin password reset is handled by wd-admin-9101.",
    },
    {
        "id": "cmp-gift-7710",
        "title": "Specific access list: client gift review board memo",
        "source": "compliance_system",
        "classification": "compliance",
        "keywords": ["specific access", "named users", "client gift exceptions"],
        "summary": "Memo restricted to named users only.",
        "answer": "This memo is limited to the named users defined in cmp-gift-7710.",
    },
    {
        "id": "wd-pay-3001",
        "title": "Payroll exception policy",
        "source": "workday",
        "classification": "gdpr",
        "keywords": ["payroll exception", "gdpr", "eu"],
        "summary": "Workday payroll exception workflow.",
        "answer": "The payroll exception policy is wd-pay-3001 and is EU-scoped.",
    },
    {
        "id": "cf-page-6001",
        "title": "Runbook: search gateway failover",
        "source": "confluence",
        "classification": "standard",
        "keywords": ["runbook", "failover", "search gateway"],
        "summary": "Confluence runbook for failover and rollback.",
        "answer": "The search gateway failover runbook is stored in Confluence as cf-page-6001.",
    },
    {
        "id": "cf-page-6002",
        "title": "Postmortem template",
        "source": "confluence",
        "classification": "standard",
        "keywords": ["postmortem", "template", "action item"],
        "summary": "Template for incident postmortems.",
        "answer": "The postmortem template is cf-page-6002.",
    },
]

DEMO_DOCUMENT_INDEX = {document["id"]: document for document in DEMO_DOCUMENTS}


def _profile_summary(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": profile["id"],
        "label": profile["label"],
        "description": profile["description"],
        "subject": profile["subject"],
        "attributes": profile["attributes"],
        "coverage_ids": profile["coverage_ids"],
        "suggested_queries": profile["suggested_queries"],
        "default_target_system": profile["default_target_system"],
        "coverage_titles": [DEMO_DOCUMENT_INDEX[document_id]["title"] for document_id in profile["coverage_ids"] if document_id in DEMO_DOCUMENT_INDEX],
    }


def _document_summary(document: dict[str, Any], visible: bool) -> dict[str, Any]:
    return {
        "id": document["id"],
        "title": document["title"],
        "source": document["source"],
        "classification": document["classification"],
        "summary": document["summary"],
        "visible": visible,
    }


def _score_mock_document(query: str, document: dict[str, Any], target_system: str) -> int:
    query_lower = query.lower()
    if target_system != "all" and document["source"] != target_system:
        return 0

    score = 0
    for keyword in document["keywords"]:
        if keyword in query_lower:
            score += 2 if len(keyword) > 6 else 1

    if document["title"].lower() in query_lower:
        score += 3

    return score


def _find_mock_documents(query: str, target_system: str) -> list[dict[str, Any]]:
    scored_documents = []
    for document in DEMO_DOCUMENTS:
        score = _score_mock_document(query, document, target_system)
        if score:
            scored_documents.append((score, document))

    scored_documents.sort(key=lambda item: (-item[0], item[1]["title"]))
    return [document for _, document in scored_documents]


def _build_mock_answer(profile: dict[str, Any], query: str, target_system: str) -> dict[str, Any]:
    matched_documents = _find_mock_documents(query, target_system)
    visible_documents = [document for document in matched_documents if document["id"] in profile["coverage_ids"]]
    blocked_documents = [document for document in matched_documents if document["id"] not in profile["coverage_ids"]]

    if visible_documents:
        answer_text = " ".join(document["answer"] for document in visible_documents)
    elif matched_documents:
        answer_text = (
            f"{profile['label']} does not have access to the matched document(s) for this query. "
            "Try another profile or narrow the target system."
        )
    else:
        answer_text = (
            f"No matching test document was found for '{query}'. Use one of the suggested profile prompts to cover the test data."
        )

    return {
        "status": "ok",
        "mode": "mock",
        "profile": _profile_summary(profile),
        "query": query,
        "target_system": target_system,
        "reply": answer_text,
        "citations": [_document_summary(document, True) for document in visible_documents],
        "blocked_documents": [_document_summary(document, False) for document in blocked_documents],
        "matched_documents": [_document_summary(document, document in visible_documents) for document in matched_documents],
        "suggested_queries": profile["suggested_queries"],
        "elapsed_ms": 0,
    }


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def determine_allowed_targets(subject: str) -> list[str]:
    subject_lower = subject.lower()

    if any(keyword in subject_lower for keyword in ("admin", "ops")):
        return list(CONNECTORS)
    if "compliance" in subject_lower:
        return ["servicenow", "compliance-system", "sharepoint", "confluence"]
    if "hr" in subject_lower:
        return ["workday", "sharepoint", "confluence"]
    return ["sharepoint", "confluence"]


def search_documents(query: str, connector_name: str) -> list[dict[str, Any]]:
    connector = CONNECTORS[connector_name]
    query_lower = query.lower()
    matched_documents: list[dict[str, Any]] = []

    for document in connector["documents"]:
        haystack = " ".join(
            [document["title"], document["snippet"], " ".join(document.get("tags", [])), " ".join(connector["keywords"])]
        ).lower()
        score = sum(1 for keyword in connector["keywords"] if keyword in query_lower)

        if query_lower in haystack:
            score += 2

        if query_lower and (query_lower in haystack or score > 0):
            matched_documents.append({
                "title": document["title"],
                "snippet": document["snippet"],
                "tags": document.get("tags", []),
                "score": score,
            })

    if not matched_documents and query_lower:
        return []

    if not query_lower:
        return [
            {
                "title": document["title"],
                "snippet": document["snippet"],
                "tags": document.get("tags", []),
                "score": 0,
            }
            for document in connector["documents"]
        ]

    return matched_documents


class SearchRequest(BaseModel):
    subject: str = Field(min_length=1)
    query: str = Field(min_length=1)
    target_system: str = Field(default="all")


class DemoMockChatRequest(BaseModel):
    profile_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    target_system: str = Field(default="all")


def create_app() -> FastAPI:
    app = FastAPI()
    started_at = time.time()
    templates = Jinja2Templates(directory="templates")

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s request_id=%(request_id)s %(message)s",
    )

    class RequestIdFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if not hasattr(record, "request_id"):
                record.request_id = "-"
            return True

    request_id_filter = RequestIdFilter()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(request_id_filter)

    logger = logging.getLogger(__name__)

    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runtime")
    def runtime() -> dict[str, Any]:
        uptime_ms = int((time.time() - started_at) * 1000)
        return {
            "status": "ok",
            "service": os.getenv("K_SERVICE", "local"),
            "revision": os.getenv("K_REVISION", "local"),
            "configuration": os.getenv("K_CONFIGURATION", "local"),
            "project": os.getenv("GOOGLE_CLOUD_PROJECT", "local"),
            "environment": os.getenv("APP_ENV", "development"),
            "demo_mode": os.getenv("DEMO_MODE", "echo"),
            "connector_count": len(CONNECTORS),
            "uptime_ms": uptime_ms,
        }

    @app.get("/api/connectors")
    def connectors() -> dict[str, Any]:
        return {
            "status": "ok",
            "connectors": [
                {
                    "key": connector_name,
                    "label": connector["label"],
                    "description": connector["description"],
                }
                for connector_name, connector in CONNECTORS.items()
            ],
        }

    @app.get("/api/demo/config")
    def demo_config() -> dict[str, Any]:
        return {
            "status": "ok",
            "modes": DEMO_MODES,
            "default_mode": "mock",
            "profiles": [_profile_summary(profile) for profile in DEMO_PROFILES.values()],
        }

    @app.post("/api/demo/mock/chat")
    async def demo_mock_chat(request: DemoMockChatRequest) -> dict[str, Any]:
        profile_key = request.profile_id.strip().lower()
        if profile_key not in DEMO_PROFILES:
            raise HTTPException(
                status_code=400,
                detail={"error": "unknown demo profile", "profile_id": request.profile_id},
            )

        profile = DEMO_PROFILES[profile_key]
        query = normalize_text(request.query)
        target_system = request.target_system.strip().lower() or "all"
        if target_system != "all" and target_system not in CONNECTORS:
            raise HTTPException(
                status_code=400,
                detail={"error": "target_system is invalid", "target_system": request.target_system},
            )

        started = time.time()
        response = _build_mock_answer(profile, query, target_system)
        response["elapsed_ms"] = int((time.time() - started) * 1000)
        return response

    @app.post("/api/search")
    async def search(request: SearchRequest) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        started = time.time()

        subject = normalize_text(request.subject)
        query = normalize_text(request.query)
        target_system = request.target_system.strip().lower() or "all"

        if not subject or not query:
            raise HTTPException(
                status_code=400,
                detail={"error": "subject and query are required", "request_id": request_id},
            )

        if target_system != "all" and target_system not in CONNECTORS:
            raise HTTPException(
                status_code=400,
                detail={"error": "target_system is invalid", "request_id": request_id},
            )

        allowed_targets = determine_allowed_targets(subject)
        requested_targets = list(CONNECTORS) if target_system == "all" else [target_system]
        denied_targets = [connector_name for connector_name in requested_targets if connector_name not in allowed_targets]

        if denied_targets:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "access denied",
                    "request_id": request_id,
                    "subject": subject,
                    "allowed_targets": allowed_targets,
                    "denied_targets": denied_targets,
                },
            )

        results = []
        for connector_name in requested_targets:
            connector = CONNECTORS[connector_name]
            documents = search_documents(query, connector_name)
            results.append(
                {
                    "key": connector_name,
                    "label": connector["label"],
                    "description": connector["description"],
                    "documents": documents,
                    "hit_count": len(documents),
                    "route_reason": "all targets" if target_system == "all" else "explicit target",
                }
            )

        elapsed_ms = int((time.time() - started) * 1000)

        return {
            "status": "ok",
            "request_id": request_id,
            "subject": subject,
            "query": query,
            "target_system": target_system,
            "allowed_targets": allowed_targets,
            "results": results,
            "elapsed_ms": elapsed_ms,
        }

    @app.post("/api/chat")
    async def chat(request: Request) -> dict[str, Any]:
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        started = time.time()

        payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        user_message = (payload.get("message") or "").strip()

        if not user_message:
            logger.warning("empty input", extra={"request_id": request_id})
            raise HTTPException(status_code=400, detail={"error": "message is required", "request_id": request_id})

        mode = os.getenv("DEMO_MODE", "echo")
        if mode == "echo":
            response_text = f"Echo: {user_message}"
        else:
            response_text = (
                "Demo mode is disabled. Set DEMO_MODE=echo "
                "or wire this endpoint to your connector/model implementation."
            )

        elapsed_ms = int((time.time() - started) * 1000)
        logger.info(
            "chat handled in %dms",
            elapsed_ms,
            extra={"request_id": request_id},
        )

        return {
            "reply": response_text,
            "request_id": request_id,
            "elapsed_ms": elapsed_ms,
        }

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            return JSONResponse(exc.detail, status_code=exc.status_code)
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        return JSONResponse({"error": str(exc.detail), "request_id": request_id}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def handle_exception(request: Request, exc: Exception) -> JSONResponse:
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        logger.exception("unhandled error: %s", exc, extra={"request_id": request_id})
        return JSONResponse({"error": "internal server error", "request_id": request_id}, status_code=500)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=os.getenv("APP_ENV", "development") == "development")
