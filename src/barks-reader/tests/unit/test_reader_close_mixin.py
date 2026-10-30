# ruff: noqa: SLF001
"""The close the comic and document readers share: the wait to be laid out, and the bar."""

from __future__ import annotations

from typing import override
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import reader_close_mixin as mixin_module
from barks_reader.ui.action_bar_helpers import ActionBarVisibility
from barks_reader.ui.reader_close_mixin import ReaderCloseMixin


class _Reader(ReaderCloseMixin):
    """A reader screen as far as the mixin sees one."""

    def __init__(self, width: float, height: float) -> None:
        self.width = width
        self.height = height
        self.size_hint = (None, None)
        self.pos_hint = {}
        self.finished = MagicMock()
        self.action_bar = MagicMock()

    @override
    def _finish_closing(self) -> None:
        self.finished()

    @override
    def _reader_action_bar(self) -> MagicMock:
        return self.action_bar


def _run_frames(clock: MagicMock, frames: int) -> None:
    """Run what the reader scheduled, a frame at a time, as the clock would."""
    for _ in range(frames):
        if not clock.schedule_once.call_args_list:
            return
        callback = clock.schedule_once.call_args_list.pop(0).args[0]
        callback(0)


def test_a_reader_not_yet_resized_waits_until_it_fills_the_window() -> None:
    """Closed from a window into full screen: the old size must not fall out."""
    reader = _Reader(782, 1225)
    with (
        patch.object(mixin_module, "Clock") as clock,
        patch.object(mixin_module, "Window", width=900, height=1300),
    ):
        reader._finish_closing_once_laid_out()
        _run_frames(clock, 3)
        reader.finished.assert_not_called()

        reader.width, reader.height = 901, 1300  # laid out, a pixel apart as a resize can land
        _run_frames(clock, 2)

    reader.finished.assert_called_once_with()


def test_a_reader_that_never_fills_the_window_still_closes() -> None:
    reader = _Reader(100, 100)
    with (
        patch.object(mixin_module, "Clock") as clock,
        patch.object(mixin_module, "Window", width=900, height=1300),
    ):
        reader._finish_closing_once_laid_out()
        frames = 0
        while clock.schedule_once.call_args_list:
            frames += 1
            _run_frames(clock, 1)

    assert frames == ReaderCloseMixin._CLOSE_LAYOUT_MAX_FRAMES
    reader.finished.assert_called_once_with()


def test_windowed_hints_make_the_screen_fill_the_window_again() -> None:
    reader = _Reader(100, 100)
    reader._set_hints_for_windowed_mode()
    assert reader.size_hint == (1, 1)
    assert reader.pos_hint == {"center_x": 0.5, "center_y": 0.5}


@pytest.mark.parametrize("fullscreen", [True, False])
def test_the_fullscreen_check_reads_the_window_and_logs_a_missed_goto(
    fullscreen: bool, loguru_sink: list[str]
) -> None:
    with patch.object(mixin_module, "WindowManager") as window_manager:
        window_manager.is_fullscreen_now.return_value = fullscreen
        window_manager.get_screen_mode_now.return_value = "auto" if fullscreen else "0"
        assert _Reader(1, 1)._is_fullscreen_now_after_goto() is fullscreen

    missed = "Finishing goto fullscreen on _Reader but Window fullscreen = '0'."
    assert any(missed in line for line in loguru_sink) is not fullscreen


@pytest.mark.parametrize(
    ("visible", "method", "expected"),
    [
        (False, "_show_action_bar", ActionBarVisibility.VISIBLE),
        (True, "_show_action_bar", None),
        (True, "_hide_action_bar", ActionBarVisibility.HIDDEN),
        (False, "_hide_action_bar", None),
    ],
)
def test_the_bar_is_shown_or_hidden_only_when_it_is_not_already(
    visible: bool, method: str, expected: ActionBarVisibility | None
) -> None:
    reader = _Reader(1, 1)
    with (
        patch.object(mixin_module, "is_action_bar_visible", return_value=visible),
        patch.object(mixin_module, "set_action_bar_visibility") as set_visibility,
    ):
        getattr(reader, method)()

    if expected is None:
        set_visibility.assert_not_called()
    else:
        set_visibility.assert_called_once_with(reader.action_bar, expected)
