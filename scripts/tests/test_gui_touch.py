"""The virtual touchscreen's kernel structures and commands (no device is created here)."""

# cspell:ignore timeval absmax

from __future__ import annotations

import struct
import sys

import gui_touch
import pytest

# struct uinput_user_dev: name[80], input_id (4 x u16), ff_effects_max, 4 x abs[64].
USER_DEV_SIZE = 80 + 8 + 4 + 4 * 64 * 4
INPUT_EVENT_SIZE = 24  # 64-bit Linux: struct timeval (2 x long), u16 type, u16 code, s32 value


def _events(data: bytes) -> list[tuple[int, int, int]]:
    # The module's own event layout: native longs, so this reads what it wrote on
    # any platform, though only Linux's kernel ever sees it.
    events = []
    for offset in range(0, len(data), gui_touch._EVENT.size):  # noqa: SLF001
        _, _, kind, code, value = gui_touch._EVENT.unpack_from(data, offset)  # noqa: SLF001
        events.append((kind, code, value))
    return events


def test_the_device_struct_is_the_kernels_size() -> None:
    assert len(gui_touch.user_dev(gui_touch.DEVICE_NAME)) == USER_DEV_SIZE


def test_the_device_is_named_and_has_its_axes() -> None:
    raw = gui_touch.user_dev(gui_touch.DEVICE_NAME)
    assert raw[:80].rstrip(b"\0").decode() == gui_touch.DEVICE_NAME
    absmax = struct.unpack_from("64i", raw, 80 + 8 + 4)
    assert absmax[gui_touch.ABS_MT_POSITION_X] == gui_touch.AXIS_MAX
    assert absmax[gui_touch.ABS_MT_POSITION_Y] == gui_touch.AXIS_MAX


def test_the_name_is_not_one_the_app_skips() -> None:
    """The app ignores devices named like a touchpad, mouse or pen (touch_keyboard.py)."""
    assert not any(word in gui_touch.DEVICE_NAME.lower() for word in ("touchpad", "mouse", "pen"))


@pytest.mark.skipif(sys.platform != "linux", reason="the kernel's event layout is Linux's")
def test_an_event_is_the_kernels_size() -> None:
    assert len(gui_touch.event(gui_touch.EV_SYN, gui_touch.SYN_REPORT, 0)) == INPUT_EVENT_SIZE


@pytest.mark.parametrize(
    ("fraction", "axis"), [(0.0, 0), (0.5, 16384), (1.0, 32767), (-1.0, 0), (2.0, 32767)]
)
def test_a_window_fraction_is_clamped_to_the_axis(fraction: float, axis: int) -> None:
    assert gui_touch.to_axis(fraction) == axis


def test_a_finger_down_touches_then_reports() -> None:
    events = _events(gui_touch.finger_down(7, 0.25, 0.75))
    assert (gui_touch.EV_ABS, gui_touch.ABS_MT_TRACKING_ID, 7) in events
    assert (gui_touch.EV_ABS, gui_touch.ABS_MT_POSITION_X, gui_touch.to_axis(0.25)) in events
    assert (gui_touch.EV_ABS, gui_touch.ABS_MT_POSITION_Y, gui_touch.to_axis(0.75)) in events
    assert (gui_touch.EV_KEY, gui_touch.BTN_TOUCH, 1) in events
    assert events[-1] == (gui_touch.EV_SYN, gui_touch.SYN_REPORT, 0)


def test_a_finger_up_ends_the_contact() -> None:
    events = _events(gui_touch.finger_up())
    assert (gui_touch.EV_ABS, gui_touch.ABS_MT_TRACKING_ID, -1) in events
    assert (gui_touch.EV_KEY, gui_touch.BTN_TOUCH, 0) in events
    assert events[-1] == (gui_touch.EV_SYN, gui_touch.SYN_REPORT, 0)


def test_an_unknown_command_prints_the_usage(capsys: pytest.CaptureFixture[str]) -> None:
    assert gui_touch.main(["bogus"]) == 2  # noqa: PLR2004
    assert "Usage:" in capsys.readouterr().err
