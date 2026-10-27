# ruff: noqa: SLF001
# cspell:ignore getbbox getextrema frombytes
"""A page built at the scale a window needs, against the same page built whole and shrunk.

A reader's window is a fraction of the book's page, so it asks the builder for a
page at that fraction rather than shrinking the whole page afterwards. The two
must agree: same size, same layout, the panels and bars in the same places; only
the page number, lettered small rather than shrunk, may differ a little.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pytest
from barks_build_comic_images.build_comic_images import (
    FULL_SCALE,
    BuildScale,
    ComicBookImageBuilder,
    get_build_scale,
)
from barks_fantagraphics.comics_consts import DEST_TARGET_HEIGHT, DEST_TARGET_WIDTH, PageType
from barks_fantagraphics.page_classes import CleanPage, RequiredDimensions
from barks_fantagraphics.panel_geometry import BoundingBox
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat

if TYPE_CHECKING:
    from pathlib import Path

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 30, 30)
# A 1440p window, as the reader asks: the 2120x3200 page fits it at 954x1440.
WINDOW = (2560, 1440)
WINDOW_PAGE = (954, 1440)


def _builder(tmp_path: Path) -> ComicBookImageBuilder:
    empty_page = tmp_path / "empty.png"
    Image.new("RGB", (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT), WHITE).save(empty_page)
    builder = ComicBookImageBuilder(None, empty_page)  # ty: ignore[invalid-argument-type]
    builder.set_required_dim(RequiredDimensions(page_num_y_bottom=120))
    return builder


def _page(page_type: PageType, bbox: BoundingBox | None = None) -> CleanPage:
    page = CleanPage("page-012.jpg", page_type, page_num=12)
    if bbox is not None:
        page.panels_bbox = bbox
    return page


def _panels_source() -> Image.Image:
    """Return a scan: a red panels region with a black strip across it, on a white page."""
    scan = Image.new("RGB", (1100, 1500), WHITE)
    scan.paste(RED, (100, 100, 1000, 1400))
    scan.paste(BLACK, (100, 700, 1000, 760))
    return scan


SRCE_BBOX = BoundingBox(100, 100, 999, 1399)
DEST_BBOX = BoundingBox(100, 209, 2019, 2990)
# A scan twice the size, its panels box on odd edges: halved, every edge falls
# between two pixels.
BIG_SCAN_SIZE = (2200, 3000)
BIG_SRCE_BBOX = BoundingBox(201, 201, 1999, 2799)


def _textured_panels_source() -> Image.Image:
    """Return a scan whose panels are a soft grain: a part-pixel shift of it shows."""
    width, height = BIG_SRCE_BBOX.get_width() + 1, BIG_SRCE_BBOX.get_height() + 1
    grain = Image.frombytes("L", (width, height), random.Random(1).randbytes(width * height))
    scan = Image.new("RGB", BIG_SCAN_SIZE, WHITE)
    scan.paste(grain.filter(ImageFilter.GaussianBlur(1.5)).convert("RGB"), (201, 201))
    return scan


def _mean_difference(a: Image.Image, b: Image.Image) -> float:
    return max(ImageStat.Stat(ImageChops.difference(a, b)).mean)


class TestGetBuildScale:
    def test_no_box_is_the_books_size(self) -> None:
        assert get_build_scale(PageType.BODY, None) is FULL_SCALE

    def test_a_title_page_is_built_whole_whatever_the_box(self) -> None:
        assert get_build_scale(PageType.TITLE, (100, 100)) is FULL_SCALE

    @pytest.mark.parametrize("box", [(DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT), (5000, 5000)])
    def test_a_box_the_page_fits_is_the_books_size(self, box: tuple[int, int]) -> None:
        """A page is never built larger than the book's."""
        assert get_build_scale(PageType.BODY, box) is FULL_SCALE

    def test_a_window_gives_the_size_the_page_takes_in_it(self) -> None:
        scale = get_build_scale(PageType.BODY, WINDOW)

        assert (scale.width, scale.height) == WINDOW_PAGE
        assert scale.factor == pytest.approx(0.45, abs=0.001)
        assert not scale.is_full

    def test_a_length_scales_by_the_factor(self) -> None:
        assert BuildScale(0.5, 1060, 1600).of(301) == 150  # noqa: PLR2004
        assert FULL_SCALE.of(301) == 301  # noqa: PLR2004


class TestAPanelsPageAtWindowScale:
    def test_it_is_the_size_the_page_takes_in_the_window(self, tmp_path: Path) -> None:
        page = _builder(tmp_path).get_dest_page_image(
            _panels_source(),
            _page(PageType.BODY, SRCE_BBOX),
            _page(PageType.BODY, DEST_BBOX),
            fit_within=WINDOW,
        )

        assert page.size == WINDOW_PAGE
        assert page.mode == "RGB"

    def test_it_matches_the_whole_page_shrunk(self, tmp_path: Path) -> None:
        """Panels, strip and margins land where the shrunk full build puts them."""
        builder = _builder(tmp_path)
        srce, dest = _page(PageType.BODY, SRCE_BBOX), _page(PageType.BODY, DEST_BBOX)

        whole = builder.get_dest_page_image(_panels_source(), srce, dest)
        shrunk = ImageOps.contain(whole, WINDOW, Image.Resampling.LANCZOS)
        at_scale = builder.get_dest_page_image(_panels_source(), srce, dest, fit_within=WINDOW)

        assert shrunk.size == at_scale.size
        assert _mean_difference(shrunk, at_scale) < 1.0
        # The black strip, a known row of the panels, is where the shrunk page has it.
        assert at_scale.getpixel((477, 700)) == BLACK
        assert shrunk.getpixel((477, 700)) == BLACK
        assert at_scale.getpixel((477, 100)) == RED

    def test_the_page_number_is_lettered_at_the_small_size(self, tmp_path: Path) -> None:
        """The number is drawn, within its scaled box at the page's foot, and is dark."""
        page = _builder(tmp_path).get_dest_page_image(
            _panels_source(),
            _page(PageType.BODY, SRCE_BBOX),
            _page(PageType.BODY, DEST_BBOX),
            fit_within=WINDOW,
        )

        foot = page.crop((0, 1440 - round(120 * 0.45) - round(40 * 0.45), 954, 1440))
        assert foot.getbbox() is not None  # not all white: the number is there
        darkest = foot.convert("L").getextrema()[0]
        assert isinstance(darkest, int)
        assert darkest < 128  # noqa: PLR2004

    def test_no_box_builds_the_book_page_as_before(self, tmp_path: Path) -> None:
        builder = _builder(tmp_path)
        srce, dest = _page(PageType.BODY, SRCE_BBOX), _page(PageType.BODY, DEST_BBOX)

        page = builder.get_dest_page_image(_panels_source(), srce, dest)

        assert page.size == (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT)
        assert (
            page.tobytes()
            == builder.get_dest_page_image(
                _panels_source(), srce, dest, fit_within=(9000, 9000)
            ).tobytes()
        )


class TestASingleImagePageAtWindowScale:
    def test_a_cover_keeps_its_black_bars_in_proportion(self, tmp_path: Path) -> None:
        """A square cover on the tall page: black above and below, the cover between."""
        cover = Image.new("RGB", (400, 400), RED)
        page_type = PageType.COVER

        page = _builder(tmp_path).get_dest_page_image(
            cover, _page(page_type), _page(page_type), fit_within=WINDOW
        )

        assert page.size == WINDOW_PAGE
        bar = (1440 - 954) // 2
        assert page.getpixel((477, bar // 2)) == BLACK
        assert page.getpixel((477, 720)) == RED
        assert page.getpixel((477, 1440 - bar // 2)) == BLACK

    def test_a_page_that_fills_the_book_page_fills_the_window_page(self, tmp_path: Path) -> None:
        """Rounding at the reduced scale must not leave a one-pixel bar."""
        full_page = Image.new("RGB", (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT), RED)
        page_type = PageType.FRONT

        page = _builder(tmp_path).get_dest_page_image(
            full_page, _page(page_type), _page(page_type), fit_within=WINDOW
        )

        assert page.size == WINDOW_PAGE
        assert page.getpixel((0, 0)) == RED
        assert page.getpixel((953, 1439)) == RED

    def test_a_blank_page_is_the_window_page(self, tmp_path: Path) -> None:
        page = _builder(tmp_path).get_dest_page_image(
            Image.new("RGB", (10, 10), WHITE),
            _page(PageType.BLANK_PAGE),
            _page(PageType.BLANK_PAGE),
            fit_within=WINDOW,
        )

        assert page.size == WINDOW_PAGE

    def test_the_empty_page_is_shrunk_once_per_scale(self, tmp_path: Path) -> None:
        builder = _builder(tmp_path)
        scale = get_build_scale(PageType.BODY, WINDOW)

        first = builder._get_empty_page_image(scale)
        second = builder._get_empty_page_image(scale)

        assert first is second
        assert first.size == WINDOW_PAGE
        assert builder._get_empty_page_image(FULL_SCALE) is builder._empty_page_image


class TestTheSourceSizeNeeded:
    """How small the scan may be decoded for a page built at the window's scale."""

    SRCE_SIZE = (2216, 3056)
    SRCE_BBOX = BoundingBox(231, 195, 2066, 2850)
    DEST_BBOX = BoundingBox(100, 209, 2019, 2990)

    def test_a_panels_page_needs_its_panels_at_their_small_size(self) -> None:
        needed = ComicBookImageBuilder.get_source_size_needed(
            _page(PageType.BODY, self.SRCE_BBOX),
            _page(PageType.BODY, self.DEST_BBOX),
            self.SRCE_SIZE,
            WINDOW,
        )

        # The panels, 1836x2656 in the scan, become 864x1252 on the page: 0.4714 of
        # the scan by height, the tighter of the two.
        assert needed == (1045, 1441)

    def test_a_single_image_page_needs_itself_at_the_page_size(self) -> None:
        needed = ComicBookImageBuilder.get_source_size_needed(
            _page(PageType.COVER), _page(PageType.COVER), (2120, 3000), WINDOW
        )

        # 954 wide is 0.45 of the scan; 1440 tall is 0.48: the tighter wins.
        assert needed == (1018, 1440)

    @pytest.mark.parametrize(
        "page_type", [PageType.TITLE, PageType.SPLASH, PageType.PAINTING, PageType.BACK_PAINTING]
    )
    def test_a_page_measured_in_scan_pixels_needs_the_whole_scan(self, page_type: PageType) -> None:
        assert (
            ComicBookImageBuilder.get_source_size_needed(
                _page(page_type), _page(page_type), self.SRCE_SIZE, WINDOW
            )
            is None
        )

    def test_a_page_built_at_the_books_size_needs_the_whole_scan(self) -> None:
        assert (
            ComicBookImageBuilder.get_source_size_needed(
                _page(PageType.BODY, self.SRCE_BBOX),
                _page(PageType.BODY, self.DEST_BBOX),
                self.SRCE_SIZE,
                (9000, 9000),
            )
            is None
        )

    def test_a_scan_smaller_than_its_page_needs_all_of_itself(self) -> None:
        """A small scan is enlarged onto the page: nothing to gain from decoding less."""
        assert (
            ComicBookImageBuilder.get_source_size_needed(
                _page(PageType.COVER), _page(PageType.COVER), (400, 600), WINDOW
            )
            is None
        )


class TestAPageFromAReducedScan:
    def test_it_matches_the_page_from_the_whole_scan(self, tmp_path: Path) -> None:
        """The scan shrunk to the size the builder asked for builds the same page."""
        builder = _builder(tmp_path)
        srce, dest = _page(PageType.BODY, SRCE_BBOX), _page(PageType.BODY, DEST_BBOX)
        scan = _panels_source()
        needed = builder.get_source_size_needed(srce, dest, scan.size, WINDOW)
        assert needed is not None
        reduced = scan.resize(needed, Image.Resampling.LANCZOS)

        from_whole = builder.get_dest_page_image(scan, srce, dest, fit_within=WINDOW)
        from_reduced = builder.get_dest_page_image(
            reduced, srce, dest, fit_within=WINDOW, srce_scale=needed[0] / scan.width
        )

        assert from_reduced.size == from_whole.size == WINDOW_PAGE
        assert _mean_difference(from_whole, from_reduced) < 1.0
        assert from_reduced.getpixel((477, 700)) == BLACK
        assert from_reduced.getpixel((477, 100)) == RED

    def test_a_half_scan_with_odd_box_edges_lands_where_the_whole_scan_does(
        self, tmp_path: Path
    ) -> None:
        """Halved, the panels box's edges fall between pixels; the page must not shift.

        Rounding the halved box to whole pixels moves the panels half a scan pixel,
        which on grain measures over 3/255 against the page from the whole scan; the
        resize takes the exact box instead.
        """
        builder = _builder(tmp_path)
        srce, dest = _page(PageType.BODY, BIG_SRCE_BBOX), _page(PageType.BODY, DEST_BBOX)
        scan = _textured_panels_source()
        half = scan.resize((scan.width // 2, scan.height // 2), Image.Resampling.LANCZOS)

        from_whole = builder.get_dest_page_image(scan, srce, dest, fit_within=WINDOW)
        from_half = builder.get_dest_page_image(half, srce, dest, fit_within=WINDOW, srce_scale=0.5)

        assert from_half.size == from_whole.size == WINDOW_PAGE
        assert _mean_difference(from_whole, from_half) < 1.0

    def test_the_crop_takes_whole_pixels_and_names_the_exact_box_within(self) -> None:
        srce = _page(PageType.BODY, BIG_SRCE_BBOX)
        half = Image.new("RGB", (1100, 1500), WHITE)

        crop, box = ComicBookImageBuilder._crop_panels(half, srce, 0.5)

        assert crop.size == (900, 1300)  # pixels 100..999 and 100..1399
        assert box == (0.5, 0.5, 899.5, 1299.5)

    def test_a_whole_scan_is_cropped_on_its_box_as_it_is(self) -> None:
        srce = _page(PageType.BODY, SRCE_BBOX)

        crop, box = ComicBookImageBuilder._crop_panels(_panels_source(), srce, 1.0)

        assert crop.size == (899, 1299)
        assert box is None

    def test_a_page_measured_in_scan_pixels_refuses_a_reduced_scan(self, tmp_path: Path) -> None:
        with pytest.raises(AssertionError):
            _builder(tmp_path).get_dest_page_image(
                Image.new("RGB", (400, 400), RED),
                _page(PageType.PAINTING),
                _page(PageType.PAINTING),
                fit_within=WINDOW,
                srce_scale=0.5,
            )
