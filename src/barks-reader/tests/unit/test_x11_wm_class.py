"""Forcing the Kivy window's WM_CLASS (barks_reader.ui.x11_wm_class)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from barks_reader.core.platform_info import Platform
from barks_reader.ui import x11_wm_class
from barks_reader.ui.x11_wm_class import force_x11_wm_class


class WindowInfoX11:
    """Named as Kivy's X11 window info is: the function goes by the class's name."""

    display = 0x1234
    window = 42


class WindowInfoWayland:
    """Any other window system's info."""


def test_on_x11_the_windows_class_is_set_to_the_name() -> None:
    with (
        patch.object(x11_wm_class, "PLATFORM", Platform.LINUX),
        patch.object(x11_wm_class, "Window") as window,
        patch.object(x11_wm_class, "set_x11_wm_class") as set_wm_class,
    ):
        window.get_window_info.return_value = WindowInfoX11()
        force_x11_wm_class("barks-reader")

    set_wm_class.assert_called_once_with(0x1234, 42, "barks-reader")


def test_a_window_that_is_not_x11s_is_left_alone() -> None:
    with (
        patch.object(x11_wm_class, "PLATFORM", Platform.LINUX),
        patch.object(x11_wm_class, "Window") as window,
        patch.object(x11_wm_class, "set_x11_wm_class") as set_wm_class,
    ):
        window.get_window_info.return_value = WindowInfoWayland()
        force_x11_wm_class("barks-reader")

    set_wm_class.assert_not_called()


@pytest.mark.parametrize("platform", [p for p in Platform if p is not Platform.LINUX])
def test_off_linux_the_window_is_not_even_asked(platform: Platform) -> None:
    with (
        patch.object(x11_wm_class, "PLATFORM", platform),
        patch.object(x11_wm_class, "Window") as window,
        patch.object(x11_wm_class, "set_x11_wm_class") as set_wm_class,
    ):
        force_x11_wm_class("barks-reader")

    window.get_window_info.assert_not_called()
    set_wm_class.assert_not_called()
