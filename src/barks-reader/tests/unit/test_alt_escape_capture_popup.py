"""The alternate-Escape capture popup: what each key does, and the line it logs."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import alt_escape_capture_popup as capture_module
from barks_reader.ui.alt_escape_capture_popup import AltEscapeCapturePopup, keycode_to_name
from barks_reader.ui.reader_keyboard_nav import KEY_ESCAPE, KEY_LEFT


@pytest.fixture
def popup() -> tuple[AltEscapeCapturePopup, MagicMock, MagicMock]:
    on_capture, on_clear = MagicMock(), MagicMock()
    with patch.object(capture_module, "Window"):
        made = AltEscapeCapturePopup(current_keycode=0, on_capture=on_capture, on_clear=on_clear)
    made.dismiss = MagicMock()
    return made, on_capture, on_clear


def _press(popup: AltEscapeCapturePopup, key: int) -> bool:
    return popup._on_key_down(None, key, 0, "", [])  # noqa: SLF001


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
    assert _press(made, KEY_LEFT) is True
    on_capture.assert_called_once_with(KEY_LEFT)
    assert f"Alternate Escape captured: {keycode_to_name(KEY_LEFT)} ({KEY_LEFT})." in loguru_sink
    assert _press(made, KEY_LEFT) is False  # once captured, keys pass on
    on_capture.assert_called_once()


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
