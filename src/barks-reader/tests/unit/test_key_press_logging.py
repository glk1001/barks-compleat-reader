"""The app logs every key press the window dispatches, ahead of any handler (KEY_PRESSED)."""

from __future__ import annotations

import re
from typing import Any

from barks_reader.core import log_markers
from barks_reader.core.log_markers import pattern
from barks_reader.ui.barks_reader_app import _install_key_press_log


class _Window:
    """Stands in for Kivy's Window: records what was dispatched, consumes every key."""

    def __init__(self) -> None:
        self.dispatched: list[tuple[str, tuple[Any, ...]]] = []

    def dispatch(self, event_name: str, *args: Any, **_kwargs: Any) -> bool:  # noqa: ANN401
        self.dispatched.append((event_name, args))
        return event_name == "on_key_down"


def _logged(sink: list[str], key: int, name: str) -> bool:
    return any(re.search(pattern(log_markers.KEY_PRESSED, key=key, name=name), ln) for ln in sink)


def test_a_key_press_is_logged_by_code_and_name_even_when_consumed(loguru_sink: list[str]) -> None:
    window = _Window()
    _install_key_press_log(window)

    consumed = window.dispatch("on_key_down", 27, 9, "", [])

    assert consumed is True, "the original dispatch still runs and its result is returned"
    assert window.dispatched == [("on_key_down", (27, 9, "", []))]
    assert _logged(loguru_sink, 27, "escape")


def test_an_unknown_key_code_is_still_logged(loguru_sink: list[str]) -> None:
    window = _Window()
    _install_key_press_log(window)

    window.dispatch("on_key_down", 999999, 0, "", [])

    assert _logged(loguru_sink, 999999, "?")


def test_other_events_pass_through_without_a_log_line(loguru_sink: list[str]) -> None:
    window = _Window()
    _install_key_press_log(window)

    assert window.dispatch("on_resize", 800, 600) is False
    assert window.dispatched == [("on_resize", (800, 600))]
    assert not any("Key pressed" in ln for ln in loguru_sink)
