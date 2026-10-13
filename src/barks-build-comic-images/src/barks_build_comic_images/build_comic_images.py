# ruff: noqa: PLR0911
# cspell:ignore getbbox getmetrics Raqm

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from barks_fantagraphics.comic_book import INTRO_TITLE_DEFAULT_FONT_SIZE, ComicBook
from barks_fantagraphics.comic_issues import ISSUE_NAME, Issues
from barks_fantagraphics.comics_consts import (
    BACK_NO_PANELS_PAGES,
    BARKS,
    DEST_TARGET_ASPECT_RATIO,
    DEST_TARGET_HEIGHT,
    DEST_TARGET_WIDTH,
    DEST_TARGET_X_MARGIN,
    INTRO_PUB_TEXT_BOLD_FONT_FILE,
    INTRO_PUB_TEXT_FONT_FILE,
    PAGE_NUM_COLOR,
    PAGE_NUM_FONT_FILE,
    PAGE_NUM_FONT_SIZE,
    PAGE_NUM_HEIGHT,
    PAGE_NUM_X_BLANK_PIXEL_OFFSET,
    PAGE_NUM_X_OFFSET_FROM_CENTRE,
    PAGES_WITHOUT_PANELS,
    PAINTING_PAGES,
    PageType,
)
from barks_fantagraphics.comics_utils import get_relpath
from barks_fantagraphics.fanta_comics_info import US_CENSORED_TITLES
from barks_fantagraphics.page_classes import CleanPage, RequiredDimensions
from barks_fantagraphics.pages import (
    FinalStoryFileResolver,
    SrceStoryFileResolver,
    SvgPngStoryFileResolver,
    get_page_num_str,
)
from barks_fantagraphics.panel_geometry import scale_height
from comic_utils.decryption import DecryptionError
from comic_utils.pil_image_utils import load_pil_image_from_bytes
from loguru import logger
from PIL import Image, ImageDraw, ImageFont
from PIL.Image import Image as PilImage
from PIL.ImageDraw import ImageDraw as PilImageDraw
from PIL.ImageFont import FreeTypeFont

from .consts import FOOTNOTE_CHAR
from .image_io import open_image_for_reading

# The intro (title) page. On every story the title starts at the same height and the
# publication text ends at the same height. The room between them, after the byline and
# the inset, is shared by three gaps: title to byline, which takes the smaller share so
# the byline stays with the title, and the equal gaps above and below the inset.
INTRO_TOP = 330
INTRO_BOTTOM_MARGIN = 380
INTRO_TITLE_SPACING = 40
INTRO_TITLE_BYLINE_MIN_GAP = 170
INTRO_TITLE_BYLINE_GAP_SHARE = 0.6  # of each inset gap
# The title is lettered like a splash-page title: the story's title colour inside a black
# outline, the letters spaced a little apart. Letters the font kerns close still share an
# outline, as in hand lettering; spacing them all apart would push the longest titles off
# the page. Both are for the default title font size, and scale with it.
INTRO_TITLE_OUTLINE_COLOR = (0, 0, 0)
INTRO_TITLE_OUTLINE_WIDTH = 9
INTRO_TITLE_TRACKING = 8
# This font's space is narrow, and letters like T and Y reach past their own width, so
# the gap between two words, and between a hyphen and the letters either side of it, is
# measured from the letters themselves: always this much, whatever the letters.
INTRO_TITLE_WORD_GAP = 60
INTRO_TITLE_HYPHEN_GAP = 28
_TITLE_LINE_PIECES = re.compile(r" +|-|[^ -]+")
# A title line made only of small words, like "of the", is lettered smaller, as on a
# splash-page logo, unless the whole title is small words.
INTRO_TITLE_SMALL_WORDS = frozenset(
    {"a", "an", "and", "at", "by", "for", "from", "in", "of", "on", "the", "to", "with"}
)
INTRO_TITLE_SMALL_WORD_SIZE_FRAC = 0.55
# A title whose widest line would come nearer the page's edges than this is lettered
# smaller, so it fits.
INTRO_TITLE_MIN_MARGIN = 50
# A "Comics and Stories" issue's title is lettered like the comic's masthead: "COMICS",
# with a small "AND" stacked over "STORIES" beside it, the two as tall as its capitals,
# and the issue number on the line below.
INTRO_CS_STACK_GAP_FRAC = 0.3  # of the font size, between COMICS and the stack
INTRO_CS_STACK_LINE_GAP_FRAC = 0.18  # of the capitals' height, between AND and STORIES
INTRO_CS_COMICS = "COMICS"
INTRO_CS_AND = "AND"
INTRO_CS_STORIES = "STORIES"
# "by Carl Barks" on one line, the smaller "by" sitting on the author's baseline.
INTRO_AUTHOR_COLOR = (0, 0, 0)
INTRO_BY_FONT_SIZE_FRAC = 0.6
INTRO_BY_AUTHOR_GAP = 28
# The inset is framed like a story panel, but in a dark shade of the title's colour
# rather than black ink, tying the art to the title. Its width cap lines it up with
# the widest title lines.
INTRO_INSET_MAX_WIDTH = 1450
INTRO_INSET_MIN_GAP = 130
INTRO_INSET_BORDER_SHADE = 0.6  # of the title colour's brightness
INTRO_INSET_BORDER_WIDTH = 4
# The first paragraph of the publication text (the original publication) is in ink,
# its first line bold; any later paragraphs (this edition's credits) are smaller and
# in sepia. Advances are baseline to baseline.
INTRO_PUB_TEXT_FONT_SIZE = 40
INTRO_PUB_TEXT_COLOR = (0, 0, 0)
INTRO_PUB_TEXT_LINE_ADVANCE = 58
INTRO_PUB_CREDITS_FONT_SIZE = 35
INTRO_PUB_CREDITS_COLOR = (84, 72, 60)
INTRO_PUB_CREDITS_LINE_ADVANCE = 50
INTRO_PUB_PARAGRAPH_GAP = 34

SPLASH_BORDER_COLOR = (0, 0, 0)
SPLASH_BORDER_WIDTH = 10
SPLASH_MARGIN = DEST_TARGET_X_MARGIN


class BasePageType(Enum):
    EMPTY_PAGE = auto()
    BLACK_PAGE = auto()


class PageImageSource(ABC):
    """Strategy describing how to interpret a source page image for the panel pages.

    Different source kinds (flat RGB scans, alpha-channel line art, etc.) need
    different conversions before the cropped panels region can be pasted onto the
    destination page. A subclass owns that conversion and supplies an optional
    paste mask so the empty page can show through transparent regions.
    """

    @abstractmethod
    def to_renderable(
        self,
        panels_image: PilImage,
    ) -> tuple[PilImage, PilImage | None]:
        """Convert a cropped panels region into an RGB image and an optional paste mask.

        Args:
            panels_image: The cropped source-image panels region, in whatever pixel
                format the concrete source produces (e.g. RGB or RGBA).

        Returns:
            A ``(rgb_image, paste_mask)`` tuple. ``rgb_image`` is the image to paste
            onto the empty page. ``paste_mask`` is the mask passed to ``PIL.paste``
            (0 = transparent, 255 = opaque), or ``None`` for a fully opaque paste.

        """


class RgbPageImageSource(PageImageSource):
    """Source images are flat RGB scans; pasted opaquely with no mask."""

    def to_renderable(
        self,
        panels_image: PilImage,
    ) -> tuple[PilImage, PilImage | None]:
        return panels_image, None


class AlphaPageImageSource(PageImageSource):
    """Source images are PNGs whose alpha channel carries the line art.

    The visible RGB is a grayscale rendition derived from the inverted alpha (so dark
    ink shows on a light page), and the original alpha is returned as the paste mask
    so transparent areas reveal the empty page underneath.
    """

    def to_renderable(
        self,
        panels_image: PilImage,
    ) -> tuple[PilImage, PilImage | None]:
        _, _, _, alpha = panels_image.split()
        inverted_alpha = alpha.point(lambda p: 255 - p)
        rgb = Image.merge("RGB", (inverted_alpha, inverted_alpha, inverted_alpha))
        return rgb, alpha


class AdaptivePageImageSource(PageImageSource):
    """Dispatches between an RGBA and an RGB source based on the loaded image's PIL mode.

    Useful when a per-page resolver may fall back from an alpha-channel PNG to a flat
    RGB JPG: the rendering strategy follows the actual pixel format rather than being
    pinned globally. ``RGBA`` images go through ``rgba_source``; everything else
    (``RGB``, ``L``, ``P``, ...) goes through ``rgb_source``.
    """

    def __init__(
        self,
        rgba_source: PageImageSource | None = None,
        rgb_source: PageImageSource | None = None,
    ) -> None:
        self._rgba_source = rgba_source or AlphaPageImageSource()
        self._rgb_source = rgb_source or RgbPageImageSource()

    def to_renderable(
        self,
        panels_image: PilImage,
    ) -> tuple[PilImage, PilImage | None]:
        if panels_image.mode == "RGBA":
            return self._rgba_source.to_renderable(panels_image)
        return self._rgb_source.to_renderable(panels_image)


@dataclass(frozen=True)
class BuildSourceProfile:
    """Pairs a source-file resolver with the matching page-image renderer.

    The resolver decides *where* source images live (final JPG vs SVG-derived PNG,
    etc.) and the renderer decides *how* to paint them onto the destination page.
    The two choices are inherently coupled — alpha-PNG paths need the alpha
    renderer, RGB JPGs need the RGB renderer — so they are bundled here to prevent
    mis-pairing at construction sites.
    """

    page_image_source: PageImageSource
    srce_story_file_resolver: SrceStoryFileResolver


@dataclass(frozen=True)
class _PubTextLine:
    """One line of the intro page's publication text, styled for drawing.

    ``advance`` is the distance from the previous line's baseline; the first line's
    is unused, since the block is placed by the top of its ink.
    """

    text: str
    font: FreeTypeFont
    color: tuple[int, int, int]
    advance: int


RGB_PROFILE = BuildSourceProfile(
    page_image_source=RgbPageImageSource(),
    srce_story_file_resolver=FinalStoryFileResolver(),
)

SVG_ADAPTIVE_PROFILE = BuildSourceProfile(
    page_image_source=AdaptivePageImageSource(),
    srce_story_file_resolver=SvgPngStoryFileResolver(fallback=FinalStoryFileResolver()),
)


class ComicBookImageBuilder:
    def __init__(
        self,
        comic: ComicBook,
        empty_page_file: Path,
        page_image_source: PageImageSource | None = None,
        get_inset_decrypted_bytes: Callable[[bytes], bytes] | None = None,
    ) -> None:
        self._comic = comic
        self._empty_page_image = open_image_for_reading(empty_page_file)
        self._page_image_source = page_image_source or RgbPageImageSource()
        self._get_inset_decrypted_bytes = get_inset_decrypted_bytes
        self._required_dim: RequiredDimensions = RequiredDimensions()

    def set_required_dim(self, required_dim: RequiredDimensions) -> None:
        self._required_dim = required_dim

    @staticmethod
    def _log_page_info(prefix: str, image: PilImage | None, page: CleanPage) -> None:
        width = image.width if image else 0
        height = image.height if image else 0
        logger.debug(
            f"{prefix}: width = {width:4}, height = {height:4},"
            f" page_type = {page.page_type.name:13},"
            f" panels bbox = {page.panels_bbox.x_min:4}, {page.panels_bbox.y_min:4},"
            f" {page.panels_bbox.x_max:4}, {page.panels_bbox.y_max:4}.",
        )

    def get_dest_page_image(
        self,
        srce_page_image: PilImage,
        srce_page: CleanPage,
        dest_page: CleanPage,
    ) -> PilImage:
        self._log_page_info(f"{srce_page.page_num}-Srce", srce_page_image, srce_page)
        self._log_page_info(f"{srce_page.page_num}-Dest", None, dest_page)

        if dest_page.page_type in PAGES_WITHOUT_PANELS:
            dest_page_image = self._get_no_panels_dest_image(srce_page_image, srce_page, dest_page)
        else:
            dest_page_image = self._get_main_page_dest_image(srce_page_image, srce_page, dest_page)

        rgb_dest_page_image = dest_page_image.convert("RGB")

        self._log_page_info("Dest", rgb_dest_page_image, dest_page)

        return rgb_dest_page_image

    def _get_no_panels_dest_image(
        self,
        srce_page_image: PilImage,
        srce_page: CleanPage,
        dest_page: CleanPage,
    ) -> PilImage:
        if dest_page.page_type == PageType.FRONT:
            return self._get_front_page_dest_image(srce_page_image, srce_page)
        if dest_page.page_type == PageType.COVER:
            return self._get_cover_page_dest_image(srce_page_image, srce_page)
        if dest_page.page_type in PAINTING_PAGES:
            return self._get_painting_page_dest_image(srce_page_image, srce_page)
        if dest_page.page_type == PageType.SPLASH:
            return self._get_splash_page_dest_image(srce_page_image, srce_page)
        if dest_page.page_type in ([*BACK_NO_PANELS_PAGES, PageType.FRONT_NO_PANELS]):
            return self._get_no_panels_page_dest_image(srce_page_image, srce_page, dest_page)
        if dest_page.page_type == PageType.BLANK_PAGE:
            return self._get_blank_page_dest_image(srce_page_image)
        if dest_page.page_type == PageType.TITLE:
            return self._get_dest_title_page_image(srce_page_image)
        raise AssertionError

    def _get_front_page_dest_image(
        self, srce_page_image: PilImage, srce_page: CleanPage
    ) -> PilImage:
        return self._get_black_bars_page_dest_image(srce_page_image, srce_page)

    def _get_cover_page_dest_image(
        self, srce_page_image: PilImage, srce_page: CleanPage
    ) -> PilImage:
        return self._get_black_bars_page_dest_image(srce_page_image, srce_page)

    def _get_painting_page_dest_image(
        self, painting_image: PilImage, srce_page: CleanPage
    ) -> PilImage:
        assert srce_page.page_type in PAINTING_PAGES

        if srce_page.page_type in [
            PageType.PAINTING_NO_BORDER,
            PageType.BACK_PAINTING_NO_BORDER,
        ]:
            return self._get_black_bars_page_dest_image(painting_image, srce_page)

        assert srce_page.page_type in [PageType.PAINTING, PageType.BACK_PAINTING]
        self._draw_border_around_image(painting_image)

        return self._get_centred_page_dest_image(painting_image, srce_page, BasePageType.EMPTY_PAGE)

    def _get_splash_page_dest_image(self, splash_image: PilImage, srce_page: CleanPage) -> PilImage:
        assert srce_page.page_type == PageType.SPLASH

        splash_width = splash_image.width
        splash_height = splash_image.height

        smaller_splash_image = splash_image.resize(
            size=(
                splash_width - (2 * SPLASH_MARGIN),
                splash_height - (2 * SPLASH_MARGIN),
            ),
            resample=Image.Resampling.BICUBIC,
        )
        self._draw_border_around_image(smaller_splash_image)

        splash_image = self._empty_page_image.resize(size=(splash_width, splash_height))
        splash_image.paste(smaller_splash_image, (SPLASH_MARGIN, SPLASH_MARGIN))

        return self._get_centred_page_dest_image(splash_image, srce_page, BasePageType.EMPTY_PAGE)

    @staticmethod
    def _draw_border_around_image(image: PilImage) -> None:
        x_min = 0
        y_min = 0
        x_max = image.width - 1
        y_max = image.height - 1
        border = [
            (x_min, y_min),
            (x_max, y_min),
            (x_max, y_max),
            (x_min, y_max),
            (x_min, y_min),
        ]
        draw = ImageDraw.Draw(image)
        draw.line(border, fill=SPLASH_BORDER_COLOR, width=SPLASH_BORDER_WIDTH)

    def _get_no_panels_page_dest_image(
        self,
        no_panels_image: PilImage,
        srce_page: CleanPage,
        dest_page: CleanPage,
    ) -> PilImage:
        dest_page_image = self._get_centred_page_dest_image(
            no_panels_image,
            srce_page,
            BasePageType.EMPTY_PAGE,
        )

        self._write_page_number(dest_page_image, dest_page, PAGE_NUM_COLOR)

        return dest_page_image

    def _get_black_bars_page_dest_image(
        self,
        srce_page_image: PilImage,
        srce_page: CleanPage,
    ) -> PilImage:
        return self._get_centred_page_dest_image(
            srce_page_image,
            srce_page,
            BasePageType.BLACK_PAGE,
        )

    def _get_centred_page_dest_image(
        self,
        srce_page_image: PilImage,
        srce_page: CleanPage,
        base_page_type: BasePageType,
    ) -> PilImage:
        small_float = 0.01

        srce_aspect_ratio = float(srce_page_image.height) / float(srce_page_image.width)
        if abs(srce_aspect_ratio - DEST_TARGET_ASPECT_RATIO) > small_float:
            logger.debug(
                f"Wrong aspect ratio for page '{get_relpath(Path(srce_page.page_filename))}':"
                f" {srce_aspect_ratio:.2f} != {DEST_TARGET_ASPECT_RATIO:.2f}."
                f" Using black bars.",
            )

        required_height = scale_height(
            DEST_TARGET_WIDTH,
            srce_page_image.width,
            srce_page_image.height,
        )

        no_margins_image = srce_page_image.resize(
            size=(DEST_TARGET_WIDTH, required_height),
            resample=Image.Resampling.BICUBIC,
        )
        no_margins_aspect_ratio = float(no_margins_image.height) / float(no_margins_image.width)
        assert abs(srce_aspect_ratio - no_margins_aspect_ratio) <= small_float

        if required_height == DEST_TARGET_HEIGHT:
            return no_margins_image

        cover_top = round(0.5 * (DEST_TARGET_HEIGHT - required_height))
        base_page_image = (
            self._empty_page_image.copy()
            if base_page_type == BasePageType.EMPTY_PAGE
            else Image.new("RGB", (DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT), (0, 0, 0))
        )
        base_page_image.paste(no_margins_image, (0, cover_top))

        return base_page_image

    @staticmethod
    def _get_blank_page_dest_image(srce_page_image: PilImage) -> PilImage:
        return srce_page_image.resize(
            size=(DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT),
            resample=Image.Resampling.BICUBIC,
        )

    def _get_main_page_dest_image(
        self,
        srce_page_image: PilImage,
        srce_page: CleanPage,
        dest_page: CleanPage,
    ) -> PilImage:
        panels_image = srce_page_image.crop(srce_page.panels_bbox.get_box())
        panels_rgb, paste_mask = self._page_image_source.to_renderable(panels_image)

        if dest_page.page_type not in PAGES_WITHOUT_PANELS:
            panels_rgb, paste_mask = self._get_resized_srce_images(
                dest_page, panels_rgb, paste_mask
            )

        dest_page_image = self._empty_page_image.copy()
        dest_panels_pos = (dest_page.panels_bbox.x_min, dest_page.panels_bbox.y_min)
        dest_page_image.paste(panels_rgb, dest_panels_pos, mask=paste_mask)

        if dest_page_image.width != DEST_TARGET_WIDTH:
            msg = (
                f'Width mismatch for page "{srce_page.page_filename}":'
                f"{dest_page_image.width} != {DEST_TARGET_WIDTH}"
            )
            raise RuntimeError(msg)
        if dest_page_image.height != DEST_TARGET_HEIGHT:
            msg = (
                f'Height mismatch for page "{srce_page.page_filename}":'
                f"{dest_page_image.height} != {DEST_TARGET_HEIGHT}"
            )
            raise RuntimeError(msg)

        self._write_page_number(dest_page_image, dest_page, PAGE_NUM_COLOR)

        return dest_page_image

    @staticmethod
    def _get_resized_srce_images(
        dest_page: CleanPage, panels_rgb: PilImage, paste_mask: PilImage | None
    ) -> tuple[PilImage, PilImage | None]:
        target_size = (
            dest_page.panels_bbox.get_width(),
            dest_page.panels_bbox.get_height(),
        )
        panels_rgb = panels_rgb.resize(
            size=target_size,
            resample=Image.Resampling.BICUBIC,
        )
        if paste_mask is not None:
            paste_mask = paste_mask.resize(
                size=target_size,
                resample=Image.Resampling.BICUBIC,
            )
        return panels_rgb, paste_mask

    def _write_page_number(
        self,
        dest_page_image: PilImage,
        dest_page: CleanPage,
        color: tuple[int, int, int],
    ) -> None:
        draw = ImageDraw.Draw(dest_page_image)

        dest_page_centre = int(dest_page_image.width / 2)
        page_num_x_start = dest_page_centre - PAGE_NUM_X_OFFSET_FROM_CENTRE
        page_num_x_end = dest_page_centre + PAGE_NUM_X_OFFSET_FROM_CENTRE
        page_num_y_start = (
            dest_page_image.height - self._required_dim.page_num_y_bottom
        ) - PAGE_NUM_HEIGHT
        page_num_y_end = page_num_y_start + PAGE_NUM_HEIGHT

        # Get the color of a blank part of the page
        page_blank_color = dest_page_image.getpixel(
            (
                page_num_x_start + PAGE_NUM_X_BLANK_PIXEL_OFFSET,
                page_num_y_end,
            ),
        )

        # Remove the existing page number
        shape = (
            (
                page_num_x_start - 1,
                page_num_y_start - 1,
            ),
            (
                page_num_x_end + 1,
                page_num_y_end + 1,
            ),
        )
        draw.rectangle(shape, fill=page_blank_color)

        font = ImageFont.truetype(PAGE_NUM_FONT_FILE, PAGE_NUM_FONT_SIZE)
        text = get_page_num_str(dest_page)
        self._draw_centered_text(
            text,
            dest_page_image,
            draw,
            font,
            color,
            page_num_y_start,
        )

    @staticmethod
    def _draw_centered_text(
        text: str,
        image: PilImage,
        draw: PilImageDraw,
        font: FreeTypeFont,
        color: tuple[int, int, int],
        top: int,
    ) -> None:
        w = draw.textlength(text, font)
        left = (image.width - w) / 2
        draw.text((left, top), text, fill=color, font=font, align="center")

    def _get_dest_title_page_image(self, srce_page_image: PilImage) -> PilImage:
        dest_page_image = srce_page_image.resize(
            size=(DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT),
            resample=Image.Resampling.BICUBIC,
        )

        self._write_introduction(dest_page_image)

        return dest_page_image

    def _write_introduction(self, dest_page_image: PilImage) -> None:
        if not self._comic.intro_inset_file.is_file():
            msg = f'Could not find inset file "{self._comic.intro_inset_file}".'
            raise FileNotFoundError(msg)

        logger.info(
            f"Writing introduction - using inset file"
            f' "{get_relpath(self._comic.intro_inset_file)}".',
        )

        draw = ImageDraw.Draw(dest_page_image)

        top = INTRO_TOP

        title, title_fonts, text_height = self._get_title_and_fonts()

        self._draw_centered_multiline_title_text(
            title,
            title_fonts,
            self._comic.title_color,
            top,
            spacing=INTRO_TITLE_SPACING,
            image=dest_page_image,
            draw=draw,
        )
        title_bottom = top + text_height

        pub_lines = self._get_publication_text_lines()
        pub_height = self._get_publication_text_height(pub_lines)
        pub_top = dest_page_image.height - INTRO_BOTTOM_MARGIN - pub_height

        # What is left for the inset and the three gaps around the byline and the inset.
        room = pub_top - title_bottom - self._get_byline_height()
        inset = self._get_resized_inset(
            INTRO_INSET_MAX_WIDTH,
            room - INTRO_TITLE_BYLINE_MIN_GAP - (2 * INTRO_INSET_MIN_GAP),
        )
        spare = room - inset.height
        byline_gap = round(
            spare * INTRO_TITLE_BYLINE_GAP_SHARE / (INTRO_TITLE_BYLINE_GAP_SHARE + 2)
        )
        byline_gap = max(INTRO_TITLE_BYLINE_MIN_GAP, byline_gap)
        inset_gap = (spare - byline_gap) // 2

        top = self._draw_byline(dest_page_image, draw, title_bottom + byline_gap)

        top += inset_gap
        inset_left = (dest_page_image.width - inset.width) // 2
        dest_page_image.paste(inset, (inset_left, top))
        self._draw_inset_border(
            draw,
            inset_left,
            top,
            inset.width,
            inset.height,
            _get_inset_border_color(self._comic.title_color),
        )

        self._draw_publication_text(dest_page_image, draw, pub_lines, pub_top)

    def _get_byline_fonts(self) -> tuple[FreeTypeFont, FreeTypeFont]:
        """Return the fonts for the byline's "by" and for the author's name."""
        author_font_size = self._comic.author_font_size
        by_font_size = int(INTRO_BY_FONT_SIZE_FRAC * author_font_size)
        return (
            _get_title_page_font(self._comic.title_font_file, by_font_size),
            _get_title_page_font(self._comic.title_font_file, author_font_size),
        )

    def _get_byline_height(self) -> int:
        _, author_font = self._get_byline_fonts()
        _, ink_top, _, ink_bottom = author_font.getbbox(BARKS, anchor="ls")
        return round(ink_bottom - ink_top)

    def _draw_byline(self, image: PilImage, draw: PilImageDraw, top: int) -> int:
        """Draw "by Carl Barks" with the top of its ink at ``top``; return its ink bottom."""
        by_font, author_font = self._get_byline_fonts()

        _, ink_top, _, ink_bottom = author_font.getbbox(BARKS, anchor="ls")
        baseline = top - ink_top

        by_width = draw.textlength("by", by_font)
        author_width = draw.textlength(BARKS, author_font)
        left = (image.width - (by_width + INTRO_BY_AUTHOR_GAP + author_width)) / 2
        draw.text((left, baseline), "by", fill=INTRO_AUTHOR_COLOR, font=by_font, anchor="ls")
        author_left = left + by_width + INTRO_BY_AUTHOR_GAP
        draw.text(
            (author_left, baseline), BARKS, fill=INTRO_AUTHOR_COLOR, font=author_font, anchor="ls"
        )

        return round(baseline + ink_bottom)

    def _get_publication_text_lines(self) -> list[_PubTextLine]:
        first_paragraph, *credit_paragraphs = self._comic.publication_text.strip("\n").split("\n\n")

        bold_font = _get_title_page_font(INTRO_PUB_TEXT_BOLD_FONT_FILE, INTRO_PUB_TEXT_FONT_SIZE)
        font = _get_title_page_font(INTRO_PUB_TEXT_FONT_FILE, INTRO_PUB_TEXT_FONT_SIZE)
        credits_font = _get_title_page_font(INTRO_PUB_TEXT_FONT_FILE, INTRO_PUB_CREDITS_FONT_SIZE)

        lines = [
            _PubTextLine(
                text,
                bold_font if i == 0 else font,
                INTRO_PUB_TEXT_COLOR,
                INTRO_PUB_TEXT_LINE_ADVANCE,
            )
            for i, text in enumerate(first_paragraph.split("\n"))
        ]
        for paragraph in credit_paragraphs:
            for i, text in enumerate(paragraph.split("\n")):
                advance = INTRO_PUB_CREDITS_LINE_ADVANCE
                if i == 0:
                    advance += INTRO_PUB_PARAGRAPH_GAP
                lines.append(_PubTextLine(text, credits_font, INTRO_PUB_CREDITS_COLOR, advance))

        return lines

    @staticmethod
    def _get_publication_text_baselines(lines: list[_PubTextLine], top: int) -> list[int]:
        """Return each line's baseline, for a block whose ink starts at ``top``."""
        first = lines[0]
        baseline = round(top - first.font.getbbox(first.text, anchor="ms")[1])
        baselines = [baseline]
        for line in lines[1:]:
            baseline += line.advance
            baselines.append(baseline)
        return baselines

    def _get_publication_text_height(self, lines: list[_PubTextLine]) -> int:
        last = lines[-1]
        last_baseline = self._get_publication_text_baselines(lines, 0)[-1]
        return round(last_baseline + last.font.getbbox(last.text, anchor="ms")[3])

    def _draw_publication_text(
        self, image: PilImage, draw: PilImageDraw, lines: list[_PubTextLine], top: int
    ) -> None:
        centre = image.width / 2
        for line, baseline in zip(
            lines, self._get_publication_text_baselines(lines, top), strict=True
        ):
            draw.text((centre, baseline), line.text, fill=line.color, font=line.font, anchor="ms")

    @staticmethod
    def _draw_inset_border(
        draw: PilImageDraw,
        left: int,
        top: int,
        width: int,
        height: int,
        color: tuple[int, int, int],
    ) -> None:
        """Frame the inset with a border drawn just outside it, leaving the art untouched."""
        b = INTRO_INSET_BORDER_WIDTH
        draw.rectangle(
            (left - b, top - b, left + width + b - 1, top + height + b - 1),
            outline=color,
            width=b,
        )

    def _get_resized_inset(self, max_width: int, max_height: int) -> PilImage:
        """Return the inset scaled, keeping its shape, to the largest size within the box."""
        if max_height <= 0:
            msg = (
                f"No room for the intro inset: the title, byline and publication text"
                f' leave {max_height} pixels for "{self._comic.intro_inset_file}".'
            )
            raise ValueError(msg)

        if isinstance(self._comic.intro_inset_file, Path):
            inset = open_image_for_reading(self._comic.intro_inset_file)
        else:
            buffer = self._comic.intro_inset_file.read_bytes()
            if self._get_inset_decrypted_bytes:
                buffer = self._get_inset_decrypted_bytes(buffer)
                if not buffer:
                    msg = (
                        f"Inset decryption failed with empty bytes:"
                        f' "{self._comic.intro_inset_file}".'
                    )
                    raise DecryptionError(msg)
            inset = load_pil_image_from_bytes(buffer, ext=self._comic.intro_inset_file.suffix)

        inset_width, inset_height = inset.size

        new_inset_width = max_width
        new_inset_height = round((inset_height / inset_width) * new_inset_width)
        if new_inset_height > max_height:
            new_inset_height = max_height
            new_inset_width = round((inset_width / inset_height) * new_inset_height)

        return inset.resize(
            size=(new_inset_width, new_inset_height),
            resample=Image.Resampling.BICUBIC,
        )

    def _get_intro_text_height(self, text: str, font: FreeTypeFont) -> int:
        lines = text.split("\n")
        fonts = self._get_title_line_fonts(lines, font)
        tops = self._get_title_line_tops(lines, fonts, font, INTRO_TITLE_SPACING)
        bboxes = [f.getbbox(line) for line, f in zip(lines, fonts, strict=True)]
        ink_top = min(top + bbox[1] for top, bbox in zip(tops, bboxes, strict=True))
        ink_bottom = max(top + bbox[3] for top, bbox in zip(tops, bboxes, strict=True))
        return round(ink_bottom - ink_top)

    @staticmethod
    def _is_small_word_line(line: str) -> bool:
        words = line.split()
        return bool(words) and all(word.lower() in INTRO_TITLE_SMALL_WORDS for word in words)

    def _get_title_line_fonts(self, lines: list[str], font: FreeTypeFont) -> list[FreeTypeFont]:
        is_small = [self._is_small_word_line(line) for line in lines]
        if all(is_small):
            return [font] * len(lines)

        small_font = font.font_variant(size=round(INTRO_TITLE_SMALL_WORD_SIZE_FRAC * font.size))
        return [small_font if small else font for small in is_small]

    @staticmethod
    def _get_title_line_tops(
        lines: list[str], fonts: list[FreeTypeFont], font: FreeTypeFont, spacing: int
    ) -> list[float]:
        """Return each title line's top, relative to the first's.

        Two full-size lines are as far apart as Pillow's multiline text puts them: the
        gap between their capitals is the spacing plus the room above a capital. A small
        line has that same gap to the lines either side, measured from its own letters, as a
        line of small words may have no capital at all.
        """
        cap_top, cap_bottom = font.getbbox("A")[1], font.getbbox("A")[3]
        gap = spacing + cap_top

        def get_extent(line: str, line_font: FreeTypeFont) -> tuple[float, float]:
            if line_font.size == font.size:
                return cap_top, cap_bottom
            bbox = line_font.getbbox(line)
            return bbox[1], bbox[3]

        tops = [0.0]
        for line_num in range(1, len(lines)):
            _, above_bottom = get_extent(lines[line_num - 1], fonts[line_num - 1])
            below_top, _ = get_extent(lines[line_num], fonts[line_num])
            tops.append(tops[-1] + above_bottom + gap - below_top)

        return tops

    @staticmethod
    def _get_title_scaled(size: int, font: FreeTypeFont) -> float:
        return size * font.size / INTRO_TITLE_DEFAULT_FONT_SIZE

    def _get_title_line_width(self, line: str, font: FreeTypeFont) -> float:
        _, width = self._get_title_letter_offsets(line, font)
        return width

    def _get_title_letter_offsets(self, line: str, font: FreeTypeFont) -> tuple[list[float], float]:
        """Return how far each letter of a title line is from the line's start, and its width.

        Within a word the letters are spaced apart from where the font puts them. Between
        two words, and either side of a hyphen, the gap is measured from the
        letters' ink, so it is the same whatever the letters. A space has no ink, so its
        offset is where the word before it ends.
        """
        tracking = self._get_title_scaled(INTRO_TITLE_TRACKING, font)
        offsets = [0.0] * len(line)
        ink_right: float | None = None
        after_space = after_hyphen = False
        width = 0.0
        for piece in _TITLE_LINE_PIECES.finditer(line):
            text = piece.group()
            if text.startswith(" "):
                for i in range(piece.start(), piece.end()):
                    offsets[i] = width
                after_space = True
                continue

            letter_offsets = [font.getlength(text[:i]) + (i * tracking) for i in range(len(text))]
            if ink_right is None:
                origin = 0.0
            else:
                gap = INTRO_TITLE_WORD_GAP if after_space else 0
                if text == "-" or after_hyphen:
                    gap = max(gap, INTRO_TITLE_HYPHEN_GAP)
                ink_left = letter_offsets[0] + font.getbbox(text[0])[0]
                origin = ink_right + self._get_title_scaled(gap, font) - ink_left

            for i, letter_offset in enumerate(letter_offsets):
                offsets[piece.start() + i] = origin + letter_offset
            ink_right = origin + letter_offsets[-1] + font.getbbox(text[-1])[2]
            width = origin + font.getlength(text) + (tracking * (len(text) - 1))
            after_space, after_hyphen = False, text == "-"

        return offsets, width

    def _get_title_text_width(self, text: str, font: FreeTypeFont) -> int:
        lines = text.split("\n")
        fonts = self._get_title_line_fonts(lines, font)
        return round(
            max(self._get_title_line_width(line, f) for line, f in zip(lines, fonts, strict=True))
        )

    def _draw_title_text(
        self,
        draw: PilImageDraw,
        left: float,
        top: float,
        text: str,
        font: FreeTypeFont,
        color: tuple[int, int, int],
        spacing: int,
    ) -> None:
        """Letter title text in its colour inside a black outline, with spaced letters.

        Each line is centred on the widest, and a line of small words is smaller (see
        `_get_title_line_tops` for how far apart the lines are). All the outlines go
        down before any colour, so a letter's outline never covers its neighbour's colour.
        """
        lines = text.split("\n")
        fonts = self._get_title_line_fonts(lines, font)
        tops = self._get_title_line_tops(lines, fonts, font, spacing)
        line_widths = [
            self._get_title_line_width(line, f) for line, f in zip(lines, fonts, strict=True)
        ]
        letters = []
        for line, line_font, line_top, line_width in zip(
            lines, fonts, tops, line_widths, strict=True
        ):
            line_left = left + ((max(line_widths) - line_width) / 2)
            offsets, _ = self._get_title_letter_offsets(line, line_font)
            for letter, offset in zip(line, offsets, strict=True):
                letters.append(((line_left + offset, top + line_top), letter, line_font))

        for xy, letter, letter_font in letters:
            outline_width = round(self._get_title_scaled(INTRO_TITLE_OUTLINE_WIDTH, letter_font))
            draw.text(
                xy,
                letter,
                fill=INTRO_TITLE_OUTLINE_COLOR,
                font=letter_font,
                stroke_width=max(1, outline_width),
                stroke_fill=INTRO_TITLE_OUTLINE_COLOR,
            )
        for xy, letter, letter_font in letters:
            draw.text(xy, letter, fill=color, font=letter_font)

    def _get_title_and_fonts(self) -> tuple[list[str], list[ImageFont.FreeTypeFont], int]:
        title = self._comic.get_comic_title()
        font_file = self._comic.title_font_file
        font_size = self._comic.title_font_size
        comic_book_info = self._comic.fanta_info.comic_book_info

        if (not comic_book_info.is_barks_title) and (comic_book_info.issue_name == Issues.CS):
            add_footnote = self._comic.get_ini_title() in US_CENSORED_TITLES

            return self._get_comics_and_stories_title_and_fonts(
                title,
                font_file,
                font_size,
                add_footnote,
            )

        title_font = self._get_fitted_title_font(title, font_file, font_size)
        text_height = self._get_intro_text_height(title, title_font)
        return [title], [title_font], text_height

    def _get_fitted_title_font(self, title: str, font_file: Path, font_size: int) -> FreeTypeFont:
        """Return the title's font, smaller if its widest line would not fit the page."""
        max_width = DEST_TARGET_WIDTH - (2 * INTRO_TITLE_MIN_MARGIN)
        font = _get_title_page_font(font_file, font_size)
        while font.size > 1 and self._get_title_ink_width(title, font) > max_width:
            font = font.font_variant(size=font.size - 1)
        return font

    def _get_title_ink_width(self, title: str, font: FreeTypeFont) -> float:
        """Return the width of a title's widest line, its outline included."""
        outline_width = self._get_title_scaled(INTRO_TITLE_OUTLINE_WIDTH, font)
        return self._get_title_text_width(title, font) + (2 * outline_width)

    def _get_comics_and_stories_title_and_fonts(
        self,
        title: str,
        font_file: Path,
        font_size: int,
        add_footnote: bool,
    ) -> tuple[list[str], list[ImageFont.FreeTypeFont], int]:
        """Return the masthead's pieces, "COMICS", "AND", "STORIES" and the issue number.

        "AND" and "STORIES" are small enough that, one over the other, they are as tall as
        the capitals of "COMICS". The height is the ink's, from "COMICS" to the number.
        """
        assert title.startswith(ISSUE_NAME[Issues.CS])

        comic_num = title[len(ISSUE_NAME[Issues.CS]) :].strip()

        font = _get_title_page_font(font_file, font_size)
        cap_height = _get_cap_height(font, INTRO_CS_COMICS)
        stack_line_cap_height = cap_height * (1 - INTRO_CS_STACK_LINE_GAP_FRAC) / 2
        small_font = font.font_variant(size=round(font_size * stack_line_cap_height / cap_height))

        text_height = self._get_intro_text_height(f"{INTRO_CS_COMICS}\n{comic_num}", font)

        if add_footnote:
            comic_num += FOOTNOTE_CHAR

        return (
            [INTRO_CS_COMICS, INTRO_CS_AND, INTRO_CS_STORIES, comic_num],
            [font, small_font, small_font, font],
            text_height,
        )

    def _draw_centered_multiline_title_text(
        self,
        text_vals: list[str],
        fonts: list[ImageFont.FreeTypeFont],
        color: tuple[int, int, int],
        top: int,
        spacing: int,
        image: PilImage,
        draw: PilImageDraw,
    ) -> None:
        """Letter the title centred on the page: a story's lines, or an issue's masthead."""
        if len(text_vals) > 1:
            self._draw_comics_and_stories_title(text_vals, fonts, color, top, spacing, image, draw)
            return

        title, font = text_vals[0], fonts[0]
        left = (image.width - self._get_title_text_width(title, font)) / 2
        self._draw_title_text(draw, left, top, title, font, color, spacing)

    def _draw_comics_and_stories_title(
        self,
        text_vals: list[str],
        fonts: list[ImageFont.FreeTypeFont],
        color: tuple[int, int, int],
        top: int,
        spacing: int,
        image: PilImage,
        draw: PilImageDraw,
    ) -> None:
        """Letter "COMICS" with "AND" over "STORIES" beside it, and the number below.

        The stack sits on the baseline of "COMICS", "AND" centred over "STORIES", and the
        whole masthead is centred, as is the number, its line as far below as a story
        title's second line. A US-censored issue's number has a raised footnote mark.
        """
        (comics, and_text, stories, number), (font, small_font, _, _) = text_vals, fonts

        comics_width = self._get_title_text_width(comics, font)
        and_width = self._get_title_text_width(and_text, small_font)
        stories_width = self._get_title_text_width(stories, small_font)
        stack_width = max(and_width, stories_width)
        stack_gap = round(INTRO_CS_STACK_GAP_FRAC * font.size)
        left = (image.width - (comics_width + stack_gap + stack_width)) / 2
        self._draw_title_text(draw, left, top, comics, font, color, spacing)

        baseline = top + font.getmetrics()[0]
        small_ascent = small_font.getmetrics()[0]
        and_baseline = baseline - (
            _get_cap_height(small_font, stories)
            + (INTRO_CS_STACK_LINE_GAP_FRAC * _get_cap_height(font, comics))
        )
        stack_left = left + comics_width + stack_gap
        for text, text_width, text_baseline in (
            (and_text, and_width, and_baseline),
            (stories, stories_width, baseline),
        ):
            text_left = stack_left + ((stack_width - text_width) / 2)
            self._draw_title_text(
                draw, text_left, text_baseline - small_ascent, text, small_font, color, spacing
            )

        digits = number.removesuffix(FOOTNOTE_CHAR)
        number_top = (
            top + self._get_title_line_tops([comics, digits], [font, font], font, spacing)[1]
        )
        number_width = self._get_title_text_width(number, font)
        number_left = (image.width - number_width) / 2
        self._draw_title_text(draw, number_left, number_top, digits, font, color, spacing)
        if digits != number:
            self._draw_superscript_title_text(
                FOOTNOTE_CHAR, color, int(number_left + number_width - 1), number_top, spacing, draw
            )

    def _draw_superscript_title_text(
        self,
        text: str,
        color: tuple[int, int, int],
        left: int,
        top: float,
        spacing: int,
        draw: PilImageDraw,
    ) -> None:
        superscript_font_size = int(0.7 * self._comic.title_font_size)
        superscript_font = _get_title_page_font(self._comic.title_font_file, superscript_font_size)
        self._draw_title_text(
            draw,
            left - int(0.75 * superscript_font_size),
            top - 20,
            text,
            superscript_font,
            color,
            spacing,
        )


def _get_cap_height(font: FreeTypeFont, text: str) -> float:
    """Return how far a text's capitals rise above its baseline."""
    return -font.getbbox(text, anchor="ls")[1]


def _get_inset_border_color(title_color: tuple[int, int, int]) -> tuple[int, int, int]:
    """Return the colour of the inset's border: a dark shade of the title's colour.

    Args:
        title_color: The title's colour.

    Returns:
        The title's colour at ``INTRO_INSET_BORDER_SHADE`` of its brightness.

    """
    red, green, blue = (round(INTRO_INSET_BORDER_SHADE * value) for value in title_color)
    return red, green, blue


def _get_title_page_font(font_file: str | Path, size: int) -> FreeTypeFont:
    """Return a font for the title page's text, at a size.

    It always uses Pillow's basic text layout. With the Raqm layout, Pillow applies a
    font's kerning, which pulls some of the Barks lettering's letters 30px closer; but
    Raqm is not there on every platform (not on Windows), and the reader letters title
    pages as it runs. The basic layout letters a title page the same everywhere, built
    page or reader.

    Args:
        font_file: The font file.
        size: The font size.

    Returns:
        The font.

    """
    return ImageFont.truetype(str(font_file), size, layout_engine=ImageFont.Layout.BASIC)


def build_double_page_image(left: PilImage, right: PilImage) -> PilImage:
    """Composite two pages side-by-side into a single landscape image.

    Args:
        left: The left page PIL image.
        right: The right page PIL image.

    Returns:
        A single landscape RGB PIL Image with left on the left and right on the right,
        both vertically centred on a black canvas.

    """
    width = left.width + right.width
    height = max(left.height, right.height)
    result = Image.new("RGB", (width, height), (0, 0, 0))

    left_top = (height - left.height) // 2
    right_top = (height - right.height) // 2
    result.paste(left, (0, left_top))
    result.paste(right, (left.width, right_top))

    return result
