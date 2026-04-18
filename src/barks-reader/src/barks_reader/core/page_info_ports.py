from typing import Protocol, runtime_checkable

from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.page_classes import RequiredDimensions, SrceAndDestPages


@runtime_checkable
class SortedPagesPort(Protocol):
    """Produces ordered source/destination page pairs for a comic.

    Hides panel-segments JSON disk I/O, volume-title lookup, and the
    fantagraphics sorted-pages helper from core layout logic.
    """

    def get_sorted_pages(self, comic: ComicBook) -> SrceAndDestPages: ...


@runtime_checkable
class RequiredDimensionsPort(Protocol):
    """Computes rendering dimensions for a comic.

    Separate from SortedPagesPort so prebuilt-comic flows can skip the
    panel-segment I/O entirely by wiring ``None`` in place of an adapter.
    """

    def get_required_dimensions(self, comic: ComicBook) -> RequiredDimensions: ...
