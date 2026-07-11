from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, request


NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionError(RuntimeError):
    pass


@dataclass(frozen=True)
class NotionConfig:
    api_token: str

    @classmethod
    def from_env(cls) -> "NotionConfig":
        api_token = os.getenv("NOTION_API_TOKEN", "").strip()
        if not api_token:
            raise NotionError("NOTION_API_TOKEN is not set")
        return cls(api_token=api_token)


class NotionClient:
    def __init__(self, config: NotionConfig | None = None) -> None:
        self.config = config or NotionConfig.from_env()

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{NOTION_API_BASE}{path}"
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = request.Request(url, method=method, data=data)
        req.add_header("Authorization", f"Bearer {self.config.api_token}")
        req.add_header("Notion-Version", NOTION_VERSION)
        req.add_header("Content-Type", "application/json")

        try:
            with request.urlopen(req, timeout=20) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload) if payload else {}
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise NotionError(f"Notion API error {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise NotionError(f"Notion API request failed: {exc.reason}") from exc

    def get_page(self, page_id: str) -> dict[str, Any]:
        return self._request("GET", f"/pages/{page_id}")

    def get_page_title(self, page_id: str) -> str:
        page = self.get_page(page_id)
        title_parts = page.get("properties", {}).get("title", {}).get("title", [])
        plain_texts = [part.get("plain_text", "") for part in title_parts if part.get("plain_text")]
        return "".join(plain_texts) or page.get("id", "")

    def append_blocks(self, block_id: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        if not blocks:
            raise NotionError("blocks must not be empty")
        return self._request("PATCH", f"/blocks/{block_id}/children", {"children": blocks})
