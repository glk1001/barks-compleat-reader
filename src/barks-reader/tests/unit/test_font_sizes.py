"""Tests for `font_group_for_height`, the font group a window's height picks."""

from __future__ import annotations

from barks_reader.core.font_sizes import (
    HI_RES_WINDOW_HEIGHT_CUTOFF,
    FontGroup,
    font_group_for_height,
)


def test_a_window_at_the_cutoff_takes_the_low_res_sizes() -> None:
    assert font_group_for_height(HI_RES_WINDOW_HEIGHT_CUTOFF) == FontGroup.LOW_RES


def test_a_window_taller_than_the_cutoff_takes_the_hi_res_sizes() -> None:
    assert font_group_for_height(HI_RES_WINDOW_HEIGHT_CUTOFF + 1) == FontGroup.HI_RES
