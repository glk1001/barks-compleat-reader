# ruff: noqa: SLF001

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, call, patch

import barks_reader.ui.main_screen
import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core import data_pack, window_minimum
from barks_reader.core.image_selector import ImageInfo
from barks_reader.core.keys import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_UP,
    set_alt_escape_key,
)
from barks_reader.core.main_layout import MainLayoutMode
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.ui.action_bar_helpers import ACTION_BAR_SIZE_Y
from barks_reader.ui.main_screen import MainScreen
from barks_reader.ui.main_screen_components import MainScreenComponents
from barks_reader.ui.screen_bundle import ScreenBundle
from barks_reader.ui.view_renderer import ImageThemesChange
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_dependencies() -> dict[str, Any]:
    screens = ScreenBundle(
        tree_view=MagicMock(),
        bottom_title_view=MagicMock(),
        fun_image_view=MagicMock(),
        main_index=MagicMock(),
        speech_index=MagicMock(),
        names_index=MagicMock(),
        locations_index=MagicMock(),
        statistics=MagicMock(),
        history=MagicMock(),
        search=MagicMock(),
    )
    return {
        "comics_database": MagicMock(),
        "reader_settings": MagicMock(),
        "reader_tree_events": MagicMock(),
        "filtered_title_lists": MagicMock(),
        "screen_switchers": MagicMock(),
        "screens": screens,
        "font_manager": MagicMock(),
        "user_error_handler": MagicMock(),
        "window_manager": MagicMock(),
    }


@pytest.fixture
def mock_components() -> MainScreenComponents:
    """Return a bundle of mock collaborators, injected in place of the real build."""
    return MainScreenComponents(
        random_title_images=MagicMock(),
        json_settings_manager=MagicMock(),
        special_fanta_overrides=MagicMock(),
        comic_reader_manager=MagicMock(),
        window_helper=MagicMock(),
        renderer=MagicMock(),
        nav_coord=MagicMock(),
        tree_view_manager=MagicMock(),
        app_initializer=MagicMock(),
        nav=MagicMock(),
    )


@pytest.fixture
def main_screen(
    mock_dependencies: dict[str, MagicMock],
    mock_components: MainScreenComponents,
) -> Generator[MainScreen]:
    # Patch Kivy Screen __init__ to avoid window creation.
    with patch.object(Screen, "__init__", autospec=True) as mock_screen_init:

        def side_effect(self, **kwargs) -> None:  # noqa: ANN001, ANN003
            from kivy.uix.widget import Widget  # noqa: PLC0415

            # Initialize Widget base to set up children list, properties, etc.
            Widget.__init__(self, **kwargs)

            self.ids = {
                "main_layout": MagicMock(),
                "book": MagicMock(),
                "action_bar": MagicMock(),
                "fullscreen_button": MagicMock(),
                "collapse_button": MagicMock(),
                "quit_button": MagicMock(),
                "go_back_button": MagicMock(),
                "change_pics_button": MagicMock(),
                "menu_button": MagicMock(),
                "icon_hitbox": MagicMock(),
            }

        mock_screen_init.side_effect = side_effect

        # The whole collaborator graph is injected as one bundle, so the only
        # other internals to patch are the Kivy glue the constructor touches.
        with (
            patch.object(barks_reader.ui.main_screen, "Screen"),
            patch.object(barks_reader.ui.main_screen, "Factory"),
            patch.object(barks_reader.ui.main_screen, "WindowManager"),
            patch.object(
                barks_reader.ui.main_screen,
                "build_main_screen_components",
                return_value=mock_components,
            ),
        ):
            screen = MainScreen(**mock_dependencies)
            screen.menu_dots_dropdown.parent = None  # closed, as the app starts
            yield screen


class TestMainScreen:
    def test_init(self, main_screen: MainScreen) -> None:
        assert main_screen._active is True
        assert main_screen._renderer is not None

    def test_on_key_down_ignored_when_not_current_screen(self, main_screen: MainScreen) -> None:
        # While another screen (e.g. the wiki reader with its search field) is on
        # top, the still-bound main-screen handler must yield the keyboard.
        main_screen.name = "main"
        main_screen.manager = MagicMock(current="wiki_reader")
        main_screen._settings_nav = None

        assert main_screen._on_key_down(None, ord("r"), 0, "r", []) is False
        main_screen._nav.handle_key.assert_not_called()

    def test_on_key_down_handled_when_current_screen(self, main_screen: MainScreen) -> None:
        main_screen.name = "main"
        main_screen.manager = MagicMock(current="main")
        main_screen._settings_nav = None
        main_screen._nav.handle_key.return_value = True

        assert main_screen._on_key_down(None, ord("r"), 0, "r", []) is True
        main_screen._nav.handle_key.assert_called_once_with(ord("r"))

    def test_on_key_down_yields_to_focused_text_input(
        self, main_screen: MainScreen, loguru_sink: list[str]
    ) -> None:
        # Editing a directory path in a settings popup: the focused TextInput must
        # receive cursor/editing keys, so the handler yields (returns False) and does
        # not drive tree/settings navigation - and says so, since nothing else would.
        main_screen.name = "main"
        main_screen.manager = MagicMock(current="main")
        main_screen._settings_nav = MagicMock()
        with patch.object(barks_reader.ui.main_screen, "_text_input_has_focus", return_value=True):
            assert main_screen._on_key_down(None, KEY_LEFT, 0, "", []) is False
        main_screen._nav.handle_key.assert_not_called()
        main_screen._settings_nav.handle_key.assert_not_called()
        assert f"Key {KEY_LEFT} left to the focused text input." in loguru_sink

    def test_on_key_down_escape_not_yielded_to_text_input(self, main_screen: MainScreen) -> None:
        # Escape must still close the settings/popup even while a text field is focused.
        main_screen.name = "main"
        main_screen.manager = MagicMock(current="main")
        main_screen._settings_nav = MagicMock()
        main_screen._settings_nav.handle_key.return_value = False
        with (
            patch.object(barks_reader.ui.main_screen, "_text_input_has_focus", return_value=True),
            patch.object(main_screen, "_focus_settings_x") as to_the_x,
        ):
            assert main_screen._on_key_down(None, KEY_ESCAPE, 0, "", []) is True
        to_the_x.assert_called_once_with(focused=True)

    def test_alt_escape_letter_reaches_a_focused_text_input(self, main_screen: MainScreen) -> None:
        """The alternate Escape is an ordinary letter on a keyboard.

        With it set to "r" (the default 114), typing "airline" into a search box used
        to swallow the "r" and exit the box instead. A press carrying a character is
        text, so the handler must yield to the field.
        """
        main_screen.name = "main"
        main_screen.manager = MagicMock(current="main")
        main_screen._settings_nav = MagicMock()
        set_alt_escape_key(ord("r"))
        try:
            with patch.object(
                barks_reader.ui.main_screen, "_text_input_has_focus", return_value=True
            ):
                assert main_screen._on_key_down(None, ord("r"), 0, "r", []) is False
        finally:
            set_alt_escape_key(0)
        main_screen._nav.handle_key.assert_not_called()
        main_screen._settings_nav.handle_key.assert_not_called()

    def test_alt_escape_without_a_character_still_escapes_a_text_input(
        self, main_screen: MainScreen
    ) -> None:
        """A remote sends the bare keycode with no character, so it must still escape."""
        main_screen.name = "main"
        main_screen.manager = MagicMock(current="main")
        main_screen._settings_nav = MagicMock()
        main_screen._settings_nav.handle_key.return_value = False
        set_alt_escape_key(ord("r"))
        try:
            with (
                patch.object(
                    barks_reader.ui.main_screen, "_text_input_has_focus", return_value=True
                ),
                patch.object(main_screen, "_focus_settings_x") as mock_close,
            ):
                assert main_screen._on_key_down(None, ord("r"), 0, "", []) is True
        finally:
            set_alt_escape_key(0)
        mock_close.assert_called_once()

    def test_text_input_has_focus_reflects_keyboard_target(self) -> None:
        from barks_reader.ui.main_screen import _text_input_has_focus  # noqa: PLC0415
        from kivy.uix.textinput import TextInput  # noqa: PLC0415

        # Focusing a real TextInput takes the real Window's keyboard; left focused, it
        # makes MainScreen yield every key for the rest of the session (a shuffled
        # overnight run failed test_on_key_down_handled_when_current_screen on it).
        focused = TextInput()
        focused.focus = True
        unfocused = TextInput()
        unfocused.focus = False

        try:
            with patch.object(barks_reader.ui.main_screen, "Window") as mock_window:
                mock_window._system_keyboard.target = focused
                assert _text_input_has_focus() is True

                mock_window._system_keyboard.target = unfocused
                assert _text_input_has_focus() is False

                mock_window._system_keyboard.target = None
                assert _text_input_has_focus() is False
        finally:
            focused.focus = False

    def test_text_input_has_focus_sees_the_virtual_keyboard_too(self) -> None:
        """The guard that yields keys to a focused box must look past the system keyboard.

        With the on-screen keyboard docked, Kivy hands the box that keyboard and the
        system keyboard's target stays None.
        """
        from types import SimpleNamespace  # noqa: PLC0415

        from barks_reader.ui.main_screen import _text_input_has_focus  # noqa: PLC0415
        from kivy.uix.textinput import TextInput  # noqa: PLC0415

        box = TextInput()
        box.focus = True
        system = SimpleNamespace(target=None)
        docked = SimpleNamespace(target=box)
        try:
            with patch.object(barks_reader.ui.main_screen, "Window") as mock_window:
                mock_window._keyboards = {"system": system, "single": docked}
                mock_window._system_keyboard = system
                assert _text_input_has_focus() is True

                box.focus = False
                assert _text_input_has_focus() is False
        finally:
            box.focus = False  # the real Window's keyboard, as above

    def test_a_keyboard_request_puts_the_key_handler_back_in_front(self) -> None:
        """Kivy binds a docked keyboard's handler afresh per request; ours must follow it."""
        from barks_reader.ui.main_screen import _install_keyboard_request_hook  # noqa: PLC0415

        class _Window:
            request_keyboard = MagicMock(return_value="keyboard")

        window = _Window()
        first, second = MagicMock(), MagicMock()
        _install_keyboard_request_hook(window, first)
        _install_keyboard_request_hook(window, second)  # once per window: only the target changes

        assert window.request_keyboard("callback", "target") == "keyboard"
        _Window.request_keyboard.assert_called_once_with("callback", "target")
        first.assert_not_called()
        second.assert_called_once()

    def test_putting_the_key_handler_first_rebinds_it_while_active(
        self, main_screen: MainScreen
    ) -> None:
        with patch.object(barks_reader.ui.main_screen, "Window") as window:
            main_screen._put_key_handler_first()
            assert window.mock_calls == [
                call.unbind(on_key_down=main_screen._on_key_down),
                call.bind(on_key_down=main_screen._on_key_down),
            ]
            window.reset_mock()
            main_screen._active = False
            main_screen._put_key_handler_first()
            assert window.mock_calls == []

    def test_on_action_bar_go_back(self, main_screen: MainScreen) -> None:
        with patch.object(barks_reader.ui.main_screen.Clock, "schedule_once") as mock_schedule:
            main_screen.on_action_bar_go_back()

        main_screen._tree_view_manager.go_back_to_previous_node.assert_called_once()
        mock_schedule.assert_called_once()

    @pytest.mark.parametrize("keyboard", [True, False])
    def test_on_action_bar_go_back_forwards_keyboard_signal(
        self, main_screen: MainScreen, keyboard: bool
    ) -> None:
        # The menu button's on_release runs after menu mode is already torn down, so
        # the decision reads the activation-time flag, not the live _menu_mode: True
        # (keyboard) restores focus on the revealed screen, False (mouse) does not.
        main_screen._menu_action_by_keyboard = keyboard
        with patch.object(barks_reader.ui.main_screen.Clock, "schedule_once") as mock_schedule:
            main_screen.on_action_bar_go_back()

        scheduled_callback = mock_schedule.call_args.args[0]
        scheduled_callback(0)
        main_screen._nav.enter_bottom_focus_if_index_visible.assert_called_once_with(keyboard)

    def test_on_action_bar_collapse(self, main_screen: MainScreen) -> None:
        main_screen.on_action_bar_collapse()
        main_screen._tree_view_manager.deselect_and_close_open_nodes.assert_called_once()

    def test_on_action_bar_change_view_images(self, main_screen: MainScreen) -> None:
        main_screen._random_title_images.get_random_reader_app_icon_file.return_value = "icon.png"

        main_screen.on_action_bar_change_view_images()

        assert main_screen.app_icon_filepath == "icon.png"
        main_screen._renderer.refresh.assert_called_once()

    def test_on_view_state_changed(self, main_screen: MainScreen) -> None:
        # Initial state -> disabled
        main_screen._on_view_state_changed(ViewStates.INITIAL)
        assert main_screen.ids.collapse_button.disabled is True

        # Other state -> enabled
        main_screen._on_view_state_changed(ViewStates.ON_TITLE_NODE)
        assert main_screen.ids.collapse_button.disabled is False

    def test_on_title_portal_image_pressed_no_title(self, main_screen: MainScreen) -> None:
        main_screen._nav_coord.current_fanta_info = None
        main_screen.on_title_portal_image_pressed()
        main_screen._nav_coord.read_comic.assert_not_called()

    def test_on_title_portal_image_pressed_delegates_to_coordinator(
        self, main_screen: MainScreen
    ) -> None:
        main_screen._nav_coord.current_fanta_info = MagicMock()
        main_screen._app_initializer.is_fanta_volumes_state_ok.return_value = (True, "")
        main_screen._nav_coord.read_comic.return_value = True

        main_screen.on_title_portal_image_pressed()

        main_screen._nav.save_focus_before_reader.assert_called_once()
        main_screen._nav_coord.read_comic.assert_called_once()

    def test_on_comic_closed_delegates_to_coordinator(self, main_screen: MainScreen) -> None:
        main_screen._active = False

        main_screen.on_comic_closed()

        assert main_screen._active is True
        main_screen._nav.restore_focus_after_reader.assert_called_once()
        main_screen._nav_coord.on_comic_closed.assert_called_once()

    def test_on_document_reader_closed_delegates_to_coordinator(
        self, main_screen: MainScreen
    ) -> None:
        main_screen._active = False

        main_screen.on_document_reader_closed()

        assert main_screen._active is True
        main_screen._nav_coord.on_document_closed.assert_called_once()


class TestMenuDotsOffScreen:
    def test_enter_off_screen_stays_in_menu_mode(self, main_screen: MainScreen) -> None:
        """Enter on the menu button mid-fade opens nothing; the menu keeps its focus."""
        with (
            patch.object(main_screen, "open_menu_dots", return_value=False),
            patch.object(main_screen, "_clear_menu_focus"),
            patch.object(main_screen, "_enter_dropdown_nav") as enter_dropdown_nav,
            patch.object(main_screen, "_update_menu_focus") as update_menu_focus,
        ):
            main_screen._open_menu_dots_for_keyboard()
        enter_dropdown_nav.assert_not_called()
        update_menu_focus.assert_called_once()


class TestMenuDotsOpenedByMouse:
    """The keys take over a dots menu the mouse opened, instead of opening it again."""

    @staticmethod
    def _open_by_mouse(main_screen: MainScreen) -> None:
        main_screen.manager = MagicMock()
        main_screen.manager.current = main_screen.name
        main_screen.menu_dots_dropdown.parent = MagicMock(name="window")
        main_screen._dropdown_nav_mode = False

    def test_escape_closes_it(self, main_screen: MainScreen) -> None:
        self._open_by_mouse(main_screen)
        with patch.object(main_screen, "_enter_menu_mode") as enter_menu:
            assert main_screen._on_key_down(None, KEY_ESCAPE, 0, "", []) is True
        main_screen.menu_dots_dropdown.dismiss.assert_called_once_with()
        enter_menu.assert_not_called()

    def test_another_key_lands_the_ring_on_its_first_item(
        self, main_screen: MainScreen, loguru_sink: list[str]
    ) -> None:
        self._open_by_mouse(main_screen)
        with (
            patch.object(main_screen, "_update_menu_focus"),
            patch.object(main_screen, "_clear_menu_focus"),
            patch.object(main_screen, "_enter_dropdown_nav") as enter_dropdown,
            patch.object(main_screen, "_handle_menu_key") as handle_menu,
        ):
            assert main_screen._on_key_down(None, KEY_DOWN, 0, "", []) is True
        assert main_screen._menu_mode is True
        assert main_screen._menu_action_by_keyboard is True
        assert (
            main_screen._menu_buttons[main_screen._focused_btn_idx]
            is main_screen.ids["menu_button"]
        )
        enter_dropdown.assert_called_once_with(initial_idx=0)
        handle_menu.assert_not_called()  # the first key only lands the ring
        main_screen.menu_dots_dropdown.dismiss.assert_not_called()
        assert "Keys taken onto the open menu." in loguru_sink

    def test_a_closed_menu_leaves_the_keys_to_the_screen(self, main_screen: MainScreen) -> None:
        self._open_by_mouse(main_screen)
        main_screen.menu_dots_dropdown.parent = None
        with patch.object(main_screen._nav, "handle_key", return_value=True) as handle:
            main_screen._on_key_down(None, KEY_DOWN, 0, "", [])
        handle.assert_called_once_with(KEY_DOWN)
        main_screen.menu_dots_dropdown.dismiss.assert_not_called()

    def test_a_menu_the_keys_opened_is_theirs_already(self, main_screen: MainScreen) -> None:
        self._open_by_mouse(main_screen)
        main_screen._dropdown_nav_mode = True
        with patch.object(main_screen._nav, "handle_key", return_value=True) as handle:
            main_screen._on_key_down(None, KEY_DOWN, 0, "", [])
        handle.assert_called_once_with(KEY_DOWN)


class TestMainScreenMarkers:
    """Quit and settings-close log lines, the oracles the GUI path tests wait on."""

    def test_quit_without_confirmation_closes_and_logs(
        self, main_screen: MainScreen, loguru_sink: list[str]
    ) -> None:
        main_screen._reader_settings.confirm_quit = False
        with patch.object(barks_reader.ui.main_screen, "App") as app_cls:
            main_screen.request_quit()
        app_cls.get_running_app.return_value.close_app.assert_called_once()
        assert "Quit requested: no confirmation needed." in loguru_sink

    def test_quit_with_confirmation_asks_and_logs(
        self, main_screen: MainScreen, loguru_sink: list[str]
    ) -> None:
        main_screen._reader_settings.confirm_quit = True
        with (
            patch.object(barks_reader.ui.main_screen, "App") as app_cls,
            patch.object(barks_reader.ui.main_screen, "open_confirm_popup") as ask,
        ):
            main_screen.request_quit()
        ask.assert_called_once()
        app_cls.get_running_app.return_value.close_app.assert_not_called()
        assert "Quit requested: asking for confirmation." in loguru_sink

    def test_both_ways_out_of_settings_log_the_close(
        self, main_screen: MainScreen, loguru_sink: list[str]
    ) -> None:
        main_screen._settings_nav = None
        main_screen._settings_close_button = None
        main_screen._on_settings_closed()
        with patch.object(barks_reader.ui.main_screen, "App"):
            main_screen._close_settings()
        assert loguru_sink.count("Settings closed.") == len(("close button", "Escape"))


class TestKeyLeavesSingleLineBox:
    """The remote's way out of a one-line box: Down, or Right at the text's end."""

    @staticmethod
    def _leaves(key: int, *, text: str = "vac", cursor: int = 3, multiline: bool = False) -> bool:
        box = MagicMock(multiline=multiline, text=text)
        box.cursor_index.return_value = cursor
        with patch.object(barks_reader.ui.main_screen, "_focused_text_input", return_value=box):
            return barks_reader.ui.main_screen._key_leaves_single_line_box(key)

    def test_down_leaves(self) -> None:
        assert self._leaves(KEY_DOWN) is True

    def test_right_leaves_only_at_the_end(self) -> None:
        assert self._leaves(KEY_RIGHT, cursor=3) is True
        assert self._leaves(KEY_RIGHT, cursor=1) is False

    def test_up_and_letters_stay_with_the_box(self) -> None:
        assert self._leaves(KEY_UP) is False
        assert self._leaves(ord("a")) is False

    def test_a_multi_line_box_keeps_them(self) -> None:
        assert self._leaves(KEY_DOWN, multiline=True) is False

    def test_no_box_no_leaving(self) -> None:
        with patch.object(barks_reader.ui.main_screen, "_focused_text_input", return_value=None):
            assert barks_reader.ui.main_screen._key_leaves_single_line_box(KEY_DOWN) is False


class TestMainScreenEdges:
    """The paths no GUI run reaches: repeated states, refusals and bad input."""

    def test_the_same_active_state_again_changes_nothing(
        self, main_screen: MainScreen, loguru_sink: list[str]
    ) -> None:
        assert main_screen._active is True
        with patch.object(barks_reader.ui.main_screen, "Window") as window:
            main_screen._is_active(active=True)

        assert window.mock_calls == []
        assert not any("MainScreen active changed" in line for line in loguru_sink)

    @pytest.mark.parametrize(("inside", "exits"), [(False, True), (True, False)])
    def test_a_touch_outside_the_bottom_view_leaves_its_focus(
        self, main_screen: MainScreen, inside: bool, exits: bool
    ) -> None:
        main_screen._nav.is_in_bottom_focus = True
        main_screen._bottom_base_view_screen.collide_point.return_value = inside
        touch = MagicMock(pos=(10, 20))

        main_screen.on_touch_down(touch)

        main_screen._bottom_base_view_screen.collide_point.assert_called_once_with(10, 20)
        assert main_screen._nav.exit_bottom_focus.called is exits

    def test_an_open_modal_popup_keeps_the_keys(self, main_screen: MainScreen) -> None:
        """A popup's own key handler binds later, so this one must yield to it."""
        main_screen.name = "main"
        main_screen.manager = MagicMock(current="main")
        main_screen._settings_nav = None
        with (
            patch.object(barks_reader.ui.main_screen, "_text_input_has_focus", return_value=False),
            patch.object(barks_reader.ui.main_screen, "_modal_popup_is_open", return_value=True),
        ):
            assert main_screen._on_key_down(None, KEY_DOWN, 0, "", []) is False

        main_screen._nav.handle_key.assert_not_called()

    def test_settings_already_on_the_window_are_not_added_again(
        self, main_screen: MainScreen
    ) -> None:
        settings = MagicMock()
        app_window = MagicMock(children=[settings])

        assert main_screen.display_settings(app_window, settings) is False

        app_window.add_widget.assert_not_called()
        assert main_screen._settings_nav is None

    def test_an_unknown_menu_option_is_refused(self, main_screen: MainScreen) -> None:
        with pytest.raises(ValueError, match=r"Invalid menu option: 'nope'\."):
            main_screen.on_action_bar_menu_dots_selected(MagicMock(), "nope")

    def test_force_fullscreen_goes_to_the_window_helper(self, main_screen: MainScreen) -> None:
        main_screen.force_fullscreen()
        main_screen._window_helper.force_fullscreen.assert_called_once_with()

    def test_an_app_icon_naming_no_title_is_refused(self, main_screen: MainScreen) -> None:
        main_screen.app_icon_filepath = "/icons/Not A Barks Title.png"
        with (
            patch.object(
                barks_reader.ui.main_screen,
                "get_title_str_from_reader_icon_file",
                return_value="Not A Barks Title",
            ),
            pytest.raises(ValueError, match=r'Invalid title string: "Not A Barks Title"'),
        ):
            main_screen.goto_reader_icon_title()

        main_screen._nav_coord.navigate_to_chrono_title.assert_not_called()

    def test_the_portal_opens_nothing_while_the_volumes_are_not_ready(
        self, main_screen: MainScreen, loguru_sink: list[str]
    ) -> None:
        main_screen._nav_coord.current_fanta_info = MagicMock()
        main_screen._app_initializer.is_fanta_volumes_state_ok.return_value = (
            False,
            "the volumes are still loading",
        )

        main_screen.on_title_portal_image_pressed()

        main_screen._nav_coord.read_comic.assert_not_called()
        main_screen._nav.save_focus_before_reader.assert_not_called()
        assert (
            "Title portal image pressed pressed. But the volumes are still loading." in loguru_sink
        )

    def test_the_wiki_page_button_with_no_title_opens_nothing(
        self, main_screen: MainScreen, loguru_sink: list[str]
    ) -> None:
        main_screen._nav_coord.current_fanta_info = None

        main_screen.on_wiki_page_button_pressed()

        main_screen._nav_coord.open_wiki_page_for_title.assert_not_called()
        main_screen._nav.save_focus_before_reader.assert_not_called()
        assert "Wiki page button pressed. But no title selected." in loguru_sink


class TestMainScreenQuietPaths:
    """Main-screen paths that change nothing visible: a window too small, a screen not shown."""

    def test_the_menu_dropdown_is_dismissed(self, main_screen: MainScreen) -> None:
        main_screen.menu_dots_dropdown = MagicMock()
        main_screen._dismiss_dropdown()
        main_screen.menu_dots_dropdown.dismiss.assert_called_once_with()

    def test_a_window_too_small_for_a_page_leaves_the_screen_its_size(
        self, main_screen: MainScreen
    ) -> None:
        """A minimized window on Windows reports a size of nothing."""
        main_screen.size = (782, 1225)
        with (
            patch.object(barks_reader.ui.main_screen, "Window"),
            patch.object(barks_reader.ui.main_screen, "get_win_dimensions", return_value=(0, 0)),
        ):
            main_screen._is_active(active=False)
        assert tuple(main_screen.size) == (782, 1225)

    def test_a_touch_while_the_screen_is_not_shown_goes_straight_to_its_widgets(
        self, main_screen: MainScreen
    ) -> None:
        main_screen._active = False
        main_screen._nav.is_in_bottom_focus = True
        with (
            patch.object(main_screen, "_clear_menu_on_touch") as clear_menu,
            patch.object(Screen, "on_touch_down", return_value=True) as widgets_press,
        ):
            assert main_screen.on_touch_down(MagicMock(pos=(1, 2))) is True
        clear_menu.assert_not_called()
        main_screen._nav.exit_bottom_focus.assert_not_called()
        widgets_press.assert_called_once()

    def test_a_settings_close_button_already_off_the_window_is_just_forgotten(
        self, main_screen: MainScreen
    ) -> None:
        button = MagicMock()
        button.parent = None  # not MagicMock(parent=None): that names the mock's own parent
        main_screen._settings_close_button = button
        main_screen._remove_settings_close_button()
        assert main_screen._settings_close_button is None

    @pytest.mark.parametrize("active", [True, False])
    def test_a_theme_row_turned_on_or_off_adds_or_drops_its_theme(
        self, main_screen: MainScreen, active: bool
    ) -> None:
        row = MagicMock(active=active)
        main_screen.on_checkbox_row_changed(row)
        expected = ImageThemesChange.ADD if active else ImageThemesChange.DISCARD
        main_screen._renderer.bottom_view_alter_fun_image_themes.assert_called_once_with(
            row.theme_enum, expected
        )

    def test_a_comic_that_does_not_open_leaves_the_first_use_as_it_is(
        self, main_screen: MainScreen
    ) -> None:
        main_screen._nav_coord.current_fanta_info = MagicMock()
        main_screen._app_initializer.is_fanta_volumes_state_ok.return_value = (True, "")
        main_screen._nav_coord.read_comic.return_value = False
        with patch.object(main_screen, "_set_no_longer_first_use") as no_longer_first_use:
            main_screen.on_title_portal_image_pressed()
        main_screen._nav_coord.read_comic.assert_called_once_with()
        no_longer_first_use.assert_not_called()


class TestQuitFocus:
    def test_after_a_stay_the_menu_reopens_on_go_back_not_the_x(
        self, main_screen: MainScreen
    ) -> None:
        """Escape, Enter, Enter must not quit after the quit popup was answered "Stay"."""
        main_screen._reader_settings.confirm_quit = True
        quit_idx = main_screen._menu_buttons.index(main_screen.ids.quit_button)
        main_screen._last_used_btn_idx = quit_idx  # as the X's keyboard activation leaves it
        with (
            patch.object(barks_reader.ui.main_screen, "App"),
            patch.object(barks_reader.ui.main_screen, "open_confirm_popup"),
        ):
            main_screen.request_quit()
        with patch.object(main_screen, "_update_menu_focus"):
            main_screen._enter_menu_mode()
        focused = main_screen._menu_buttons[main_screen._focused_btn_idx]
        assert focused is main_screen.ids.go_back_button


class TestDataPackUpdate:
    """Newer data packs beside the executable are offered at boot and from the dots menu."""

    @staticmethod
    def _check(status: data_pack.UpdateStatus) -> data_pack.UpdateCheck:
        available = data_pack.DataPackInfo(
            6, "data-v6", datetime(2026, 10, 29, tzinfo=UTC), "main-pc", {}
        )
        packs = (available, available) if status is data_pack.UpdateStatus.UPDATE_AVAILABLE else ()
        return data_pack.UpdateCheck(status, Path("/exe"), None, packs)

    @pytest.fixture
    def popups(self) -> Generator[tuple[MagicMock, MagicMock]]:
        with (
            patch.object(barks_reader.ui.main_screen, "open_confirm_popup") as confirm,
            patch.object(barks_reader.ui.main_screen, "open_message_popup") as message,
            patch.object(
                barks_reader.ui.main_screen.data_pack, "read_installed", return_value=None
            ),
        ):
            yield confirm, message

    def test_at_boot_newer_packs_are_offered(
        self, main_screen: MainScreen, popups: tuple[MagicMock, MagicMock], loguru_sink: list[str]
    ) -> None:
        confirm, message = popups
        check = self._check(data_pack.UpdateStatus.UPDATE_AVAILABLE)
        with patch.object(barks_reader.ui.main_screen.data_pack, "find_update", return_value=check):
            main_screen._on_tree_build_finished()
        confirm.assert_called_once()
        assert confirm.call_args.kwargs["title"] == "Update Data Pack"
        assert confirm.call_args.kwargs["text"].startswith("Data pack 6 (29 Oct 2026) is beside")
        assert confirm.call_args.kwargs["on_cancel"] is None  # no menu to go back to at boot
        message.assert_not_called()
        # The path as the OS spells it: "\exe" on Windows.
        assert f'Data pack check: update available (looked in "{check.pack_dir}").' in loguru_sink
        assert "Data pack update offered: Data pack 6 (29 Oct 2026)." in loguru_sink

    @pytest.mark.parametrize(
        "status",
        [s for s in data_pack.UpdateStatus if s is not data_pack.UpdateStatus.UPDATE_AVAILABLE],
    )
    def test_at_boot_nothing_to_install_shows_nothing(
        self,
        main_screen: MainScreen,
        popups: tuple[MagicMock, MagicMock],
        status: data_pack.UpdateStatus,
        loguru_sink: list[str],
    ) -> None:
        confirm, message = popups
        with patch.object(
            barks_reader.ui.main_screen.data_pack, "find_update", return_value=self._check(status)
        ):
            main_screen.check_for_data_pack_update(at_boot=True)
        confirm.assert_not_called()
        message.assert_not_called()
        assert any(line.startswith(f"Data pack check: {status.value}") for line in loguru_sink)

    def test_from_the_menu_nothing_to_install_says_why(
        self, main_screen: MainScreen, popups: tuple[MagicMock, MagicMock]
    ) -> None:
        confirm, message = popups
        main_screen._menu_action_by_keyboard = True
        check = self._check(data_pack.UpdateStatus.PACKS_MISSING)
        with patch.object(barks_reader.ui.main_screen.data_pack, "find_update", return_value=check):
            main_screen.on_action_bar_menu_dots_selected(MagicMock(), "update-data-pack")
        confirm.assert_not_called()
        message.assert_called_once()
        assert message.call_args.kwargs["title"] == "Update Data Pack"
        assert message.call_args.kwargs["text"] == check.no_update_message()
        assert message.call_args.kwargs["on_cancel"] == main_screen._enter_menu_mode

    def test_from_the_menu_by_mouse_the_popup_leaves_the_keys_alone(
        self, main_screen: MainScreen, popups: tuple[MagicMock, MagicMock]
    ) -> None:
        confirm, _message = popups
        main_screen._menu_action_by_keyboard = False
        check = self._check(data_pack.UpdateStatus.UPDATE_AVAILABLE)
        with patch.object(barks_reader.ui.main_screen.data_pack, "find_update", return_value=check):
            main_screen.check_for_data_pack_update(at_boot=False)
        assert confirm.call_args.kwargs["on_cancel"] is None

    def test_accepting_spawns_the_installer_then_closes_the_reader(
        self, main_screen: MainScreen, popups: tuple[MagicMock, MagicMock], loguru_sink: list[str]
    ) -> None:
        confirm, _message = popups
        check = self._check(data_pack.UpdateStatus.UPDATE_AVAILABLE)
        order: list[str] = []
        with (
            patch.object(barks_reader.ui.main_screen.data_pack, "find_update", return_value=check),
            patch.object(barks_reader.ui.main_screen, "App") as app_cls,
            patch.object(
                barks_reader.ui.main_screen.data_pack,
                "spawn_detached",
                side_effect=lambda argv: order.append(f"spawn {argv[-1]}"),
            ),
            patch.object(barks_reader.ui.main_screen, "IS_COMPILED", new=True),
            patch.object(sys, "argv", ["/exe/barks-reader"]),
        ):
            app_cls.get_running_app.return_value.close_app.side_effect = lambda: order.append(
                "close"
            )
            main_screen.check_for_data_pack_update(at_boot=True)
            confirm.call_args.kwargs["on_ok"]()
        assert order == ["spawn --install-data-pack", "close"]
        assert "Data pack installer started for Data pack 6 (29 Oct 2026); closing the reader." in (
            loguru_sink
        )


class TestSmallScreenWarning:
    """A screen smaller than the reader is laid out for is warned about, once per size."""

    @pytest.fixture(autouse=True)
    def _no_env_suppression(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(window_minimum.NO_SCREEN_WARNING_ENV_VAR, raising=False)

    def test_a_small_screen_is_warned_about_and_remembered(
        self,
        main_screen: MainScreen,
        mock_components: MainScreenComponents,
        loguru_sink: list[str],
    ) -> None:
        settings = cast("MagicMock", mock_components.json_settings_manager)
        settings.is_screen_size_warned.return_value = False
        with patch.object(barks_reader.ui.main_screen, "open_message_popup") as popup:
            main_screen.warn_if_screen_too_small(1366, 768)
        popup.assert_called_once()
        assert "1366 x 768" in popup.call_args.kwargs["text"]
        settings.save_screen_size_warned.assert_called_once_with("1366x768")
        assert "Screen 1366x768 is smaller than the reader is laid out for: warned." in loguru_sink

    def test_a_screen_size_warned_before_is_not_warned_again(
        self,
        main_screen: MainScreen,
        mock_components: MainScreenComponents,
        loguru_sink: list[str],
    ) -> None:
        settings = cast("MagicMock", mock_components.json_settings_manager)
        settings.is_screen_size_warned.return_value = True
        with patch.object(barks_reader.ui.main_screen, "open_message_popup") as popup:
            main_screen.warn_if_screen_too_small(1366, 768)
        popup.assert_not_called()
        assert (
            "Screen 1366x768 is smaller than the reader is laid out for: warned before."
            in loguru_sink
        )

    def test_a_big_enough_screen_is_not_warned_about(
        self, main_screen: MainScreen, mock_components: MainScreenComponents
    ) -> None:
        with patch.object(barks_reader.ui.main_screen, "open_message_popup") as popup:
            main_screen.warn_if_screen_too_small(1920, 1080)
        popup.assert_not_called()
        cast(
            "MagicMock", mock_components.json_settings_manager
        ).save_screen_size_warned.assert_not_called()

    def test_the_environment_can_keep_the_popup_away(
        self,
        main_screen: MainScreen,
        mock_components: MainScreenComponents,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(window_minimum.NO_SCREEN_WARNING_ENV_VAR, "1")
        cast(
            "MagicMock", mock_components.json_settings_manager
        ).is_screen_size_warned.return_value = False
        with patch.object(barks_reader.ui.main_screen, "open_message_popup") as popup:
            main_screen.warn_if_screen_too_small(1366, 768)
        popup.assert_not_called()


def test_the_settings_take_the_window_drag_and_hand_it_back(main_screen: MainScreen) -> None:
    """Their X sits under the main bar's title area on the spread, where a tap was a drag."""
    settings = MagicMock()
    app_window = MagicMock(children=[])
    with (
        patch.object(barks_reader.ui.main_screen, "set_titlebar_drag_region") as drag,
        patch.object(barks_reader.ui.main_screen.SettingsKeyboardNav, "focus_first"),
        patch.object(main_screen, "_add_settings_close_button"),
    ):
        main_screen.display_settings(app_window, settings)
        drag.assert_called_once_with(settings.interface.drag_region)
        main_screen._teardown_settings()
    assert drag.call_args_list[-1].args == (main_screen.ids.action_bar.drag_region,)


def test_settings_open_with_their_first_item_focused(main_screen: MainScreen) -> None:
    """Otherwise the first item is focused invisibly and the first Down lands on the second."""
    settings = MagicMock()
    app_window = MagicMock(children=[])
    with (
        patch.object(barks_reader.ui.main_screen.SettingsKeyboardNav, "focus_first") as first,
        patch.object(main_screen, "_add_settings_close_button"),
    ):
        assert main_screen.display_settings(app_window, settings) is True
    first.assert_called_once_with()


class TestHistoryGoto:
    """A journal row names a page: the title view offers it, the page last read a step away."""

    def test_a_row_with_a_page_goes_to_that_page(self, main_screen: MainScreen) -> None:
        main_screen._on_goto_history_title(Titles.LOST_IN_THE_ANDES, "7")
        main_screen._nav_coord.navigate_to_title_with_page.assert_called_once_with(
            ImageInfo(from_title=Titles.LOST_IN_THE_ANDES, filename=None), "7"
        )
        main_screen._nav_coord.navigate_to_chrono_title.assert_not_called()

    @pytest.mark.parametrize("page", ["", "0"])
    def test_a_row_with_no_page_goes_to_the_title(self, main_screen: MainScreen, page: str) -> None:
        main_screen._on_goto_history_title(Titles.LOST_IN_THE_ANDES, page)
        main_screen._nav_coord.navigate_to_chrono_title.assert_called_once_with(
            ImageInfo(from_title=Titles.LOST_IN_THE_ANDES, filename=None)
        )


class TestDocumentGoto:
    """A document figure names a story page: offered as a history row's page is."""

    @pytest.mark.parametrize("keyboard_initiated", [True, False])
    def test_a_figure_goes_to_its_page(
        self, main_screen: MainScreen, keyboard_initiated: bool
    ) -> None:
        main_screen.goto_title_from_document(
            Titles.LOST_IN_THE_ANDES, "7", keyboard_initiated=keyboard_initiated
        )
        main_screen._nav_coord.navigate_to_title_with_page.assert_called_once_with(
            ImageInfo(from_title=Titles.LOST_IN_THE_ANDES, filename=None), "7"
        )
        main_screen._nav.focus_title_portal_after_goto.assert_called_once_with(
            keyboard_initiated=keyboard_initiated
        )


def test_the_settings_x_follows_the_panel_when_the_window_refits(main_screen: MainScreen) -> None:
    """The layout setting refits the window under the open panel, which is re-centred.

    The X is placed from the panel's x/width and y/height: Kivy caches the `right` and
    `top` aliases, and a pos callback bound before the alias was first read sees the
    old value (the X stayed off the window's right edge, 2026-10-29).
    """
    settings = Widget(size_hint=(None, None), size=(874, 1365), pos=(450, 0))
    close_button = Widget(size_hint=(None, None), size=(45, 45))
    with patch.object(
        barks_reader.ui.main_screen.Factory, "SettingsCloseButton", return_value=close_button
    ):
        main_screen._add_settings_close_button(MagicMock(children=[]), settings)
    assert close_button.x == pytest.approx(450 + 874 - dp(7) - 45)

    settings.pos = (0, 0)

    assert close_button.x == pytest.approx(874 - dp(7) - 45)
    assert close_button.center_y == pytest.approx(1365 - ACTION_BAR_SIZE_Y / 2)


class TestSettingsEscape:
    """Escape lands on the settings' X, Enter there closes and returns to the action bar."""

    def test_escape_lands_on_the_x_and_enter_there_closes_into_menu_mode(
        self, main_screen: MainScreen
    ) -> None:
        main_screen._settings_nav = MagicMock()
        main_screen._settings_nav.handle_key.return_value = False
        main_screen._settings_close_button = MagicMock()
        with (
            patch.object(barks_reader.ui.main_screen, "draw_focus_highlight") as draw,
            patch.object(main_screen, "_close_settings") as close,
            patch.object(main_screen, "_enter_menu_mode") as menu,
        ):
            assert main_screen._handle_settings_key(KEY_ESCAPE) is True
            close.assert_not_called()
            draw.assert_called_once()
            main_screen._settings_nav.blur.assert_called_once_with()
            assert main_screen._settings_x_focused is True
            assert main_screen._handle_settings_key(KEY_ENTER) is True
        close.assert_called_once_with()
        menu.assert_called_once_with()

    def test_escape_on_the_x_gives_the_list_its_focus_back(self, main_screen: MainScreen) -> None:
        main_screen._settings_nav = MagicMock()
        main_screen._settings_close_button = MagicMock()
        main_screen._settings_x_focused = True
        with (
            patch.object(barks_reader.ui.main_screen, "clear_focus_highlight") as clear,
            patch.object(main_screen, "_close_settings") as close,
        ):
            assert main_screen._handle_settings_key(KEY_ESCAPE) is True
        close.assert_not_called()
        clear.assert_called_once()
        main_screen._settings_nav.refocus.assert_called_once_with()
        assert main_screen._settings_x_focused is False

    def test_escape_with_no_x_on_the_window_marks_it_and_draws_nothing(
        self, main_screen: MainScreen
    ) -> None:
        main_screen._settings_nav = MagicMock()
        main_screen._settings_nav.handle_key.return_value = False
        main_screen._settings_close_button = None
        with patch.object(barks_reader.ui.main_screen, "draw_focus_highlight") as draw:
            assert main_screen._handle_settings_key(KEY_ESCAPE) is True
        assert main_screen._settings_x_focused is True
        draw.assert_not_called()
        main_screen._settings_nav.blur.assert_not_called()

    def test_a_key_the_settings_take_leaves_them_open(self, main_screen: MainScreen) -> None:
        main_screen._settings_nav = MagicMock()
        main_screen._settings_nav.handle_key.return_value = True
        with (
            patch.object(main_screen, "_close_settings") as close,
            patch.object(main_screen, "_enter_menu_mode") as menu,
        ):
            assert main_screen._handle_settings_key(KEY_DOWN) is True
        close.assert_not_called()
        menu.assert_not_called()


class TestAboutBoxFocus:
    """The About box closed puts the keys back on the Menu button, when the keys opened it."""

    @pytest.mark.parametrize("by_keyboard", [True, False])
    def test_opened_by_the_keys_its_closing_enters_the_menu(
        self, main_screen: MainScreen, by_keyboard: bool
    ) -> None:
        main_screen._menu_action_by_keyboard = by_keyboard
        with patch.object(barks_reader.ui.main_screen, "show_about_box") as show:
            main_screen.open_about()
        on_dismiss = show.call_args.kwargs["on_dismiss"]
        if by_keyboard:
            assert on_dismiss == main_screen._enter_menu_mode
        else:
            assert on_dismiss is None

    def test_about_names_the_installed_data_pack(self, main_screen: MainScreen) -> None:
        with (
            patch.object(barks_reader.ui.main_screen, "show_about_box") as show,
            patch.object(barks_reader.ui.main_screen.data_pack, "read_installed") as read,
        ):
            read.return_value = None
            main_screen.open_about()
        read.assert_called_once_with(main_screen._reader_settings.reader_files_dir)
        assert show.call_args.kwargs["data_pack_text"] == "Data pack: not versioned"

    def test_enter_on_the_menu_button_records_keyboard_intent(
        self, main_screen: MainScreen
    ) -> None:
        """The dots menu's own path skipped the base's record, so About saw a mouse opening."""
        main_screen._menu_action_by_keyboard = False
        main_screen._focused_btn_idx = main_screen._menu_buttons.index(main_screen.ids.menu_button)
        with patch.object(main_screen, "_open_menu_dots_for_keyboard") as open_dots:
            main_screen._activate_focused_button()
        open_dots.assert_called_once_with()
        assert main_screen._menu_action_by_keyboard is True


class TestTheBooksLayout:
    """The layout mode reaches the page screens; the spread seeds the fun page."""

    def test_the_spread_reaches_the_screens_and_seeds_the_fun_view(
        self, main_screen: MainScreen
    ) -> None:
        main_screen.set_layout_mode(MainLayoutMode.SPREAD)
        for screen in (
            main_screen._tree_view_screen,
            main_screen._bottom_title_view_screen,
            main_screen._fun_image_view_screen,
            main_screen._search_screen,
        ):
            assert screen.layout_mode == "spread"
        main_screen._renderer.seed_fun_view_second_image.assert_called_once()
        main_screen._window_helper.refit_fullscreen.assert_called_once()

    def test_a_single_page_seeds_nothing(self, main_screen: MainScreen) -> None:
        main_screen.set_layout_mode(MainLayoutMode.SPREAD)
        main_screen._renderer.seed_fun_view_second_image.reset_mock()
        main_screen.set_layout_mode(MainLayoutMode.SINGLE)
        assert main_screen._fun_image_view_screen.layout_mode == "single"
        main_screen._renderer.seed_fun_view_second_image.assert_not_called()

    def test_the_tree_knows_when_it_is_collapsed(self, main_screen: MainScreen) -> None:
        main_screen._on_view_state_changed(ViewStates.INITIAL)
        assert main_screen._tree_view_screen.tree_collapsed is True
        main_screen._on_view_state_changed(ViewStates.ON_TITLE_NODE)
        assert main_screen._tree_view_screen.tree_collapsed is False
