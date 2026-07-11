from __future__ import annotations

from pathlib import Path

from ..client import NotionError
from ..blocks import build_blocks_from_markdown


DESIGN_OUTLINE_PATH = Path(__file__).with_name("design_outline.md")


def build_design_outline_blocks() -> list[dict[str, object]]:
    if not DESIGN_OUTLINE_PATH.exists():
        raise NotionError(f"Missing outline file: {DESIGN_OUTLINE_PATH}")
    return build_blocks_from_markdown(DESIGN_OUTLINE_PATH.read_text(encoding="utf-8"))
