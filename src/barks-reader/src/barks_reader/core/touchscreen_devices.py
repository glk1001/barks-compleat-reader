"""Which of a Linux machine's input devices are touchscreens, read from sysfs.

The part of the touch keyboard's support without Kivy: ``barks_reader.ui.touch_keyboard``
registers an input provider for each device found here.
"""

from __future__ import annotations

import ctypes
from pathlib import Path

SYSFS_INPUT = Path("/sys/class/input")

_ABS_MT_POSITION_X = 0x35
_EXCLUDE_DEVICE_NAMES = {"touchpad", "mouse", "pen"}


def find_touchscreen_devices(sysfs_input: Path = SYSFS_INPUT) -> list[str]:
    """Return ``/dev/input/eventN`` paths for likely touchscreen devices.

    Scans sysfs for input devices that have ``ABS_MT_POSITION_X`` capability
    (multitouch) and whose name does not contain "Touchpad", "Mouse", or "Pen".
    A device whose name or capabilities cannot be read, or whose capabilities are
    not the hex words sysfs writes, is skipped: the scan runs at boot.

    Args:
        sysfs_input: The folder of input devices, sysfs's own unless a test's.

    Returns:
        The devices' paths, in event-name order; none where there is no such folder.

    """
    devices: list[str] = []
    if not sysfs_input.is_dir():
        return devices
    for entry in sorted(sysfs_input.glob("event*")):
        try:
            name = (entry / "device" / "name").read_text(encoding="utf-8").strip()
        except (OSError, ValueError):
            continue
        if any(exc in name.lower() for exc in _EXCLUDE_DEVICE_NAMES):
            continue

        caps_path = entry / "device" / "capabilities" / "abs"
        try:
            words = caps_path.read_text(encoding="utf-8").strip().split()
            has_multitouch = _has_bit(words, _ABS_MT_POSITION_X)
        except (OSError, ValueError):
            continue
        if has_multitouch:
            devices.append(f"/dev/input/{entry.name}")

    return devices


def _has_bit(words: list[str], bit: int) -> bool:
    """Whether `bit` is set in a sysfs capabilities bitmap: hex words, the highest first."""
    long_bit = ctypes.sizeof(ctypes.c_long) * 8
    bits: list[bool] = []
    for word in words:
        val = int(word, 16)
        bits[:0] = [bool(val & (1 << i)) for i in range(long_bit)]
    return len(bits) > bit and bits[bit]
