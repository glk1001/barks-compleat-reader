from __future__ import annotations

from kivy.core.window import Window

from barks_reader.core.platform_info import PLATFORM, Platform
from barks_reader.core.x11_window import set_x11_wm_class


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

    set_x11_wm_class(info.display, info.window, name)
