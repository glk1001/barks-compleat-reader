# ruff: noqa: SLF001
"""The page builder's rarer pages and its refusals.

A painting with its border drawn on, against one with black bars; a page that
comes out the wrong size for the book; panels pasted through an alpha mask; and
an intro inset that is missing, or that fails to decrypt. The pages are real
``CleanPage`` objects and the images real, small enough to build quickly.
"""

from __future__ import annotations

import io
import zipfile
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from barks_build_comic_images.build_comic_images import (
    SPLASH_BORDER_COLOR,
    ComicBookImageBuilder,
)
from barks_fantagraphics.comics_consts import DEST_TARGET_HEIGHT, DEST_TARGET_WIDTH, PageType
from barks_fantagraphics.page_classes import CleanPage
from barks_fantagraphics.panel_geometry import BoundingBox
from comic_utils.decryption import DecryptionError
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
# A square painting, centred on a page taller than it is wide: a band above and
# below it shows the page underneath.
PAINTING_SIZE = 400
PAINTING_TOP = (DEST_TARGET_HEIGHT - DEST_TARGET_WIDTH) // 2
# The band of the intro page an inset is fitted into.
INSET_TOP, INSET_BOTTOM = 100, 600


def _builder(
    tmp_path: Path, empty_size: tuple[int, int], inset: object = None, **kwargs: object
) -> ComicBookImageBuilder:
    empty_page = tmp_path / "empty.png"
    Image.new("RGB", empty_size, WHITE).save(empty_page)
    comic = MagicMock()
    comic.intro_inset_file = inset
    return ComicBookImageBuilder(comic, empty_page, **kwargs)  # ty: ignore[invalid-argument-type]


def _page(page_type: PageType, bbox: BoundingBox | None = None) -> CleanPage:
    page = CleanPage("page-012.jpg", page_type, page_num=12)
    if bbox is not None:
        page.panels_bbox = bbox
    return page


class TestPaintings:
    """A bordered painting sits on the empty page; a borderless one on black bars."""

    @pytest.mark.parametrize("page_type", [PageType.PAINTING, PageType.BACK_PAINTING])
    def test_a_bordered_painting_gets_its_border_and_the_empty_page(
        self, tmp_path: Path, page_type: PageType
    ) -> None:
        builder = _builder(tmp_path, (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT))
        painting = Image.new("RGB", (PAINTING_SIZE, PAINTING_SIZE), WHITE)

        page = builder.get_dest_page_image(painting, _page(page_type), _page(page_type))

        assert page.size == (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT)
        # The border is drawn on the painting itself, then scaled up with it.
        assert painting.getpixel((0, 0)) == SPLASH_BORDER_COLOR
        assert page.getpixel((DEST_TARGET_WIDTH // 2, PAINTING_TOP + 5)) == BLACK
        assert page.getpixel((DEST_TARGET_WIDTH // 2, DEST_TARGET_HEIGHT // 2)) == WHITE
        # Above the painting, the empty page, not a black bar.
        assert page.getpixel((DEST_TARGET_WIDTH // 2, PAINTING_TOP // 2)) == WHITE

    def test_a_borderless_painting_gets_black_bars_and_no_border(self, tmp_path: Path) -> None:
        builder = _builder(tmp_path, (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT))
        painting = Image.new("RGB", (PAINTING_SIZE, PAINTING_SIZE), WHITE)
        page_type = PageType.PAINTING_NO_BORDER

        page = builder.get_dest_page_image(painting, _page(page_type), _page(page_type))

        assert painting.getpixel((0, 0)) == WHITE
        assert page.getpixel((DEST_TARGET_WIDTH // 2, PAINTING_TOP // 2)) == BLACK


class TestTheBookSize:
    """A page with panels must come out at the book's size, or the build stops."""

    SRCE_BBOX = BoundingBox(0, 0, 49, 49)
    DEST_BBOX = BoundingBox(10, 10, 109, 109)

    def _build(self, builder: ComicBookImageBuilder) -> None:
        builder.get_dest_page_image(
            Image.new("RGB", (60, 60), WHITE),
            _page(PageType.BODY, self.SRCE_BBOX),
            _page(PageType.BODY, self.DEST_BBOX),
        )

    def test_a_page_too_narrow_is_refused_by_name(self, tmp_path: Path) -> None:
        builder = _builder(tmp_path, (DEST_TARGET_WIDTH - 1, DEST_TARGET_HEIGHT))
        with pytest.raises(RuntimeError, match=r'Width mismatch for page "page-012\.jpg"'):
            self._build(builder)

    def test_a_page_too_short_is_refused_by_name(self, tmp_path: Path) -> None:
        builder = _builder(tmp_path, (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT - 1))
        with pytest.raises(RuntimeError, match=r'Height mismatch for page "page-012\.jpg"'):
            self._build(builder)


def test_panels_and_their_mask_are_scaled_together_to_the_dest_panels() -> None:
    """With an alpha source the paste mask goes with the panels, at the same size."""
    dest_page = _page(PageType.BODY, BoundingBox(0, 0, 99, 49))
    panels = Image.new("RGB", (20, 10), WHITE)
    mask = Image.new("L", (20, 10), 255)

    scaled, scaled_mask = ComicBookImageBuilder._get_resized_srce_images(dest_page, panels, mask)

    assert scaled.size == (100, 50)
    assert scaled_mask is not None
    assert scaled_mask.size == (100, 50)


class TestTheIntroInset:
    def test_a_title_page_without_its_inset_file_is_refused(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing-inset.png"
        builder = _builder(tmp_path, (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT), inset=missing)

        with pytest.raises(FileNotFoundError, match="Could not find inset file") as raised:
            builder.get_dest_page_image(
                Image.new("RGB", (40, 60), WHITE),
                _page(PageType.TITLE),
                _page(PageType.TITLE),
            )

        assert str(missing) in str(raised.value)

    @staticmethod
    def _inset_in_a_zip(tmp_path: Path) -> zipfile.Path:
        """Return an inset inside an archive, as the reader's insets come: no plain Path."""
        image = io.BytesIO()
        Image.new("RGB", (30, 20), WHITE).save(image, format="PNG")
        archive = tmp_path / "insets.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("Insets/Lost in the Andes.png", image.getvalue())
        return zipfile.Path(archive, "Insets/Lost in the Andes.png")

    def test_an_inset_that_decrypts_to_nothing_is_refused_by_name(self, tmp_path: Path) -> None:
        builder = _builder(
            tmp_path,
            (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT),
            inset=self._inset_in_a_zip(tmp_path),
            get_inset_decrypted_bytes=lambda _: b"",
        )

        with pytest.raises(DecryptionError, match="Lost in the Andes"):
            builder._get_resized_inset(INSET_TOP, INSET_BOTTOM, DEST_TARGET_WIDTH)

    def test_a_decrypted_inset_is_scaled_into_the_space_it_is_given(self, tmp_path: Path) -> None:
        builder = _builder(
            tmp_path,
            (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT),
            inset=self._inset_in_a_zip(tmp_path),
            get_inset_decrypted_bytes=lambda data: data,
        )

        (left, top), inset = builder._get_resized_inset(INSET_TOP, INSET_BOTTOM, DEST_TARGET_WIDTH)

        assert inset.height <= INSET_BOTTOM - INSET_TOP
        assert inset.width / inset.height == pytest.approx(30 / 20, rel=0.02)
        assert left == (DEST_TARGET_WIDTH - inset.width) // 2
        assert INSET_TOP <= top <= INSET_BOTTOM - inset.height
