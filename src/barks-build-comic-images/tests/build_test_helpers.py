# cspell:ignore getbbox
"""What the page builder's tests share: a builder on a plain page, a page, and where ink is."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from barks_build_comic_images.build_comic_images import ComicBookImageBuilder
from barks_fantagraphics.comics_consts import DEST_TARGET_HEIGHT, DEST_TARGET_WIDTH, PageType
from barks_fantagraphics.page_classes import CleanPage
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path

    from barks_fantagraphics.panel_geometry import BoundingBox

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BOOK_PAGE_SIZE = (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT)
# The size the comics' own titles are lettered at, and their font files name.
TITLE_FONT_SIZE = 155
# A pixel is ink if it is darker than this; gaps are measured on visible ink, which a
# font's bounding box overshoots by a pixel or few.
INK_THRESHOLD = 250


def make_builder(
    tmp_path: Path,
    empty_size: tuple[int, int] = BOOK_PAGE_SIZE,
    inset: object = None,
    comic: MagicMock | None = None,
    **kwargs: object,
) -> ComicBookImageBuilder:
    """Return a builder whose empty page is plain white, of `empty_size`."""
    empty_page = tmp_path / "empty.png"
    Image.new("RGB", empty_size, WHITE).save(empty_page)
    comic = comic or MagicMock()
    comic.intro_inset_file = inset
    return ComicBookImageBuilder(comic, empty_page, **kwargs)  # ty: ignore[invalid-argument-type]


def make_page(page_type: PageType, bbox: BoundingBox | None = None) -> CleanPage:
    """Return page 12 of `page_type`, with `bbox` as its panels box if one is given."""
    page = CleanPage("page-012.jpg", page_type, page_num=12)
    if bbox is not None:
        page.panels_bbox = bbox
    return page


def ink_mask(image: Image.Image) -> Image.Image:
    """Return `image` as a mask: white where it has ink, black elsewhere."""
    return image.convert("L").point(lambda p: 255 if p < INK_THRESHOLD else 0)


def ink_rows(page: Image.Image) -> list[int]:
    """Return every row of `page` with ink on it, top to bottom."""
    ink = ink_mask(page)
    return [y for y in range(page.height) if ink.crop((0, y, page.width, y + 1)).getbbox()]


def ink_bands(page: Image.Image) -> list[tuple[int, int]]:
    """Return the first and last row of each run of ink rows, top to bottom."""
    rows = ink_rows(page)
    bands = [(rows[0], rows[0])]
    for y in rows[1:]:
        if y == bands[-1][1] + 1:
            bands[-1] = (bands[-1][0], y)
        else:
            bands.append((y, y))
    return bands
