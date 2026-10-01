# ruff: noqa: PLR2004, SLF001
# cspell:ignore getbbox

from __future__ import annotations

import importlib.util
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from barks_build_comic_images.build_comic_images import (
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
from barks_fantagraphics.fanta_comics_info import US_CENSORED_TITLES
from barks_fantagraphics.pages import (
    FinalStoryFileResolver,
    SvgPngStoryFileResolver,
)
from PIL import Image, ImageChops, ImageDraw


class TestPageImageSource:
    def test_abstract_base_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            PageImageSource()  # type: ignore[abstract]


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
    def test_rgba_dispatches_to_rgba_source(self) -> None:
        rgba_src = AlphaPageImageSource()
        rgb_src = RgbPageImageSource()
        adapter = AdaptivePageImageSource(rgba_source=rgba_src, rgb_source=rgb_src)

        rgba_image = Image.new("RGBA", (1, 1), color=(0, 0, 0, 255))
        rgb, mask = adapter.to_renderable(rgba_image)

        # AlphaPageImageSource always emits an RGB image plus a mask.
        assert rgb.mode == "RGB"
        assert mask is not None

    def test_non_rgba_dispatches_to_rgb_source(self) -> None:
        adapter = AdaptivePageImageSource()
        rgb_image = Image.new("RGB", (1, 1), color=(1, 2, 3))

        rgb, mask = adapter.to_renderable(rgb_image)

        # RgbPageImageSource returns the input image as-is, no mask.
        assert rgb is rgb_image
        assert mask is None

    def test_defaults_match_the_module_constants(self) -> None:
        adapter = AdaptivePageImageSource()

        # RGBA → alpha pipeline (mask is not None).
        rgba_image = Image.new("RGBA", (1, 1), color=(0, 0, 0, 0))
        _, mask = adapter.to_renderable(rgba_image)
        assert mask is not None

        # Non-RGBA (e.g. L) → rgb pipeline (mask is None).
        l_image = Image.new("L", (1, 1), color=128)
        _, mask = adapter.to_renderable(l_image)
        assert mask is None


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
# Stories" issue, three, with a superscript footnote mark on a US-censored one.
# ---------------------------------------------------------------------------

# A TrueType font any workspace has: Kivy's, found without importing Kivy.
_KIVY_SPEC = importlib.util.find_spec("kivy")
assert _KIVY_SPEC is not None
assert _KIVY_SPEC.origin is not None
TITLE_FONT = Path(_KIVY_SPEC.origin).parent / "data" / "fonts" / "Roboto-Regular.ttf"
TITLE_FONT_SIZE = 40
CS_TITLE = f"{ISSUE_NAME[Issues.CS]}91"


def _builder(
    tmp_path: Path, *, title: str, is_barks: bool, ini_title: str
) -> ComicBookImageBuilder:
    empty_page = tmp_path / "empty.png"
    Image.new("RGB", (8, 8), "white").save(empty_page)
    comic = MagicMock()
    comic.get_comic_title.return_value = title
    comic.title_font_file = TITLE_FONT
    comic.title_font_size = TITLE_FONT_SIZE
    comic.fanta_info.comic_book_info.is_barks_title = is_barks
    comic.fanta_info.comic_book_info.issue_name = Issues.CS
    comic.get_ini_title.return_value = ini_title
    return ComicBookImageBuilder(comic, empty_page)


def _draw() -> ImageDraw.ImageDraw:
    return ImageDraw.Draw(Image.new("RGB", (600, 400), "white"))


class TestTitleAndFonts:
    def test_a_barks_title_is_one_line_in_one_font(self, tmp_path: Path) -> None:
        builder = _builder(tmp_path, title="Lost in the Andes!", is_barks=True, ini_title="x")
        texts, fonts, height = builder._get_title_and_fonts(_draw())
        assert texts == ["Lost in the Andes!"]
        assert [f.size for f in fonts] == [TITLE_FONT_SIZE]
        assert height > 0

    def test_a_comics_and_stories_issue_splits_over_three_fonts(self, tmp_path: Path) -> None:
        builder = _builder(tmp_path, title=CS_TITLE, is_barks=False, ini_title="Not censored")
        texts, fonts, _ = builder._get_title_and_fonts(_draw())
        assert texts == ["Comics", "and Stories", "91"]
        assert [f.size for f in fonts] == [TITLE_FONT_SIZE, TITLE_FONT_SIZE // 2, TITLE_FONT_SIZE]

    def test_a_us_censored_one_gets_the_footnote_mark(self, tmp_path: Path) -> None:
        censored = US_CENSORED_TITLES[0]
        builder = _builder(tmp_path, title=CS_TITLE, is_barks=False, ini_title=censored)
        texts, _, _ = builder._get_title_and_fonts(_draw())
        assert texts[-1] == f"91{FOOTNOTE_CHAR}"


class TestDrawingTheTitle:
    def test_two_lines_and_a_superscript_mark_are_drawn(self, tmp_path: Path) -> None:
        censored = US_CENSORED_TITLES[0]
        builder = _builder(tmp_path, title=CS_TITLE, is_barks=False, ini_title=censored)
        image = Image.new("RGB", (600, 400), "white")
        draw = ImageDraw.Draw(image)
        texts, fonts, _ = builder._get_title_and_fonts(draw)
        texts[2] = "\n" + texts[2]  # the issue number on a line of its own
        blank = image.copy()

        builder._draw_centered_multiline_title_text(texts, fonts, (0, 0, 0), 20, 10, image, draw)

        drawn = ImageChops.difference(image, blank).getbbox()
        assert drawn is not None
        assert drawn[3] - drawn[1] > TITLE_FONT_SIZE  # more than one line high
