"""An X11 window's WM_CLASS (barks_reader.core.x11_window)."""

from __future__ import annotations

import ctypes
from unittest.mock import MagicMock, patch

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


def test_without_libx11_nothing_is_set_and_it_is_logged(loguru_sink: list[str]) -> None:
    with patch.object(ctypes, "CDLL", side_effect=OSError("no libX11")):
        assert set_x11_wm_class(1, 2, "barks-reader") is False
    assert any(line.startswith("Could not load libX11") for line in loguru_sink)
