from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.etl.transform import TransformedBatch


class LoadError(RuntimeError):
    pass


class LoadService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(self, batch: TransformedBatch, dry_run: bool = False) -> int:
        if dry_run:
            return len(batch.documents)

        if self.settings.etl_mock_mode:
            return len(batch.documents)

        if not self.settings.etl_discovery_engine_load_url:
            raise LoadError("SEARCH_APP_ETL_DISCOVERY_ENGINE_LOAD_URL is required")
        if not self.settings.etl_bigquery_table:
            raise LoadError("SEARCH_APP_ETL_BIGQUERY_TABLE is required")

        payload: dict[str, Any] = {
            "system": batch.system,
            "destination": {
                "type": "bigquery",
                "table": self.settings.etl_bigquery_table,
            },
            "documents": [
                {
                    "id": document.id,
                    "title": document.title,
                    "content": document.content,
                    "acl": document.acl,
                    "source": document.source,
                }
                for document in batch.documents
            ],
        }

        async with httpx.AsyncClient(timeout=self.settings.etl_request_timeout_seconds) as client:
            response = await client.post(
                self.settings.etl_discovery_engine_load_url,
                json=payload,
            )
            response.raise_for_status()

        return len(batch.documents)
