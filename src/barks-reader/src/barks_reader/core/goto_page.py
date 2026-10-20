"""The page a title offers to open at, and the pages the offer steps through. Kivy-free.

The title view's goto-page row shows one `GotoPageOffer`: the page last read, or a
tag's first page, with a tag's pages (and the page last read) a step away.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .reader_consts_and_types import COMIC_BEGIN_PAGE
from .reader_utils import get_page_run_end, get_page_run_starts, get_page_sort_key

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class GotoPageOffer:
    """A page offered to open a comic at, with the pages to step through; none by default.

    Attributes:
        page: The page offered, or "" for none.
        active: Whether the offer is ticked.
        tagged_pages: A tag's pages in the title, which name a run ("pages 16-23").
        pages: The pages the row steps through: the start of each run of the tag's,
            and the page offered or kept when it is none of them.

    """

    page: str = ""
    active: bool = False
    tagged_pages: tuple[str, ...] = ()
    pages: tuple[str, ...] = ()

    @classmethod
    def make(
        cls,
        page_to_goto: str = "",
        *,
        active: bool = False,
        tagged_pages: Sequence[str] = (),
        kept_page: str = "",
    ) -> GotoPageOffer:
        """Make an offer, working out the pages to step through.

        Args:
            page_to_goto: The page offered; none for "", or for the comic's beginning.
            active: Whether the offer starts ticked.
            tagged_pages: A tag's pages in the title, when the offer comes from a tag:
                the row then steps through the start of each run of them, and through
                the page offered when that is none of them. Any other offer has none.
            kept_page: Another page to step through with a tag's pages, though not the
                one offered: the page the comic was closed on, when a tag offers its own.

        Returns:
            The offer.

        """
        page = "" if page_to_goto == COMIC_BEGIN_PAGE else page_to_goto
        pages = get_page_run_starts(tagged_pages)
        if pages:
            extra_pages = {
                p for p in (page, kept_page) if p and p != COMIC_BEGIN_PAGE and p not in pages
            }
            if extra_pages:
                pages = sorted([*pages, *extra_pages], key=get_page_sort_key)
        return cls(page, active, tuple(tagged_pages), tuple(pages))

    @property
    def can_step(self) -> bool:
        """Whether there is more than one page to step through."""
        return len(self.pages) > 1

    @property
    def index(self) -> int | None:
        """The offered page's place among the pages to step through, or None if not among them."""
        return self.pages.index(self.page) if self.page in self.pages else None

    def stepped(self, delta: int) -> GotoPageOffer:
        """Return the offer of the next (or previous) page to step through, wrapping round, ticked.

        Args:
            delta: How many pages to move: 1 for the next, -1 for the previous.

        Returns:
            The new offer; this one when there is nothing to step through.

        """
        if not self.can_step:
            return self
        index = ((self.index or 0) + delta) % len(self.pages)
        return GotoPageOffer(
            page=self.pages[index], active=True, tagged_pages=self.tagged_pages, pages=self.pages
        )

    @property
    def run_end(self) -> str:
        """The last page of the run of a tag's pages the offered page starts, or ""."""
        return get_page_run_end(self.page, self.tagged_pages)

    @property
    def position(self) -> str:
        """The offered page's place in the pages to step through, " (2 of 3)", or ""."""
        if not self.can_step or self.index is None:
            return ""
        return f" ({self.index + 1} of {len(self.pages)})"

    @property
    def text(self) -> str:
        """The row's label: "Goto page 7 (1 of 3):", or "Goto pages 16-23:" for a run."""
        run_end = self.run_end
        pages = f"pages {self.page}-{run_end}" if run_end else f"page {self.page}"
        return f"Goto {pages}{self.position}:"


def goto_page_after_reading(last_read_page: str, tagged_pages: Sequence[str] = ()) -> GotoPageOffer:
    """Return the page to offer a title: the page last read, else a tag's first page, else none.

    Args:
        last_read_page: The page the comic was last read to; "" or the beginning for none.
        tagged_pages: A tag's pages in the title, when it is listed under one; kept a step
            away from the page last read, and the first of them offered with nothing read.

    Returns:
        The offer, ticked when there is a page; none otherwise.

    """
    if last_read_page and last_read_page != COMIC_BEGIN_PAGE:
        return GotoPageOffer.make(last_read_page, active=True, tagged_pages=tagged_pages)
    if tagged_pages:
        return GotoPageOffer.make(tagged_pages[0], active=True, tagged_pages=tagged_pages)
    return GotoPageOffer()
