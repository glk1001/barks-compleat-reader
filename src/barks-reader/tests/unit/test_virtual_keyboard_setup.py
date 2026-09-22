"""The virtual keyboard setting shows an on-screen keyboard without silencing the real one."""

from __future__ import annotations

from types import SimpleNamespace

from barks_reader.ui.barks_reader_app import _configure_virtual_keyboard


def test_the_on_screen_keyboard_is_docked_and_the_physical_keyboard_still_types() -> None:
    """Kivy's "systemanddock": hardware keys reach the focused box only with use_syskeyboard on."""
    window = SimpleNamespace()
    _configure_virtual_keyboard(window)
    assert window.allow_vkeyboard is True
    assert window.docked_vkeyboard is True
    assert window.single_vkeyboard is True
    assert window.use_syskeyboard is True
