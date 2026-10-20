"""An X11 window's WM_CLASS (barks_reader.core.x11_window)."""

from __future__ import annotations

import ctypes
from unittest.mock import MagicMock, patch

import barks_reader.core.x11_window as x11_window_module
from barks_reader.core.x11_window import set_x11_wm_class


def test_the_name_is_set_as_both_name_and_class_and_flushed(loguru_sink: list[str]) -> None:
    libx11 = MagicMock()
    with patch.object(ctypes, "CDLL", return_value=libx11) as cdll:
        assert set_x11_wm_class(0x1234, 42, "barks-reader") is True

    cdll.assert_called_once_with("libX11.so.6")
    display, window, hint_ref = libx11.XSetClassHint.call_args.args
    assert (display, window) == (0x1234, 42)
    hint = hint_ref._obj  # noqa: SLF001
    assert (hint.res_name, hint.res_class) == (b"barks-reader", b"barks-reader")
    libx11.XFlush.assert_called_once_with(0x1234)
    assert "Forced X11 WM_CLASS to 'barks-reader'." in loguru_sink


def test_the_calls_are_declared_so_a_64_bit_display_pointer_survives() -> None:
    """Undeclared, ctypes passes a Python int as a C int: a display pointer is cut short."""
    libx11 = MagicMock()
    with patch.object(ctypes, "CDLL", return_value=libx11):
        set_x11_wm_class(0x7F00_0000_1234, 42, "barks-reader")

    hint_type = x11_window_module._XClassHint  # noqa: SLF001
    assert libx11.XSetClassHint.argtypes == (
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(hint_type),
    )
    assert libx11.XSetClassHint.restype is ctypes.c_int
    assert libx11.XFlush.argtypes == (ctypes.c_void_p,)
    assert libx11.XFlush.restype is ctypes.c_int


def test_without_libx11_nothing_is_set_and_it_is_logged(loguru_sink: list[str]) -> None:
    with patch.object(ctypes, "CDLL", side_effect=OSError("no libX11")):
        assert set_x11_wm_class(1, 2, "barks-reader") is False
    assert any(line.startswith("Could not load libX11") for line in loguru_sink)
