"""The virtual touchscreen's kernel structures and commands (no device is created here)."""

# cspell:ignore timeval absmax EVBIT KEYBIT ABSBIT PROPBIT

from __future__ import annotations

import ast
import contextlib
import os
import struct
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import gui_touch
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

_REPO_ROOT = Path(__file__).resolve().parents[2]

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


def _names_the_app_skips() -> set[str]:
    """Read the app's own list from its source, where the scan of sysfs is."""
    source = _REPO_ROOT / "src/barks-reader/src/barks_reader/core/touchscreen_devices.py"
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_EXCLUDE_DEVICE_NAMES"
            for target in node.targets
        ):
            return set(ast.literal_eval(node.value))
    pytest.fail("touchscreen_devices.py no longer has _EXCLUDE_DEVICE_NAMES: follow where it went")


def test_the_name_is_not_one_the_app_skips() -> None:
    """The app ignores devices named like a touchpad, mouse or pen: its list, not a copy."""
    skipped = _names_the_app_skips()

    assert "touchpad" in skipped  # the list was found, and is the one meant
    assert not any(word in gui_touch.DEVICE_NAME.lower() for word in skipped)


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


# Linux alone: uinput is its kernel's, and a macOS temporary path is too long for a socket.
needs_linux = pytest.mark.skipif(sys.platform != "linux", reason="uinput is Linux's")


class _StopServing(Exception):  # noqa: N818 - not an error: how a test ends the server's loop
    pass


@pytest.fixture
def uinput() -> Iterator[tuple[int, int]]:
    """Stand in for ``/dev/uinput`` with a pipe: yield its read end and the "device" end."""
    read_end, write_end = os.pipe()
    yield read_end, write_end
    for fd in (read_end, write_end):
        with contextlib.suppress(OSError):
            os.close(fd)


@needs_linux
class TestCreateDevice:
    def test_the_device_is_declared_a_direct_touchscreen_then_created(
        self, uinput: tuple[int, int]
    ) -> None:
        import fcntl  # noqa: PLC0415 (Unix only)

        read_end, write_end = uinput
        with (
            patch.object(gui_touch.os, "open", return_value=write_end) as opened,
            patch.object(fcntl, "ioctl") as ioctl,
        ):
            assert gui_touch.create_device("a test screen") == write_end

        assert opened.call_args.args[0] == gui_touch.UINPUT
        requests = [c.args[1:] for c in ioctl.call_args_list]
        assert requests[:3] == [
            (gui_touch.UI_SET_EVBIT, gui_touch.EV_KEY),
            (gui_touch.UI_SET_EVBIT, gui_touch.EV_ABS),
            (gui_touch.UI_SET_KEYBIT, gui_touch.BTN_TOUCH),
        ]
        axes = [c for c in requests if c[0] == gui_touch.UI_SET_ABSBIT]
        assert [code for _, code in axes] == list(gui_touch.AXES)
        assert requests[-2:] == [
            (gui_touch.UI_SET_PROPBIT, gui_touch.INPUT_PROP_DIRECT),
            (gui_touch.UI_DEV_CREATE,),
        ]
        # The device's description goes in before it is created.
        described = gui_touch.user_dev("a test screen")
        assert os.read(read_end, len(described) + 1) == described


class TestDeviceNode:
    @staticmethod
    def _sysfs(tmp_path: Path, names: dict[str, str]) -> list[Path]:
        for entry, name in names.items():
            (tmp_path / entry / "device").mkdir(parents=True)
            (tmp_path / entry / "device" / "name").write_text(f"{name}\n", encoding="utf-8")
        return [tmp_path / entry for entry in names]

    def test_it_is_the_event_node_whose_device_has_the_name(self, tmp_path: Path) -> None:
        entries = self._sysfs(tmp_path, {"event3": "a mouse", "event7": gui_touch.DEVICE_NAME})
        entries.append(tmp_path / "event9")  # one that went away: no name to read
        with (
            patch.object(gui_touch.Path, "glob", return_value=entries),
            patch.object(gui_touch.os, "access", return_value=True),
        ):
            assert gui_touch.device_node() == Path("/dev/input/event7")

    def test_a_node_udev_has_not_opened_up_yet_is_waited_for_then_given_up_on(
        self, tmp_path: Path
    ) -> None:
        entries = self._sysfs(tmp_path, {"event7": gui_touch.DEVICE_NAME})
        with (
            patch.object(gui_touch.Path, "glob", return_value=entries),
            patch.object(gui_touch.os, "access", return_value=False),
            patch.object(gui_touch.time, "monotonic", side_effect=[0.0, 1.0, 2.0, 6.0]),
            patch.object(gui_touch.time, "sleep") as sleep,
        ):
            assert gui_touch.device_node(timeout=5.0) is None

        assert sleep.call_count == 2  # noqa: PLR2004


@needs_linux
class TestServeAndSend:
    """The server and its client over a real socket, the device a pipe."""

    @pytest.fixture
    def serving(self, tmp_path: Path, uinput: tuple[int, int]) -> Iterator[tuple[Path, int]]:
        """Serve on a socket under `tmp_path`; yield it and the end the events come out of."""
        read_end, write_end = uinput
        sock = tmp_path / "touch.sock"
        real_finger_down = gui_touch.finger_down

        def finger_down(tracking_id: int, x: float, y: float) -> bytes:
            if x < 0:
                raise _StopServing
            return real_finger_down(tracking_id, x, y)

        def serve() -> None:
            with contextlib.suppress(_StopServing):
                gui_touch.serve(sock)

        with (
            patch.object(gui_touch, "create_device", return_value=write_end),
            patch.object(gui_touch, "device_node", return_value=Path("/dev/input/event7")),
            patch.object(gui_touch, "finger_down", side_effect=finger_down),
        ):
            server = threading.Thread(target=serve)
            server.start()
            deadline = time.monotonic() + 30
            while not sock.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            try:
                yield sock, read_end
            finally:
                gui_touch.send(sock, ["down", "-1", "-1"])  # the server's way out
                server.join(timeout=30)
        assert not server.is_alive()
        assert not sock.exists()  # it clears its socket away as it goes

    def test_a_touch_and_its_lift_reach_the_device_and_are_answered(
        self, serving: tuple[Path, int]
    ) -> None:
        sock, device = serving

        assert gui_touch.send(sock, ["down", "0.5", "0.25"]) == 0
        down = os.read(device, 4096)
        assert gui_touch.send(sock, ["up"]) == 0
        up = os.read(device, 4096)

        assert down == gui_touch.finger_down(1, 0.5, 0.25)
        assert up == gui_touch.finger_up()

    def test_each_touch_is_a_new_contact(self, serving: tuple[Path, int]) -> None:
        sock, device = serving

        gui_touch.send(sock, ["down", "0.1", "0.1"])
        gui_touch.send(sock, ["down", "0.9", "0.9"])

        both = os.read(device, 4096)
        assert both == gui_touch.finger_down(1, 0.1, 0.1) + gui_touch.finger_down(2, 0.9, 0.9)

    def test_a_line_that_is_neither_is_answered_and_touches_nothing(
        self, serving: tuple[Path, int]
    ) -> None:
        sock, device = serving

        assert gui_touch.send(sock, ["down", "0.5"]) == 0
        assert gui_touch.send(sock, ["sideways"]) == 0

        os.set_blocking(device, False)
        with pytest.raises(BlockingIOError):
            os.read(device, 4096)

    def test_a_device_that_never_shows_up_fails_the_server(
        self, tmp_path: Path, uinput: tuple[int, int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        with (
            patch.object(gui_touch, "create_device", return_value=uinput[1]),
            patch.object(gui_touch, "device_node", return_value=None),
        ):
            assert gui_touch.serve(tmp_path / "touch.sock") == 1

        assert "never became readable in /dev/input" in capsys.readouterr().err
        assert not (tmp_path / "touch.sock").exists()


class TestCommands:
    @pytest.mark.parametrize(("writable", "status"), [(True, 0), (False, 1)])
    def test_check_says_whether_this_user_may_make_a_device(
        self, writable: bool, status: int
    ) -> None:
        with patch.object(gui_touch.os, "access", return_value=writable) as access:
            assert gui_touch.main(["check"]) == status

        access.assert_called_once_with(gui_touch.UINPUT, os.W_OK)

    def test_serve_and_send_are_given_the_socket(self) -> None:
        with (
            patch.object(gui_touch, "serve", return_value=0) as serve,
            patch.object(gui_touch, "send", return_value=1) as send,
        ):
            assert gui_touch.main(["serve", "/run/touch.sock"]) == 0
            assert gui_touch.main(["send", "/run/touch.sock", "down", "0.5", "0.25"]) == 1

        serve.assert_called_once_with(Path("/run/touch.sock"))
        send.assert_called_once_with(Path("/run/touch.sock"), ["down", "0.5", "0.25"])
