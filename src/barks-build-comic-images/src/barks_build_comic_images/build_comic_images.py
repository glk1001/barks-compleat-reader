# ruff: noqa: PLR0911
# cspell:ignore getbbox getmetrics Raqm

import functools
import math
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import NamedTuple

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
    INTRO_PUB_TEXT_ITALIC_FONT_FILE,
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
from comic_utils.pil_image_utils import contain_size, load_pil_image_from_bytes
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
# the page. Under it, a hard black shadow down and to the right lifts it off the page,
# as on a comic's logo. All are for the default title font size, and scale with it.
INTRO_TITLE_OUTLINE_COLOR = (0, 0, 0)
INTRO_TITLE_OUTLINE_WIDTH = 9
INTRO_TITLE_TRACKING = 8
INTRO_TITLE_SHADOW_COLOR = (0, 0, 0)
INTRO_TITLE_SHADOW_OFFSET = 5
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
# A US-censored issue's number carries a raised footnote mark, lettered smaller, a
# little after its last digit. The gap and the raise are for the default title font
# size, and scale with it.
INTRO_CS_FOOTNOTE_SIZE_FRAC = 0.7  # of the title font size
INTRO_CS_FOOTNOTE_GAP = 24
INTRO_CS_FOOTNOTE_RAISE = 20
# "by Carl Barks" on one line, the smaller "by" sitting on the author's baseline; or
# "art by", "story by" and the like, where the credits name another writer or artist.
INTRO_AUTHOR_COLOR = (0, 0, 0)
INTRO_BY_FONT_SIZE_FRAC = 0.6
INTRO_BY_AUTHOR_GAP = 28
# The inset is framed like a story panel, but in a dark shade of the title's colour
# rather than black ink, tying the art to the title. Its width cap lines it up with
# the widest title lines. A wide inset would be a thin strip at that width, so it is
# widened, up to a wider cap, until it is at least the minimum height: art wider than
# about 2:1 grows, the more the wider it is. And no inset is taller than 4:3 art at the
# width cap, so square and tall art leaves the page as much room as 4:3 art does,
# rather than filling all of it.
INTRO_INSET_MAX_WIDTH = 1450
INTRO_INSET_MAX_WIDE_WIDTH = 1850
INTRO_INSET_MIN_HEIGHT = 750
INTRO_INSET_MAX_HEIGHT = round(INTRO_INSET_MAX_WIDTH * 3 / 4)
INTRO_INSET_MIN_GAP = 130
# A page whose title, byline and publication text leave the inset less than this, after
# the gaps around it, is refused rather than built with a sliver of art: the title wants
# re-breaking, or a smaller title_font_size.
INTRO_INSET_LEAST_HEIGHT = INTRO_INSET_MIN_HEIGHT // 2
INTRO_INSET_BORDER_SHADE = 0.6  # of the title colour's brightness
INTRO_INSET_BORDER_WIDTH = 4
# The first paragraph of the publication text (the original publication) is in ink,
# its first line bold; any later paragraphs (this edition's credits) are smaller and
# in sepia. Above them all, a story Barks gave no title of his own, whose page is
# lettered with its issue's name, has the name it has since been given, in italic
# parentheses and sepia: an editor's note, set apart from his lettering. Advances are
# baseline to baseline.
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


class _InkExtent(NamedTuple):
    """Where lettering's ink lies, relative to the top it is lettered at."""

    top: int
    bottom: int

    @property
    def height(self) -> int:
        return self.bottom - self.top


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


@dataclass(frozen=True)
class BuildScale:
    """The size a page is built at: the book's own, or a fraction of it.

    A reader showing a page in a window a fraction of the book's size has no use
    for the whole page, so it asks for one built at that fraction: each length of
    the page's geometry is scaled by *factor* as the page is laid out, once, rather
    than the whole page being built and then shrunk.
    """

    factor: float
    width: int
    height: int

    def of(self, length: int) -> int:
        """Return *length* at this scale."""
        return round(length * self.factor)

    @property
    def is_full(self) -> bool:
        """Whether this is the book's own size."""
        return self.factor == 1.0


FULL_SCALE = BuildScale(1.0, DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT)

# The pages whose build measures something in the scan's own pixels: a splash's
# margin, a painting's border, a title page's lettering. Every other page is only
# resized from the scan, so a scan decoded smaller serves it as well.
SOURCE_MEASURED_PAGES = frozenset(
    {PageType.TITLE, PageType.SPLASH, PageType.PAINTING, PageType.BACK_PAINTING}
)


def get_build_scale(page_type: PageType, fit_within: tuple[int, int] | None) -> BuildScale:
    """Return the scale to build a page of *page_type* at so that it fits *fit_within*.

    A title page is lettered and laid out at the book's size, so it is built whole;
    so is any page when no box is given or the box is at least the book's page.

    Args:
        page_type: The destination page's type.
        fit_within: The width and height the page is to fit inside, or None.

    Returns:
        The scale to build at.

    """
    if fit_within is None or page_type == PageType.TITLE:
        return FULL_SCALE
    width, height = contain_size((DEST_TARGET_WIDTH, DEST_TARGET_HEIGHT), fit_within)
    if width >= DEST_TARGET_WIDTH or height >= DEST_TARGET_HEIGHT:
        return FULL_SCALE
    return BuildScale(min(width / DEST_TARGET_WIDTH, height / DEST_TARGET_HEIGHT), width, height)


def source_may_be_reduced(page_type: PageType) -> bool:
    """Whether a page of *page_type* builds as well from a scan decoded at a reduced scale."""
    return page_type not in SOURCE_MEASURED_PAGES


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
        # The empty page at each reduced scale it has been asked for.
        self._scaled_empty_pages: dict[tuple[int, int], PilImage] = {}

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
        *,
        fit_within: tuple[int, int] | None = None,
        srce_scale: float = 1.0,
    ) -> PilImage:
        """Build the destination page from its source page image.

        Args:
            srce_page_image: The source page, decoded.
            srce_page: The source page's geometry: its panels box in the scan.
            dest_page: The destination page's type and geometry, at the book's size.
            fit_within: The width and height the page is to fit inside, when it is
                for a window rather than the book. Every page but a title page is
                then built at that scale (see :func:`get_build_scale`).
            srce_scale: The scale *srce_page_image* was decoded at, when the scan was
                decoded smaller than it is (see :meth:`get_source_size_needed`): the
                source panels box is scaled by it. Only for a page
                :func:`source_may_be_reduced` allows.

        Returns:
            The page, in RGB, at the book's size or the scale that fits the box.

        """
        self._log_page_info(f"{srce_page.page_num}-Srce", srce_page_image, srce_page)
        self._log_page_info(f"{srce_page.page_num}-Dest", None, dest_page)
        assert srce_scale == 1.0 or source_may_be_reduced(dest_page.page_type)

        scale = get_build_scale(dest_page.page_type, fit_within)
        if dest_page.page_type in PAGES_WITHOUT_PANELS:
            dest_page_image = self._get_no_panels_dest_image(
                srce_page_image, srce_page, dest_page, scale
            )
        else:
            dest_page_image = self._get_main_page_dest_image(
                srce_page_image, srce_page, dest_page, scale, srce_scale
            )

        rgb_dest_page_image = dest_page_image.convert("RGB")

        self._log_page_info("Dest", rgb_dest_page_image, dest_page)

        return rgb_dest_page_image

    @staticmethod
    def get_source_size_needed(
        srce_page: CleanPage,
        dest_page: CleanPage,
        srce_size: tuple[int, int],
        fit_within: tuple[int, int],
    ) -> tuple[int, int] | None:
        """Return the least size the scan need be decoded at for a page built to fit a box.

        A page built at a reduced scale takes its panels, or its whole image, shrunk;
        a scan decoded at that shrunken size already, as a JPEG decoder can, serves
        it as well as the whole scan and costs a fraction to decode and resize.

        Args:
            srce_page: The source page's geometry: its panels box in the scan.
            dest_page: The destination page's type and geometry, at the book's size.
            srce_size: The scan's width and height, from its header.
            fit_within: The width and height the page is to fit inside.

        Returns:
            The width and height the scan must be decoded at, at least; or None when
            it must be decoded whole: a page measured in scan pixels, or one built
            at the book's size.

        """
        scale = get_build_scale(dest_page.page_type, fit_within)
        if scale.is_full or not source_may_be_reduced(dest_page.page_type):
            return None
        srce_width, srce_height = srce_size
        if dest_page.page_type in PAGES_WITHOUT_PANELS:
            # The whole image is resized onto the page at this scale.
            needed = max(scale.width / srce_width, scale.height / srce_height)
        else:
            needed = max(
                scale.of(dest_page.panels_bbox.get_width()) / srce_page.panels_bbox.get_width(),
                scale.of(dest_page.panels_bbox.get_height()) / srce_page.panels_bbox.get_height(),
            )
        if needed >= 1.0:
            return None
        return math.ceil(srce_width * needed), math.ceil(srce_height * needed)

    def _get_no_panels_dest_image(
        self,
        srce_page_image: PilImage,
        srce_page: CleanPage,
        dest_page: CleanPage,
        scale: BuildScale,
    ) -> PilImage:
        if dest_page.page_type == PageType.FRONT:
            return self._get_front_page_dest_image(srce_page_image, srce_page, scale)
        if dest_page.page_type == PageType.COVER:
            return self._get_cover_page_dest_image(srce_page_image, srce_page, scale)
        if dest_page.page_type in PAINTING_PAGES:
            return self._get_painting_page_dest_image(srce_page_image, srce_page, scale)
        if dest_page.page_type == PageType.SPLASH:
            return self._get_splash_page_dest_image(srce_page_image, srce_page, scale)
        if dest_page.page_type in ([*BACK_NO_PANELS_PAGES, PageType.FRONT_NO_PANELS]):
            return self._get_no_panels_page_dest_image(srce_page_image, srce_page, dest_page, scale)
        if dest_page.page_type == PageType.BLANK_PAGE:
            return self._get_blank_page_dest_image(srce_page_image, scale)
        if dest_page.page_type == PageType.TITLE:
            assert scale.is_full
            return self._get_dest_title_page_image(srce_page_image)
        raise AssertionError

    def _get_front_page_dest_image(
        self, srce_page_image: PilImage, srce_page: CleanPage, scale: BuildScale
    ) -> PilImage:
        return self._get_black_bars_page_dest_image(srce_page_image, srce_page, scale)

    def _get_cover_page_dest_image(
        self, srce_page_image: PilImage, srce_page: CleanPage, scale: BuildScale
    ) -> PilImage:
        return self._get_black_bars_page_dest_image(srce_page_image, srce_page, scale)

    def _get_painting_page_dest_image(
        self, painting_image: PilImage, srce_page: CleanPage, scale: BuildScale
    ) -> PilImage:
        assert srce_page.page_type in PAINTING_PAGES

        if srce_page.page_type in [
            PageType.PAINTING_NO_BORDER,
            PageType.BACK_PAINTING_NO_BORDER,
        ]:
            return self._get_black_bars_page_dest_image(painting_image, srce_page, scale)

        assert srce_page.page_type in [PageType.PAINTING, PageType.BACK_PAINTING]
        self._draw_border_around_image(painting_image)

        return self._get_centred_page_dest_image(
            painting_image, srce_page, BasePageType.EMPTY_PAGE, scale
        )

    def _get_splash_page_dest_image(
        self, splash_image: PilImage, srce_page: CleanPage, scale: BuildScale
    ) -> PilImage:
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

        return self._get_centred_page_dest_image(
            splash_image, srce_page, BasePageType.EMPTY_PAGE, scale
        )

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
        scale: BuildScale,
    ) -> PilImage:
        dest_page_image = self._get_centred_page_dest_image(
            no_panels_image,
            srce_page,
            BasePageType.EMPTY_PAGE,
            scale,
        )

        self._write_page_number(dest_page_image, dest_page, PAGE_NUM_COLOR, scale)

        return dest_page_image

    def _get_black_bars_page_dest_image(
        self,
        srce_page_image: PilImage,
        srce_page: CleanPage,
        scale: BuildScale,
    ) -> PilImage:
        return self._get_centred_page_dest_image(
            srce_page_image,
            srce_page,
            BasePageType.BLACK_PAGE,
            scale,
        )

    def _get_empty_page_image(self, scale: BuildScale) -> PilImage:
        """Return the empty page at *scale*, shrunk once and kept for the next page."""
        if scale.is_full:
            return self._empty_page_image
        size = (scale.width, scale.height)
        if size not in self._scaled_empty_pages:
            self._scaled_empty_pages[size] = self._empty_page_image.resize(
                size, resample=Image.Resampling.LANCZOS
            )
        return self._scaled_empty_pages[size]

    def _get_centred_page_dest_image(
        self,
        srce_page_image: PilImage,
        srce_page: CleanPage,
        base_page_type: BasePageType,
        scale: BuildScale,
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
            scale.width,
            srce_page_image.width,
            srce_page_image.height,
        )
        # At a reduced scale the rounding of a page that fills the book's page can
        # leave it a pixel short or over: that is the whole page, not a black bar.
        if not scale.is_full and abs(required_height - scale.height) <= 1:
            required_height = scale.height

        no_margins_image = srce_page_image.resize(
            size=(scale.width, required_height),
            resample=Image.Resampling.BICUBIC if scale.is_full else Image.Resampling.LANCZOS,
        )
        no_margins_aspect_ratio = float(no_margins_image.height) / float(no_margins_image.width)
        assert abs(srce_aspect_ratio - no_margins_aspect_ratio) <= small_float

        if required_height == scale.height:
            return no_margins_image

        cover_top = round(0.5 * (scale.height - required_height))
        base_page_image = (
            self._get_empty_page_image(scale).copy()
            if base_page_type == BasePageType.EMPTY_PAGE
            else Image.new("RGB", (scale.width, scale.height), (0, 0, 0))
        )
        base_page_image.paste(no_margins_image, (0, cover_top))

        return base_page_image

    @staticmethod
    def _get_blank_page_dest_image(srce_page_image: PilImage, scale: BuildScale) -> PilImage:
        return srce_page_image.resize(
            size=(scale.width, scale.height),
            resample=Image.Resampling.BICUBIC,
        )

    def _get_main_page_dest_image(
        self,
        srce_page_image: PilImage,
        srce_page: CleanPage,
        dest_page: CleanPage,
        scale: BuildScale,
        srce_scale: float = 1.0,
    ) -> PilImage:
        panels_image, panels_box = self._crop_panels(srce_page_image, srce_page, srce_scale)
        panels_rgb, paste_mask = self._page_image_source.to_renderable(panels_image)
        panels_rgb, paste_mask = self._get_resized_srce_images(
            dest_page, panels_rgb, paste_mask, scale, panels_box
        )

        dest_page_image = self._get_empty_page_image(scale).copy()
        dest_panels_pos = (
            scale.of(dest_page.panels_bbox.x_min),
            scale.of(dest_page.panels_bbox.y_min),
        )
        dest_page_image.paste(panels_rgb, dest_panels_pos, mask=paste_mask)

        if dest_page_image.width != scale.width:
            msg = (
                f'Width mismatch for page "{srce_page.page_filename}":'
                f"{dest_page_image.width} != {scale.width}"
            )
            raise RuntimeError(msg)
        if dest_page_image.height != scale.height:
            msg = (
                f'Height mismatch for page "{srce_page.page_filename}":'
                f"{dest_page_image.height} != {scale.height}"
            )
            raise RuntimeError(msg)

        self._write_page_number(dest_page_image, dest_page, PAGE_NUM_COLOR, scale)

        return dest_page_image

    @staticmethod
    def _crop_panels(
        srce_page_image: PilImage, srce_page: CleanPage, srce_scale: float
    ) -> tuple[PilImage, tuple[float, float, float, float] | None]:
        """Crop the panels out of the scan, and say where they lie within the crop.

        The panels box is measured on the whole scan. On a scan decoded smaller its
        edges fall between pixels, so the crop takes the whole pixels around them and
        the resize is told the exact box, as fractions of a pixel: rounding the box
        instead would shift every page a part of a pixel, which shows on line art.

        Returns:
            The crop, and the panels box within it when it is fractional, else ``None``.

        """
        if srce_scale == 1.0:
            return srce_page_image.crop(srce_page.panels_bbox.get_box()), None

        left, upper, right, lower = (edge * srce_scale for edge in srce_page.panels_bbox.get_box())
        crop_left, crop_upper = math.floor(left), math.floor(upper)
        crop = srce_page_image.crop((crop_left, crop_upper, math.ceil(right), math.ceil(lower)))
        return crop, (left - crop_left, upper - crop_upper, right - crop_left, lower - crop_upper)

    @staticmethod
    def _get_resized_srce_images(
        dest_page: CleanPage,
        panels_rgb: PilImage,
        paste_mask: PilImage | None,
        scale: BuildScale,
        box: tuple[float, float, float, float] | None,
    ) -> tuple[PilImage, PilImage | None]:
        """Resize the panels, and their paste mask with them, to the page's panels box.

        Args:
            dest_page: The page being built; its panels box gives the target size.
            panels_rgb: The panels cropped out of the scan.
            paste_mask: The panels' alpha, when the source has one, else ``None``.
            scale: The scale the page is built at.
            box: The panels' exact, fractional edges within the crop, or ``None`` for
                the whole crop.

        Returns:
            The resized panels and, when there was one, the resized mask.

        """
        target_size = (
            scale.of(dest_page.panels_bbox.get_width()),
            scale.of(dest_page.panels_bbox.get_height()),
        )
        # At the book's size the panels are enlarged a little, or not at all; at a
        # reduced scale they are shrunk, which LANCZOS does better.
        resample = Image.Resampling.BICUBIC if scale.is_full else Image.Resampling.LANCZOS
        panels_rgb = panels_rgb.resize(size=target_size, resample=resample, box=box)
        if paste_mask is not None:
            paste_mask = paste_mask.resize(size=target_size, resample=resample, box=box)
        return panels_rgb, paste_mask

    def _write_page_number(
        self,
        dest_page_image: PilImage,
        dest_page: CleanPage,
        color: tuple[int, int, int],
        scale: BuildScale,
    ) -> None:
        draw = ImageDraw.Draw(dest_page_image)

        dest_page_centre = int(dest_page_image.width / 2)
        page_num_x_start = dest_page_centre - scale.of(PAGE_NUM_X_OFFSET_FROM_CENTRE)
        page_num_x_end = dest_page_centre + scale.of(PAGE_NUM_X_OFFSET_FROM_CENTRE)
        page_num_height = scale.of(PAGE_NUM_HEIGHT)
        page_num_y_start = (
            dest_page_image.height - scale.of(self._required_dim.page_num_y_bottom)
        ) - page_num_height
        page_num_y_end = page_num_y_start + page_num_height

        # Get the color of a blank part of the page
        page_blank_color = dest_page_image.getpixel(
            (
                page_num_x_start + scale.of(PAGE_NUM_X_BLANK_PIXEL_OFFSET),
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

        font = ImageFont.truetype(PAGE_NUM_FONT_FILE, max(1, scale.of(PAGE_NUM_FONT_SIZE)))
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

        title, title_fonts, title_ink = self._get_title_and_fonts()

        # Lettered so that the top of its ink, outline included, is at INTRO_TOP.
        self._draw_centered_multiline_title_text(
            title,
            title_fonts,
            self._comic.title_color,
            top - title_ink.top,
            spacing=INTRO_TITLE_SPACING,
            image=dest_page_image,
            draw=draw,
        )
        title_bottom = top + title_ink.height

        pub_lines = self._get_publication_text_lines()
        pub_height = self._get_publication_text_height(pub_lines)
        pub_top = dest_page_image.height - INTRO_BOTTOM_MARGIN - pub_height

        # What is left for the inset and the three gaps around the byline and the inset.
        room = pub_top - title_bottom - self._get_byline_height()
        inset_room = room - INTRO_TITLE_BYLINE_MIN_GAP - (2 * INTRO_INSET_MIN_GAP)
        if inset_room < INTRO_INSET_LEAST_HEIGHT:
            msg = (
                f'No room for the intro inset "{self._comic.intro_inset_file}": the title,'
                f" byline and publication text leave {room} pixels, {inset_room} after the"
                f" gaps around the inset, and it needs {INTRO_INSET_LEAST_HEIGHT}."
            )
            raise ValueError(msg)
        inset = self._get_resized_inset(
            INTRO_INSET_MAX_WIDTH,
            min(INTRO_INSET_MAX_HEIGHT, inset_room),
            min_height=INTRO_INSET_MIN_HEIGHT,
            max_wide_width=INTRO_INSET_MAX_WIDE_WIDTH,
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
        """Return the fonts for the byline's "by" (or "art by"...) and for the author's name."""
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
        """Draw "by Carl Barks" with the top of its ink at ``top``; return its ink bottom.

        The small words before the name are the story's byline: "by", or "art by" and the
        like, where the credits name another writer or artist.
        """
        byline = self._comic.byline
        by_font, author_font = self._get_byline_fonts()

        _, ink_top, _, ink_bottom = author_font.getbbox(BARKS, anchor="ls")
        baseline = top - ink_top

        by_width = draw.textlength(byline, by_font)
        author_width = draw.textlength(BARKS, author_font)
        left = (image.width - (by_width + INTRO_BY_AUTHOR_GAP + author_width)) / 2
        draw.text((left, baseline), byline, fill=INTRO_AUTHOR_COLOR, font=by_font, anchor="ls")
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

        lines = []
        if not self._comic.title:
            italic_font = _get_title_page_font(
                INTRO_PUB_TEXT_ITALIC_FONT_FILE, INTRO_PUB_TEXT_FONT_SIZE
            )
            lines.append(
                _PubTextLine(
                    f"({self._comic.get_ini_title()})",
                    italic_font,
                    INTRO_PUB_CREDITS_COLOR,
                    INTRO_PUB_TEXT_LINE_ADVANCE,
                )
            )
        for i, text in enumerate(first_paragraph.split("\n")):
            advance = INTRO_PUB_TEXT_LINE_ADVANCE
            if i == 0 and lines:
                advance += INTRO_PUB_PARAGRAPH_GAP
            lines.append(
                _PubTextLine(text, bold_font if i == 0 else font, INTRO_PUB_TEXT_COLOR, advance)
            )
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

    def _get_resized_inset(
        self, max_width: int, max_height: int, min_height: int = 0, max_wide_width: int = 0
    ) -> PilImage:
        """Return the inset scaled, keeping its shape, to the largest size within the box.

        A wide inset, one that would be less than ``min_height`` tall at ``max_width``, may
        be as wide as ``max_wide_width`` instead, to come nearer that height.
        """
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

        wide_width = min(max_wide_width, round(min_height * inset_width / inset_height))
        new_inset_width = max(max_width, wide_width)
        new_inset_height = round((inset_height / inset_width) * new_inset_width)
        if new_inset_height > max_height:
            new_inset_height = max_height
            new_inset_width = round((inset_width / inset_height) * new_inset_height)

        return inset.resize(
            size=(new_inset_width, new_inset_height),
            resample=Image.Resampling.BICUBIC,
        )

    def _get_intro_text_extent(self, text: str, font: FreeTypeFont) -> _InkExtent:
        """Return where a title's ink lies, relative to the top it is lettered at.

        From the top of its letters' outline to the bottom of their shadow: the outline
        is drawn around each letter and the shadow below it, so the ink reaches past the
        letters' own box at both ends.
        """
        lines = text.split("\n")
        fonts = self._get_title_line_fonts(lines, font)
        tops = self._get_title_line_tops(lines, fonts, font, INTRO_TITLE_SPACING)
        bboxes = [f.getbbox(line) for line, f in zip(lines, fonts, strict=True)]
        outlines = [self._get_title_outline_width(f) for f in fonts]
        ink_top = min(
            top + bbox[1] - outline
            for top, bbox, outline in zip(tops, bboxes, outlines, strict=True)
        )
        ink_bottom = max(
            top + bbox[3] + outline + self._get_title_scaled(INTRO_TITLE_SHADOW_OFFSET, f)
            for top, bbox, outline, f in zip(tops, bboxes, outlines, fonts, strict=True)
        )
        return _InkExtent(round(ink_top), round(ink_bottom))

    def _get_intro_text_height(self, text: str, font: FreeTypeFont) -> int:
        """Return how tall a title's ink is, from its outline's top to its shadow's bottom."""
        return self._get_intro_text_extent(text, font).height

    @staticmethod
    def _is_small_word_line(line: str) -> bool:
        words = line.split()
        return bool(words) and all(word.lower() in INTRO_TITLE_SMALL_WORDS for word in words)

    def _get_title_line_fonts(self, lines: list[str], font: FreeTypeFont) -> list[FreeTypeFont]:
        is_small = [self._is_small_word_line(line) for line in lines]
        if all(is_small):
            return [font] * len(lines)

        small_font = _get_title_page_font_sized(
            font, round(INTRO_TITLE_SMALL_WORD_SIZE_FRAC * font.size)
        )
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

    def _get_title_outline_width(self, font: FreeTypeFont) -> int:
        return max(1, round(self._get_title_scaled(INTRO_TITLE_OUTLINE_WIDTH, font)))

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
        `_get_title_line_tops` for how far apart the lines are). The shadows go down first,
        then all the outlines, then the colour, so neither a letter's shadow nor its outline
        ever covers its neighbour's colour.
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

        for (x, y), letter, letter_font in letters:
            shadow_offset = self._get_title_scaled(INTRO_TITLE_SHADOW_OFFSET, letter_font)
            draw.text(
                (x + shadow_offset, y + shadow_offset),
                letter,
                fill=INTRO_TITLE_SHADOW_COLOR,
                font=letter_font,
                stroke_width=self._get_title_outline_width(letter_font),
                stroke_fill=INTRO_TITLE_SHADOW_COLOR,
            )
        for xy, letter, letter_font in letters:
            draw.text(
                xy,
                letter,
                fill=INTRO_TITLE_OUTLINE_COLOR,
                font=letter_font,
                stroke_width=self._get_title_outline_width(letter_font),
                stroke_fill=INTRO_TITLE_OUTLINE_COLOR,
            )
        for xy, letter, letter_font in letters:
            draw.text(xy, letter, fill=color, font=letter_font)

    def _get_title_and_fonts(self) -> tuple[list[str], list[FreeTypeFont], _InkExtent]:
        """Return the title's lines, their fonts, and where its ink lies below its top."""
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
        return [title], [title_font], self._get_intro_text_extent(title, title_font)

    def _get_fitted_title_font(self, title: str, font_file: Path, font_size: int) -> FreeTypeFont:
        """Return the title's font, smaller if its widest line would not fit the page.

        The largest size, up to the title's own, at which its widest line fits. The
        width grows all but in step with the size (the letter gaps and the outline scale
        with it; only their rounding does not), so one step in proportion lands within a
        point or two of that size, and single points settle it, rather than measuring
        every letter at every size down from the title's own.
        """
        max_width = DEST_TARGET_WIDTH - (2 * INTRO_TITLE_MIN_MARGIN)

        def fits(size: int) -> bool:
            return self._get_title_ink_width(title, _get_title_page_font(font_file, size)) <= (
                max_width
            )

        size = font_size
        width = self._get_title_ink_width(title, _get_title_page_font(font_file, size))
        if width > max_width:
            size = max(1, math.floor(size * max_width / width))
            while size > 1 and not fits(size):
                size -= 1
            while size < font_size and fits(size + 1):
                size += 1
        return _get_title_page_font(font_file, size)

    def _get_title_ink_width(self, title: str, font: FreeTypeFont) -> float:
        """Return the width of a title's widest line, its outline and shadow included."""
        outline_width = self._get_title_scaled(INTRO_TITLE_OUTLINE_WIDTH, font)
        shadow_offset = self._get_title_scaled(INTRO_TITLE_SHADOW_OFFSET, font)
        return self._get_title_text_width(title, font) + (2 * outline_width) + shadow_offset

    def _get_comics_and_stories_title_and_fonts(
        self,
        title: str,
        font_file: Path,
        font_size: int,
        add_footnote: bool,
    ) -> tuple[list[str], list[FreeTypeFont], _InkExtent]:
        """Return the masthead's pieces, "COMICS", "AND", "STORIES" and the issue number.

        "AND" and "STORIES" are small enough that, one over the other, they are as tall as
        the capitals of "COMICS". The height is the ink's, from "COMICS" to the number.
        """
        assert title.startswith(ISSUE_NAME[Issues.CS])

        comic_num = title[len(ISSUE_NAME[Issues.CS]) :].strip()

        font = _get_title_page_font(font_file, font_size)
        cap_height = _get_cap_height(font, INTRO_CS_COMICS)
        stack_line_cap_height = cap_height * (1 - INTRO_CS_STACK_LINE_GAP_FRAC) / 2
        small_font = _get_title_page_font_sized(
            font, round(font_size * stack_line_cap_height / cap_height)
        )

        ink = self._get_intro_text_extent(f"{INTRO_CS_COMICS}\n{comic_num}", font)

        if add_footnote:
            comic_num += FOOTNOTE_CHAR

        return (
            [INTRO_CS_COMICS, INTRO_CS_AND, INTRO_CS_STORIES, comic_num],
            [font, small_font, small_font, font],
            ink,
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
        digits_width = self._get_title_text_width(digits, font)
        number_left = (image.width - digits_width) / 2
        self._draw_title_text(draw, number_left, number_top, digits, font, color, spacing)
        if digits != number:
            self._draw_footnote_mark(
                draw, number_left + digits_width, number_top, font, color, spacing
            )

    def _draw_footnote_mark(
        self,
        draw: PilImageDraw,
        digits_right: float,
        number_top: float,
        font: FreeTypeFont,
        color: tuple[int, int, int],
        spacing: int,
    ) -> None:
        """Letter the raised footnote mark a little after the number's last digit."""
        mark_font = _get_title_page_font_sized(font, round(INTRO_CS_FOOTNOTE_SIZE_FRAC * font.size))
        left = digits_right + self._get_title_scaled(INTRO_CS_FOOTNOTE_GAP, font)
        top = number_top - self._get_title_scaled(INTRO_CS_FOOTNOTE_RAISE, font)
        self._draw_title_text(draw, left, top, FOOTNOTE_CHAR, mark_font, color, spacing)


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

    Each face is loaded once and kept: laying out one title page asks for the same few
    faces many times over, and the reader letters a page for every comic it opens.

    Args:
        font_file: The font file.
        size: The font size.

    Returns:
        The font.

    """
    return _load_title_page_font(str(font_file), size)


def _get_title_page_font_sized(font: FreeTypeFont, size: int) -> FreeTypeFont:
    """Return a title page font's face at another size, from the same cache."""
    font_file = font.path
    assert isinstance(font_file, str)
    return _load_title_page_font(font_file, size)


@functools.cache
def _load_title_page_font(font_file: str, size: int) -> FreeTypeFont:
    return ImageFont.truetype(font_file, size, layout_engine=ImageFont.Layout.BASIC)


def build_double_page_image(
    left: PilImage,
    right: PilImage,
    gap: int = 0,
    gap_color: tuple[int, int, int] = (0, 0, 0),
) -> PilImage:
    """Composite two pages side-by-side into a single landscape image.

    Args:
        left: The left page PIL image.
        right: The right page PIL image.
        gap: Pixels between the two pages (a book's gutter).
        gap_color: The gutter's RGB colour.

    Returns:
        A single landscape RGB PIL Image with left on the left and right on the right,
        *gap* apart, both vertically centred on a black canvas.

    """
    width = left.width + gap + right.width
    height = max(left.height, right.height)
    result = Image.new("RGB", (width, height), (0, 0, 0))

    left_top = (height - left.height) // 2
    right_top = (height - right.height) // 2
    result.paste(left, (0, left_top))
    result.paste(right, (left.width + gap, right_top))
    if gap > 0:
        ImageDraw.Draw(result).rectangle(
            (left.width, 0, left.width + gap - 1, height - 1), fill=gap_color
        )

    return result
