"""Protocol for loading display-ready page images.

``PageImageSource`` hides all image I/O concerns (archive access, source
resolution, decryption, transformation, resizing) behind a single method.
``ComicBookLoader`` depends only on this protocol, keeping its own code
focused on prefetch orchestration and lifecycle management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .comic_book_page_info import PageInfo
    from .page_image import PageImage


@runtime_checkable
class PageImageSource(Protocol):
    """Resolves, loads, and transforms a single page image for display."""

    def load_page_image(self, page_info: PageInfo) -> PageImage:
        """Load and return a display-ready image for the given page.

        Args:
            page_info: Metadata identifying which page to load.

        Returns:
            The page resized for the window, as the pixels a texture takes.

        """
        ...

    def get_image_info_str(self, page_info: PageInfo) -> str:
        """Return a human-readable description of the image source for *page_info*."""
        ...
