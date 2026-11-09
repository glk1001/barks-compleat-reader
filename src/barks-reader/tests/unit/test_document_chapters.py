"""Document chapters found on disk: order, titles, and the folders left out."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from barks_reader.core import log_markers
from barks_reader.core.document_chapters import DocumentChapter, find_document_chapters

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_REAL_ITERDIR = Path.iterdir


def _listing_refused_for(locked: Path) -> Callable[[Path], Iterator[Path]]:
    """Return a `Path.iterdir` that refuses `locked`, as bad permissions after a copy do."""

    def iterdir(path: Path) -> Iterator[Path]:
        if path == locked:
            msg = f"Permission denied: '{path}'"
            raise PermissionError(msg)
        return _REAL_ITERDIR(path)

    return iterdir


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


def test_a_folder_without_pages_is_left_out_and_the_rest_kept(
    tmp_path: Path, loguru_sink: list[str]
) -> None:
    not_yet = _chapter(tmp_path, "05-not-yet", {"title": "Not Yet"}, pages=False)
    later = _chapter(tmp_path, "06-later", {"title": "Later"})
    assert find_document_chapters(tmp_path) == [DocumentChapter(later, "Later")]
    assert log_markers.DOCUMENT_CHAPTER_NO_PAGES.format(path=not_yet) in loguru_sink


def test_a_folder_that_cannot_be_listed_is_left_out_and_the_rest_kept(
    tmp_path: Path, loguru_sink: list[str]
) -> None:
    locked = _chapter(tmp_path, "03-locked", {"title": "Locked"})
    later = _chapter(tmp_path, "04-later", {"title": "Later"})

    with patch.object(Path, Path.iterdir.__name__, _listing_refused_for(locked)):
        chapters = find_document_chapters(tmp_path)

    assert chapters == [DocumentChapter(later, "Later")]
    assert (
        log_markers.DOCUMENT_FOLDER_UNREADABLE.format(
            path=locked, error=f"Permission denied: '{locked}'"
        )
        in loguru_sink
    )


def test_a_root_that_cannot_be_listed_has_no_chapters(
    tmp_path: Path, loguru_sink: list[str]
) -> None:
    _chapter(tmp_path, "00-introduction", {"title": "Introduction"})

    with patch.object(Path, Path.iterdir.__name__, _listing_refused_for(tmp_path)):
        assert find_document_chapters(tmp_path) == []
    assert (
        log_markers.DOCUMENT_FOLDER_UNREADABLE.format(
            path=tmp_path, error=f"Permission denied: '{tmp_path}'"
        )
        in loguru_sink
    )


def test_a_chapter_without_a_title_is_named_by_its_folder(
    tmp_path: Path, loguru_sink: list[str]
) -> None:
    no_info = _chapter(tmp_path, "01-no-info", None)
    blank = _chapter(tmp_path, "02-blank", {"title": "  "})
    assert find_document_chapters(tmp_path) == [
        DocumentChapter(no_info, "01-no-info"),
        DocumentChapter(blank, "02-blank"),
    ]
    no_info_path = no_info / "document.json"
    with pytest.raises(FileNotFoundError) as error:
        no_info_path.read_text(encoding="utf-8")
    assert [line for line in loguru_sink if "titled by its folder" in line] == [
        log_markers.DOCUMENT_CHAPTER_UNTITLED.format(path=no_info_path, error=error.value),
        log_markers.DOCUMENT_CHAPTER_UNTITLED.format(
            path=blank / "document.json", error="no title"
        ),
    ]
