"""A standalone popup closes on Escape or Return, and logs its opening and closing.

The first-run installer's popup has no main reader around it, so these lines are
all a test (the build smoke test) can wait on; and with a remote's keys, Return is
the only "OK" there is, since the popup's close button takes no keyboard focus.
"""

from __future__ import annotations

import pytest
from barks_reader.core import log_markers
from barks_reader.ui.kivy_standalone_show_message import (
    closes_popup,
    log_popup_closed,
    log_popup_opened,
)
from barks_reader.ui.reader_keyboard_nav import KEY_ENTER, KEY_ESCAPE, KEY_NUMPAD_ENTER

KEY_DOWN = 274


@pytest.mark.parametrize("key", [KEY_ESCAPE, KEY_ENTER, KEY_NUMPAD_ENTER])
def test_escape_and_return_close_the_popup(key: int) -> None:
    assert closes_popup(key)


def test_other_keys_leave_it_open() -> None:
    assert not closes_popup(KEY_DOWN)


def test_opening_and_closing_are_logged(loguru_sink: list[str]) -> None:
    log_popup_opened("Barks Reader Installer")
    log_popup_closed("Barks Reader Installer")

    assert loguru_sink == [
        log_markers.STANDALONE_POPUP_OPENED.format(title="Barks Reader Installer"),
        log_markers.STANDALONE_POPUP_CLOSED.format(title="Barks Reader Installer"),
    ]
