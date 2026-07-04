"""Kivy-free background-image selection for the OKF reader.

Mirrors the Barks Reader's pattern in miniature: a provider Protocol is the seam
between "what images suit this page" and the UI, and a pure chooser picks one at
random while avoiding an immediate repeat. okf_reader must stay independent of the
Barks packages (import-linter contract), so the provider speaks only in frontmatter
dicts and paths; an embedding app (or the launcher script) wires a root directory —
e.g. the Barks "Favourites" panels tree — from its own configuration.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


class ImageProvider(Protocol):
    """Source of candidate background images for a page."""

    def candidate_images(self, frontmatter: dict, page_path: Path) -> list[Path]:
        """Return the background candidates for a page (may be empty)."""
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

    def candidate_images(self, frontmatter: dict, page_path: Path) -> list[Path]:  # noqa: ARG002
        """Return the title-matched images, else the all-titles fallback pool."""
        title = frontmatter.get("title")
        if isinstance(title, str) and title:
            title_dir = self._root / title
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
