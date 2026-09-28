# ruff: noqa: SLF001
"""The folder chooser's remote keys, and the lines the settings popups log."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from barks_reader.ui import settings_fix
from barks_reader.ui.reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_UP,
)
from barks_reader.ui.settings_fix import SettingLongPathPopup, SettingOptionsWithValue


def _chooser(*, box_focused: bool = False) -> MagicMock:
    """Stand in for an open chooser: its handlers need only its box and dismiss."""
    chooser = MagicMock()
    chooser.ids.path_input.focus = box_focused
    chooser.ids.path_input.text = "/library"
    return chooser


def _press(chooser: MagicMock, key: int) -> bool:
    return SettingLongPathPopup._on_key_down(chooser, None, key, 0, "", [])


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

    def test_the_arrows_browse(self) -> None:
        chooser = _chooser()
        chooser.ids.file_chooser.path = "/books/library"
        assert _press(chooser, KEY_DOWN) is True
        chooser._move_highlight.assert_called_once_with(1)
        _press(chooser, KEY_UP)
        chooser._move_highlight.assert_called_with(-1)
        _press(chooser, KEY_RIGHT)
        chooser._open_highlighted.assert_called_once()
        _press(chooser, KEY_LEFT)
        chooser._open_folder.assert_called_once_with(str(Path("/books")))

    def test_while_the_box_types_only_escape_is_taken(self) -> None:
        chooser = _chooser(box_focused=True)
        assert _press(chooser, KEY_DOWN) is False
        assert _press(chooser, KEY_ESCAPE) is True

    def test_other_keys_pass(self) -> None:
        assert _press(_chooser(), ord("a")) is False


def _browsing(tmp_path: Path, selected: str | None) -> MagicMock:
    """Stand in for a chooser listing '../', alpha/, beta/ and a file in `tmp_path`."""
    for name in ("alpha", "beta"):
        (tmp_path / name).mkdir()
    (tmp_path / "notes.txt").write_text("x")
    names = ["..", "alpha", "beta", "notes.txt"]
    chooser = MagicMock()
    chooser.ids.file_chooser.path = str(tmp_path)
    chooser.ids.file_chooser._items = [SimpleNamespace(path=str(tmp_path / n)) for n in names]
    chooser.ids.file_chooser.selection = [str(tmp_path / selected)] if selected else []
    return chooser


class TestFolderChooserBrowsing:
    def test_the_highlight_moves_and_stops_at_the_ends(self, tmp_path: Path) -> None:
        chooser = _browsing(tmp_path, "alpha")
        SettingLongPathPopup._move_highlight(chooser, 1)
        assert chooser.ids.file_chooser.selection == [str(tmp_path / "beta")]
        SettingLongPathPopup._move_highlight(chooser, 5)
        assert chooser.ids.file_chooser.selection == [str(tmp_path / "notes.txt")]

    def test_with_nothing_highlighted_it_starts_at_the_top(self, tmp_path: Path) -> None:
        chooser = _browsing(tmp_path, None)
        SettingLongPathPopup._move_highlight(chooser, 1)
        assert chooser.ids.file_chooser.selection == [str(tmp_path / "..")]

    def test_right_opens_a_folder_and_the_parent_entry(self, tmp_path: Path) -> None:
        chooser = _browsing(tmp_path, "beta")
        SettingLongPathPopup._open_highlighted(chooser)
        chooser._open_folder.assert_called_once_with(str(tmp_path / "beta"))
        chooser = _browsing(tmp_path / "beta", "..")
        SettingLongPathPopup._open_highlighted(chooser)
        chooser._open_folder.assert_called_once_with(str(tmp_path))

    def test_right_on_a_file_does_nothing(self, tmp_path: Path) -> None:
        chooser = _browsing(tmp_path, "notes.txt")
        SettingLongPathPopup._open_highlighted(chooser)
        chooser._open_folder.assert_not_called()

    def test_opening_a_folder_shows_it_in_the_box(
        self, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        chooser = _browsing(tmp_path, "alpha")
        SettingLongPathPopup._open_folder(chooser, str(tmp_path / "alpha"))
        chooser.ids.file_chooser.set_path.assert_called_once_with(str(tmp_path / "alpha"))
        assert chooser.ids.file_chooser.selection == []
        assert chooser.ids.path_input.text == str(tmp_path / "alpha")
        assert f'Folder chooser: in "{tmp_path / "alpha"}".' in loguru_sink


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
        SettingOptionsWithValue._set_option(setting, MagicMock())
    assert 'Setting "color_theme" set to "Duckburg".' in loguru_sink
