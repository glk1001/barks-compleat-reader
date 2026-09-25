#!/usr/bin/env python3
"""A virtual touchscreen for the GUI probe's touch mode, on Linux (uinput).

``gui-probe.sh`` taps by clicking; with ``BARKS_PROBE_TOUCH=1`` it taps by touch:
this creates a kernel touchscreen device before the app boots and turns each tap
into a finger press on it. The app finds the device as it finds a real one (with
its virtual keyboard setting on, it reads every touchscreen through Kivy's mtdev
provider) and the probe then sends the click SDL makes of a real touch - on a
nested X server there is no touch to make one from. So a tap reaches the app down
both of a real touchscreen's paths: the hardware event, and the pointer press.

The device is system-wide. The udev rule in ``scripts/udev/`` hides it from the
desktop (libinput ignores it), or its taps would land on the real screen too; it
also lets the ``input`` group open ``/dev/uinput``. ``gui-probe.sh doctor`` checks
both. Only the standard library is used.

Usage:
    gui_touch.py serve SOCKET   # create the device, then take taps on a unix socket
    gui_touch.py send SOCKET down X Y | up   # X and Y in 0..1 of the app window
    gui_touch.py check          # exit 0 when /dev/uinput can be opened for writing
"""

# cspell:ignore EVBIT KEYBIT ABSBIT PROPBIT timeval absmax absmin absfuzz absflat WRONLY NONBLOCK

from __future__ import annotations

import contextlib
import os
import socket
import struct
import sys
import time
from pathlib import Path

DEVICE_NAME = "Barks GUI Test Touchscreen"
UINPUT = Path("/dev/uinput")
AXIS_MAX = 32767

# linux/input-event-codes.h and linux/uinput.h.
EV_SYN, EV_KEY, EV_ABS = 0x00, 0x01, 0x03
SYN_REPORT = 0
BTN_TOUCH = 0x14A
ABS_X, ABS_Y = 0x00, 0x01
ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TRACKING_ID = 0x2F, 0x35, 0x36, 0x39
INPUT_PROP_DIRECT = 0x01
BUS_VIRTUAL = 0x06
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_ABSBIT, UI_SET_PROPBIT = (
    0x40045564,
    0x40045565,
    0x40045567,
    0x4004556E,
)
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
ABS_CNT = 64
UINPUT_MAX_NAME_SIZE = 80
_EVENT = struct.Struct("llHHi")  # struct input_event: timeval, type, code, value

AXES = {
    ABS_X: AXIS_MAX,
    ABS_Y: AXIS_MAX,
    ABS_MT_SLOT: 0,
    ABS_MT_POSITION_X: AXIS_MAX,
    ABS_MT_POSITION_Y: AXIS_MAX,
    ABS_MT_TRACKING_ID: 0xFFFF,
}


def user_dev(name: str) -> bytes:
    """Return a ``struct uinput_user_dev`` for a one-finger touchscreen named `name`.

    Args:
        name: The device's name, as ``/sys/class/input/*/device/name`` shows it.

    Returns:
        The struct's bytes, to write to ``/dev/uinput`` before ``UI_DEV_CREATE``.

    """
    absmax = [0] * ABS_CNT
    for code, top in AXES.items():
        absmax[code] = top
    zeros = [0] * ABS_CNT
    return (
        name.encode()[: UINPUT_MAX_NAME_SIZE - 1].ljust(UINPUT_MAX_NAME_SIZE, b"\0")
        + struct.pack("HHHH", BUS_VIRTUAL, 0x1209, 0xBA4C, 1)  # bus, vendor, product, version
        + struct.pack("i", 0)  # ff_effects_max
        + struct.pack(f"{ABS_CNT}i", *absmax)
        + struct.pack(f"{ABS_CNT}i", *zeros)  # absmin
        + struct.pack(f"{ABS_CNT}i", *zeros)  # absfuzz
        + struct.pack(f"{ABS_CNT}i", *zeros)  # absflat
    )


def event(kind: int, code: int, value: int) -> bytes:
    """Return one ``struct input_event``, its time left for the kernel to stamp."""
    return _EVENT.pack(0, 0, kind, code, value)


def to_axis(fraction: float) -> int:
    """Return a 0..1 window fraction as a device axis value, clamped to the axis."""
    return max(0, min(AXIS_MAX, round(fraction * AXIS_MAX)))


def finger_down(tracking_id: int, x: float, y: float) -> bytes:
    """Return the events of one finger touching at window fractions `x`, `y`."""
    ax, ay = to_axis(x), to_axis(y)
    return b"".join(
        [
            event(EV_ABS, ABS_MT_SLOT, 0),
            event(EV_ABS, ABS_MT_TRACKING_ID, tracking_id),
            event(EV_ABS, ABS_MT_POSITION_X, ax),
            event(EV_ABS, ABS_MT_POSITION_Y, ay),
            event(EV_KEY, BTN_TOUCH, 1),
            event(EV_ABS, ABS_X, ax),
            event(EV_ABS, ABS_Y, ay),
            event(EV_SYN, SYN_REPORT, 0),
        ]
    )


def finger_up() -> bytes:
    """Return the events of the finger lifting."""
    return b"".join(
        [
            event(EV_ABS, ABS_MT_SLOT, 0),
            event(EV_ABS, ABS_MT_TRACKING_ID, -1),
            event(EV_KEY, BTN_TOUCH, 0),
            event(EV_SYN, SYN_REPORT, 0),
        ]
    )


def create_device(name: str = DEVICE_NAME) -> int:
    """Create the touchscreen and return the open ``/dev/uinput`` descriptor behind it."""
    import fcntl  # noqa: PLC0415  (Unix only: the rest of this module is imported on Windows too)

    fd = os.open(UINPUT, os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_ABS)
    fcntl.ioctl(fd, UI_SET_KEYBIT, BTN_TOUCH)
    for code in AXES:
        fcntl.ioctl(fd, UI_SET_ABSBIT, code)
    fcntl.ioctl(fd, UI_SET_PROPBIT, INPUT_PROP_DIRECT)
    os.write(fd, user_dev(name))
    fcntl.ioctl(fd, UI_DEV_CREATE)
    return fd


def device_node(name: str = DEVICE_NAME, timeout: float = 5.0) -> Path | None:
    """Return the ``/dev/input/eventN`` the device `name` got, once it can be opened."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for entry in sorted(Path("/sys/class/input").glob("event*")):
            with contextlib.suppress(OSError):
                if (entry / "device" / "name").read_text().strip() == name:
                    node = Path("/dev/input") / entry.name
                    if os.access(node, os.R_OK):  # udev has set its group
                        return node
        time.sleep(0.05)
    return None


def serve(sock_path: Path) -> int:
    """Create the device, then apply "down X Y" and "up" lines sent to `sock_path`."""
    fd = create_device()
    node = device_node()
    if node is None:
        print(f"gui-touch: {DEVICE_NAME} never became readable in /dev/input", file=sys.stderr)  # noqa: T201
        return 1
    sock_path.unlink(missing_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sock_path))
    server.listen(1)
    print(f"gui-touch: ready, {node}", flush=True)  # noqa: T201
    tracking_id = 0
    try:
        while True:
            conn, _ = server.accept()
            with conn:
                words = conn.recv(256).decode().split()
                if words[:1] == ["down"] and len(words) == 3:  # noqa: PLR2004
                    tracking_id = (tracking_id + 1) % 0xFFFF
                    os.write(fd, finger_down(tracking_id, float(words[1]), float(words[2])))
                elif words == ["up"]:
                    os.write(fd, finger_up())
                conn.sendall(b"ok\n")
    finally:
        import fcntl  # noqa: PLC0415  (Unix only, as in create_device)

        with contextlib.suppress(OSError):
            fcntl.ioctl(fd, UI_DEV_DESTROY)
        os.close(fd)
        sock_path.unlink(missing_ok=True)


def send(sock_path: Path, words: list[str]) -> int:
    """Send one "down X Y" or "up" to a serving device and wait for its answer."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.connect(str(sock_path))
        conn.sendall(" ".join(words).encode())
        return 0 if conn.recv(16).startswith(b"ok") else 1


def can_create() -> bool:
    """Return whether this user may open ``/dev/uinput`` for writing."""
    return os.access(UINPUT, os.W_OK)


def main(argv: list[str]) -> int:
    """Run the command `argv` names (see the module docstring)."""
    match argv:
        case ["serve", sock]:
            return serve(Path(sock))
        case ["send", sock, *words]:
            return send(Path(sock), words)
        case ["check"]:
            return 0 if can_create() else 1
        case _:
            print(__doc__, file=sys.stderr)  # noqa: T201
            return 2


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        sys.exit(main(sys.argv[1:]))
