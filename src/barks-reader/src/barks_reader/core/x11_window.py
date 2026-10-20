"""An X11 window's WM_CLASS, set through libX11. Kivy-free: the handles are passed in."""

from __future__ import annotations

import ctypes

from loguru import logger


class _XClassHint(ctypes.Structure):
    _fields_ = (
        ("res_name", ctypes.c_char_p),
        ("res_class", ctypes.c_char_p),
    )


def set_x11_wm_class(display: int, window: int, name: str) -> bool:
    """Set an X11 window's WM_CLASS, both name and class, to `name` via XSetClassHint.

    GNOME and other compositors match a window to its ``.desktop`` icon by
    ``WM_CLASS`` / ``StartupWMClass``; a mismatch leaves the dock on a generic icon.

    Args:
        display: The X display connection, as the window's toolkit holds it.
        window: The X window.
        name: Value to set for both ``res_name`` and ``res_class``.

    Returns:
        Whether it was set; False when libX11 cannot be loaded.

    """
    try:
        libx11 = ctypes.CDLL("libX11.so.6")
    except OSError as exc:
        logger.warning(f"Could not load libX11: {exc}")
        return False

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
    libx11.XSetClassHint(display, window, ctypes.byref(hint))
    libx11.XFlush(display)

    logger.info(f"Forced X11 WM_CLASS to '{name}'.")
    return True
