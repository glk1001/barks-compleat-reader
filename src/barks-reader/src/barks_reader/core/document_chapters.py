"""Document chapters found on disk: a folder of document folders, one tree node each.

A many-part document, such as the illustrated history, is a folder holding one folder of page
images per part (``illustrated-history/03-learning-the-medium/page-001.png``, ...). Each part
folder names itself in a ``document.json`` beside its pages, ``{"title": "Learning the
Medium"}``, so a new part needs no code change. The barks-wiki illustrated history writes
these folders (``barks-wiki/scripts/history_reader.py``).

The parts come in folder-name order. A folder with no page images is left out; one with no
readable ``document.json`` is titled by its folder name, with a warning. A missing root
means no parts: the folder is optional, so it is not among the reader's required directories.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from . import log_markers

if TYPE_CHECKING:
    from pathlib import Path

PAGE_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png"})
DOCUMENT_INFO_FILE = "document.json"


@dataclass(frozen=True, slots=True)
class DocumentChapter:
    """One part of a many-part document: its folder of pages and its title."""

    doc_dir: Path
    title: str


def has_page_images(doc_dir: Path) -> bool:
    """Return whether a folder holds at least one page image.

    Args:
        doc_dir: The folder.

    Returns:
        True if any file in it has a page-image extension.

    """
    return any(p.suffix.lower() in PAGE_IMAGE_EXTENSIONS for p in doc_dir.iterdir())


def find_document_chapters(root: Path) -> list[DocumentChapter]:
    """Return the parts of a many-part document, in folder-name order.

    Args:
        root: The folder holding one folder per part.

    Returns:
        The parts; none when the root does not exist.

    """
    if not root.is_dir():
        return []
    chapters = []
    for doc_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if not has_page_images(doc_dir):
            logger.debug(log_markers.DOCUMENT_CHAPTER_NO_PAGES.format(path=doc_dir))
            continue
        chapters.append(DocumentChapter(doc_dir, _chapter_title(doc_dir)))
    return chapters


def _chapter_title(doc_dir: Path) -> str:
    info_path = doc_dir / DOCUMENT_INFO_FILE
    try:
        title = json.loads(info_path.read_text(encoding="utf-8"))["title"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        logger.warning(log_markers.DOCUMENT_CHAPTER_UNTITLED.format(path=info_path, error=e))
        return doc_dir.name
    if not isinstance(title, str) or not title.strip():
        logger.warning(
            log_markers.DOCUMENT_CHAPTER_UNTITLED.format(path=info_path, error="no title")
        )
        return doc_dir.name
    return title.strip()
