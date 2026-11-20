# ruff: noqa: PLR2004, SLF001
# cspell:ignore getbbox

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from barks_build_comic_images.build_comic_images import (
    INTRO_CS_STACK_LINE_GAP_FRAC,
    RGB_PROFILE,
    SVG_ADAPTIVE_PROFILE,
    AdaptivePageImageSource,
    AlphaPageImageSource,
    BuildSourceProfile,
    ComicBookImageBuilder,
    PageImageSource,
    RgbPageImageSource,
)
from barks_build_comic_images.consts import FOOTNOTE_CHAR
from barks_fantagraphics.comic_issues import ISSUE_NAME, Issues
from barks_fantagraphics.comics_consts import CARL_BARKS_FONT_FILE
from barks_fantagraphics.fanta_comics_info import US_CENSORED_TITLES
from barks_fantagraphics.pages import (
    FinalStoryFileResolver,
    SvgPngStoryFileResolver,
)
from build_test_helpers import make_builder
from PIL import Image, ImageChops, ImageDraw, ImageFont

if TYPE_CHECKING:
    from pathlib import Path


class TestPageImageSource:
    def test_abstract_base_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            PageImageSource()  # ty: ignore[abstract-class-instantiation]


class TestRgbPageImageSource:
    def test_returns_image_unchanged_and_no_mask(self) -> None:
        image = Image.new("RGB", (4, 4), color=(10, 20, 30))

        rgb, mask = RgbPageImageSource().to_renderable(image)

        assert rgb is image
        assert mask is None


class TestAlphaPageImageSource:
    def test_alpha_becomes_mask_and_inverted_alpha_becomes_grayscale_rgb(self) -> None:
        # Pixel 1 fully opaque (alpha=255), pixel 2 fully transparent (alpha=0).
        image = Image.new("RGBA", (2, 1))
        image.putpixel((0, 0), (50, 60, 70, 255))
        image.putpixel((1, 0), (50, 60, 70, 0))

        rgb, mask = AlphaPageImageSource().to_renderable(image)

        assert rgb.mode == "RGB"
        assert mask is not None
        # Opaque source pixel → inverted alpha 0 → black ink on the page.
        assert rgb.getpixel((0, 0)) == (0, 0, 0)
        # Transparent source pixel → inverted alpha 255 → white (lets page show).
        assert rgb.getpixel((1, 0)) == (255, 255, 255)
        # Paste mask is the *original* alpha — opaque where ink should land.
        assert mask.getpixel((0, 0)) == 255
        assert mask.getpixel((1, 0)) == 0


class TestAdaptivePageImageSource:
    """An image with an alpha channel goes to one source, every other to the other."""

    @staticmethod
    def _sources() -> tuple[AdaptivePageImageSource, MagicMock, MagicMock]:
        rgba_source = MagicMock(spec=PageImageSource)
        rgb_source = MagicMock(spec=PageImageSource)
        adapter = AdaptivePageImageSource(rgba_source=rgba_source, rgb_source=rgb_source)
        return adapter, rgba_source, rgb_source

    def test_an_rgba_image_goes_to_the_rgba_source_it_was_given(self) -> None:
        adapter, rgba_source, rgb_source = self._sources()
        image = Image.new("RGBA", (1, 1), color=(0, 0, 0, 255))

        assert adapter.to_renderable(image) is rgba_source.to_renderable.return_value

        rgba_source.to_renderable.assert_called_once_with(image)
        rgb_source.to_renderable.assert_not_called()

    @pytest.mark.parametrize("mode", ["RGB", "L", "P"])
    def test_any_other_image_goes_to_the_rgb_source_it_was_given(self, mode: str) -> None:
        adapter, rgba_source, rgb_source = self._sources()
        image = Image.new(mode, (1, 1))

        assert adapter.to_renderable(image) is rgb_source.to_renderable.return_value

        rgb_source.to_renderable.assert_called_once_with(image)
        rgba_source.to_renderable.assert_not_called()

    def test_given_none_it_uses_the_alpha_and_the_plain_sources(self) -> None:
        adapter = AdaptivePageImageSource()

        _, mask = adapter.to_renderable(Image.new("RGBA", (1, 1), color=(0, 0, 0, 0)))
        assert mask is not None  # the alpha source's

        plain = Image.new("L", (1, 1), color=128)
        assert adapter.to_renderable(plain) == (plain, None)  # the plain source's


class TestBuildSourceProfile:
    def test_frozen_dataclass_blocks_field_reassignment(self) -> None:
        profile = BuildSourceProfile(
            page_image_source=RgbPageImageSource(),
            srce_story_file_resolver=FinalStoryFileResolver(),
        )

        with pytest.raises(FrozenInstanceError):
            profile.page_image_source = RgbPageImageSource()  # ty: ignore[invalid-assignment]

    def test_rgb_profile_pairs_rgb_source_with_final_resolver(self) -> None:
        assert isinstance(RGB_PROFILE.page_image_source, RgbPageImageSource)
        assert isinstance(RGB_PROFILE.srce_story_file_resolver, FinalStoryFileResolver)

    def test_svg_adaptive_profile_pairs_adaptive_source_with_svg_resolver(self) -> None:
        assert isinstance(SVG_ADAPTIVE_PROFILE.page_image_source, AdaptivePageImageSource)
        assert isinstance(SVG_ADAPTIVE_PROFILE.srce_story_file_resolver, SvgPngStoryFileResolver)

    def test_svg_adaptive_profile_resolver_has_final_fallback(self) -> None:
        # The SVG-PNG resolver must fall back to the final story file so pages that
        # have not yet been SVG-rendered still render via the JPG pipeline.
        resolver = SVG_ADAPTIVE_PROFILE.srce_story_file_resolver
        assert isinstance(resolver, SvgPngStoryFileResolver)
        assert isinstance(resolver._fallback, FinalStoryFileResolver)


# ---------------------------------------------------------------------------
# The intro page's title: one font for a Barks title; for a non-Barks "Comics and
# Stories" issue, its masthead's pieces, with a footnote mark on a US-censored one.
# ---------------------------------------------------------------------------

# The comics' own title font, which the package's data has: no other package's.
TITLE_FONT = CARL_BARKS_FONT_FILE
TITLE_FONT_SIZE = 40
CS_TITLE = f"{ISSUE_NAME[Issues.CS]}91"


def _builder(
    tmp_path: Path, *, title: str, is_barks: bool, title_str: str
) -> ComicBookImageBuilder:
    comic = MagicMock()
    comic.get_comic_title.return_value = title
    comic.title_font_file = TITLE_FONT
    comic.title_font_size = TITLE_FONT_SIZE
    comic.fanta_info.comic_book_info.is_barks_title = is_barks
    comic.fanta_info.comic_book_info.issue_name = Issues.CS
    # The censored list is of title strings: the ini title is not what is looked up.
    comic.get_title_str.return_value = title_str
    comic.get_ini_title.return_value = "the ini title, which this does not read"
    return make_builder(tmp_path, (8, 8), comic=comic)


class TestTitleAndFonts:
    def test_a_barks_title_is_one_line_in_one_font(self, tmp_path: Path) -> None:
        builder = _builder(tmp_path, title="Lost in the Andes!", is_barks=True, title_str="x")
        texts, fonts, ink = builder._get_title_and_fonts()
        assert texts == ["Lost in the Andes!"]
        assert [f.size for f in fonts] == [TITLE_FONT_SIZE]
        # The ink starts above the letters' own box: the outline is drawn around them.
        assert ink.top < fonts[0].getbbox(texts[0])[1]
        assert ink.height > 0

    def test_a_comics_and_stories_issue_is_lettered_as_its_masthead(self, tmp_path: Path) -> None:
        builder = _builder(tmp_path, title=CS_TITLE, is_barks=False, title_str="Not censored")
        texts, fonts, _ = builder._get_title_and_fonts()
        assert texts == ["COMICS", "AND", "STORIES", "91"]
        comics_font, and_font, stories_font, number_font = fonts
        assert comics_font.size == number_font.size == TITLE_FONT_SIZE
        assert and_font.size == stories_font.size < TITLE_FONT_SIZE

    def test_and_over_stories_is_as_tall_as_the_capitals_of_comics(self, tmp_path: Path) -> None:
        builder = _builder(tmp_path, title=CS_TITLE, is_barks=False, title_str="Not censored")
        _, (comics_font, small_font, _, _), _ = builder._get_title_and_fonts()

        def cap_height(font: ImageFont.FreeTypeFont, text: str) -> float:
            return -font.getbbox(text, anchor="ls")[1]

        comics_cap = cap_height(comics_font, "COMICS")
        line_gap = INTRO_CS_STACK_LINE_GAP_FRAC * comics_cap
        stack = cap_height(small_font, "STORIES") + line_gap + cap_height(small_font, "AND")
        assert stack == pytest.approx(comics_cap, abs=2)  # the small font's size is whole

    def test_a_us_censored_one_gets_the_footnote_mark(self, tmp_path: Path) -> None:
        censored = US_CENSORED_TITLES[0]
        builder = _builder(tmp_path, title=CS_TITLE, is_barks=False, title_str=censored)
        texts, _, _ = builder._get_title_and_fonts()
        assert texts[-1] == f"91{FOOTNOTE_CHAR}"


class TestDrawingTheTitle:
    def test_two_lines_and_a_superscript_mark_are_drawn(self, tmp_path: Path) -> None:
        censored = US_CENSORED_TITLES[0]
        builder = _builder(tmp_path, title=CS_TITLE, is_barks=False, title_str=censored)
        image = Image.new("RGB", (600, 400), "white")
        draw = ImageDraw.Draw(image)
        texts, fonts, _ = builder._get_title_and_fonts()
        blank = image.copy()

        builder._draw_centered_multiline_title_text(texts, fonts, (0, 0, 0), 20, 10, image, draw)

        drawn = ImageChops.difference(image, blank).getbbox()
        assert drawn is not None
        assert drawn[3] - drawn[1] > TITLE_FONT_SIZE  # more than one line high
