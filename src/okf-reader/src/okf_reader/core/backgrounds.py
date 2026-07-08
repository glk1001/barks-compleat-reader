"""Kivy-free background-image selection for the OKF reader.

Mirrors the Barks Reader's pattern in miniature: a provider Protocol is the seam
between "what image suits this page" and the UI. The provider owns selection —
stateful choosers (e.g. the Barks Reader's ImageSelector with its recently-used
tracking) cannot be reduced to a candidate list. okf_reader must stay independent
of the Barks packages (import-linter contract), so the provider speaks only in
frontmatter dicts and paths, and hands back either a plain image file or raw
image bytes (for sources the UI cannot open by filename, e.g. members of an
encrypted archive).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pathlib import Path

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


@dataclass(frozen=True)
class PageBackground:
    """One background image: a plain file on disk, or in-memory image bytes.

    Exactly one of ``path``/``data`` is set. ``ext`` (e.g. ``".png"``) tells the
    UI how to decode ``data``; it is informational for ``path``.
    """

    ext: str
    path: Path | None = None
    data: bytes | None = None


class ImageProvider(Protocol):
    """Source of the background image for a page."""

    def background_for(self, frontmatter: dict[str, Any], page_path: Path) -> PageBackground | None:
        """Return the background to show for a page, or None for no background."""
        ...


class DirPerTitleImageProvider:
    """Images organized one subdirectory per title: ``<root>/<title>/*.png``.

    A page whose frontmatter ``title`` matches a subdirectory gets that
    subdirectory's images; any other page falls back to the pool of all images
    under ``root`` (so every page can show *something*). The fallback pool is
    scanned once and cached.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._all_images: list[Path] | None = None  # lazy fallback pool
        self._last: Path | None = None

    def background_for(self, frontmatter: dict[str, Any], page_path: Path) -> PageBackground | None:
        """Return a random title-matched (else pool) image, avoiding an immediate repeat."""
        image = choose_image(self._candidate_images(frontmatter, page_path), self._last)
        self._last = image
        return None if image is None else PageBackground(ext=image.suffix, path=image)

    def _candidate_images(self, frontmatter: dict, page_path: Path) -> list[Path]:  # noqa: ARG002
        """Return the title-matched images, else the all-titles fallback pool."""
        title = frontmatter.get("title")
        if isinstance(title, str) and title:
            # Exact directory first, then the title minus filesystem-awkward
            # characters — image trees drop them from directory names (e.g. the
            # Barks panels dir for 'Adventure "Down Under"' is "Adventure Down
            # Under", and "Want to Buy an Island?" loses its "?").
            for name in (title, _strip_unsafe_filename_chars(title)):
                title_dir = self._root / name
                if title_dir.is_dir():
                    images = _image_files(title_dir)
                    if images:
                        return images
        if self._all_images is None:
            self._all_images = (
                sorted(
                    p
                    for p in self._root.rglob("*")
                    if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
                )
                if self._root.is_dir()
                else []
            )
        return self._all_images


def _strip_unsafe_filename_chars(title: str) -> str:
    return title.replace('"', "").replace("?", "")


def _image_files(directory: Path) -> list[Path]:
    return sorted(
        p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )


def choose_image(candidates: list[Path], last: Path | None) -> Path | None:
    """Randomly pick a candidate, avoiding an immediate repeat of ``last`` if possible."""
    if not candidates:
        return None
    pool = [c for c in candidates if c != last] or candidates
    return random.choice(pool)
