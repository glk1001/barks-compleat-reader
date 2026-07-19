"""Tests for `FixedColorSource` and the fixed scrim palette."""

import pytest
from barks_reader.core.ports import PaletteId
from barks_reader.core.reader_colors import FixedColorSource
from barks_reader.core.reader_palette import (
    FIXED_SCRIMS,
    SCRIM_FUN,
    SCRIM_TITLE,
    SCRIM_TOP_VIEW,
)


@pytest.fixture
def color_source() -> FixedColorSource:
    return FixedColorSource(FIXED_SCRIMS)


class TestFixedColorSource:
    def test_returns_configured_color_per_palette(self, color_source: FixedColorSource) -> None:
        assert color_source.next_color(PaletteId.TOP_VIEW) == SCRIM_TOP_VIEW
        assert color_source.next_color(PaletteId.FUN) == SCRIM_FUN
        assert color_source.next_color(PaletteId.TITLE) == SCRIM_TITLE

    def test_color_is_stable_across_calls(self, color_source: FixedColorSource) -> None:
        first = color_source.next_color(PaletteId.TOP_VIEW)
        for _ in range(10):
            assert color_source.next_color(PaletteId.TOP_VIEW) == first

    def test_all_palettes_covered_by_fixed_scrims(self) -> None:
        assert set(FIXED_SCRIMS) == set(PaletteId)

    def test_scrims_are_neutral_grey(self) -> None:
        # A neutral multiply (r == g == b) darkens art without shifting its hue.
        for color in FIXED_SCRIMS.values():
            r, g, b, a = color
            assert r == g == b
            assert 0.0 < r <= 1.0
            assert a == 1.0
