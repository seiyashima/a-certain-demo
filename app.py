import logging
import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


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
            "uptime_ms": uptime_ms,
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
