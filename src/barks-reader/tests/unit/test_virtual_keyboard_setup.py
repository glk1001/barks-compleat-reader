"""The virtual keyboard setting shows an on-screen keyboard without silencing the real one."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.platform_info import Platform
from barks_reader.ui import barks_reader_app as app_module
from barks_reader.ui import touch_keyboard
from barks_reader.ui.barks_reader_app import (
    _apply_virtual_keyboard_setting,
    _configure_virtual_keyboard,
)


def test_the_on_screen_keyboard_is_docked_and_the_physical_keyboard_still_types() -> None:
    """Kivy's "systemanddock": hardware keys reach the focused box only with use_syskeyboard on."""
    window = SimpleNamespace()
    _configure_virtual_keyboard(window)
    assert window.allow_vkeyboard is True
    assert window.docked_vkeyboard is True
    assert window.single_vkeyboard is True
    assert window.use_syskeyboard is True


def _modes(window: MagicMock) -> tuple[bool, bool, bool, bool]:
    return (
        window.allow_vkeyboard,
        window.docked_vkeyboard,
        window.single_vkeyboard,
        window.use_syskeyboard,
    )


@pytest.mark.parametrize("platform", [Platform.LINUX, Platform.WIN])
def test_turned_on_the_keyboard_docks_and_only_linux_sets_up_its_touchscreens(
    platform: Platform,
) -> None:
    window = MagicMock()
    with (
        patch.object(app_module, "PLATFORM", platform),
        patch.object(touch_keyboard, "enable_linux_touchscreen_input") as enable_touchscreens,
    ):
        _apply_virtual_keyboard_setting(window, on=True)
    assert _modes(window) == (True, True, True, True)
    window.release_all_keyboards.assert_not_called()
    assert enable_touchscreens.called is (platform is Platform.LINUX)


def test_turned_off_a_keyboard_on_show_is_released_and_only_the_system_one_is_left() -> None:
    window = MagicMock()
    with patch.object(touch_keyboard, "enable_linux_touchscreen_input") as enable_touchscreens:
        _apply_virtual_keyboard_setting(window, on=False)
    window.release_all_keyboards.assert_called_once_with()
    assert _modes(window) == (False, False, True, True)
    enable_touchscreens.assert_not_called()
