"""Tests for `font_group_for_height`, the font group a window's height picks."""

from __future__ import annotations

import pytest
from barks_reader.core.font_sizes import (
    HI_RES_WINDOW_HEIGHT_CUTOFF,
    TITLE_TEXT_SMALLEST_WINDOW_HEIGHT,
    FontGroup,
    TitleTextSizes,
    font_group_for_height,
    title_text_sizes_for_height,
)


def test_a_window_at_the_cutoff_takes_the_low_res_sizes() -> None:
    assert font_group_for_height(HI_RES_WINDOW_HEIGHT_CUTOFF) == FontGroup.LOW_RES


def test_a_window_taller_than_the_cutoff_takes_the_hi_res_sizes() -> None:
    assert font_group_for_height(HI_RES_WINDOW_HEIGHT_CUTOFF + 1) == FontGroup.HI_RES


@pytest.mark.parametrize(
    ("window_height", "expected"),
    [
        (1360, TitleTextSizes(info=19, notes=17)),  # 2560x1440, on Windows
        (1365, TitleTextSizes(info=19, notes=17)),  # 2560x1440, elsewhere
        (1359, TitleTextSizes(info=18, notes=16)),
        (1005, TitleTextSizes(info=14, notes=12)),  # 1920x1080
        (2720, TitleTextSizes(info=38, notes=34)),
    ],
)
def test_the_title_text_scales_with_the_window(
    window_height: int, expected: TitleTextSizes
) -> None:
    assert title_text_sizes_for_height(window_height) == expected


def test_the_title_text_stops_shrinking_below_a_1080p_window() -> None:
    smallest = title_text_sizes_for_height(TITLE_TEXT_SMALLEST_WINDOW_HEIGHT)
    assert title_text_sizes_for_height(TITLE_TEXT_SMALLEST_WINDOW_HEIGHT - 300) == smallest
