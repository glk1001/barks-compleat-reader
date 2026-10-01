"""The app's settings-change handler: what a changed setting does at once.

The handler needs only the app's reader settings, so it runs on a stand-in rather
than a booted Kivy app. No GUI test changes the alt-escape key, so its branch is
held here: the key takes effect at once, and a value that is not a key code
turns the extra Escape key off rather than crashing the settings panel.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import barks_reader.ui.barks_reader_app as app_module
import pytest
from barks_reader.core.reader_settings import ALT_ESCAPE_KEY, BARKS_READER_SECTION
from barks_reader.ui.barks_reader_app import BarksReaderApp


def _change(key: str, value: object, *, accepted: bool = True) -> tuple[MagicMock, MagicMock]:
    """Run the handler for one change; return the alt-escape setter and the notifier."""
    reader_settings = MagicMock()
    reader_settings.on_changed_setting.return_value = accepted
    stand_in = SimpleNamespace(reader_settings=reader_settings)
    with (
        patch.object(app_module, "set_alt_escape_key") as set_key,
        patch.object(app_module, "settings_notifier") as notifier,
    ):
        BarksReaderApp.on_config_change(
            cast("Any", stand_in), MagicMock(), BARKS_READER_SECTION, key, value
        )
    return set_key, notifier


def test_a_new_alt_escape_key_takes_effect_at_once() -> None:
    set_key, notifier = _change(ALT_ESCAPE_KEY, "27")
    set_key.assert_called_once_with(27)
    notifier.notify.assert_called_once_with(BARKS_READER_SECTION, ALT_ESCAPE_KEY)


@pytest.mark.parametrize("value", ["", "Esc", None])
def test_an_alt_escape_value_that_is_no_key_code_turns_it_off(value: object) -> None:
    set_key, _ = _change(ALT_ESCAPE_KEY, value)
    set_key.assert_called_once_with(0)


def test_a_rejected_change_does_nothing() -> None:
    set_key, notifier = _change(ALT_ESCAPE_KEY, "27", accepted=False)
    set_key.assert_not_called()
    notifier.notify.assert_not_called()
