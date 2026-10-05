"""Touchscreen support: which devices count as touchscreens, and which keyboard a press gets.

The touch-aware search box logs which keyboard a press chose, for the GUI tap tests.
The device scan reads a fake sysfs tree, built under ``tmp_path``.
"""

from __future__ import annotations

import ctypes
import time
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import log_markers
from barks_reader.ui import touch_keyboard
from barks_reader.ui.touch_keyboard import (
    TouchAwareTextInput,
    _find_touchscreen_devices,
    enable_linux_touchscreen_input,
)
from kivy.base import EventLoop
from kivy.input.factory import MotionEventFactory
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.textinput import TextInput

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

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


def test_a_click_takes_the_system_keyboard_from_a_stale_owner(box: TouchAwareTextInput) -> None:
    """A widget left holding the system keyboard would unfocus this one; it is let go."""
    sys_kb = object()
    allowed_during_press: list[bool] = []

    def press(_touch: object) -> bool:
        allowed_during_press.append(window.allow_vkeyboard)
        return True

    with (
        patch.object(touch_keyboard, "Window") as window,
        patch.dict(FocusBehavior._keyboards, {sys_kb: MagicMock()}),  # noqa: SLF001
        patch.object(TextInput, "on_touch_down", side_effect=press),
    ):
        window._system_keyboard = sys_kb  # noqa: SLF001
        window.allow_vkeyboard = True
        assert box._use_system_keyboard_for_click(MagicMock())  # noqa: SLF001
        assert FocusBehavior._keyboards[sys_kb] is None  # noqa: SLF001

    assert allowed_during_press == [False]
    assert window.allow_vkeyboard is True


# A C long's bits: sysfs writes a capability bitmap in words of that size (32 on Windows).
_LONG_BIT = ctypes.sizeof(ctypes.c_long) * 8
_ABS_MT_POSITION_X = 0x35


def _abs_caps(bit: int) -> str:
    """Return a sysfs abs-capabilities bitmap with one bit set: hex words, highest first."""
    value = 1 << bit
    words = [
        (value >> (i * _LONG_BIT)) & ((1 << _LONG_BIT) - 1) for i in range(bit // _LONG_BIT + 1)
    ]
    return " ".join(f"{w:x}" for w in reversed(words))


# The multitouch X axis, the one a touchscreen has.
_MULTITOUCH = _abs_caps(_ABS_MT_POSITION_X)


def _device(sysfs: Path, event: str, name: str | None, abs_caps: str | None) -> None:
    device = sysfs / event / "device"
    (device / "capabilities").mkdir(parents=True)
    if name is not None:
        (device / "name").write_text(f"{name}\n")
    if abs_caps is not None:
        (device / "capabilities" / "abs").write_text(f"{abs_caps}\n")


@pytest.fixture
def sysfs(tmp_path: Path) -> Iterator[Path]:
    with patch.object(touch_keyboard, "_SYSFS_INPUT", tmp_path):
        yield tmp_path


class TestFindTouchscreenDevices:
    def test_a_multitouch_screen_is_found(self, sysfs: Path) -> None:
        _device(sysfs, "event4", "ELAN Touchscreen", _MULTITOUCH)
        _device(sysfs, "event2", "AT Translated Set 2 keyboard", "0")
        assert _find_touchscreen_devices() == ["/dev/input/event4"]

    def test_the_multitouch_bit_may_be_in_the_last_of_several_words(self, sysfs: Path) -> None:
        """Sysfs writes the highest word first: the bits are counted from the last word."""
        _device(sysfs, "event5", "Wacom HID 52A2 Finger", f"1 {_MULTITOUCH}")
        _device(sysfs, "event6", "Not multitouch", f"{_MULTITOUCH} 0")
        assert _find_touchscreen_devices() == ["/dev/input/event5"]

    @pytest.mark.parametrize("name", ["ELAN TouchPad", "Logitech Mouse", "Stylus Pen"])
    def test_touchpads_mice_and_pens_are_not_touchscreens(self, sysfs: Path, name: str) -> None:
        _device(sysfs, "event7", name, _MULTITOUCH)
        assert _find_touchscreen_devices() == []

    def test_a_device_whose_name_or_capabilities_cannot_be_read_is_skipped(
        self, sysfs: Path
    ) -> None:
        _device(sysfs, "event8", None, _MULTITOUCH)
        _device(sysfs, "event9", "ELAN Touchscreen", None)
        assert _find_touchscreen_devices() == []

    def test_with_no_sysfs_input_there_is_none(self, tmp_path: Path) -> None:
        with patch.object(touch_keyboard, "_SYSFS_INPUT", tmp_path / "missing"):
            assert _find_touchscreen_devices() == []


class TestEnableLinuxTouchscreenInput:
    @pytest.fixture
    def window(self) -> Iterator[MagicMock]:
        with patch.object(touch_keyboard, "Window") as window:
            yield window

    @staticmethod
    def _enable(providers: dict[str, object], devices: list[str]) -> MagicMock:
        with (
            patch.object(touch_keyboard, "_find_touchscreen_devices", return_value=devices),
            patch.object(MotionEventFactory, "get", side_effect=providers.get),
            patch.object(EventLoop, "add_input_provider") as add_input_provider,
        ):
            enable_linux_touchscreen_input()
        return add_input_provider

    def test_with_no_touchscreen_nothing_is_registered(
        self, window: MagicMock, loguru_sink: list[str]
    ) -> None:
        original = window.on_motion
        add_input_provider = self._enable({"mtdev": MagicMock()}, [])
        add_input_provider.assert_not_called()
        assert window.on_motion is original
        assert "No touchscreen devices found in sysfs." in loguru_sink

    def test_each_screen_gets_an_mtdev_provider(self, window: MagicMock) -> None:
        mtdev = MagicMock()
        add_input_provider = self._enable(
            {"mtdev": mtdev, "hidinput": MagicMock()}, ["/dev/input/event4", "/dev/input/event5"]
        )
        assert [c.args for c in mtdev.call_args_list] == [
            ("touch_event4", "/dev/input/event4"),
            ("touch_event5", "/dev/input/event5"),
        ]
        assert add_input_provider.call_count == 2  # noqa: PLR2004
        assert window.on_motion.__name__ == "_touch_intercepting_on_motion"

    def test_without_mtdev_hidinput_is_used(self, window: MagicMock) -> None:  # noqa: ARG002
        hidinput = MagicMock()
        self._enable({"hidinput": hidinput}, ["/dev/input/event4"])
        hidinput.assert_called_once_with("touch_event4", "/dev/input/event4")

    def test_without_either_provider_touch_is_left_alone(
        self, window: MagicMock, loguru_sink: list[str]
    ) -> None:
        original = window.on_motion
        add_input_provider = self._enable({}, ["/dev/input/event4"])
        add_input_provider.assert_not_called()
        assert window.on_motion is original
        assert "No mtdev or hidinput provider available for touchscreen input." in loguru_sink

    def test_a_provider_that_could_not_open_its_device_is_not_registered(
        self,
        window: MagicMock,  # noqa: ARG002
    ) -> None:
        add_input_provider = self._enable({"mtdev": MagicMock(return_value=None)}, ["/dev/x"])
        add_input_provider.assert_not_called()

    def test_hardware_touches_are_stamped_and_kept_from_the_widgets(
        self, window: MagicMock
    ) -> None:
        original = window.on_motion
        self._enable({"mtdev": MagicMock()}, ["/dev/input/event4"])
        window._last_hardware_touch_time = 0.0  # noqa: SLF001

        before = time.monotonic()
        assert window.on_motion("begin", MagicMock(device="touch_event4")) is True
        original.assert_not_called()
        assert window._last_hardware_touch_time >= before  # noqa: SLF001

        mouse = MagicMock(device="mouse")
        assert window.on_motion("begin", mouse) is original.return_value
        original.assert_called_once_with("begin", mouse)
