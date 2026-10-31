"""The main screen's layout rule: single page or two-page spread (barks_reader.core.main_layout)."""

from __future__ import annotations

import pytest
from barks_reader.core.main_layout import (
    MAIN_SCREEN_LAYOUT_OPTIONS,
    MATCH_THE_SCREEN,
    SINGLE_PAGE,
    SPREAD_WIDTH_IN_PAGES,
    TWO_PAGE_SPREAD,
    MainLayoutMode,
    choose_main_layout,
    content_aspect_ratio,
    page_width,
    spread_fits,
)
from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO

BAR = 45


# The geometry table in docs/plans/two-page-spread.md: the spread when two pages as tall
# as the screen allows fit side by side.
@pytest.mark.parametrize(
    ("name", "width", "height", "fits"),
    [
        ("4K TV 16:9", 3840, 2160, True),
        ("27-inch 2560x1440", 2560, 1440, True),
        ("1920x1080", 1920, 1080, True),
        ("laptop 1920x1200", 1920, 1200, True),
        ("3:2 2160x1440", 2160, 1440, True),
        ("1366x768", 1366, 768, True),
        ("4:3 1440x1080, 68 px to spare", 1440, 1080, True),
        ("5:4 1280x1024, the pages would shrink 1%", 1280, 1024, False),
        ("ultra-wide 3440x1440", 3440, 1440, True),
        ("the flip laptop in portrait", 1200, 1920, False),
    ],
)
def test_the_spread_fits_when_two_full_height_pages_do(
    name: str, width: int, height: int, fits: bool
) -> None:
    assert spread_fits(width, height, BAR) is fits, name


def test_the_boundary_is_the_pair_exactly_as_wide_as_the_screen() -> None:
    page = (1080 - BAR) / COMIC_PAGE_ASPECT_RATIO
    pair = page * SPREAD_WIDTH_IN_PAGES
    assert spread_fits(round(pair + 1), 1080, BAR)
    assert not spread_fits(round(pair - 1), 1080, BAR)


@pytest.mark.parametrize(
    ("setting", "width", "height", "mode"),
    [
        (MATCH_THE_SCREEN, 1920, 1080, MainLayoutMode.SPREAD),
        (MATCH_THE_SCREEN, 1200, 1920, MainLayoutMode.SINGLE),
        (SINGLE_PAGE, 1920, 1080, MainLayoutMode.SINGLE),  # the setting, whatever the screen
        (TWO_PAGE_SPREAD, 1200, 1920, MainLayoutMode.SPREAD),  # width-limited, as asked
        ("not a setting", 1920, 1080, MainLayoutMode.SPREAD),  # an unknown value matches
    ],
)
def test_the_setting_chooses_or_the_screen_does(
    setting: str, width: int, height: int, mode: MainLayoutMode
) -> None:
    assert choose_main_layout(setting, width, height, BAR) is mode


def test_the_settings_options_are_the_three_values_in_the_panels_order() -> None:
    assert MAIN_SCREEN_LAYOUT_OPTIONS == (MATCH_THE_SCREEN, SINGLE_PAGE, TWO_PAGE_SPREAD)


def test_the_spreads_shape_is_the_page_over_two_pages() -> None:
    assert content_aspect_ratio(MainLayoutMode.SINGLE) == COMIC_PAGE_ASPECT_RATIO
    spread = content_aspect_ratio(MainLayoutMode.SPREAD)
    assert spread == pytest.approx(COMIC_PAGE_ASPECT_RATIO / 2)
    assert spread == pytest.approx(0.755, abs=0.001)
    assert content_aspect_ratio(MainLayoutMode.SPREAD, 2.0) == pytest.approx(1.0)


def test_a_spread_is_two_touching_pages() -> None:
    """No gutter: the readers' two-up pairs, which touch, fill the window as the pages do."""
    assert page_width(2000.0) == pytest.approx(1000.0)
    assert 2 * page_width(2000.0) == pytest.approx(2000.0)


def test_a_page_in_the_spread_is_as_wide_as_the_single_column_at_the_same_height() -> None:
    """Why the rule needs no tolerance: in the spread nothing gets smaller."""
    height = 1080 - BAR
    single_width = height / COMIC_PAGE_ASPECT_RATIO
    spread_width = height / content_aspect_ratio(MainLayoutMode.SPREAD)
    assert page_width(spread_width) == pytest.approx(single_width)
