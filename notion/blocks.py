from __future__ import annotations

from typing import Any


def paragraph(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
        },
    }


def heading(text: str, level: int = 2) -> dict[str, Any]:
    block_type = {1: "heading_1", 2: "heading_2", 3: "heading_3"}.get(level, "heading_2")
    return {
        "object": "block",
        "type": block_type,
        block_type: {
            "rich_text": [{"type": "text", "text": {"content": text}}],
        },
    }


def bullet(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [{"type": "text", "text": {"content": text}}],
        },
    }


def build_blocks_from_markdown(markdown_text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            blocks.append(heading(stripped[2:].strip(), 1))
            continue
        if stripped.startswith("## "):
            blocks.append(heading(stripped[3:].strip(), 2))
            continue
        if stripped.startswith("### "):
            blocks.append(heading(stripped[4:].strip(), 3))
            continue
        if stripped.startswith("- "):
            blocks.append(bullet(stripped[2:].strip()))
            continue
        blocks.append(paragraph(stripped))
    return blocks
