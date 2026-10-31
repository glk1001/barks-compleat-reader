"""The app's font sizes, by role, for a low- or high-resolution window. Kivy-free.

The sizes are in scale-independent pixels, as Kivy's ``sp`` takes them; the font
manager scales them for the display.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

# A window taller than this takes the high-resolution sizes.
HI_RES_WINDOW_HEIGHT_CUTOFF = 1090


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
    title_info: float
    title_extra_info: float
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
    main_title_footnote=9,
    title_info=16,
    title_extra_info=14,
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
    main_title_footnote=10,
    title_info=20,
    title_extra_info=18,
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
