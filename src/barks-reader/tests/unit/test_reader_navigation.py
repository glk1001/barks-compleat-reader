"""Where a press on a reader lands (barks_reader.core.reader_navigation)."""

from __future__ import annotations

import pytest
from barks_reader.core.reader_navigation import ReaderNavigation


class _Mode:
    """The window mode the navigation asks about: fullscreen or not, set by a test."""

    def __init__(self) -> None:
        self.fullscreen = False

    def __call__(self) -> bool:
        return self.fullscreen


class TestReaderNavigation:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.max_width = 2000
        self.top_frac = 0.1
        self.bottom_frac = 0.9
        self.mode = _Mode()
        self.nav = ReaderNavigation(
            self.max_width, self.top_frac, self.bottom_frac, is_fullscreen=self.mode
        )

    def test_update_regions(self) -> None:
        win_width = 1000
        win_height = 1000
        win_left = 0
        win_top = 0

        self.nav.update_regions(win_width, win_height, win_left, win_top)

        # x_mid = 1000/2 - 0 = 500
        assert self.nav.x_mid == 500  # noqa: PLR2004

        # y_top_margin = (1000 - 0) - (0.1 * 1000) = 900
        assert self.nav.y_top_margin == 900  # noqa: PLR2004

        # y_bottom_margin = (1000 - 0) - (0.9 * 1000) = 100
        assert self.nav.y_bottom_margin == 100  # noqa: PLR2004

    def test_is_in_top_margin(self) -> None:
        self.nav.update_regions(1000, 1000, 0, 0)
        # y_top_margin is 900

        # Case 1: Not fullscreen
        self.mode.fullscreen = False

        assert self.nav.is_in_top_margin(500, 950)
        assert self.nav.is_in_top_margin(500, 900)
        assert not self.nav.is_in_top_margin(500, 850)

        # Case 2: Fullscreen
        self.mode.fullscreen = True
        # Fullscreen margins: left = 2000/4 = 500. right = 2000 - 500 = 1500.

        # Inside horizontal center area (500 < x <= 1500) AND above top margin
        assert self.nav.is_in_top_margin(600, 950)

        # Outside horizontal center area
        assert not self.nav.is_in_top_margin(400, 950)
        assert not self.nav.is_in_top_margin(1600, 950)

    def test_is_in_bottom_margin(self) -> None:
        self.nav.update_regions(1000, 1000, 0, 0)
        # y_bottom_margin is 100

        # Case 1: Not fullscreen
        self.mode.fullscreen = False

        assert self.nav.is_in_bottom_margin(500, 50)
        assert self.nav.is_in_bottom_margin(500, 100)
        assert not self.nav.is_in_bottom_margin(500, 150)

        # Case 2: Fullscreen
        self.mode.fullscreen = True

        # Inside horizontal center area AND below bottom margin
        assert self.nav.is_in_bottom_margin(600, 50)

        # Outside horizontal center area
        assert not self.nav.is_in_bottom_margin(400, 50)
        assert not self.nav.is_in_bottom_margin(1600, 50)

    def test_is_in_left_margin(self) -> None:
        self.nav.update_regions(1000, 1000, 0, 0)
        # x_mid = 500, y_bottom = 100, y_top = 900

        assert self.nav.is_in_left_margin(400, 500)
        assert not self.nav.is_in_left_margin(600, 500)
        assert not self.nav.is_in_left_margin(400, 950)
        assert not self.nav.is_in_left_margin(400, 50)

    def test_is_in_right_margin(self) -> None:
        self.nav.update_regions(1000, 1000, 0, 0)
        # x_mid = 500, y_bottom = 100, y_top = 900

        assert self.nav.is_in_right_margin(600, 500)
        assert not self.nav.is_in_right_margin(400, 500)
        assert not self.nav.is_in_right_margin(600, 950)
        assert not self.nav.is_in_right_margin(600, 50)

    def test_offset_coordinates(self) -> None:
        # Test with win_left/win_top offsets (e.g. widget not at 0,0)
        self.nav.update_regions(1000, 1000, 100, 100)

        # x_mid = 1000/2 - 100 = 400
        assert self.nav.x_mid == 400  # noqa: PLR2004

        # y_top_margin = (1000 - 100) - (0.1 * 1000) = 800
        assert self.nav.y_top_margin == 800  # noqa: PLR2004

        # y_bottom_margin = (1000 - 100) - (0.9 * 1000) = 0
        assert self.nav.y_bottom_margin == 0


def _inside_points(rect: tuple[int, int, int, int]) -> list[tuple[int, int]]:
    """Return the centre and the four corners of `rect`, all inside it."""
    x, y, w, h = rect
    return [
        (x + w // 2, y + h // 2),
        (x, y),
        (x + w - 1, y),
        (x, y + h - 1),
        (x + w - 1, y + h - 1),
    ]


class TestTapRegions:
    """Every point of a reported region is one its own check accepts."""

    WIDTH = 1000
    HEIGHT = 1000

    @pytest.fixture
    def mode(self) -> _Mode:
        return _Mode()

    @pytest.fixture
    def nav(self, mode: _Mode) -> ReaderNavigation:
        nav = ReaderNavigation(2000, 0.1, 0.9, is_fullscreen=mode)
        nav.update_regions(self.WIDTH, self.HEIGHT, 0, 0)
        return nav

    @pytest.mark.parametrize("fullscreen", [False, True])
    def test_each_region_is_inside_its_check(
        self, mode: _Mode, nav: ReaderNavigation, *, fullscreen: bool
    ) -> None:
        mode.fullscreen = fullscreen
        regions = nav.tap_regions(self.WIDTH, self.HEIGHT)
        checks = {
            "left margin": nav.is_in_left_margin,
            "right margin": nav.is_in_right_margin,
            "top margin": nav.is_in_top_margin,
        }
        assert set(regions) == set(checks)
        for name, rect in regions.items():
            for point in _inside_points(rect):
                assert checks[name](*point), (name, rect, point)

    def test_the_left_and_right_margins_meet_at_the_middle(
        self, mode: _Mode, nav: ReaderNavigation
    ) -> None:
        mode.fullscreen = False
        regions = nav.tap_regions(self.WIDTH, self.HEIGHT)
        left_x, _, left_w, _ = regions["left margin"]
        right_x, _, right_w, _ = regions["right margin"]
        assert left_x + left_w == right_x == nav.x_mid
        assert right_x + right_w == self.WIDTH

    def test_fullscreen_narrows_the_top_margin_to_the_middle(
        self, mode: _Mode, nav: ReaderNavigation
    ) -> None:
        mode.fullscreen = True
        x, _, w, _ = nav.tap_regions(self.WIDTH, self.HEIGHT)["top margin"]
        # The fullscreen band is (500, 1500]: in a 1000-wide widget, 501 to the edge.
        assert (x, x + w) == (501, self.WIDTH)
        assert not nav.is_in_top_margin(x - 1, 950)

    def test_no_regions_before_the_sizes_are_known(self) -> None:
        # Before update_regions every margin is -1: nothing to press yet.
        nav = ReaderNavigation(2000, 0.1, 0.9, is_fullscreen=lambda: False)
        regions = nav.tap_regions(self.WIDTH, self.HEIGHT)
        assert "left margin" not in regions
        assert "right margin" not in regions


class TestEdges:
    """A press on a margin's own edge, and the margins before the sizes are known."""

    @pytest.fixture
    def mode(self) -> _Mode:
        return _Mode()

    @pytest.fixture
    def nav(self, mode: _Mode) -> ReaderNavigation:
        nav = ReaderNavigation(2000, 0.1, 0.9, is_fullscreen=mode)
        nav.update_regions(1000, 1000, 0, 0)  # x_mid 500, bottom 100, top 900
        return nav

    def test_the_middle_is_the_right_pages_and_the_top_line_turns_too(
        self, nav: ReaderNavigation
    ) -> None:
        assert not nav.is_in_left_margin(500, 500)
        assert nav.is_in_right_margin(500, 500)
        assert nav.is_in_left_margin(400, 900)
        assert nav.is_in_right_margin(600, 900)

    def test_in_fullscreen_the_bars_band_takes_its_right_edge_not_its_left(
        self, mode: _Mode, nav: ReaderNavigation
    ) -> None:
        mode.fullscreen = True  # the band is (500, 1500]
        assert nav.is_in_top_margin(1500, 950)
        assert not nav.is_in_top_margin(500, 950)
        assert nav.is_in_bottom_margin(1500, 50)
        assert not nav.is_in_bottom_margin(500, 50)

    def test_no_bottom_margin_by_default(self) -> None:
        nav = ReaderNavigation(2000, 0.1, is_fullscreen=lambda: False)
        nav.update_regions(1000, 1000, 0, 0)
        assert nav.y_bottom_margin == 0

    def test_every_margin_is_unknown_until_the_sizes_are(self) -> None:
        nav = ReaderNavigation(2000, 0.1, 0.9, is_fullscreen=lambda: True)
        assert (nav.x_mid, nav.y_bottom_margin, nav.y_top_margin) == (-1, -1, -1)
        assert nav.tap_regions(1000, 1000) == {}


_L, _R, _T = "left margin", "right margin", "top margin"


@pytest.mark.parametrize(
    ("top_frac", "bottom_frac", "win", "fullscreen", "expected"),
    [
        pytest.param(
            0.1,
            0.9,
            (1000, 1000, 0, 0),
            False,
            {_L: (0, 100, 500, 800), _R: (500, 100, 500, 800), _T: (0, 900, 1000, 100)},
            id="windowed",
        ),
        pytest.param(
            0.1,
            1.0,
            (1000, 1000, 0, 0),
            False,
            {_L: (0, 0, 500, 900), _R: (500, 0, 500, 900), _T: (0, 900, 1000, 100)},
            id="no-bottom-margin",
        ),
        pytest.param(
            0.0,
            0.9,
            (1000, 1000, 0, 0),
            False,
            {_L: (0, 100, 500, 899), _R: (500, 100, 500, 899)},
            id="no-top-margin",  # the turns stop a pixel short of the widget's top
        ),
        pytest.param(
            1.0,
            1.0,
            (1000, 1000, 0, 0),
            False,
            {_T: (0, 0, 1000, 1000)},
            id="all-top-margin",
        ),
        pytest.param(
            0.1,
            0.9,
            (1000, 1000, 600, 0),
            False,
            {_R: (0, 100, 1000, 800), _T: (0, 900, 1000, 100)},
            id="middle-left-of-the-widget",
        ),
        pytest.param(
            0.1,
            0.9,
            (1000, 1000, 499, 0),
            False,
            {_L: (0, 100, 1, 800), _R: (1, 100, 999, 800), _T: (0, 900, 1000, 100)},
            id="middle-at-its-first-pixel",
        ),
        pytest.param(
            0.1,
            0.9,
            (1000, 1000, -500, 0),
            False,
            {_L: (0, 100, 1000, 800), _T: (0, 900, 1000, 100)},
            id="middle-at-its-right-edge",
        ),
        pytest.param(
            0.1,
            0.9,
            (2000, 1000, 0, 0),
            True,
            {_L: (0, 100, 1000, 800), _R: (1000, 100, 1000, 800), _T: (501, 900, 1000, 100)},
            id="fullscreen-band",
        ),
        pytest.param(
            0.1,
            0.9,
            (400, 1000, 0, 0),
            True,
            {_L: (0, 100, 200, 800), _R: (200, 100, 200, 800)},
            id="fullscreen-band-off-the-widget",
        ),
    ],
)
def test_the_tap_regions_are_exactly_the_margins(
    top_frac: float,
    bottom_frac: float,
    win: tuple[int, int, int, int],
    expected: dict[str, tuple[int, int, int, int]],
    *,
    fullscreen: bool,
) -> None:
    nav = ReaderNavigation(2000, top_frac, bottom_frac, is_fullscreen=lambda: fullscreen)
    nav.update_regions(*win)
    assert nav.tap_regions(win[0], win[1]) == expected
