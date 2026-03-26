"""Touchscreen-aware virtual keyboard support for Linux.

On Linux, Kivy's SDL2 backend converts touchscreen finger events into
ordinary mouse events, making them indistinguishable from real mouse clicks.
This module works around the problem in three layers:

1. **Device detection** — :func:`_find_touchscreen_devices` scans ``/sys/class/input``
   for devices with ``ABS_MT_POSITION_X`` capability whose name does *not*
   indicate a touchpad, mouse, or pen.

2. **MTD event interception** — :func:`enable_linux_touchscreen_input` registers
   ``mtdev`` providers for the discovered touchscreens, then patches
   ``Window.on_motion`` so that their events are consumed (they carry
   uncalibrated coordinates that would break widget focus) after recording a
   monotonic timestamp on the Window.

3. **Per-widget keyboard selection** — :class:`TouchAwareTextInput` checks
   that timestamp to decide whether an incoming ``device='mouse'`` event is
   really a touch-emulated click (recent hardware touch → show virtual
   keyboard) or a genuine mouse click (no recent touch → suppress virtual
   keyboard, use system keyboard).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from kivy.core.window import Window
from kivy.uix.textinput import TextInput
from loguru import logger

if TYPE_CHECKING:
    from kivy.input import MotionEvent

# ---------------------------------------------------------------------------
# Touchscreen device discovery
# ---------------------------------------------------------------------------

_ABS_MT_POSITION_X = 0x35
_EXCLUDE_DEVICE_NAMES = {"touchpad", "mouse", "pen"}


def _find_touchscreen_devices() -> list[str]:
    """Return ``/dev/input/eventN`` paths for likely touchscreen devices.

    Scans sysfs for input devices that have ``ABS_MT_POSITION_X`` capability
    (multitouch) and whose name does not contain "Touchpad", "Mouse", or "Pen".
    """
    import ctypes  # noqa: PLC0415

    long_bit = ctypes.sizeof(ctypes.c_long) * 8
    devices: list[str] = []
    sysfs_input = Path("/sys/class/input")
    if not sysfs_input.is_dir():
        return devices
    for entry in sorted(sysfs_input.glob("event*")):
        name_path = entry / "device" / "name"
        try:
            name = name_path.read_text().strip()
        except OSError:
            continue
        if any(exc in name.lower() for exc in _EXCLUDE_DEVICE_NAMES):
            continue

        caps_path = entry / "device" / "capabilities" / "abs"
        try:
            words = caps_path.read_text().strip().split()
        except OSError:
            continue
        bits: list[bool] = []
        for word in words:
            val = int(word, 16)
            bits[:0] = [bool(val & (1 << i)) for i in range(long_bit)]
        if len(bits) > _ABS_MT_POSITION_X and bits[_ABS_MT_POSITION_X]:
            devices.append(f"/dev/input/{entry.name}")

    return devices


# ---------------------------------------------------------------------------
# MTD provider registration + Window.on_motion interception
# ---------------------------------------------------------------------------


def enable_linux_touchscreen_input() -> None:
    """Register MTD providers for touchscreens and intercept their events.

    MTD events carry uncalibrated coordinates that would interfere with widget
    focus, so we intercept them in ``Window.on_motion`` — recording a timestamp
    as a "hardware touch happened" signal — and prevent them from being
    dispatched to the widget tree.

    Must be called after ``EventLoop.ensure_window()`` and before
    ``EventLoop.start()`` (i.e. during ``App.build()``).
    """
    from kivy.base import EventLoop  # noqa: PLC0415
    from kivy.input.factory import MotionEventFactory  # noqa: PLC0415

    touchscreen_devices = _find_touchscreen_devices()
    if not touchscreen_devices:
        logger.info("No touchscreen devices found in sysfs.")
        return

    provider_cls = MotionEventFactory.get("mtdev")
    if provider_cls is None:
        provider_cls = MotionEventFactory.get("hidinput")
    if provider_cls is None:
        logger.warning("No mtdev or hidinput provider available for touchscreen input.")
        return

    for device_path in touchscreen_devices:
        name = Path(device_path).name
        provider = provider_cls(f"touch_{name}", device_path)
        if provider:
            EventLoop.add_input_provider(provider)
            logger.info(f"Registered touchscreen input provider for {device_path}.")

    original_on_motion = Window.on_motion

    def _touch_intercepting_on_motion(etype: str, me: object) -> bool:
        if getattr(me, "device", "mouse") != "mouse":
            Window._last_hardware_touch_time = time.monotonic()  # type: ignore[attr-defined]  # noqa: SLF001
            return True
        return original_on_motion(etype, me)

    Window.on_motion = _touch_intercepting_on_motion  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Touch-aware TextInput widget
# ---------------------------------------------------------------------------

# Time window (seconds) within which a mouse event following a hardware
# touch is considered touch-emulated rather than a real mouse click.
_TOUCH_WINDOW_SECS = 0.15


class TouchAwareTextInput(TextInput):
    """TextInput that shows the virtual keyboard only for real touchscreen taps.

    A touchscreen tap generates both an MTD event (``device='eventN'``) and an
    SDL2-emulated mouse event (``device='mouse'``), arriving in separate frames.
    MTD events are intercepted at the Window level (see
    :func:`enable_linux_touchscreen_input`) and never reach widgets — they only
    set ``Window._last_hardware_touch_time``.  This widget checks that timestamp
    to decide whether an incoming mouse event is a real mouse click or a
    touch-emulated one.
    """

    _TOUCH_WINDOW_SECS: ClassVar[float] = _TOUCH_WINDOW_SECS

    def on_touch_down(self, touch: MotionEvent) -> bool:
        """Show virtual keyboard for touch taps, suppress for mouse clicks."""
        if not self.collide_point(*touch.pos) or not Window.allow_vkeyboard:
            return super().on_touch_down(touch)

        last_hw_touch: float = getattr(Window, "_last_hardware_touch_time", 0.0)
        recent_touch = (time.monotonic() - last_hw_touch) < self._TOUCH_WINDOW_SECS

        if not recent_touch:
            self._use_system_keyboard_for_click(touch)
            return True

        return super().on_touch_down(touch)

    def _use_system_keyboard_for_click(self, touch: MotionEvent) -> bool:
        """Handle a real mouse click by requesting the system keyboard.

        Temporarily suppresses ``Window.allow_vkeyboard`` so that
        ``request_keyboard`` returns the system keyboard instead of the
        virtual one.  Also clears the stale ``FocusBehavior._keyboards``
        entry for the system keyboard singleton so that ``_bind_keyboard``
        does not self-unfocus this widget.
        """
        from kivy.uix.behaviors import FocusBehavior  # noqa: PLC0415

        sys_kb = Window._system_keyboard  # noqa: SLF001
        if sys_kb in FocusBehavior._keyboards:  # noqa: SLF001
            FocusBehavior._keyboards[sys_kb] = None  # noqa: SLF001

        Window.allow_vkeyboard = False
        result = super().on_touch_down(touch)
        Window.allow_vkeyboard = True
        return result
