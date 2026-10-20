"""The alternate-Escape capture popup: what each key does, and the line it logs."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.keys import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
)
from barks_reader.ui import alt_escape_capture_popup as capture_module
from barks_reader.ui.alt_escape_capture_popup import AltEscapeCapturePopup, keycode_to_name


@pytest.fixture
def popup() -> tuple[AltEscapeCapturePopup, MagicMock, MagicMock]:
    on_capture, on_clear = MagicMock(), MagicMock()
    with patch.object(capture_module, "Window"):
        made = AltEscapeCapturePopup(current_keycode=0, on_capture=on_capture, on_clear=on_clear)
    made.dismiss = MagicMock()
    return made, on_capture, on_clear


def _press(popup: AltEscapeCapturePopup, key: int) -> bool:
    return popup._on_key_down(None, key, 0, "", [])  # noqa: SLF001


def test_opening_logs_the_current_key_and_focuses_cancel(
    popup: tuple[AltEscapeCapturePopup, MagicMock, MagicMock], loguru_sink: list[str]
) -> None:
    made, _, _ = popup
    with patch.object(capture_module, "update_focus_in_list") as focus:
        made.dispatch("on_open")
    assert f"Alternate Escape capture opened (current {keycode_to_name(0)})." in loguru_sink
    assert focus.call_args.args[1] == 1  # the Cancel button: a slip must not clear the key


def test_real_escape_cancels(
    popup: tuple[AltEscapeCapturePopup, MagicMock, MagicMock], loguru_sink: list[str]
) -> None:
    made, on_capture, _ = popup
    assert _press(made, KEY_ESCAPE) is True
    on_capture.assert_not_called()
    cast("MagicMock", made.dismiss).assert_called_once()
    assert "Alternate Escape capture cancelled." in loguru_sink


def test_any_other_key_is_captured_once(
    popup: tuple[AltEscapeCapturePopup, MagicMock, MagicMock], loguru_sink: list[str]
) -> None:
    made, on_capture, _ = popup
    assert _press(made, KEY_TAB) is True
    on_capture.assert_called_once_with(KEY_TAB)
    assert f"Alternate Escape captured: {keycode_to_name(KEY_TAB)} ({KEY_TAB})." in loguru_sink
    assert _press(made, KEY_TAB) is False  # once captured, keys pass on
    on_capture.assert_called_once()


@pytest.mark.parametrize("key", [KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN, KEY_ENTER])
def test_the_remotes_own_keys_are_not_captured(
    popup: tuple[AltEscapeCapturePopup, MagicMock, MagicMock], key: int
) -> None:
    """Each has work of its own, in the popup and in the app: none can be bound as Escape."""
    made, on_capture, _ = popup
    with patch.object(capture_module, "update_focus_in_list"):
        assert _press(made, key) is True
    on_capture.assert_not_called()


def test_enter_presses_cancel_to_start_and_clear_after_a_left(
    popup: tuple[AltEscapeCapturePopup, MagicMock, MagicMock], loguru_sink: list[str]
) -> None:
    """A slip of the hand must not clear the key: Cancel is focused first, Clear is a Left away."""
    made, _, on_clear = popup
    with patch.object(capture_module, "update_focus_in_list") as focus:
        assert _press(made, KEY_ENTER) is True
        assert "Alternate Escape capture cancelled." in loguru_sink
        on_clear.assert_not_called()
        assert _press(made, KEY_LEFT) is True
        assert focus.call_args.args[1] == 0  # the Clear button
        assert _press(made, KEY_ENTER) is True
    on_clear.assert_called_once()
    assert "Alternate Escape cleared." in loguru_sink


def test_clear_empties_it(
    popup: tuple[AltEscapeCapturePopup, MagicMock, MagicMock], loguru_sink: list[str]
) -> None:
    made, _, on_clear = popup
    made._handle_clear()  # noqa: SLF001
    on_clear.assert_called_once()
    assert "Alternate Escape cleared." in loguru_sink


def test_unset_and_unknown_keys_are_named() -> None:
    assert keycode_to_name(0) == "<unset>"
    assert keycode_to_name(KEY_LEFT) == "Left"
    assert keycode_to_name(987654) == "key 987654"
