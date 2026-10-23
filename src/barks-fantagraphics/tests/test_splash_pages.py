import pytest
from barks_fantagraphics.splash_pages import get_panel_area_fractions, get_splash_pages

# Fractions of a page's panel area, gutters left out.
_EIGHTH = 0.12
_SIXTH = 0.16

_EIGHT_PANELS = [_EIGHTH] * 8
_SIX_PANELS = [_SIXTH] * 6


class TestGetPanelAreaFractions:
    def test_each_panel_is_a_fraction_of_the_overall_bounds(self) -> None:
        # The bounds are inclusive: x 100 to 299 and y 200 to 599 are 200 by 400 pixels.
        segments = {
            "overall_bounds": [100, 200, 299, 599],
            "panels": [[100, 200, 200, 200], [100, 400, 100, 200]],
        }
        assert get_panel_area_fractions(segments) == [0.5, 0.25]

    def test_a_page_with_no_panels_has_no_fractions(self) -> None:
        assert get_panel_area_fractions({"overall_bounds": [0, 0, 0, 0], "panels": []}) == []

    def test_bounds_with_no_area_give_no_fractions(self) -> None:
        segments = {"overall_bounds": [300, 200, 100, 600], "panels": [[100, 200, 200, 200]]}
        assert get_panel_area_fractions(segments) == []

    def test_bounds_with_exactly_no_area_give_no_fractions(self) -> None:
        # x 100 to 99 is no pixels wide.
        segments = {"overall_bounds": [100, 200, 99, 600], "panels": [[100, 200, 1, 1]]}
        assert get_panel_area_fractions(segments) == []

    def test_one_pixel_bounds_still_give_fractions(self) -> None:
        segments = {"overall_bounds": [5, 5, 5, 5], "panels": [[5, 5, 1, 1]]}
        assert get_panel_area_fractions(segments) == [1.0]


class TestGetSplashPages:
    def test_a_half_page_panel_among_eight_to_a_page_is_a_splash(self) -> None:
        pages = {"1": _EIGHT_PANELS, "2": [0.49, *[_EIGHTH] * 4], "3": _EIGHT_PANELS}
        assert get_splash_pages(pages) == ["2"]

    def test_a_two_thirds_page_panel_among_six_to_a_page_is_a_splash(self) -> None:
        pages = {"1": _SIX_PANELS, "2": [0.66, _SIXTH, _SIXTH], "3": _SIX_PANELS}
        assert get_splash_pages(pages) == ["2"]

    def test_a_half_page_panel_among_six_to_a_page_is_a_splash(self) -> None:
        pages = {"1": _SIX_PANELS, "2": [0.49, _SIXTH, _SIXTH, _SIXTH], "3": _SIX_PANELS}
        assert get_splash_pages(pages) == ["2"]

    @pytest.mark.parametrize(
        ("largest", "is_splash"),
        [(0.42, False), (0.46, False), (0.469, False), (0.47, True), (1.0, True)],
    )
    def test_the_largest_panel_must_cover_half_the_page_less_the_gutters(
        self, largest: float, is_splash: bool
    ) -> None:
        # A page-1 title panel drawn short of half the page covers 0.40 to 0.46; a
        # half-page one 0.47 up.
        pages = {"1": _EIGHT_PANELS, "2": [largest, *[_EIGHTH] * 4], "3": _EIGHT_PANELS}
        assert get_splash_pages(pages) == (["2"] if is_splash else [])

    def test_every_splash_is_returned_in_page_order(self) -> None:
        splash = [0.5, *[_EIGHTH] * 4]
        pages = {"1": splash, "2": _EIGHT_PANELS, "3": _EIGHT_PANELS, "4": splash}
        assert get_splash_pages(pages) == ["1", "4"]

    def test_pages_with_no_panels_are_never_splashes(self) -> None:
        assert get_splash_pages({"1": [], "2": _EIGHT_PANELS}) == []
        assert get_splash_pages({"1": []}) == []
