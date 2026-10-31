# ruff: noqa: SLF001
"""The settings popups on the shared frame: their remote keys, and the lines they log."""

from __future__ import annotations

import stat
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.keys import KEY_DOWN, KEY_ENTER, KEY_ESCAPE, KEY_LEFT, KEY_RIGHT, KEY_UP
from barks_reader.core.popup_frame import PopupSize
from barks_reader.ui import popup_frame, settings_fix
from barks_reader.ui.action_bar_helpers import ACTION_BAR_SIZE_Y
from barks_reader.ui.settings_fix import (
    PinnedTitleSettings,
    PinnedTitleSettingsInterface,
    QuietFileSystem,
    SettingLongPathPopup,
    SettingNumberEntry,
    SettingNumberPopup,
    SettingOptionsPopup,
    SettingOptionsWithValue,
)
from kivy.lang import Builder
from kivy.uix import filechooser
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.settings import ContentPanel, SettingsPanel
from kivy.uix.widget import Widget

if TYPE_CHECKING:
    from collections.abc import Generator

    from barks_reader.ui.popup_frame import PopupFrame


def _stand_in(**attrs: object) -> Any:  # noqa: ANN401
    """Stand in for a widget as `self`: only the attributes the method reads."""
    return cast("Any", SimpleNamespace(**attrs))


def _chooser(*, box_focused: bool = False) -> MagicMock:
    """Stand in for an open chooser: its handlers need only its box and dismiss."""
    chooser = MagicMock()
    chooser.ids.path_input.focus = box_focused
    chooser.ids.path_input.text = "/library"
    return chooser


def _press(chooser: MagicMock, key: int) -> bool:
    return SettingLongPathPopup._handle_key(chooser, key)


class TestFolderChooserKeys:
    """Its browsing keys, asked before the frame's (``ui.popup_frame``)."""

    def test_escape_is_left_to_the_frame(self) -> None:
        chooser = _chooser()
        assert _press(chooser, KEY_ESCAPE) is False  # the frame's: it presses Cancel
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

    def test_while_the_box_types_nothing_is_taken(self) -> None:
        chooser = _chooser(box_focused=True)
        assert _press(chooser, KEY_DOWN) is False

    def test_other_keys_pass(self) -> None:
        assert _press(_chooser(), ord("a")) is False


class TestFolderChooserOnTheFrame:
    """The real popup: a large frame, its body the box and the folders, Select and Cancel."""

    KV_FILE = "test_settings_fix-chooser.kv"

    @pytest.fixture
    def chooser(self) -> Generator[SettingLongPathPopup]:
        Builder.load_string(settings_fix._themed_settings_kv(), filename=self.KV_FILE)
        try:
            with patch.object(popup_frame, "Window") as window:
                window.width, window.height = 1760, 1300
                yield SettingLongPathPopup(title="Fantagraphics Directory")
        finally:
            Builder.unload_file(self.KV_FILE)

    def test_it_is_large_with_select_and_cancel(self, chooser: SettingLongPathPopup) -> None:
        assert chooser.size_class is PopupSize.LARGE
        assert [b.text for b in chooser.button_widgets] == ["Select", "Cancel"]
        assert chooser.ids.path_input.parent is not None
        assert chooser.ids.file_chooser.parent is not None

    def test_select_keeps_the_box_path(self, chooser: SettingLongPathPopup) -> None:
        chooser.ids.path_input.text = "/library"
        with patch.object(SettingLongPathPopup, "select_path") as select:
            chooser.button_widgets[0].dispatch("on_release")
        select.assert_called_once_with("/library")

    def test_escape_cancels_it_unchanged(self, chooser: SettingLongPathPopup) -> None:
        with (
            patch.object(chooser, "dismiss") as dismiss,
            patch.object(SettingLongPathPopup, "select_path") as select,
        ):
            assert chooser._on_key_down(None, KEY_ESCAPE, 0, "", []) is True
        dismiss.assert_called_once_with()
        select.assert_not_called()

    def test_opened_is_logged_once_open(
        self, chooser: SettingLongPathPopup, loguru_sink: list[str]
    ) -> None:
        """A test waits on this line and presses Escape: the frame has the keys by then."""
        chooser.dispatch("on_open")
        assert 'Folder chooser opened for "Fantagraphics Directory".' in loguru_sink


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

    def test_a_folder_it_may_not_list_stays_shut(
        self, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        r"""Windows refuses a listing of C:\Documents and Settings; Kivy logs that as an error."""
        chooser = _browsing(tmp_path, "alpha")
        chooser.ids.path_input.text = str(tmp_path)
        with patch.object(settings_fix.os, "scandir", side_effect=PermissionError("denied")):
            SettingLongPathPopup._open_folder(chooser, str(tmp_path / "alpha"))
        chooser.ids.file_chooser.set_path.assert_not_called()
        assert chooser.ids.path_input.text == str(tmp_path)
        assert f'Folder chooser: cannot list "{tmp_path / "alpha"}".' in loguru_sink


class TestQuietFileSystem:
    """A file Windows keeps locked is hidden without the error Kivy logs for it."""

    @staticmethod
    @contextmanager
    def _on_windows(stat_result: object, target_result: object = None) -> Generator[None]:
        """Stand in for Windows: `stat_result` is the entry's own, `target_result` its target's."""

        def fake_lstat() -> object:
            if isinstance(stat_result, Exception):
                raise stat_result
            return stat_result

        with patch.multiple(
            settings_fix,
            sys=SimpleNamespace(platform="win32"),
            Path=lambda _fn: SimpleNamespace(lstat=fake_lstat, stat=lambda: target_result),
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

    def test_a_hidden_junction_is_hidden_though_its_target_is_not(self) -> None:
        r"""C:\Documents and Settings: listing it is refused, and Explorer hides it."""
        hidden = SimpleNamespace(st_file_attributes=stat.FILE_ATTRIBUTE_HIDDEN)
        shown = SimpleNamespace(st_file_attributes=stat.FILE_ATTRIBUTE_DIRECTORY)
        with self._on_windows(hidden, target_result=shown):
            assert QuietFileSystem().is_hidden("C:\\Documents and Settings") is True

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
    setting = _stand_in(key="color_theme", value="")
    with patch.object(settings_fix, "Clock"):
        SettingOptionsWithValue._pick_option(setting, "Duckburg")
    assert setting.value == "Duckburg"
    assert 'Setting "color_theme" set to "Duckburg".' in loguru_sink


_THEMES = ("Duckburg", "Calisota", "Klondike")


def _options_popup(current: str = "Calisota") -> tuple[SettingOptionsPopup, MagicMock]:
    on_pick = MagicMock()
    with patch.object(popup_frame, "Window") as window:
        window.width, window.height = 1760, 1300
        return SettingOptionsPopup("Color Theme", _THEMES, current, on_pick), on_pick


def _key(popup: PopupFrame, key: int) -> bool:
    return popup._on_key_down(None, key, 0, "", [])


class TestOptionsOnTheFrame:
    """A choice setting's list: medium, the current choice marked and focused, Cancel below."""

    def test_it_is_medium_with_the_choices_and_only_cancel(self) -> None:
        popup, _ = _options_popup()
        assert popup.size_class is PopupSize.MEDIUM
        assert [c.text for c in popup.choices] == list(_THEMES)
        assert [b.text for b in popup.button_widgets] == ["Cancel"]
        assert [c.bold for c in popup.choices] == [False, True, False]  # the current one
        assert popup.choice_idx == 1

    def test_down_and_return_pick_the_next_choice(self) -> None:
        popup, on_pick = _options_popup()
        with patch.object(popup, "dismiss") as dismiss:
            assert _key(popup, KEY_DOWN) is True
            assert _key(popup, KEY_ENTER) is True
        dismiss.assert_called_once_with()
        on_pick.assert_called_once_with("Klondike")

    def test_up_stops_at_the_top_without_moving_the_focus_again(
        self, loguru_sink: list[str]
    ) -> None:
        popup, _ = _options_popup(current="Duckburg")
        popup.dispatch("on_pre_open")
        focus_lines = len(loguru_sink)
        assert _key(popup, KEY_UP) is True
        assert popup.choice_idx == 0
        assert len(loguru_sink) == focus_lines  # no new "Nav focus on" line

    def test_down_past_the_last_choice_reaches_cancel_and_up_comes_back(self) -> None:
        popup, on_pick = _options_popup(current="Klondike")
        _key(popup, KEY_DOWN)
        assert popup.choice_idx is None
        assert _key(popup, KEY_DOWN) is True  # Cancel is the bottom
        with patch.object(popup, "dismiss") as dismiss:
            _key(popup, KEY_ENTER)  # the frame's: Return on Cancel
        dismiss.assert_called_once_with()
        on_pick.assert_not_called()
        _key(popup, KEY_UP)
        assert popup.choice_idx == len(_THEMES) - 1

    def test_left_and_right_stay_in_the_column(self) -> None:
        popup, _ = _options_popup()
        assert _key(popup, KEY_RIGHT) is True
        assert _key(popup, KEY_LEFT) is True
        assert popup.choice_idx == 1

    def test_escape_cancels_unchanged(self) -> None:
        popup, on_pick = _options_popup()
        with patch.object(popup, "dismiss") as dismiss:
            assert _key(popup, KEY_ESCAPE) is True
        dismiss.assert_called_once_with()
        on_pick.assert_not_called()

    def test_a_tapped_choice_is_picked(self) -> None:
        popup, on_pick = _options_popup()
        with patch.object(popup, "dismiss"):
            popup.choices[0].dispatch("on_release")
        on_pick.assert_called_once_with("Duckburg")

    def test_with_nothing_to_choose_the_focus_is_cancels(self) -> None:
        on_pick = MagicMock()
        with patch.object(popup_frame, "Window") as window:
            window.width, window.height = 1760, 1300
            popup = SettingOptionsPopup("Empty", (), "", on_pick)
        assert popup.choice_idx is None
        _key(popup, KEY_UP)  # nowhere to go
        assert popup.choice_idx is None
        with patch.object(popup, "dismiss") as dismiss:
            _key(popup, KEY_ENTER)
        dismiss.assert_called_once_with()

    def test_the_setting_opens_it_and_logs_it_open(self, loguru_sink: list[str]) -> None:
        setting = _stand_in(
            title="Color Theme", options=list(_THEMES), value="Klondike", key="color_theme"
        )
        setting._pick_option = MagicMock()
        with patch.object(settings_fix, "SettingOptionsPopup") as popup_class:
            SettingOptionsWithValue._create_popup(setting, MagicMock())
        popup_class.assert_called_once_with(
            "Color Theme", list(_THEMES), "Klondike", setting._pick_option
        )
        popup = popup_class.return_value
        assert setting.popup is popup
        popup.open.assert_called_once_with()
        on_open = popup.bind.call_args.kwargs["on_open"]
        on_open(popup)
        assert 'Setting options opened for "color_theme" (current "Klondike").' in loguru_sink


def _number_popup(value: str = "20") -> tuple[SettingNumberPopup, MagicMock]:
    on_enter = MagicMock()
    with patch.object(popup_frame, "Window") as window:
        window.width, window.height = 1760, 1300
        return SettingNumberPopup("Main Window Height", value, on_enter), on_enter


class TestNumberOnTheFrame:
    """A number setting's entry box: small, the box focused, OK and Cancel."""

    def test_it_is_small_with_the_box_and_ok_and_cancel(self) -> None:
        popup, _ = _number_popup()
        assert popup.size_class is PopupSize.SMALL
        assert [b.text for b in popup.button_widgets] == ["OK", "Cancel"]
        assert popup.textinput.text == "20"
        assert popup.textinput.input_filter == "int"
        assert _number_popup("1.5")[0].textinput.input_filter == "float"

    def test_the_box_has_the_keyboard_once_it_opens_and_return_there_takes_it(self) -> None:
        popup, on_enter = _number_popup()
        popup.dispatch("on_pre_open")
        try:
            assert popup.textinput.focus is True
            assert _key(popup, KEY_ENTER) is False  # the box's own Return
            popup.textinput.text = "640"
            with patch.object(popup, "dismiss") as dismiss:
                popup.textinput.dispatch("on_text_validate")
            dismiss.assert_called_once_with()
            on_enter.assert_called_once_with("640")
        finally:
            popup.textinput.focus = False

    def test_down_leaves_the_box_for_ok_and_up_goes_back(self) -> None:
        popup, on_enter = _number_popup()
        popup.dispatch("on_pre_open")
        try:
            assert _key(popup, KEY_DOWN) is True
            assert popup.textinput.focus is False
            with patch.object(popup, "dismiss"):
                _key(popup, KEY_ENTER)  # OK, focused
            on_enter.assert_called_once_with("20")
            assert _key(popup, KEY_UP) is True
            assert popup.textinput.focus is True
            assert _key(popup, KEY_UP) is True  # kept from the settings list behind
        finally:
            popup.textinput.focus = False

    def test_escape_cancels_unchanged(self) -> None:
        popup, on_enter = _number_popup()
        with patch.object(popup, "dismiss") as dismiss:
            assert _key(popup, KEY_ESCAPE) is True
        dismiss.assert_called_once_with()
        on_enter.assert_not_called()


class TestNumberSetting:
    def test_a_number_is_taken_as_the_value(self) -> None:
        setting = _stand_in(key="main_window_height", value="0")
        SettingNumberEntry._take_number(setting, "640")
        assert setting.value == "640"

    def test_a_float_setting_stays_a_float(self) -> None:
        setting = _stand_in(key="zoom", value="1.0")
        SettingNumberEntry._take_number(setting, "2")
        assert setting.value == "2.0"

    def test_what_is_not_a_number_is_refused_and_logged(self, loguru_sink: list[str]) -> None:
        setting = _stand_in(key="main_window_height", value="0")
        SettingNumberEntry._take_number(setting, "")
        assert setting.value == "0"
        assert 'Setting "main_window_height" left as it was: "" is not a number.' in loguru_sink

    def test_the_setting_opens_it_and_logs_it_open(self, loguru_sink: list[str]) -> None:
        setting = _stand_in(title="Main Window Height", value="0", key="main_window_height")
        setting._take_number = MagicMock()
        with patch.object(settings_fix, "SettingNumberPopup") as popup_class:
            SettingNumberEntry._create_popup(setting, MagicMock())
        popup_class.assert_called_once_with("Main Window Height", "0", setting._take_number)
        popup = popup_class.return_value
        assert (setting.popup, setting.textinput) == (popup, popup.textinput)
        popup.open.assert_called_once_with()
        popup.bind.call_args.kwargs["on_open"](popup)
        assert 'Setting number entry opened for "main_window_height" (current "0").' in loguru_sink


def test_an_option_picked_reaches_the_panel_which_saves_it_and_tells_the_app() -> None:
    """Kivy's panel writes the config and dispatches on_config_change: the live path."""
    setting = MagicMock(spec=SettingOptionsWithValue)
    setting.section, setting.key, setting.panel = "Barks Reader", "main_screen_layout", MagicMock()
    with patch.object(settings_fix.SettingOptions, "on_value") as kivy_on_value:
        SettingOptionsWithValue.on_value(setting, setting, "Single page")
    kivy_on_value.assert_called_once_with(setting, "Single page")
    setting._update_value_display.assert_called_once_with()


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

    def test_a_folder_opened_by_a_double_tap_is_put_back(self, tmp_path: Path) -> None:
        """Kivy opens a double-tapped folder inside the touch: the chooser stays put.

        The revert once called a setter Kivy's properties do not have, and the
        double tap crashed the app instead.
        """
        inside = tmp_path / "Inside"
        inside.mkdir()
        chooser = settings_fix.CustomFileChooserListView()
        chooser.set_path(str(tmp_path))

        def double_tap_on_the_folder(_touch: object) -> bool:
            chooser.open_entry(SimpleNamespace(path=str(inside), locked=False))
            return True

        with patch.object(
            settings_fix.FileChooserListView, "on_touch_down", side_effect=double_tap_on_the_folder
        ):
            assert chooser.on_touch_down(MagicMock()) is True

        assert chooser.path == str(tmp_path)
        assert chooser._real_path == str(tmp_path)
        assert chooser._allow_path_change is True

        chooser.set_path(str(inside))  # the route that may move it still does
        assert chooser.path == str(inside)


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


class TestPinnedTitleSettings:
    """The title stays put over the scrolling panel, and the scrollbar stays below it."""

    KV_FILE = "test_settings_fix-themed.kv"
    TITLE = "Barks Reader"

    @pytest.fixture
    def interface(self) -> Generator[PinnedTitleSettingsInterface]:
        Builder.load_string(settings_fix._themed_settings_kv(), filename=self.KV_FILE)
        try:
            interface = PinnedTitleSettingsInterface(
                size_hint=(None, None), size=(800, 600), pos=(0, 0)
            )
            panel = SettingsPanel(title=self.TITLE)
            panel.add_widget(Widget(size_hint_y=None, height=3000))
            interface.add_panel(panel, self.TITLE, panel.uid)
            # What a frame's layout pass would settle.
            panel.do_layout()
            interface.content.container.do_layout()
            interface.do_layout()
            yield interface
        finally:
            Builder.unload_file(self.KV_FILE)

    @staticmethod
    def _bar_top(pane: ContentPanel) -> float:
        return pane._handle_y_pos[1] + pane._handle_y_size[1]

    def test_the_title_is_a_bar_above_the_pane_not_a_row_in_it(
        self, interface: PinnedTitleSettingsInterface
    ) -> None:
        title_bar, pane = interface.ids.title_bar, interface.content
        assert title_bar.text == self.TITLE
        assert title_bar.height == ACTION_BAR_SIZE_Y
        assert title_bar.top == interface.top
        assert pane.top == title_bar.y
        assert pane.vbar[1] < 1  # there is something to scroll
        rows = pane.current_panel.children
        assert not [row for row in rows if getattr(row, "text", None) == self.TITLE]

    def test_scrolling_moves_neither_the_title_nor_the_bar_onto_it(
        self, interface: PinnedTitleSettingsInterface
    ) -> None:
        title_bar, pane = interface.ids.title_bar, interface.content
        title_y = title_bar.y
        assert self._bar_top(pane) == pytest.approx(pane.top)

        pane.scroll_y = 0

        assert title_bar.y == title_y
        assert self._bar_top(pane) < pane.top

    def test_a_later_panel_leaves_the_shown_one_and_its_title(
        self, interface: PinnedTitleSettingsInterface
    ) -> None:
        shown = interface.content.current_panel
        kivy_panel = SettingsPanel(title="Kivy")

        interface.add_panel(kivy_panel, "Kivy", kivy_panel.uid)

        assert interface.content.current_panel is shown
        assert interface.ids.title_bar.text == self.TITLE

    def test_the_settings_use_it_and_hear_its_close(self) -> None:
        settings = PinnedTitleSettings()
        closed = MagicMock()
        settings.bind(on_close=closed)

        settings.interface.dispatch("on_close")

        assert isinstance(settings.interface, PinnedTitleSettingsInterface)
        closed.assert_called_once()


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


class TestFolderChooserEdges:
    """The chooser's quieter paths: entries with no path, nothing highlighted, no setting."""

    def test_a_new_selection_marks_only_entries_that_have_a_path(self) -> None:
        chosen = SimpleNamespace(path="/library/alpha", is_selected=False)
        other = SimpleNamespace(path="/library/beta", is_selected=True)
        no_path = SimpleNamespace()  # the '../' row and the like
        chooser = _stand_in(_items=[chosen, no_path, other])

        settings_fix.CustomFileChooserListView._on_selection_changed(
            chooser, None, ["/library/alpha"]
        )

        assert (chosen.is_selected, other.is_selected) == (True, False)
        assert not hasattr(no_path, "is_selected")

    def test_with_nothing_highlighted_right_opens_nothing(self, tmp_path: Path) -> None:
        chooser = _browsing(tmp_path, None)
        SettingLongPathPopup._open_highlighted(chooser)
        chooser._open_folder.assert_not_called()

    @pytest.mark.parametrize(("has_setting", "path"), [(False, "/library"), (True, "")])
    def test_with_no_setting_or_no_path_nothing_is_set(self, has_setting: bool, path: str) -> None:
        chooser = _chooser()
        chooser.setting_widget = MagicMock() if has_setting else None
        with patch.object(settings_fix, "Clock") as clock:
            SettingLongPathPopup.select_path(chooser, path)
        clock.schedule_once.assert_not_called()
        chooser.dismiss.assert_called_once_with()


class TestLongPathPopupStart:
    """The popup opens on the setting's folder and highlights it once the files are listed."""

    @staticmethod
    def _open(tmp_path: Path, listed: list[str]) -> MagicMock:
        setting = _stand_in(value=str(tmp_path / "library"), title="Fantagraphics")
        with (
            patch.object(settings_fix, "SettingLongPathPopup") as popup_class,
            patch.object(settings_fix, "Clock") as clock,
        ):
            settings_fix.SettingLongPath._create_popup(setting, MagicMock())
        popup = popup_class.return_value
        popup.ids.file_chooser.files = listed
        (set_initial_selection, _delay), _ = clock.schedule_once.call_args
        set_initial_selection(0)
        return popup.ids.file_chooser

    def test_the_settings_folder_is_highlighted_when_listed(self, tmp_path: Path) -> None:
        library = str(tmp_path / "library")
        chooser = self._open(tmp_path, [str(tmp_path / "other"), library])
        chooser.set_initial_selection.assert_called_once_with([library])

    def test_a_folder_not_listed_leaves_nothing_highlighted(self, tmp_path: Path) -> None:
        chooser = self._open(tmp_path, [str(tmp_path / "other")])
        chooser.set_initial_selection.assert_not_called()


class TestOptionValueDisplay:
    """An option's value is shown in its row's value box, whatever else that box holds."""

    @staticmethod
    def _row(content_box: object, *, columns: int = 2) -> Any:  # noqa: ANN401
        main_box = SimpleNamespace(children=[content_box, *[Widget() for _ in range(columns - 1)]])
        return _stand_in(value="Duckburg", children=[main_box])

    def test_an_existing_label_past_other_widgets_gets_the_value(self) -> None:
        label = Label(text="old")
        content_box = BoxLayout()
        content_box.add_widget(label)
        content_box.add_widget(Widget())  # children are newest first: this one comes first

        SettingOptionsWithValue._update_value_display(self._row(content_box))

        assert label.text == "Duckburg"
        assert len(content_box.children) == 2  # noqa: PLR2004

    def test_a_row_without_a_value_box_is_left_alone(self) -> None:
        not_a_box = Widget()
        SettingOptionsWithValue._update_value_display(self._row(not_a_box))
        assert not_a_box.children == []

    def test_a_row_with_one_column_is_left_alone(self) -> None:
        content_box = BoxLayout()
        SettingOptionsWithValue._update_value_display(self._row(content_box, columns=1))
        assert content_box.children == []


class TestSettingsSavedWithoutAConfig:
    """A setting with no panel, or a panel with no config, takes the value and writes nothing."""

    def test_an_option_set_with_no_config_is_still_logged(self, loguru_sink: list[str]) -> None:
        setting = MagicMock(spec=SettingOptionsWithValue)
        setting.key, setting.value = "color_theme", "Duckburg"
        setting.panel = MagicMock(config=None)
        with patch.object(settings_fix, "Clock"):
            SettingOptionsWithValue._pick_option(setting, "Duckburg")
        assert 'Setting "color_theme" set to "Duckburg".' in loguru_sink

    @pytest.mark.parametrize("has_panel", [False, True])
    def test_a_captured_key_takes_effect_without_a_config(self, has_panel: bool) -> None:
        setting = _stand_in(value="", panel=MagicMock(config=None) if has_panel else None)
        with patch.object(settings_fix, "set_alt_escape_key") as set_key:
            settings_fix.SettingAltEscapeKey._set_keycode(setting, 96)
        assert setting.value == "96"
        set_key.assert_called_once_with(96)


def test_the_long_path_rows_title_column_shrinks_to_its_text() -> None:
    label = SimpleNamespace(size_hint_x=0.6, width=100)
    settings_fix.SettingLongPath.on_kv_post(_stand_in(ids=SimpleNamespace(labellayout=label)), None)
    assert label.size_hint_x is None
    assert label.width == settings_fix.dp(310)
