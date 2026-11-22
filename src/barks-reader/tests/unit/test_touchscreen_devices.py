"""Which input devices count as touchscreens: the scan of a fake sysfs tree under ``tmp_path``."""

from __future__ import annotations

import ctypes
from pathlib import Path

import pytest
from barks_reader.core.touchscreen_devices import (
    SYSFS_INPUT,
    _has_bit,
    find_touchscreen_devices,
)

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
def sysfs(tmp_path: Path) -> Path:
    return tmp_path


class TestFindTouchscreenDevices:
    def test_a_multitouch_screen_is_found(self, sysfs: Path) -> None:
        _device(sysfs, "event4", "ELAN Touchscreen", _MULTITOUCH)
        _device(sysfs, "event2", "AT Translated Set 2 keyboard", "0")
        assert find_touchscreen_devices(sysfs) == ["/dev/input/event4"]

    def test_the_multitouch_bit_may_be_in_the_last_of_several_words(self, sysfs: Path) -> None:
        """Sysfs writes the highest word first: the bits are counted from the last word."""
        _device(sysfs, "event5", "Wacom HID 52A2 Finger", f"1 {_MULTITOUCH}")
        _device(sysfs, "event6", "Not multitouch", f"{_MULTITOUCH} 0")
        assert find_touchscreen_devices(sysfs) == ["/dev/input/event5"]

    @pytest.mark.parametrize("name", ["ELAN TouchPad", "Logitech Mouse", "Stylus Pen"])
    def test_touchpads_mice_and_pens_are_not_touchscreens(self, sysfs: Path, name: str) -> None:
        _device(sysfs, "event7", name, _MULTITOUCH)
        assert find_touchscreen_devices(sysfs) == []

    def test_a_device_whose_name_or_capabilities_cannot_be_read_is_skipped(
        self, sysfs: Path
    ) -> None:
        _device(sysfs, "event8", None, _MULTITOUCH)
        _device(sysfs, "event9", "ELAN Touchscreen", None)
        assert find_touchscreen_devices(sysfs) == []

    def test_with_no_sysfs_input_there_is_none(self, sysfs: Path) -> None:
        assert find_touchscreen_devices(sysfs / "missing") == []

    def test_a_device_whose_capabilities_are_not_hex_words_is_skipped(self, sysfs: Path) -> None:
        """Raised from the scan, at boot, one odd capabilities file ended the app."""
        _device(sysfs, "event3", "Odd Touchscreen", "not-hex")
        _device(sysfs, "event4", "ELAN Touchscreen", _MULTITOUCH)
        assert find_touchscreen_devices(sysfs) == ["/dev/input/event4"]

    def test_a_device_whose_name_is_not_text_is_skipped(self, sysfs: Path) -> None:
        _device(sysfs, "event3", "ELAN Touchscreen", _MULTITOUCH)
        (sysfs / "event3" / "device" / "name").write_bytes(b"\xff\xfe")
        assert find_touchscreen_devices(sysfs) == []

    def test_the_scan_reads_sysfs_unless_told_another_folder(self) -> None:
        assert Path("/sys/class/input") == SYSFS_INPUT

    def test_a_device_skipped_does_not_end_the_scan(self, sysfs: Path) -> None:
        """Each kind of skip goes on to the next device: the touchscreen is the last."""
        _device(sysfs, "event1", None, _MULTITOUCH)  # no name
        _device(sysfs, "event2", "ELAN TouchPad", _MULTITOUCH)  # not a screen
        _device(sysfs, "event3", "Screen with no capabilities", None)
        _device(sysfs, "event4", "ELAN Touchscreen", _MULTITOUCH)
        assert find_touchscreen_devices(sysfs) == ["/dev/input/event4"]


class TestHasBit:
    """A bit of a sysfs bitmap: hex words of a C long each, the highest word first."""

    def test_a_bit_of_the_only_word(self) -> None:
        assert _has_bit(["5"], 0) is True
        assert _has_bit(["5"], 1) is False
        assert _has_bit(["5"], 2) is True

    def test_a_bit_of_a_higher_word_is_counted_past_the_lower_words(self) -> None:
        assert _has_bit(["1", "0"], _LONG_BIT) is True
        assert _has_bit(["1", "0"], 0) is False
        assert _has_bit(["2", "1"], _LONG_BIT + 1) is True
        assert _has_bit(["2", "1"], 0) is True

    def test_a_bit_past_the_last_word_is_not_set(self) -> None:
        assert _has_bit(["f"], _LONG_BIT) is False
        assert _has_bit([], 0) is False
