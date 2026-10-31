"""The reader's minimum window, and screens too small for it (barks_reader.core.window_minimum)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from barks_reader.core import screen_metrics
from barks_reader.core.main_layout import SPREAD_WIDTH_IN_PAGES
from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO
from barks_reader.core.screen_metrics import largest_window_size
from barks_reader.core.window_minimum import (
    NO_SCREEN_WARNING_ENV_VAR,
    is_screen_too_small,
    is_screen_warning_suppressed,
    minimum_window_size,
    screen_size_key,
    screen_warning_text,
)

TASKBAR = 40
CHROME = 45


def _fit(screen_height: int) -> int:
    return screen_height - TASKBAR


# The window's height is the screen's less the taskbar and the 20 margin; its width
# follows from the comic page's shape (3200 / 2120), unless the screen is narrower.
@pytest.mark.parametrize(
    ("screen_width", "screen_height", "size"),
    [
        (1920, 1080, (646, 1020)),  # a 1080p screen's window
        (2560, 1600, (646, 1020)),  # a bigger screen: still the 1080p window
        (1366, 768, (439, 708)),  # a smaller screen: its own largest window
        (400, 1080, (400, 649)),  # a screen narrower than the window: as wide as it
    ],
)
def test_the_minimum_window_is_a_1080p_screens_or_a_smaller_screens_own(
    screen_width: int, screen_height: int, size: tuple[int, int]
) -> None:
    with patch.object(screen_metrics, "get_best_window_height_fit", side_effect=_fit):
        assert minimum_window_size(screen_width, screen_height, CHROME) == size


def test_the_spreads_minimum_is_the_pair_at_the_same_height() -> None:
    """The two-page spread's minimum window: the single page's height, the pair's width."""
    spread = COMIC_PAGE_ASPECT_RATIO / SPREAD_WIDTH_IN_PAGES
    with patch.object(screen_metrics, "get_best_window_height_fit", side_effect=_fit):
        width, height = minimum_window_size(1920, 1080, CHROME, spread)
        assert (width, height) == (round(975 / spread), 1020)
        assert width == pytest.approx(SPREAD_WIDTH_IN_PAGES * 646, abs=2)


def test_the_minimum_is_the_window_the_reader_opens_on_a_1080p_screen() -> None:
    """main.py opens the largest window; it must not then be grown to the minimum."""
    with patch.object(screen_metrics, "get_best_window_height_fit", side_effect=_fit):
        assert minimum_window_size(1920, 1080, CHROME) == largest_window_size(1920, 1080, CHROME)
        assert largest_window_size(1366, 768, CHROME) == (439, 708)


@pytest.mark.parametrize(
    ("width", "height", "too_small"),
    [
        (1920, 1080, False),
        (2560, 1600, False),
        (1080, 1920, False),  # a portrait 1080p monitor
        (1366, 768, True),
        (1600, 900, True),
        (900, 1300, False),  # narrow, but the portrait window is narrower
    ],
)
def test_a_screen_is_too_small_when_shorter_than_1080(
    width: int, height: int, too_small: bool
) -> None:
    assert is_screen_too_small(width, height) is too_small


def test_a_screen_size_is_remembered_by_its_name() -> None:
    assert screen_size_key(1366, 768) == "1366x768"


def test_the_warning_names_the_screen_and_the_size_the_reader_is_laid_out_for() -> None:
    text = screen_warning_text(1366, 768)
    assert "1366 x 768" in text
    assert "1920 x 1080" in text
    assert text.endswith(
        "\n\nThe reader will run, but some titles may be cut short and some screens crowded."
    )


def test_the_environment_can_ask_for_no_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(NO_SCREEN_WARNING_ENV_VAR, raising=False)
    assert not is_screen_warning_suppressed()
    monkeypatch.setenv(NO_SCREEN_WARNING_ENV_VAR, "1")
    assert is_screen_warning_suppressed()
