from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.etl.extract import ExtractedBatch


@dataclass
class DiscoveryDocument:
    id: str
    title: str
    content: str
    acl: dict[str, list[str]]
    source: str


@dataclass
class TransformedBatch:
    system: str
    documents: list[DiscoveryDocument]


class TransformService:
    def run(self, batch: ExtractedBatch) -> TransformedBatch:
        documents: list[DiscoveryDocument] = []
        for index, record in enumerate(batch.records):
            record_id = str(record.get("id") or record.get("document_id") or f"{batch.system}-{index}")
            title = str(record.get("title") or record.get("name") or record_id)
            content = str(record.get("content") or record.get("body") or record.get("summary") or "")
            documents.append(
                DiscoveryDocument(
                    id=record_id,
                    title=title,
                    content=content,
                    acl=self._extract_acl(record),
                    source=batch.system,
                )
            )

        return TransformedBatch(system=batch.system, documents=documents)

    def _extract_acl(self, record: dict[str, Any]) -> dict[str, list[str]]:
        return {
            "allowed_groups": self._as_string_list(record.get("allowed_groups")),
            "allowed_departments": self._as_string_list(record.get("allowed_departments")),
            "allowed_regions": self._as_string_list(record.get("allowed_regions")),
            "allowed_positions": self._as_string_list(record.get("allowed_positions")),
            "allowed_manager_ids": self._as_string_list(record.get("allowed_manager_ids")),
            "allowed_user_subs": self._as_string_list(record.get("allowed_user_subs")),
        }

    def _as_string_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        return [text] if text else []
