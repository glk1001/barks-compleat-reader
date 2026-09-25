"""The touch-aware search box logs which keyboard a press chose, for the GUI tap tests."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import log_markers
from barks_reader.ui import touch_keyboard
from barks_reader.ui.touch_keyboard import TouchAwareTextInput
from kivy.uix.textinput import TextInput

WIDGET = "TouchAwareTextInput"


@pytest.fixture
def box() -> TouchAwareTextInput:
    return TouchAwareTextInput()


def test_a_click_with_no_touch_before_it_uses_the_system_keyboard(
    box: TouchAwareTextInput, loguru_sink: list[str]
) -> None:
    touch = MagicMock(pos=(1, 1))
    with (
        patch.object(box, "collide_point", return_value=True),
        patch.object(touch_keyboard, "Window") as window,
        patch.object(box, "_use_system_keyboard_for_click") as use_system_keyboard,
    ):
        window.allow_vkeyboard = True
        window._last_hardware_touch_time = 0.0  # noqa: SLF001
        assert box.on_touch_down(touch)
    use_system_keyboard.assert_called_once_with(touch)
    assert log_markers.TEXT_INPUT_CLICKED.format(widget=WIDGET) in loguru_sink
    assert log_markers.TEXT_INPUT_TOUCHED.format(widget=WIDGET) not in loguru_sink


def test_a_press_just_after_a_hardware_touch_is_a_tap(
    box: TouchAwareTextInput, loguru_sink: list[str]
) -> None:
    touch = MagicMock(pos=(1, 1))
    with (
        patch.object(box, "collide_point", return_value=True),
        patch.object(touch_keyboard, "Window") as window,
        patch.object(TextInput, "on_touch_down", return_value=True) as text_input_press,
    ):
        window.allow_vkeyboard = True
        window._last_hardware_touch_time = time.monotonic()  # noqa: SLF001
        assert box.on_touch_down(touch)
    text_input_press.assert_called_once_with(touch)
    assert log_markers.TEXT_INPUT_TOUCHED.format(widget=WIDGET) in loguru_sink
    assert log_markers.TEXT_INPUT_CLICKED.format(widget=WIDGET) not in loguru_sink


def test_with_no_virtual_keyboard_nothing_is_logged(
    box: TouchAwareTextInput, loguru_sink: list[str]
) -> None:
    with (
        patch.object(box, "collide_point", return_value=True),
        patch.object(touch_keyboard, "Window") as window,
        patch.object(TextInput, "on_touch_down", return_value=True),
    ):
        window.allow_vkeyboard = False
        box.on_touch_down(MagicMock(pos=(1, 1)))
    assert not [m for m in loguru_sink if m.startswith("Text input ")]
