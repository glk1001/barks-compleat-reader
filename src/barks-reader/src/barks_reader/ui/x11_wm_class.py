from __future__ import annotations

import ctypes

from kivy.core.window import Window
from loguru import logger

from barks_reader.core.platform_info import PLATFORM, Platform


class _XClassHint(ctypes.Structure):
    _fields_ = (
        ("res_name", ctypes.c_char_p),
        ("res_class", ctypes.c_char_p),
    )


def force_x11_wm_class(name: str) -> None:
    """Override the X11 WM_CLASS of the current SDL2/Kivy window via XSetClassHint.

    Kivy's bundled SDL2 derives WM_CLASS from the ``App`` class name and ignores the
    ``SDL_VIDEO_X11_WMCLASS`` env var, leaving WM_CLASS as e.g. ``BarksReader.BarksReader``.
    GNOME and other compositors match a window to its ``.desktop`` icon by
    ``WM_CLASS`` / ``StartupWMClass``, so a mismatch here makes the dock fall back to a
    generic icon. This forces the value to ``name`` after Kivy/SDL2 has created the
    window so the match succeeds.

    No-op on non-Linux, when the WindowInfo isn't X11 (e.g. native Wayland or
    Windows), or if libX11 isn't loadable. The window must already exist.

    Args:
        name: Value to set for both ``res_name`` and ``res_class``.

    """
    if PLATFORM != Platform.LINUX:
        return

    info = Window.get_window_info()
    if type(info).__name__ != "WindowInfoX11":
        return

    try:
        libx11 = ctypes.CDLL("libX11.so.6")
    except OSError as exc:
        logger.warning(f"Could not load libX11: {exc}")
        return

    libx11.XSetClassHint.argtypes = (
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(_XClassHint),
    )
    libx11.XSetClassHint.restype = ctypes.c_int
    libx11.XFlush.argtypes = (ctypes.c_void_p,)
    libx11.XFlush.restype = ctypes.c_int

    encoded = name.encode("utf-8")
    hint = _XClassHint(res_name=encoded, res_class=encoded)
    libx11.XSetClassHint(info.display, info.window, ctypes.byref(hint))
    libx11.XFlush(info.display)

    logger.info(f"Forced X11 WM_CLASS to '{name}'.")
