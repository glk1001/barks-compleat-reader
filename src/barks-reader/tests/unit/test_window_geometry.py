"""The window geometry's sums, by numbers alone (barks_reader.core.window_geometry)."""

from __future__ import annotations

import pytest
from barks_reader.core.screen_metrics import ScreenInfo
from barks_reader.core.window_geometry import (
    WindowPlace,
    WindowUnits,
    centred_if_over,
    on_monitor_position,
)

CHROME = 45


def _monitor(x: int = 0, y: int = 0, width: int = 2560, height: int = 1440) -> ScreenInfo:
    return ScreenInfo(
        display=0,
        monitor_x=x,
        monitor_y=y,
        width_pixels=width,
        height_pixels=height,
        width_mm=600,
        height_mm=340,
        width_in=24,
        height_in=13,
        dpi=109,
        is_primary=True,
    )


class TestWindowUnits:
    def test_where_pixels_are_the_units_a_size_is_unchanged(self) -> None:
        units = WindowUnits(size_pixels=(800, 1200), system_size=(800, 1200))
        assert units.pixels_per_size_unit == 1.0
        assert units.in_size_units(640, 1000) == (640, 1000)
        assert units.length_in_size_units(CHROME) == CHROME

    def test_a_retina_window_is_two_pixels_to_a_unit(self) -> None:
        """A correction worked out in pixels and set in points doubled the window (2026-10-14)."""
        units = WindowUnits(size_pixels=(1600, 2400), system_size=(800, 1200))
        assert units.pixels_per_size_unit == 2.0  # noqa: PLR2004
        # A resize event's size, in pixels, is half that in the units a size is set in.
        assert units.in_size_units(1600, 2400) == (800, 1200)
        assert units.length_in_size_units(90) == CHROME

    def test_a_fractional_scale_rounds_to_whole_units(self) -> None:
        units = WindowUnits(size_pixels=(1200, 1800), system_size=(800, 1200))
        assert units.pixels_per_size_unit == 1.5  # noqa: PLR2004
        assert units.in_size_units(1000, 1001) == (667, 667)
        assert units.length_in_size_units(CHROME) == 30  # noqa: PLR2004

    @pytest.mark.parametrize("system_width", [0, -1])
    def test_a_window_with_no_width_yet_counts_as_one_to_one(self, system_width: int) -> None:
        units = WindowUnits(size_pixels=(800, 1200), system_size=(system_width, 0))
        assert units.pixels_per_size_unit == 1.0
        assert units.in_size_units(640, 1000) == (640, 1000)


class TestCentredIfOver:
    def test_a_side_that_fits_stays_where_it_is(self) -> None:
        assert centred_if_over(100, 800, 0, 2560) == 100  # noqa: PLR2004

    def test_a_side_that_ends_exactly_at_the_monitors_end_stays(self) -> None:
        assert centred_if_over(1760, 800, 0, 2560) == 1760  # noqa: PLR2004

    def test_a_side_one_past_the_end_is_centred(self) -> None:
        assert centred_if_over(1761, 800, 0, 2560) == 880  # noqa: PLR2004

    def test_it_is_centred_on_its_own_monitor_not_the_first(self) -> None:
        assert centred_if_over(4500, 800, 2560, 1920) == 2560 + 560

    def test_a_window_larger_than_its_monitor_starts_at_the_monitors_start(self) -> None:
        assert centred_if_over(100, 3000, 0, 2560) == 0
        assert centred_if_over(2600, 3000, 2560, 1920) == 2560  # noqa: PLR2004

    def test_an_odd_gap_rounds_the_centre_down(self) -> None:
        assert centred_if_over(2000, 801, 0, 2560) == 879  # noqa: PLR2004


class TestOnMonitorPosition:
    def test_a_window_that_fits_where_it_stands_need_not_move(self) -> None:
        place = WindowPlace(left=100, top=50, monitor=_monitor())
        assert on_monitor_position(place, 800, 1200) is None

    def test_only_the_side_that_passes_the_edge_is_centred(self) -> None:
        place = WindowPlace(left=2000, top=50, monitor=_monitor())
        assert on_monitor_position(place, 800, 1200) == (880, 50)

    def test_too_tall_where_it_stands_it_is_centred_down_the_monitor(self) -> None:
        place = WindowPlace(left=100, top=400, monitor=_monitor())
        assert on_monitor_position(place, 800, 1200) == (100, 120)

    def test_both_sides_over_are_both_centred(self) -> None:
        place = WindowPlace(left=2000, top=400, monitor=_monitor())
        assert on_monitor_position(place, 800, 1200) == (880, 120)

    def test_on_a_second_monitor_it_stays_on_that_one(self) -> None:
        second = _monitor(x=2560, y=0, width=1920, height=1080)
        place = WindowPlace(left=4000, top=10, monitor=second)
        assert on_monitor_position(place, 800, 1000) == (2560 + 560, 10)

    def test_off_every_monitor_there_is_nowhere_to_stay(self) -> None:
        place = WindowPlace(left=-5000, top=-5000, monitor=None)
        assert on_monitor_position(place, 800, 1200) is None
