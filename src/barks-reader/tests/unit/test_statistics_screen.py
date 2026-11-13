# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.keys import KEY_DOWN, KEY_ESCAPE
from barks_reader.ui import reader_keyboard_nav as reader_keyboard_nav_module
from barks_reader.ui import statistics_screen as statistics_screen_module
from barks_reader.ui.statistics_screen import (
    StatisticsScreen,
    StatMenuButton,
)
from kivy.uix.floatlayout import FloatLayout

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture
def statistics_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for statistics files."""
    stats_dir = tmp_path / "statistics"
    stats_dir.mkdir()
    (stats_dir / "stories_per_year.png").touch()
    (stats_dir / "pages_per_year.png").touch()
    (stats_dir / "word_stat.png").touch()
    return stats_dir


@pytest.fixture
def screen(statistics_dir: Path) -> Generator[StatisticsScreen]:
    """Fixture for the StatisticsScreen with mocked Kivy dependencies."""
    with (
        patch.object(FloatLayout, "__init__", autospec=True) as mock_layout_init,
        patch.object(statistics_screen_module, "StatMenuButton", spec=True) as mock_stat_button_cls,
        patch.object(statistics_screen_module, "ReaderDropDown") as mock_dropdown_cls,
        patch.object(statistics_screen_module, "Button"),
        patch.object(statistics_screen_module, "dp", side_effect=lambda x: x),
    ):
        mock_ids = {
            "stat_menu_layout": MagicMock(),
            "stat_image": MagicMock(),
        }

        def side_effect(instance: StatisticsScreen, **_kwargs) -> None:  # noqa: ANN003
            instance.ids = mock_ids
            # DropdownNavMixin needs this
            instance._dropdown_nav_mode = False

        mock_layout_init.side_effect = side_effect

        mock_dropdown = MagicMock()
        mock_dropdown.container.children = [MagicMock(), MagicMock()]
        mock_dropdown_cls.return_value = mock_dropdown

        # This will be used by _build_menu inside __init__
        mock_buttons = [MagicMock(spec=StatMenuButton) for _ in range(8)]
        mock_stat_button_cls.side_effect = mock_buttons

        screen_instance = StatisticsScreen(statistics_dir=statistics_dir)
        yield screen_instance


class TestStatisticsScreen:
    def test_init_builds_menu(self, screen: StatisticsScreen, statistics_dir: Path) -> None:
        """Test that the constructor correctly builds the menu."""
        assert screen._statistics_dir == statistics_dir

        menu_layout = screen.ids.stat_menu_layout
        assert menu_layout.add_widget.call_count == 8

        word_button = screen._word_stat_button
        assert word_button is not None
        word_button.bind.assert_called_with(on_press=screen._on_word_stat_button_pressed)

        dropdown = screen._word_stat_dropdown
        dropdown.bind.assert_any_call(on_select=screen._on_word_stat_selected)
        dropdown.bind.assert_any_call(on_dismiss=screen._on_dropdown_dismissed)

    def test_on_is_visible_true_activates_screen(self, screen: StatisticsScreen) -> None:
        """Test that the screen is activated when it becomes visible."""
        with patch.object(screen, "_on_screen_activated") as mock_activate:
            screen.on_is_visible(screen, value=True)
            mock_activate.assert_called_once()

    def test_on_screen_activated(self, screen: StatisticsScreen, statistics_dir: Path) -> None:
        """Test that activating the screen shows the first statistic."""
        first_button = screen._stat_buttons[0]

        with patch.object(screen, "show_stat") as mock_show_stat:
            screen._on_screen_activated()

            assert first_button.state == "down"
            expected_path = statistics_dir / "stories_per_year.png"
            mock_show_stat.assert_called_with(expected_path)

    def test_show_stat_file_exists(self, screen: StatisticsScreen, statistics_dir: Path) -> None:
        """Test showing a statistic when the image file exists."""
        png_path = statistics_dir / "stories_per_year.png"
        screen.show_stat(png_path)

        assert screen.ids.stat_image.source == str(png_path)
        # Setting the source loads the chart: a reload decoded it a second time.
        screen.ids.stat_image.reload.assert_not_called()

    def test_show_stat_file_does_not_exist(
        self, screen: StatisticsScreen, statistics_dir: Path
    ) -> None:
        """Test showing a statistic when the image file is missing."""
        png_path = statistics_dir / "non_existent.png"
        screen.show_stat(png_path)

        assert screen.ids.stat_image.source == ""
        screen.ids.stat_image.reload.assert_not_called()

    def test_word_stat_button_opens_dropdown(self, screen: StatisticsScreen) -> None:
        """Test that pressing the word statistics button opens the dropdown."""
        word_button = screen._word_stat_button
        dropdown = screen._word_stat_dropdown

        screen._on_word_stat_button_pressed(word_button)
        dropdown.open_if_shown.assert_called_with(word_button)

    def test_no_dropdown_nav_when_the_dropdown_does_not_open(
        self, screen: StatisticsScreen
    ) -> None:
        """Off screen (mid-fade) the dropdown stays shut, so keys stay on the tabs."""
        word_button = screen._word_stat_button
        assert word_button is not None
        screen._word_stat_dropdown.open_if_shown.return_value = False
        word_button.trigger_action.side_effect = lambda: screen._on_word_stat_button_pressed(
            word_button
        )
        screen._nav_focused_idx = screen._stat_buttons.index(word_button)
        with patch.object(statistics_screen_module, "Clock") as clock:
            screen._activate_focused_tab()
        clock.schedule_once.assert_not_called()

    def test_word_stat_selected(self, screen: StatisticsScreen, statistics_dir: Path) -> None:
        """Test selecting an item from the word statistics dropdown."""
        word_button = screen._word_stat_button
        assert word_button is not None

        with patch.object(screen, "show_stat") as mock_show_stat:
            screen._on_word_stat_selected(None, "word_stat.png")

            assert word_button.state == "down"
            mock_show_stat.assert_called_with(statistics_dir / "word_stat.png")

    def test_enter_and_exit_nav_focus(self, screen: StatisticsScreen) -> None:
        """Test entering and exiting keyboard navigation mode."""
        on_exit = MagicMock()

        with (
            patch.object(statistics_screen_module, "update_focus_in_list") as mock_update,
            patch.object(statistics_screen_module, "clear_focus_in_list") as mock_clear,
        ):
            screen.enter_nav_focus(on_exit)
            assert screen._nav_active is True
            assert screen._nav_focused_idx == 0
            mock_update.assert_called_once()

            screen.exit_nav_focus()
            assert screen._nav_active is False
            mock_clear.assert_called_once()

    def test_handle_tab_key_right_left(self, screen: StatisticsScreen) -> None:
        """Test moving focus left and right between tabs."""
        with patch.object(statistics_screen_module, "update_focus_in_list") as mock_update:
            # Enter nav focus while the drawing function is mocked
            screen.enter_nav_focus(MagicMock())

            # Reset the mock so we don't count the initial focus call
            mock_update.reset_mock()

            screen.handle_key(statistics_screen_module.KEY_RIGHT)
            assert screen._nav_focused_idx == 1
            mock_update.assert_called_with(
                screen._stat_buttons, 1, statistics_screen_module.MENU_FOCUS_HIGHLIGHT_GROUP
            )

            screen.handle_key(statistics_screen_module.KEY_LEFT)
            assert screen._nav_focused_idx == 0
            mock_update.assert_called_with(
                screen._stat_buttons, 0, statistics_screen_module.MENU_FOCUS_HIGHLIGHT_GROUP
            )

    def test_handle_tab_key_enter(self, screen: StatisticsScreen) -> None:
        """Test activating a tab with the Enter key."""
        with patch.object(statistics_screen_module, "update_focus_in_list"):
            screen.enter_nav_focus(MagicMock())

        focused_button = screen._stat_buttons[0]

        screen.handle_key(statistics_screen_module.KEY_ENTER)
        focused_button.trigger_action.assert_called_once()

    def test_handle_tab_key_enter_on_word_stats(self, screen: StatisticsScreen) -> None:
        """Test activating the word stats tab, which should open the dropdown."""
        with patch.object(statistics_screen_module, "update_focus_in_list"):
            screen.enter_nav_focus(MagicMock())

        screen._nav_focused_idx = len(screen._stat_buttons) - 1
        word_button = screen._word_stat_button

        assert word_button is not None
        # As a real button's does, trigger_action presses it (opening the dropdown).
        word_button.trigger_action.side_effect = lambda: screen._on_word_stat_button_pressed(
            word_button
        )
        with (
            patch.object(statistics_screen_module.Clock, "schedule_once") as mock_schedule,
            patch.object(screen, "_enter_dropdown_nav") as mock_enter_dropdown,
        ):
            screen.handle_key(statistics_screen_module.KEY_ENTER)
            word_button.trigger_action.assert_called_once()

            mock_schedule.assert_called_once()
            lambda_func = mock_schedule.call_args[0][0]
            lambda_func(0)
            mock_enter_dropdown.assert_called_once()

    def test_handle_tab_key_escape(self, screen: StatisticsScreen) -> None:
        """Test that Escape key calls the on_exit_request callback."""
        on_exit = MagicMock()
        with patch.object(statistics_screen_module, "update_focus_in_list"):
            screen.enter_nav_focus(on_exit)

        screen.handle_key(KEY_ESCAPE)
        on_exit.assert_called_once()

    def test_dropdown_nav(self, screen: StatisticsScreen) -> None:
        """Test entering, navigating, and exiting dropdown navigation mode."""
        # We must patch the graphics functions in the mixin's module to prevent segfaults!
        with (
            patch.object(reader_keyboard_nav_module, attribute="update_focus_in_list"),
            patch.object(reader_keyboard_nav_module, attribute="clear_focus_in_list"),
        ):
            # 1. Enter dropdown nav and verify the mixin's state is updated
            screen._enter_dropdown_nav()
            assert screen._dropdown_nav_mode is True
            assert screen._dropdown_focused_idx == 0

            # 2. Verify that keystrokes route correctly to the mixin's logic
            # Sending KEY_DOWN should advance the index to 1
            screen._handle_dropdown_key(KEY_DOWN)
            assert screen._dropdown_focused_idx == 1

            # 3. Verify that dismissing the Kivy dropdown exits the navigation mode
            screen._on_dropdown_dismissed(None)
            assert screen._dropdown_nav_mode is False


class TestWordListOpenedByMouse:
    """The keys take over the word statistics list the mouse opened."""

    def test_an_open_list_not_the_keys_says_so(self, screen: StatisticsScreen) -> None:
        screen._word_stat_dropdown.parent = MagicMock(name="window")
        screen._dropdown_nav_mode = False
        assert screen.has_list_open_without_the_keys() is True
        screen._dropdown_nav_mode = True
        assert screen.has_list_open_without_the_keys() is False
        screen._dropdown_nav_mode = False
        screen._word_stat_dropdown.parent = None
        assert screen.has_list_open_without_the_keys() is False

    def test_closing_it_dismisses_the_list(self, screen: StatisticsScreen) -> None:
        screen.close_open_list()
        screen._word_stat_dropdown.dismiss.assert_called_once_with()

    def test_the_keys_land_on_its_first_row_with_the_ring_on_its_tab(
        self, screen: StatisticsScreen, loguru_sink: list[str]
    ) -> None:
        on_exit = MagicMock()
        with (
            patch.object(statistics_screen_module, "update_focus_in_list") as focus_tab,
            patch.object(screen, "_enter_dropdown_nav") as enter_list,
        ):
            screen.take_keys_onto_open_list(on_exit)
        assert screen._nav_active is True
        assert screen._nav_on_exit_request is on_exit
        assert screen._stat_buttons[screen._nav_focused_idx] is screen._word_stat_button
        focus_tab.assert_called_once()
        enter_list.assert_called_once_with()
        assert "StatisticsScreen: entered nav focus." in loguru_sink


@pytest.fixture
def real_tabs_screen(statistics_dir: Path) -> Generator[StatisticsScreen]:
    """Build the screen with real tabs in their real toggle group; the rest mocked.

    Mock tabs take any state they are given, so two tabs marked at once, and a tab
    marked for a list nothing was chosen from, passed every test (2026-11-13).
    """
    with (
        patch.object(FloatLayout, "__init__", autospec=True) as mock_layout_init,
        patch.object(statistics_screen_module, "ReaderDropDown"),
        patch.object(statistics_screen_module, "Button"),
    ):

        def side_effect(instance: StatisticsScreen, **_kwargs) -> None:  # noqa: ANN003
            instance.ids = {"stat_menu_layout": MagicMock(), "stat_image": MagicMock()}
            instance._dropdown_nav_mode = False

        mock_layout_init.side_effect = side_effect
        yield StatisticsScreen(statistics_dir=statistics_dir)


def _marked(screen: StatisticsScreen) -> list[str]:
    return [tab.text for tab in screen._stat_buttons if tab.state == "down"]


class TestTheOneMarkedTab:
    """Exactly one tab is marked: the one whose chart is on show."""

    def test_the_tabs_are_real_toggle_buttons_in_one_group(
        self, real_tabs_screen: StatisticsScreen
    ) -> None:
        assert all(type(tab) is StatMenuButton for tab in real_tabs_screen._stat_buttons)
        assert {tab.group for tab in real_tabs_screen._stat_buttons} == {"stats"}
        assert _marked(real_tabs_screen) == []

    def test_coming_back_to_the_screen_marks_only_the_first_tab(
        self, real_tabs_screen: StatisticsScreen
    ) -> None:
        """The first tab was set down beside the one pressed before leaving."""
        screen = real_tabs_screen
        first, third = screen._stat_buttons[0], screen._stat_buttons[2]
        screen.on_is_visible(screen, value=True)
        third.trigger_action(duration=0)
        assert _marked(screen) == [third.text]

        screen.on_is_visible(screen, value=False)
        screen.on_is_visible(screen, value=True)

        assert _marked(screen) == [first.text]

    def test_a_list_closed_with_nothing_chosen_leaves_the_shown_tab_marked(
        self, real_tabs_screen: StatisticsScreen
    ) -> None:
        screen = real_tabs_screen
        second, word_tab = screen._stat_buttons[1], screen._word_stat_button
        assert word_tab is not None
        second.trigger_action(duration=0)

        word_tab.trigger_action(duration=0)  # opens the list; nothing is chosen from it

        assert _marked(screen) == [second.text]
        screen._word_stat_dropdown.open_if_shown.assert_called_once_with(word_tab)

    def test_choosing_from_the_list_marks_the_word_statistics_tab(
        self, real_tabs_screen: StatisticsScreen
    ) -> None:
        screen = real_tabs_screen
        second, word_tab = screen._stat_buttons[1], screen._word_stat_button
        assert word_tab is not None
        second.trigger_action(duration=0)
        word_tab.trigger_action(duration=0)

        screen._on_word_stat_selected(None, "word_stat.png")

        assert _marked(screen) == [word_tab.text]

    def test_opening_the_list_again_keeps_the_word_statistics_tab_marked(
        self, real_tabs_screen: StatisticsScreen
    ) -> None:
        screen = real_tabs_screen
        word_tab = screen._word_stat_button
        assert word_tab is not None
        word_tab.trigger_action(duration=0)
        screen._on_word_stat_selected(None, "word_stat.png")

        word_tab.trigger_action(duration=0)

        assert _marked(screen) == [word_tab.text]
        assert screen._word_stat_dropdown.open_if_shown.call_count == 2

    def test_a_pressed_tab_shows_its_own_chart(
        self, real_tabs_screen: StatisticsScreen, statistics_dir: Path
    ) -> None:
        screen = real_tabs_screen
        with patch.object(screen, "show_stat") as show_stat:
            screen._stat_buttons[1].trigger_action(duration=0)
        _label, filename = statistics_screen_module.CHART_ITEMS[1]
        show_stat.assert_called_once_with(statistics_dir / filename)


def test_with_the_list_open_the_keys_go_to_it(screen: StatisticsScreen) -> None:
    screen._nav_active = True
    screen._dropdown_nav_mode = True
    with (
        patch.object(screen, "_handle_dropdown_key", return_value=True) as list_key,
        patch.object(screen, "_handle_tab_key") as tab_key,
    ):
        assert screen.handle_key(KEY_DOWN) is True
    list_key.assert_called_once_with(KEY_DOWN)
    tab_key.assert_not_called()


class TestStatMenuButton:
    def test_the_selected_tab_cannot_be_pressed_off(self) -> None:
        button = StatMenuButton(group="stats-test")
        button.state = "down"

        button._do_press()

        assert button.state == "down"

    def test_a_press_selects_a_tab_and_releases_the_one_that_was(self) -> None:
        was, pressed = StatMenuButton(group="stats-test-2"), StatMenuButton(group="stats-test-2")
        was.state = "down"

        pressed._do_press()

        assert (was.state, pressed.state) == ("normal", "down")


class TestStatisticsScreenEdges:
    def test_becoming_hidden_selects_nothing(self, screen: StatisticsScreen) -> None:
        with patch.object(screen, "_on_screen_activated") as mock_activate:
            screen.on_is_visible(screen, value=False)
        mock_activate.assert_not_called()

    def test_with_no_tabs_activating_shows_nothing(self, screen: StatisticsScreen) -> None:
        screen._stat_buttons = []
        with patch.object(screen, "show_stat") as mock_show_stat:
            screen._on_screen_activated()
        mock_show_stat.assert_not_called()

    def test_a_word_stat_is_shown_even_without_its_tab(
        self, screen: StatisticsScreen, statistics_dir: Path
    ) -> None:
        screen._word_stat_button = None
        with patch.object(screen, "show_stat") as mock_show_stat:
            screen._on_word_stat_selected(None, "word_stat.png")
        mock_show_stat.assert_called_once_with(statistics_dir / "word_stat.png")

    def test_dismissing_the_dropdown_dismisses_the_word_stat_dropdown(
        self, screen: StatisticsScreen
    ) -> None:
        screen._dismiss_dropdown()
        screen._word_stat_dropdown.dismiss.assert_called_once_with()

    def test_leaving_from_the_dropdown_leaves_its_navigation_too(
        self, screen: StatisticsScreen
    ) -> None:
        screen._dropdown_nav_mode = True
        with (
            patch.object(statistics_screen_module, "clear_focus_in_list"),
            patch.object(screen, "_exit_dropdown_nav") as exit_dropdown_nav,
        ):
            screen.exit_nav_focus()
        exit_dropdown_nav.assert_called_once_with()
        screen._word_stat_dropdown.dismiss.assert_called_once_with()

    def test_leaving_with_no_dropdown_built_still_leaves(self, screen: StatisticsScreen) -> None:
        screen._nav_active = True
        screen._word_stat_dropdown = None
        with patch.object(statistics_screen_module, "clear_focus_in_list"):
            screen.exit_nav_focus()
        assert screen._nav_active is False

    def test_without_focus_no_key_is_taken(self, screen: StatisticsScreen) -> None:
        assert screen.handle_key(statistics_screen_module.KEY_RIGHT) is False

    def test_escape_with_no_one_to_hand_focus_back_to_is_still_taken(
        self, screen: StatisticsScreen
    ) -> None:
        with patch.object(statistics_screen_module, "update_focus_in_list"):
            screen.enter_nav_focus(MagicMock())
        screen._nav_on_exit_request = None
        assert screen.handle_key(KEY_ESCAPE) is True

    def test_an_unused_key_on_the_tabs_is_handed_back(self, screen: StatisticsScreen) -> None:
        with patch.object(statistics_screen_module, "update_focus_in_list"):
            screen.enter_nav_focus(MagicMock())
        assert screen.handle_key(KEY_DOWN) is False
