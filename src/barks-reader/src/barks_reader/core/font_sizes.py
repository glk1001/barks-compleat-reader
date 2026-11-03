"""The app's font sizes, by role, for a low- or high-resolution window. Kivy-free.

The sizes are in scale-independent pixels, as Kivy's ``sp`` takes them; the font
manager scales them for the display.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import NamedTuple

# A window taller than this takes the high-resolution sizes.
HI_RES_WINDOW_HEIGHT_CUTOFF = 1090

# The title panel's publication info and notes take these sizes in the window a 2560x1440
# screen opens (1360 tall on Windows, 1365 elsewhere), and scale with the window's height
# from there: its shape is fixed and the panel grows with it, so the lines break much the
# same at any size. Kivy cuts a font size down to a whole number, so these do it themselves.
TITLE_TEXT_REFERENCE_WINDOW_HEIGHT = 1360
TITLE_INFO_REFERENCE_SIZE = 19
TITLE_EXTRA_INFO_REFERENCE_SIZE = 17
# A window shorter than a 1080p screen's keeps this height's sizes, to stay readable.
TITLE_TEXT_SMALLEST_WINDOW_HEIGHT = 1000


class FontGroup(Enum):
    """Which set of sizes a window takes; NOT_SET until its height is known."""

    NOT_SET = auto()
    LOW_RES = auto()
    HI_RES = auto()


def font_group_for_height(window_height: int) -> FontGroup:
    """Return the set of sizes a window of `window_height` takes."""
    if window_height <= HI_RES_WINDOW_HEIGHT_CUTOFF:
        return FontGroup.LOW_RES
    return FontGroup.HI_RES


class TitleTextSizes(NamedTuple):
    """The title panel's text sizes, in pixels."""

    info: int
    notes: int


def title_text_sizes_for_height(window_height: int) -> TitleTextSizes:
    """Return the sizes of the title panel's publication info and notes.

    Args:
        window_height: The window's height, in pixels.

    Returns:
        The sizes, in pixels rather than sp: they follow the window's pixels, as the panel does.

    """
    height = max(window_height, TITLE_TEXT_SMALLEST_WINDOW_HEIGHT)
    return TitleTextSizes(
        info=TITLE_INFO_REFERENCE_SIZE * height // TITLE_TEXT_REFERENCE_WINDOW_HEIGHT,
        notes=TITLE_EXTRA_INFO_REFERENCE_SIZE * height // TITLE_TEXT_REFERENCE_WINDOW_HEIGHT,
    )


def font_sizes_for_height(window_height: int) -> FontTheme:
    """Return the sizes a window of `window_height` takes, unscaled (in sp).

    For a popup that is its own window, opened before the font manager exists, and for
    the popup frame, whose sizes follow the window it is on.

    Args:
        window_height: The window's height, in pixels.

    Returns:
        The low- or high-resolution sizes.

    """
    if font_group_for_height(window_height) is FontGroup.LOW_RES:
        return LOW_RES_FONT_SIZES
    return HI_RES_FONT_SIZES


@dataclass(frozen=True, slots=True)
class FontTheme:
    """Every font size the app uses, by role."""

    main_title: float
    main_title_footnote: float
    playlist_intro: float
    index_menu: float
    index_prefix: float
    main_index_item: float
    speech_index_item: float
    index_title_item: float
    speech_bubble_text: float
    year_range: float
    checkbox: float
    default: float
    error_main_view: float
    text_block_heading: float
    app_title: float
    about_box_title: float
    about_box_version: float
    # Every popup on the shared frame (``ui.popup_frame``): its title, its message text
    # and its buttons.
    popup_title: float
    popup_text: float
    popup_button: float
    search_result: float
    search_input: float
    search_tag_chip: float
    search_label: float
    search_clear_button: float
    search_button: float


LOW_RES_FONT_SIZES = FontTheme(
    main_title=30,
    main_title_footnote=12,
    playlist_intro=14,
    index_menu=13,
    index_prefix=12,
    main_index_item=12,
    speech_index_item=11,
    index_title_item=12,
    speech_bubble_text=13,
    year_range=14,
    checkbox=14,
    default=15,
    error_main_view=40,
    text_block_heading=20,
    app_title=12,
    about_box_title=20,
    about_box_version=17,
    popup_title=18,
    popup_text=15,
    popup_button=15,
    search_result=14,
    search_input=17,
    search_tag_chip=13,
    search_label=14,
    search_clear_button=16,
    search_button=14,
)
HI_RES_FONT_SIZES = FontTheme(
    main_title=40,
    main_title_footnote=14,
    playlist_intro=18,
    index_menu=17,
    index_prefix=15,
    main_index_item=16,
    speech_index_item=15,
    index_title_item=16,
    speech_bubble_text=15,
    year_range=18,
    checkbox=19,
    default=19,
    error_main_view=40,
    text_block_heading=25,
    app_title=17,
    about_box_title=26,
    about_box_version=23,
    popup_title=23,
    popup_text=20,
    popup_button=18,
    search_result=18,
    search_input=22,
    search_tag_chip=17,
    search_label=18,
    search_clear_button=20,
    search_button=18,
)
