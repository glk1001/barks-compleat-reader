"""The folder chooser's remote keys, and the lines the settings popups log."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from barks_reader.ui import settings_fix
from barks_reader.ui.reader_keyboard_nav import KEY_DOWN, KEY_ENTER, KEY_ESCAPE
from barks_reader.ui.settings_fix import SettingLongPathPopup, SettingOptionsWithValue


def _chooser(*, box_focused: bool = False) -> MagicMock:
    """Stand in for an open chooser: its handlers need only its box and dismiss."""
    chooser = MagicMock()
    chooser.ids.path_input.focus = box_focused
    chooser.ids.path_input.text = "/library"
    return chooser


def _press(chooser: MagicMock, key: int) -> bool:
    return SettingLongPathPopup._on_key_down(chooser, None, key, 0, "", [])  # noqa: SLF001


class TestFolderChooserKeys:
    """auto_dismiss is off, so without these a remote could never leave the chooser."""

    def test_escape_closes_it_unchanged(self) -> None:
        chooser = _chooser()
        assert _press(chooser, KEY_ESCAPE) is True
        chooser.dismiss.assert_called_once()
        chooser.select_path.assert_not_called()

    def test_enter_takes_the_path_in_its_box(self) -> None:
        chooser = _chooser()
        assert _press(chooser, KEY_ENTER) is True
        chooser.select_path.assert_called_once_with("/library")

    def test_enter_in_the_focused_box_is_left_to_the_box(self) -> None:
        """The box's own Enter (on_text_validate) selects; handling it here would select twice."""
        chooser = _chooser(box_focused=True)
        assert _press(chooser, KEY_ENTER) is False
        chooser.select_path.assert_not_called()

    def test_other_keys_pass(self) -> None:
        assert _press(_chooser(), KEY_DOWN) is False


def test_selecting_a_path_logs_it(loguru_sink: list[str]) -> None:
    chooser = _chooser()
    with patch.object(settings_fix, "Clock"):
        SettingLongPathPopup.select_path(chooser, " /library ")
    assert 'Folder chooser: selected "/library".' in loguru_sink
    chooser.dismiss.assert_called_once()


def test_an_option_picked_from_its_list_logs_the_new_value(loguru_sink: list[str]) -> None:
    setting = MagicMock(spec=SettingOptionsWithValue)  # passes _set_option's super()
    setting.key, setting.value, setting.panel = "color_theme", "Duckburg", None
    with (
        patch.object(settings_fix.SettingOptions, "_set_option"),
        patch.object(settings_fix, "Clock"),
    ):
        SettingOptionsWithValue._set_option(setting, MagicMock())  # noqa: SLF001
    assert 'Setting "color_theme" set to "Duckburg".' in loguru_sink
