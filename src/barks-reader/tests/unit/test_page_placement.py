"""The reader logs where its page lands (PAGE_PLACED), once for each new placement."""

from __future__ import annotations

from barks_reader.core import log_markers
from barks_reader.core.page_placement import PagePlacement, fitted_page_rect, log_page_placement

SPREAD = PagePlacement(x=640, y=0, width=1280, height=1440, win_width=2560, win_height=1440)


def test_the_fitted_page_is_centred_where_the_image_is() -> None:
    assert fitted_page_rect(1280, 720, 1280, 1440) == (640, 0, 1280, 1440)
    assert fitted_page_rect(419.5, 655, 600.4, 900.6) == (119, 205, 600, 901)


def test_a_new_placement_is_logged_as_the_marker_says(loguru_sink: list[str]) -> None:
    assert log_page_placement(SPREAD, None) == SPREAD
    expected = log_markers.PAGE_PLACED.format(
        width=1280, height=1440, x=640, y=0, win_width=2560, win_height=1440
    )
    assert loguru_sink == [expected]


def test_the_same_placement_again_is_not_logged(loguru_sink: list[str]) -> None:
    log_page_placement(SPREAD, SPREAD)
    assert loguru_sink == []


def test_a_moved_page_is_logged_again(loguru_sink: list[str]) -> None:
    moved = PagePlacement(x=1400, y=0, width=1280, height=1440, win_width=2560, win_height=1440)
    assert log_page_placement(moved, SPREAD) == moved
    assert len(loguru_sink) == 1
    assert "+1400+0" in loguru_sink[0]
