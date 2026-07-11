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
