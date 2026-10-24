"""Document chapters found on disk: order, titles, and the folders left out."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from barks_reader.core.document_chapters import DocumentChapter, find_document_chapters

if TYPE_CHECKING:
    from pathlib import Path


def _chapter(root: Path, name: str, info: object | None, *, pages: bool = True) -> Path:
    doc_dir = root / name
    doc_dir.mkdir(parents=True)
    if pages:
        (doc_dir / "page-001.png").write_bytes(b"")
    if info is not None:
        (doc_dir / "document.json").write_text(json.dumps(info), encoding="utf-8")
    return doc_dir


def test_a_missing_root_has_no_chapters(tmp_path: Path) -> None:
    assert find_document_chapters(tmp_path / "illustrated-history") == []


def test_chapters_come_in_folder_name_order_titled_by_their_info(tmp_path: Path) -> None:
    later = _chapter(tmp_path, "04-becoming-himself", {"title": "Becoming Himself"})
    first = _chapter(tmp_path, "00-introduction", {"title": " Introduction "})
    (tmp_path / "notes.txt").write_text("not a chapter", encoding="utf-8")
    assert find_document_chapters(tmp_path) == [
        DocumentChapter(first, "Introduction"),
        DocumentChapter(later, "Becoming Himself"),
    ]


def test_a_folder_without_pages_is_left_out(tmp_path: Path) -> None:
    _chapter(tmp_path, "05-not-yet", {"title": "Not Yet"}, pages=False)
    assert find_document_chapters(tmp_path) == []


def test_a_chapter_without_a_title_is_named_by_its_folder(
    tmp_path: Path, loguru_sink: list[str]
) -> None:
    no_info = _chapter(tmp_path, "01-no-info", None)
    blank = _chapter(tmp_path, "02-blank", {"title": "  "})
    assert find_document_chapters(tmp_path) == [
        DocumentChapter(no_info, "01-no-info"),
        DocumentChapter(blank, "02-blank"),
    ]
    assert sum("titled by its folder" in line for line in loguru_sink) == 2  # noqa: PLR2004
