"""The window geometry's sums, by numbers alone (barks_reader.core.window_geometry)."""

from __future__ import annotations

import pytest
from barks_reader.core.main_layout import SPREAD_WIDTH_IN_PAGES, size_under_bar
from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO
from barks_reader.core.screen_metrics import ScreenInfo
from barks_reader.core.window_geometry import (
    AspectCorrection,
    AspectCorrectionKind,
    WindowPlace,
    WindowUnits,
    aspect_correction,
    centred_if_over,
    held_to_minimum,
    is_degenerate_size,
    layout_fit_at,
    on_monitor_position,
    raised_to_minimum,
)
from barks_reader.core.window_minimum import minimum_window_size

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


MINIMUM = (636, 1005)


class TestRaisedToMinimum:
    def test_a_size_at_or_over_the_minimum_is_kept(self) -> None:
        assert raised_to_minimum((800, 1200), MINIMUM) == (800, 1200)
        assert raised_to_minimum(MINIMUM, MINIMUM) == MINIMUM

    def test_only_the_short_side_goes_up(self) -> None:
        assert raised_to_minimum((400, 1200), MINIMUM) == (636, 1200)
        assert raised_to_minimum((800, 600), MINIMUM) == (800, 1005)

    def test_both_short_sides_go_up(self) -> None:
        assert raised_to_minimum((400, 800), MINIMUM) == MINIMUM


class TestHeldToMinimum:
    def test_a_size_at_or_over_the_minimum_is_kept(self) -> None:
        assert held_to_minimum((800, 1200), MINIMUM) == (800, 1200)
        assert held_to_minimum(MINIMUM, MINIMUM) == MINIMUM

    @pytest.mark.parametrize("size", [(635, 1200), (800, 1004), (400, 800)])
    def test_a_size_short_on_either_side_becomes_the_whole_minimum(
        self, size: tuple[int, int]
    ) -> None:
        """Not the short side alone: the long one would no longer be in the layout's shape."""
        assert held_to_minimum(size, MINIMUM) == MINIMUM


class TestLayoutFitAt:
    def test_the_layout_at_a_height_centred_on_the_monitor(self) -> None:
        width, height, left = layout_fit_at(
            1245, _monitor(), CHROME, COMIC_PAGE_ASPECT_RATIO, MINIMUM
        )
        assert (width, height) == size_under_bar(1245, 2560, CHROME, COMIC_PAGE_ASPECT_RATIO)
        assert height == 1245  # noqa: PLR2004
        assert left == (2560 - width) // 2

    def test_it_is_centred_on_its_own_monitor(self) -> None:
        second = _monitor(x=2560, width=1920, height=1080)
        width, _height, left = layout_fit_at(1045, second, CHROME, COMIC_PAGE_ASPECT_RATIO, MINIMUM)
        assert left == 2560 + (1920 - width) // 2

    def test_the_spread_is_twice_as_wide_at_the_same_height(self) -> None:
        spread = COMIC_PAGE_ASPECT_RATIO / SPREAD_WIDTH_IN_PAGES
        page_width, _, _ = layout_fit_at(1245, _monitor(), CHROME, COMIC_PAGE_ASPECT_RATIO, (1, 1))
        width, height, left = layout_fit_at(1245, _monitor(), CHROME, spread, (1, 1))
        assert width == pytest.approx(SPREAD_WIDTH_IN_PAGES * page_width, abs=1)
        assert height == 1245  # noqa: PLR2004
        assert left == (2560 - width) // 2

    def test_a_layout_wider_than_the_monitor_takes_its_width_and_less_height(self) -> None:
        narrow = _monitor(width=700, height=2400)
        width, height, left = layout_fit_at(2045, narrow, CHROME, COMIC_PAGE_ASPECT_RATIO, (1, 1))
        assert width == 700  # noqa: PLR2004
        assert height == round(700 * COMIC_PAGE_ASPECT_RATIO) + CHROME
        assert left == 0

    def test_a_height_below_the_minimum_gives_the_minimum_centred(self) -> None:
        assert layout_fit_at(500, _monitor(), CHROME, COMIC_PAGE_ASPECT_RATIO, MINIMUM) == (
            *MINIMUM,
            (2560 - MINIMUM[0]) // 2,
        )


SPREAD = COMIC_PAGE_ASPECT_RATIO / SPREAD_WIDTH_IN_PAGES
MONITOR_WIDTH = 2560


class TestIsDegenerateSize:
    @pytest.mark.parametrize("size", [(0, 45), (0, 1000), (-3, 1000), (800, 45), (800, 10)])
    def test_no_width_or_no_height_over_the_chrome_is_degenerate(
        self, size: tuple[int, int]
    ) -> None:
        """Sizes like (0, 45) come during the Windows fullscreen-exit resize storm."""
        assert is_degenerate_size(size, CHROME)

    @pytest.mark.parametrize("size", [(1, 46), (800, 1200)])
    def test_any_content_at_all_is_not(self, size: tuple[int, int]) -> None:
        assert not is_degenerate_size(size, CHROME)


class TestAspectCorrection:
    def test_a_window_in_the_layouts_shape_wants_nothing(self) -> None:
        in_shape = size_under_bar(1245, MONITOR_WIDTH, CHROME, COMIC_PAGE_ASPECT_RATIO)
        assert aspect_correction(
            in_shape, MONITOR_WIDTH, CHROME, COMIC_PAGE_ASPECT_RATIO, MINIMUM
        ) == AspectCorrection(AspectCorrectionKind.IN_PROPORTION, in_shape)

    @pytest.mark.parametrize("width", [600, 1200])
    def test_the_height_drives_the_width_whichever_way_it_is_off(self, width: int) -> None:
        right = size_under_bar(1245, MONITOR_WIDTH, CHROME, COMIC_PAGE_ASPECT_RATIO)
        assert aspect_correction(
            (width, 1245), MONITOR_WIDTH, CHROME, COMIC_PAGE_ASPECT_RATIO, MINIMUM
        ) == AspectCorrection(AspectCorrectionKind.RESIZE, right)

    def test_on_the_spread_the_width_is_the_pairs(self) -> None:
        correction = aspect_correction((800, 1245), MONITOR_WIDTH, CHROME, SPREAD, (1, 1))
        assert correction.kind is AspectCorrectionKind.RESIZE
        assert correction.size == size_under_bar(1245, MONITOR_WIDTH, CHROME, SPREAD)

    def test_a_window_too_tall_for_the_monitors_width_loses_height(self) -> None:
        correction = aspect_correction((700, 2045), 700, CHROME, COMIC_PAGE_ASPECT_RATIO, (1, 1))
        assert correction.kind is AspectCorrectionKind.RESIZE
        assert correction.size == (700, round(700 * COMIC_PAGE_ASPECT_RATIO) + CHROME)

    def test_a_window_on_no_monitor_has_no_size_to_correct_to(self) -> None:
        """Its position off every screen, the monitor's width is 0: nothing is set."""
        correction = aspect_correction((800, 1245), 0, CHROME, COMIC_PAGE_ASPECT_RATIO, MINIMUM)
        assert correction == AspectCorrection(AspectCorrectionKind.NO_TARGET, (0, CHROME))

    def test_a_height_below_the_minimum_is_corrected_to_the_minimum(self) -> None:
        assert aspect_correction(
            (300, 500), MONITOR_WIDTH, CHROME, COMIC_PAGE_ASPECT_RATIO, MINIMUM
        ) == AspectCorrection(AspectCorrectionKind.RESIZE, MINIMUM, held_at_minimum=True)

    @pytest.mark.parametrize("aspect_ratio", [COMIC_PAGE_ASPECT_RATIO, SPREAD])
    def test_a_window_at_the_real_minimum_stays_there(self, aspect_ratio: float) -> None:
        """The minimum has the layout's shape, so a window held at it is in proportion."""
        minimum = minimum_window_size(MONITOR_WIDTH, 1440, CHROME, aspect_ratio)
        short = (minimum[0], minimum[1] - 200)
        first = aspect_correction(short, MONITOR_WIDTH, CHROME, aspect_ratio, minimum)
        assert first == AspectCorrection(AspectCorrectionKind.RESIZE, minimum, held_at_minimum=True)
        again = aspect_correction(minimum, MONITOR_WIDTH, CHROME, aspect_ratio, minimum)
        assert again.kind is AspectCorrectionKind.IN_PROPORTION
        assert again.size == minimum

    @pytest.mark.parametrize("aspect_ratio", [COMIC_PAGE_ASPECT_RATIO, SPREAD])
    @pytest.mark.parametrize("height", range(300, 2400, 97))
    @pytest.mark.parametrize("monitor_width", [1366, 1920, 2560])
    def test_a_corrected_window_wants_no_second_correction(
        self, aspect_ratio: float, height: int, monitor_width: int
    ) -> None:
        """One correction settles the shape: a second from its own result grew the window."""
        first = aspect_correction((777, height), monitor_width, CHROME, aspect_ratio, (1, 1))
        again = aspect_correction(first.size, monitor_width, CHROME, aspect_ratio, (1, 1))
        assert again == AspectCorrection(AspectCorrectionKind.IN_PROPORTION, first.size)

    def test_a_retina_window_is_corrected_in_units_not_pixels(self) -> None:
        """In pixels and set in points, each correction doubled the window (2026-10-14)."""
        units = WindowUnits(size_pixels=(1600, 2490), system_size=(800, 1245))
        chrome = units.length_in_size_units(2 * CHROME)
        correction = aspect_correction(
            units.in_size_units(1600, 2490),
            MONITOR_WIDTH,
            chrome,
            COMIC_PAGE_ASPECT_RATIO,
            MINIMUM,
        )
        assert chrome == CHROME
        assert correction.size == size_under_bar(
            1245, MONITOR_WIDTH, CHROME, COMIC_PAGE_ASPECT_RATIO
        )
        assert correction.size[1] == 1245  # noqa: PLR2004
