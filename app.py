import logging
import os
import time
import uuid
from typing import Any

from flask import Flask, jsonify, render_template, request


def create_app() -> Flask:
    app = Flask(__name__)

    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s request_id=%(request_id)s %(message)s",
    )

    class RequestIdAdapter(logging.LoggerAdapter):
        def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            extra = kwargs.setdefault("extra", {})
            extra.setdefault("request_id", request.headers.get("X-Request-Id", "-"))
            return msg, kwargs

    logger = RequestIdAdapter(logging.getLogger(__name__), {})

    @app.route("/")
    def index() -> str:
        return render_template("index.html")

    @app.route("/healthz")
    def healthz() -> tuple[dict[str, str], int]:
        return {"status": "ok"}, 200

    @app.route("/api/chat", methods=["POST"])
    def chat() -> tuple[Any, int]:
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        started = time.time()

        payload = request.get_json(silent=True) or {}
        user_message = (payload.get("message") or "").strip()

        if not user_message:
            logger.warning("empty input", extra={"request_id": request_id})
            return jsonify({"error": "message is required", "request_id": request_id}), 400

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

        return jsonify(
            {
                "reply": response_text,
                "request_id": request_id,
                "elapsed_ms": elapsed_ms,
            }
        ), 200

    @app.errorhandler(Exception)
    def handle_exception(exc: Exception) -> tuple[Any, int]:
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        logger.exception("unhandled error: %s", exc, extra={"request_id": request_id})
        return jsonify({"error": "internal server error", "request_id": request_id}), 500

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    debug = os.getenv("APP_ENV", "development") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
