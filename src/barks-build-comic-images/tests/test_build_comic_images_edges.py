# ruff: noqa: SLF001
# cspell:ignore getbbox
"""The page builder's rarer pages and its refusals.

A painting with its border drawn on, against one with black bars; a page that
comes out the wrong size for the book; panels pasted through an alpha mask; and
an intro inset that is missing, or that fails to decrypt. The pages are real
``CleanPage`` objects and the images real, small enough to build quickly.
"""

from __future__ import annotations

import io
import itertools
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from barks_build_comic_images.build_comic_images import (
    INTRO_INSET_BORDER_COLOR,
    INTRO_INSET_BORDER_WIDTH,
    INTRO_INSET_MIN_GAP,
    INTRO_PUB_CREDITS_COLOR,
    INTRO_PUB_CREDITS_LINE_ADVANCE,
    INTRO_PUB_PARAGRAPH_GAP,
    INTRO_PUB_TEXT_COLOR,
    INTRO_TITLE_BYLINE_GAP_SHARE,
    INTRO_TITLE_BYLINE_MIN_GAP,
    INTRO_TITLE_HYPHEN_GAP,
    INTRO_TITLE_OUTLINE_COLOR,
    INTRO_TITLE_OUTLINE_WIDTH,
    INTRO_TITLE_SMALL_WORD_SIZE_FRAC,
    INTRO_TITLE_SPACING,
    INTRO_TITLE_TRACKING,
    INTRO_TITLE_WORD_GAP,
    SPLASH_BORDER_COLOR,
    ComicBookImageBuilder,
    _PubTextLine,
)
from barks_fantagraphics.comics_consts import (
    CARL_BARKS_FONT_FILE,
    DEST_TARGET_HEIGHT,
    DEST_TARGET_WIDTH,
    INTRO_PUB_TEXT_BOLD_FONT_FILE,
    INTRO_PUB_TEXT_FONT_FILE,
    PageType,
)
from barks_fantagraphics.page_classes import CleanPage
from barks_fantagraphics.panel_geometry import BoundingBox
from comic_utils.decryption import DecryptionError
from PIL import Image, ImageChops, ImageDraw, ImageFont

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
# A square painting, centred on a page taller than it is wide: a band above and
# below it shows the page underneath.
PAINTING_SIZE = 400
PAINTING_TOP = (DEST_TARGET_HEIGHT - DEST_TARGET_WIDTH) // 2
# The box an intro inset is fitted into, and the 3:2 inset fitted.
INSET_MAX_WIDTH, INSET_MAX_HEIGHT = 600, 500
INSET_SIZE = (30, 20)
# On a laid-out intro page: a row is ink if any pixel is darker than this; gaps are
# measured on visible ink, which a font's bounding box overshoots by a pixel or few.
INK_THRESHOLD = 250
GAP_TOLERANCE = 4


def _builder(
    tmp_path: Path,
    empty_size: tuple[int, int],
    inset: object = None,
    comic: MagicMock | None = None,
    **kwargs: object,
) -> ComicBookImageBuilder:
    empty_page = tmp_path / "empty.png"
    Image.new("RGB", empty_size, WHITE).save(empty_page)
    comic = comic or MagicMock()
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
        Image.new("RGB", INSET_SIZE, WHITE).save(image, format="PNG")
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
            builder._get_resized_inset(INSET_MAX_WIDTH, INSET_MAX_HEIGHT)

    @pytest.mark.parametrize(
        ("max_width", "max_height", "expected_size"),
        [
            pytest.param(300, 1000, (300, 200), id="as-wide-as-allowed"),
            pytest.param(1000, 100, (150, 100), id="as-tall-as-allowed"),
        ],
    )
    def test_a_decrypted_inset_is_scaled_to_fill_its_box_keeping_its_shape(
        self,
        tmp_path: Path,
        max_width: int,
        max_height: int,
        expected_size: tuple[int, int],
    ) -> None:
        builder = _builder(
            tmp_path,
            (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT),
            inset=self._inset_in_a_zip(tmp_path),
            get_inset_decrypted_bytes=lambda data: data,
        )

        inset = builder._get_resized_inset(max_width, max_height)

        assert inset.size == expected_size

    def test_no_room_left_for_the_inset_is_refused_by_name(self, tmp_path: Path) -> None:
        inset = self._inset_in_a_zip(tmp_path)
        builder = _builder(tmp_path, (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT), inset=inset)

        with pytest.raises(ValueError, match=r"No room for the intro inset.*Lost in the Andes"):
            builder._get_resized_inset(INSET_MAX_WIDTH, 0)

    def test_the_inset_border_is_drawn_outside_the_art(self) -> None:
        image = Image.new("RGB", (200, 200), WHITE)
        left, top, b = 50, 60, INTRO_INSET_BORDER_WIDTH

        ComicBookImageBuilder._draw_inset_border(ImageDraw.Draw(image), left, top, 100, 80)

        assert image.getpixel((left - 1, top + 40)) == INTRO_INSET_BORDER_COLOR
        assert image.getpixel((left - b, top + 40)) == INTRO_INSET_BORDER_COLOR
        assert image.getpixel((left - b - 1, top + 40)) == WHITE
        assert image.getpixel((left, top + 40)) == WHITE  # the art's own first column
        assert image.getpixel((left + 50, top + 80 + b - 1)) == INTRO_INSET_BORDER_COLOR


PUBLICATION_TEXT = (
    "First published in Four Color #223, April 1949\n"
    "Submitted to Western Publishing on October 21st, 1948\n"
    "\n"
    "This edition published in Fantagraphics CBDL, Volume 7, 2011\n"
    "Color restoration by Rich Tommaso\n"
)


class TestThePublicationText:
    """The original publication in ink, its first line bold; this edition's credits in sepia."""

    @staticmethod
    def _lines(tmp_path: Path, text: str) -> list[_PubTextLine]:
        comic = MagicMock()
        comic.publication_text = text
        builder = _builder(tmp_path, (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT), comic=comic)
        return builder._get_publication_text_lines()

    def test_the_paragraphs_are_styled_by_what_they_say(self, tmp_path: Path) -> None:
        lines = self._lines(tmp_path, PUBLICATION_TEXT)

        assert [line.text for line in lines] == PUBLICATION_TEXT.strip("\n").replace(
            "\n\n", "\n"
        ).split("\n")
        assert [line.color for line in lines] == [
            INTRO_PUB_TEXT_COLOR,
            INTRO_PUB_TEXT_COLOR,
            INTRO_PUB_CREDITS_COLOR,
            INTRO_PUB_CREDITS_COLOR,
        ]
        assert [Path(str(line.font.path)).name for line in lines[:2]] == [
            Path(INTRO_PUB_TEXT_BOLD_FONT_FILE).name,
            Path(INTRO_PUB_TEXT_FONT_FILE).name,
        ]
        assert lines[2].font.size < lines[1].font.size
        # A paragraph break opens a gap; the lines within a paragraph do not.
        assert lines[2].advance == INTRO_PUB_CREDITS_LINE_ADVANCE + INTRO_PUB_PARAGRAPH_GAP
        assert lines[3].advance == INTRO_PUB_CREDITS_LINE_ADVANCE

    def test_a_story_with_no_edition_credits_is_all_in_ink(self, tmp_path: Path) -> None:
        lines = self._lines(tmp_path, PUBLICATION_TEXT.split("\n\n", maxsplit=1)[0])

        assert {line.color for line in lines} == {INTRO_PUB_TEXT_COLOR}

    def test_the_block_is_placed_by_the_top_of_its_ink(self, tmp_path: Path) -> None:
        lines = self._lines(tmp_path, PUBLICATION_TEXT)
        image = Image.new("RGB", (DEST_TARGET_WIDTH, 1000), WHITE)
        draw = ImageDraw.Draw(image)
        builder = _builder(tmp_path, (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT))
        top = 200

        builder._draw_publication_text(image, draw, lines, top)

        drawn = ImageChops.difference(image, Image.new("RGB", image.size, WHITE)).getbbox()
        assert drawn is not None
        assert abs(drawn[1] - top) <= 1
        assert abs(drawn[3] - (top + builder._get_publication_text_height(lines))) <= 1


class TestTheIntroPageLayout:
    """The title and the publication text are pinned; the room between them is shared."""

    INSET_COLOR = (0, 120, 255)
    TITLE_COLOR = (38, 104, 178)

    def _intro_page(self, tmp_path: Path, inset_size: tuple[int, int]) -> Image.Image:
        inset_file = tmp_path / f"inset-{inset_size[0]}x{inset_size[1]}.png"
        Image.new("RGB", inset_size, self.INSET_COLOR).save(inset_file)
        comic = MagicMock()
        comic.get_comic_title.return_value = "Lost in the\nAndes!"
        comic.title_font_file = CARL_BARKS_FONT_FILE
        comic.title_font_size = 155
        comic.title_color = self.TITLE_COLOR
        comic.author_font_size = 90
        comic.fanta_info.comic_book_info.is_barks_title = True
        comic.publication_text = PUBLICATION_TEXT
        builder = _builder(
            tmp_path, (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT), inset=inset_file, comic=comic
        )
        return builder._get_dest_title_page_image(Image.new("RGB", (40, 60), WHITE))

    @staticmethod
    def _ink_rows(page: Image.Image) -> list[int]:
        ink = page.convert("L").point(lambda p: 255 if p < INK_THRESHOLD else 0)
        return [y for y in range(page.height) if ink.crop((0, y, page.width, y + 1)).getbbox()]

    @classmethod
    def _ink_bands(cls, page: Image.Image) -> list[tuple[int, int]]:
        """Return the first and last row of each run of ink rows, top to bottom."""
        rows = cls._ink_rows(page)
        bands = [(rows[0], rows[0])]
        for y in rows[1:]:
            if y == bands[-1][1] + 1:
                bands[-1] = (bands[-1][0], y)
            else:
                bands.append((y, y))
        return bands

    def _inset_rows(self, page: Image.Image) -> tuple[int, int]:
        column = page.width // 2
        rows = [y for y in range(page.height) if page.getpixel((column, y)) == self.INSET_COLOR]
        return rows[0], rows[-1]

    def test_the_title_and_publication_text_are_pinned_whatever_the_inset(
        self, tmp_path: Path
    ) -> None:
        wide = self._ink_rows(self._intro_page(tmp_path, (300, 100)))
        tall = self._ink_rows(self._intro_page(tmp_path, (300, 400)))

        assert wide[0] == tall[0]
        assert wide[-1] == tall[-1]

    def test_spare_room_widens_the_byline_gap_by_a_smaller_share(self, tmp_path: Path) -> None:
        page = self._intro_page(tmp_path, (300, 100))
        inset_top, _ = self._inset_rows(page)
        # The border runs on into the inset, so the last two bands wholly above the
        # inset are the title's last line and the byline.
        above_inset = [band for band in self._ink_bands(page) if band[1] < inset_top]
        (_, title_bottom), (byline_top, byline_bottom) = above_inset[-2:]

        byline_gap = byline_top - title_bottom
        inset_gap = inset_top - byline_bottom
        assert byline_gap > INTRO_TITLE_BYLINE_MIN_GAP
        assert byline_gap / inset_gap == pytest.approx(INTRO_TITLE_BYLINE_GAP_SHARE, abs=0.03)

    @pytest.mark.parametrize("inset_size", [(300, 100), (300, 200), (300, 400)])
    def test_the_inset_is_centred_between_the_byline_and_the_publication_text(
        self, tmp_path: Path, inset_size: tuple[int, int]
    ) -> None:
        page = self._intro_page(tmp_path, inset_size)
        inset_top, inset_bottom = self._inset_rows(page)
        b = INTRO_INSET_BORDER_WIDTH
        ink = self._ink_rows(page)
        byline_bottom = max(y for y in ink if y < inset_top - b)
        text_top = min(y for y in ink if y > inset_bottom + b)

        above = inset_top - byline_bottom
        below = text_top - inset_bottom
        assert abs(above - below) <= GAP_TOLERANCE
        assert above >= INTRO_INSET_MIN_GAP
        assert page.getpixel((page.width // 2, inset_top - 1)) == INTRO_INSET_BORDER_COLOR


class TestTheIntroTitle:
    """The title is in its colour inside a black outline, its letters spaced apart."""

    @staticmethod
    def _font(size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(CARL_BARKS_FONT_FILE, size)

    @staticmethod
    def _color_mask(image: Image.Image, color: tuple[int, int, int]) -> Image.Image:
        """Return a mask of the pixels that are exactly `color`."""
        red, green, blue = ImageChops.difference(image, Image.new("RGB", image.size, color)).split()
        off = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        return off.point(lambda v: 255 if v == 0 else 0)

    def test_the_title_colour_sits_inside_a_black_outline(self, tmp_path: Path) -> None:
        color = (38, 104, 178)
        image = Image.new("RGB", (900, 300), WHITE)
        builder = _builder(tmp_path, (8, 8))

        builder._draw_title_text(ImageDraw.Draw(image), 20, 20, "Lost", self._font(155), color, 40)

        colored_box = self._color_mask(image, color).getbbox()
        outlined_box = self._color_mask(image, INTRO_TITLE_OUTLINE_COLOR).getbbox()
        assert colored_box is not None
        assert outlined_box is not None
        w = INTRO_TITLE_OUTLINE_WIDTH
        assert colored_box[0] - outlined_box[0] == pytest.approx(w, abs=1)
        assert colored_box[1] - outlined_box[1] == pytest.approx(w, abs=1)
        assert outlined_box[2] - colored_box[2] == pytest.approx(w, abs=1)
        assert outlined_box[3] - colored_box[3] == pytest.approx(w, abs=1)

    def test_the_letters_are_spaced_apart(self, tmp_path: Path) -> None:
        font = self._font(155)
        builder = _builder(tmp_path, (8, 8))

        width = builder._get_title_text_width("Lost in\nthe Andes", font)

        spaced = 8 * INTRO_TITLE_TRACKING
        assert width == round(font.getlength("the Andes") + spaced + INTRO_TITLE_WORD_GAP)

    @pytest.mark.parametrize(
        ("line", "hyphen_gaps"),
        [("Two-Way Luck", 2), ("Second-", 1)],  # a hyphen ending a line has nothing after it
    )
    def test_words_and_hyphens_get_extra_room(
        self, tmp_path: Path, line: str, hyphen_gaps: int
    ) -> None:
        font = self._font(155)
        builder = _builder(tmp_path, (8, 8))

        width = builder._get_title_line_width(line, font)

        spaced = font.getlength(line) + (INTRO_TITLE_TRACKING * (len(line) - 1))
        extra = (line.count(" ") * INTRO_TITLE_WORD_GAP) + (hyphen_gaps * INTRO_TITLE_HYPHEN_GAP)
        assert width == pytest.approx(spaced + extra)

    def test_words_stand_apart_where_a_letter_overhangs_the_space(self, tmp_path: Path) -> None:
        image = Image.new("RGB", (1600, 300), WHITE)
        builder = _builder(tmp_path, (8, 8))

        builder._draw_title_text(
            ImageDraw.Draw(image), 20, 20, "Carat Moon", self._font(155), (214, 48, 39), 40
        )

        ink = image.convert("L").point(lambda p: 255 if p < INK_THRESHOLD else 0)
        columns = [x for x in range(image.width) if ink.crop((x, 0, x + 1, image.height)).getbbox()]
        widest_gap = max(right - left - 1 for left, right in itertools.pairwise(columns))
        assert widest_gap >= INTRO_TITLE_WORD_GAP  # without it, T and M are 6px apart

    def test_the_outline_and_spacing_scale_with_the_font_size(self, tmp_path: Path) -> None:
        font = self._font(155 // 2)
        builder = _builder(tmp_path, (8, 8))

        width = builder._get_title_text_width("and", font)

        tracking = INTRO_TITLE_TRACKING * font.size / 155
        assert width == round(font.getlength("and") + (2 * tracking))
        assert builder._get_title_scaled(INTRO_TITLE_OUTLINE_WIDTH, font) == pytest.approx(
            INTRO_TITLE_OUTLINE_WIDTH / 2, abs=0.1
        )

    def test_the_title_page_title_is_in_the_comics_title_colour(self, tmp_path: Path) -> None:
        page = TestTheIntroPageLayout()._intro_page(tmp_path, (300, 100))
        title_band = page.crop((0, 0, page.width, 700))

        assert self._color_mask(title_band, TestTheIntroPageLayout.TITLE_COLOR).getbbox()


class TestSmallWordTitleLines:
    """A title line of small words, like "of the", is lettered smaller, evenly spaced."""

    SIZE = 155
    SMALL_SIZE = round(INTRO_TITLE_SMALL_WORD_SIZE_FRAC * SIZE)

    @staticmethod
    def _font(size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(CARL_BARKS_FONT_FILE, size)

    @pytest.mark.parametrize(
        ("title", "sizes"),
        [
            ("Hound\nof the\nMoaning Hills", [SIZE, SMALL_SIZE, SIZE]),
            ("The\nBear Tamer", [SMALL_SIZE, SIZE]),
            ("Hound of the\nMoaning Hills", [SIZE, SIZE]),
            ("Of The\nIn", [SIZE, SIZE]),  # all small words: nothing to set off
        ],
    )
    def test_only_a_line_of_small_words_is_smaller(
        self, tmp_path: Path, title: str, sizes: list[int]
    ) -> None:
        builder = _builder(tmp_path, (8, 8))

        fonts = builder._get_title_line_fonts(title.split("\n"), self._font(self.SIZE))

        assert [f.size for f in fonts] == sizes

    def test_full_size_lines_keep_their_spacing(self, tmp_path: Path) -> None:
        font = self._font(self.SIZE)
        builder = _builder(tmp_path, (8, 8))
        lines = ["Lost in the", "Andes!"]

        tops = builder._get_title_line_tops(lines, [font, font], font, INTRO_TITLE_SPACING)

        assert tops == [0, font.getbbox("A")[3] + INTRO_TITLE_SPACING]

    def test_a_small_line_has_even_gaps_above_and_below(self, tmp_path: Path) -> None:
        image = Image.new("RGB", (2120, 800), WHITE)
        builder = _builder(tmp_path, (8, 8))

        builder._draw_title_text(
            ImageDraw.Draw(image),
            100,
            50,
            "Knights\nof the\nFlying Sleds",
            self._font(self.SIZE),
            (214, 48, 39),
            INTRO_TITLE_SPACING,
        )

        (_, first_bottom), (small_top, small_bottom), (last_top, _) = (
            TestTheIntroPageLayout._ink_bands(image)
        )
        gap_above = small_top - first_bottom
        gap_below = last_top - small_bottom
        assert abs(gap_above - gap_below) <= GAP_TOLERANCE

    def test_a_small_line_makes_the_title_shorter(self, tmp_path: Path) -> None:
        font = self._font(self.SIZE)
        builder = _builder(tmp_path, (8, 8))

        small = builder._get_intro_text_height("Hound\nof the\nMoaning Hills", font)
        full = builder._get_intro_text_height("Hound\nof thy\nMoaning Hills", font)

        assert small < full
