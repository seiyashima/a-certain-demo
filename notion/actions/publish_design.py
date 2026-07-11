from __future__ import annotations

import os

from ..client import NotionClient, NotionError
from ..content.design import build_design_outline_blocks


def publish_design_outline(page_id: str) -> dict[str, object]:
    client = NotionClient()
    return client.append_blocks(page_id, build_design_outline_blocks())


def main() -> None:
    page_id = os.getenv("NOTION_PAGE_ID", "").strip()
    if not page_id:
        raise NotionError("NOTION_PAGE_ID is not set")

    action = os.getenv("NOTION_ACTION", "title").strip().lower()

    client = NotionClient()
    if action == "publish_design":
        publish_design_outline(page_id)
        print("published")
        return

    title = client.get_page_title(page_id)
    print(title)


if __name__ == "__main__":
    main()
