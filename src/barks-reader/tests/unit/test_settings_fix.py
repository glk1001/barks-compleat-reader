# ruff: noqa: SLF001
"""The folder chooser's remote keys, and the lines the settings popups log."""

from __future__ import annotations

import stat
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
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
from barks_reader.ui.settings_fix import (
    QuietFileSystem,
    SettingLongPathPopup,
    SettingOptionsWithValue,
)
from kivy.uix import filechooser

if TYPE_CHECKING:
    from collections.abc import Iterator


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

    def test_opened_is_logged_once_the_keys_are_bound(self, loguru_sink: list[str]) -> None:
        """A test waits on this line and presses Escape: before on_open, the panel took it."""
        chooser = _chooser()
        chooser.title = "Fantagraphics Directory"
        with patch.object(settings_fix, "Window") as window:
            SettingLongPathPopup._bind_keys(chooser)
        window.bind.assert_called_once_with(on_key_down=chooser._on_key_down)
        assert 'Folder chooser opened for "Fantagraphics Directory".' in loguru_sink

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


class TestQuietFileSystem:
    """A file Windows keeps locked is hidden without the error Kivy logs for it."""

    @staticmethod
    @contextmanager
    def _on_windows(stat_result: object) -> Iterator[None]:
        def fake_stat() -> object:
            if isinstance(stat_result, Exception):
                raise stat_result
            return stat_result

        with patch.multiple(
            settings_fix,
            sys=SimpleNamespace(platform="win32"),
            Path=lambda _fn: SimpleNamespace(stat=fake_stat),
        ):
            yield

    def test_a_locked_file_is_hidden_and_nothing_is_logged(self, loguru_sink: list[str]) -> None:
        with self._on_windows(PermissionError("in use")):
            assert QuietFileSystem().is_hidden("C:\\pagefile.sys") is True
        assert loguru_sink == []

    def test_a_file_marked_hidden_is_hidden_and_others_are_not(self) -> None:
        with self._on_windows(SimpleNamespace(st_file_attributes=stat.FILE_ATTRIBUTE_HIDDEN)):
            assert QuietFileSystem().is_hidden("C:\\secret") is True
        with self._on_windows(SimpleNamespace(st_file_attributes=stat.FILE_ATTRIBUTE_ARCHIVE)):
            assert QuietFileSystem().is_hidden("C:\\Comics") is False

    def test_elsewhere_a_dot_file_is_hidden(self) -> None:
        # Kivy's own check reads its platform, not ours, so it moves off Windows too.
        with (
            patch.object(settings_fix, "sys", SimpleNamespace(platform="linux")),
            patch.object(filechooser, "platform", "linux"),
        ):
            assert QuietFileSystem().is_hidden("/home/me/.config") is True
            assert QuietFileSystem().is_hidden("/home/me/Comics") is False


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


class TestFileChooserTouch:
    """A touch on the chooser may not move it to another folder; only set_path may."""

    def test_path_changes_are_held_off_only_while_a_touch_is_handled(self) -> None:
        chooser = settings_fix.CustomFileChooserListView()
        allowed_during: list[bool] = []

        def handle(_touch: object) -> bool:
            allowed_during.append(chooser._allow_path_change)
            return True

        with patch.object(settings_fix.FileChooserListView, "on_touch_down", side_effect=handle):
            assert chooser.on_touch_down(MagicMock()) is True

        assert allowed_during == [False]
        assert chooser._allow_path_change is True


class TestSettingsThemeKv:
    def test_it_is_loaded_once_themed(self) -> None:
        with (
            patch.object(settings_fix, "_settings_kv_installed", False),  # noqa: FBT003
            patch.object(settings_fix, "Builder") as builder,
        ):
            settings_fix.install_settings_theme_kv()
            settings_fix.install_settings_theme_kv()

        builder.load_string.assert_called_once()
        kv = builder.load_string.call_args.args[0]
        assert "__SEL_RGBA__" not in kv
        assert "__TITLE_BAR_H__" not in kv


def test_an_empty_folder_has_nothing_to_highlight(tmp_path: Path) -> None:
    chooser = _browsing(tmp_path, None)
    chooser.ids.file_chooser._items = []

    SettingLongPathPopup._move_highlight(chooser, 1)

    assert chooser.ids.file_chooser.selection == []
    chooser.ids.file_chooser.layout.ids.scrollview.scroll_to.assert_not_called()


class TestTypingAPath:
    """What the box holds, once typing pauses, moves the list to it, or to its folder."""

    @staticmethod
    def _typed(text: str) -> MagicMock:
        chooser = MagicMock()
        chooser._updating = False
        chooser._update_event = None
        with patch.object(settings_fix, "Clock") as clock:
            SettingLongPathPopup.update_file_chooser_path(chooser, text)
        do_update, delay = clock.schedule_once.call_args.args
        assert delay == 0.5  # noqa: PLR2004
        do_update(delay)
        return chooser

    def test_a_folder_is_shown_and_highlighted(self, tmp_path: Path) -> None:
        chooser = self._typed(str(tmp_path))
        chooser.ids.file_chooser.set_path.assert_called_once_with(str(tmp_path))
        assert chooser.ids.file_chooser.selection == [str(tmp_path)]
        assert chooser._updating is False

    def test_a_new_name_in_a_folder_shows_that_folder(self, tmp_path: Path) -> None:
        typed = tmp_path / "not yet made"
        chooser = self._typed(str(typed))
        chooser.ids.file_chooser.set_path.assert_called_once_with(str(tmp_path))
        assert chooser.ids.file_chooser.selection == [str(typed)]

    def test_a_path_nowhere_moves_nothing(self, tmp_path: Path) -> None:
        chooser = self._typed(str(tmp_path / "no" / "such" / "place"))
        chooser.ids.file_chooser.set_path.assert_not_called()

    def test_a_path_that_cannot_be_read_is_logged_and_left(self, loguru_sink: list[str]) -> None:
        chooser = MagicMock()
        chooser._updating = False
        chooser._update_event = None
        with (
            patch.object(settings_fix, "Clock") as clock,
            patch.object(settings_fix, "Path", side_effect=RuntimeError("no home")),
        ):
            SettingLongPathPopup.update_file_chooser_path(chooser, "~nobody/comics")
            clock.schedule_once.call_args.args[0](0.5)

        assert 'Invalid path in long path file chooser: "~nobody/comics"' in loguru_sink
        chooser.ids.file_chooser.set_path.assert_not_called()
        assert chooser._updating is False


class TestAltEscapeKeySetting:
    """A stored value that is not a keycode reads as unset, and the capture starts from none."""

    def test_a_value_not_a_keycode_shows_as_unset(self) -> None:
        setting = MagicMock()
        setting.value = "not a key"
        settings_fix.SettingAltEscapeKey._refresh_display_text(setting)
        assert setting.display_text == "<unset>"

    def test_the_capture_starts_from_no_key_for_such_a_value(self) -> None:
        setting = MagicMock()
        setting.value = "not a key"
        with patch.object(settings_fix, "AltEscapeCapturePopup") as popup:
            settings_fix.SettingAltEscapeKey._open_capture_popup(setting, MagicMock())
        assert popup.call_args.kwargs["current_keycode"] == 0
        popup.return_value.open.assert_called_once_with()
