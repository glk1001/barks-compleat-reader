"""Which page of a document is showing, and the moves between them. Kivy-free."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .display_unit import DisplayUnit, build_document_units

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class DocumentView:
    """What a document shows now: a page alone, or a pair on the two-page spread."""

    left: Path
    right: Path | None
    left_index: int
    right_index: int | None
    page_count: int


class DocumentPager:
    """The page walk of a folder of page images (``ui.document_reader``'s model).

    One page is current. Two-up, it shows with its pair, the pages paired from the first
    (``build_document_units``), and a step moves a pair; one-up it shows alone. Whether
    the pages show two-up is asked on each call: the layout can change under an open
    document.

    The pager outlives its documents: each folder's page is remembered as it is shown,
    for a later ``open`` with ``resume``.
    """

    def __init__(self) -> None:
        """Start with no document open and no page remembered."""
        self._doc_dir: Path | None = None
        self._pages: list[Path] = []
        self._units: list[DisplayUnit] = []
        self._unit_idx_for_index: dict[int, int] = {}
        self._current_page_index = 0
        self._last_page_indexes: dict[Path, int] = {}

    @property
    def is_open(self) -> bool:
        """Whether a document with pages is open."""
        return bool(self._pages)

    @property
    def page_count(self) -> int:
        """The open document's number of pages; none when closed."""
        return len(self._pages)

    @property
    def current_page_index(self) -> int:
        """The current page's index, from 0."""
        return self._current_page_index

    @property
    def doc_dir(self) -> Path | None:
        """The folder of the document last opened; None before the first."""
        return self._doc_dir

    def open(
        self, doc_dir: Path, pages: list[Path], *, resume: bool, at_last_page: bool = False
    ) -> None:
        """Open a document at its first page, the page last shown, or its last page.

        Args:
            doc_dir: The document's folder: what its page is remembered by.
            pages: The document's pages, in reading order.
            resume: Open at the page of this folder last shown, held inside the
                document should it have fewer pages now.
            at_last_page: Open at the last page (a turn back into the document from
                the one after it); `resume` is then ignored.

        """
        self._doc_dir = doc_dir
        self._pages = list(pages)
        self._units, self._unit_idx_for_index = build_document_units(len(self._pages))
        if at_last_page:
            last_index = len(self._pages) - 1
        else:
            last_index = self._last_page_indexes.get(doc_dir, 0) if resume else 0
        self._current_page_index = max(0, min(last_index, len(self._pages) - 1))

    def close(self) -> None:
        """Close the document: no pages, so no view. The remembered pages stay."""
        self._pages = []

    def view(self, *, two_up: bool) -> DocumentView | None:
        """Return what shows now, making its left page the current one and remembering it.

        Args:
            two_up: Whether the pages show in pairs.

        Returns:
            The page or pair, or None when there are no pages.

        """
        if not self._pages:
            return None

        unit = self._current_unit(two_up=two_up)
        self._current_page_index = unit.left_page_index
        if self._doc_dir is not None:
            self._last_page_indexes[self._doc_dir] = self._current_page_index

        right_index = unit.right_page_index
        return DocumentView(
            left=self._pages[unit.left_page_index],
            right=None if right_index is None else self._pages[right_index],
            left_index=unit.left_page_index,
            right_index=right_index,
            page_count=len(self._pages),
        )

    def next_page(self, *, two_up: bool) -> bool:
        """Go to the page after the last one showing, if there is one.

        Args:
            two_up: Whether the pages show in pairs.

        Returns:
            Whether the current page changed.

        """
        if not self._pages:
            return False  # an empty document has no unit to step on from
        unit = self._current_unit(two_up=two_up)
        last_shown = (
            unit.left_page_index if unit.right_page_index is None else unit.right_page_index
        )
        if last_shown >= len(self._pages) - 1:
            return False
        self._current_page_index = last_shown + 1
        return True

    def prev_page(self) -> bool:
        """Go back one page, or stay on the first.

        The page before the one showing's left: two-up, ``view`` then shows its pair.

        Returns:
            Whether the current page changed.

        """
        if not self._pages or self._current_page_index <= 0:
            return False
        self._current_page_index -= 1
        return True

    def _current_unit(self, *, two_up: bool) -> DisplayUnit:
        """Return what the current page shows: itself alone, or its pair two-up."""
        if two_up:
            return self._units[self._unit_idx_for_index[self._current_page_index]]
        return DisplayUnit(self._current_page_index, None)
