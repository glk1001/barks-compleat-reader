"""The reader's minimum window, and screens too small for it (barks_reader.core.window_minimum)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from barks_reader.core import window_minimum
from barks_reader.core.window_minimum import (
    NO_SCREEN_WARNING_ENV_VAR,
    is_screen_too_small,
    is_screen_warning_suppressed,
    minimum_window_size,
    screen_size_key,
    screen_warning_text,
)

TASKBAR = 40
ASPECT = 1.5
CHROME = 45


def _fit(screen_height: int) -> int:
    return screen_height - TASKBAR


@pytest.mark.parametrize(
    ("screen_height", "size"),
    [
        (1080, (663, 1040)),  # a 1080p screen's window
        (1600, (663, 1040)),  # a bigger screen: still the 1080p window
        (768, (455, 728)),  # a smaller screen: its own largest window
    ],
)
def test_the_minimum_window_is_a_1080p_screens_or_a_smaller_screens_own(
    screen_height: int, size: tuple[int, int]
) -> None:
    with patch.object(window_minimum, "get_best_window_height_fit", side_effect=_fit):
        assert minimum_window_size(screen_height, ASPECT, CHROME) == size


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


def test_the_environment_can_ask_for_no_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(NO_SCREEN_WARNING_ENV_VAR, raising=False)
    assert not is_screen_warning_suppressed()
    monkeypatch.setenv(NO_SCREEN_WARNING_ENV_VAR, "1")
    assert is_screen_warning_suppressed()
