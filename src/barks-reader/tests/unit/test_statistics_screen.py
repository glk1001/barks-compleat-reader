# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import reader_keyboard_nav as reader_keyboard_nav_module
from barks_reader.ui import statistics_screen as statistics_screen_module
from barks_reader.ui.reader_keyboard_nav import KEY_DOWN
from barks_reader.ui.statistics_screen import (
    StatisticsScreen,
    StatMenuButton,
    _discover_wordclouds,
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
        patch.object(statistics_screen_module, "DropDown") as mock_dropdown_cls,
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


class TestDiscoverWordclouds:
    def test_discovers_and_sorts_wordclouds(self, tmp_path: Path) -> None:
        """Test that wordcloud files are discovered with correct labels."""
        (tmp_path / "tfidf_wordcloud_1943-46.png").touch()
        (tmp_path / "tfidf_wordcloud_1947-50.png").touch()
        (tmp_path / "tfidf_wordcloud_1951-54.png").touch()
        # Non-matching file should be ignored
        (tmp_path / "other_image.png").touch()

        result = _discover_wordclouds(tmp_path)

        assert result == [
            ("Word Cloud 1943-46", "tfidf_wordcloud_1943-46.png"),
            ("Word Cloud 1947-50", "tfidf_wordcloud_1947-50.png"),
            ("Word Cloud 1951-54", "tfidf_wordcloud_1951-54.png"),
        ]

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Test that an empty directory returns no wordclouds."""
        assert _discover_wordclouds(tmp_path) == []

    def test_no_matching_files(self, tmp_path: Path) -> None:
        """Test that non-matching files are excluded."""
        (tmp_path / "stories_per_year.png").touch()
        (tmp_path / "most_frequent.png").touch()

        assert _discover_wordclouds(tmp_path) == []


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
        screen.ids.stat_image.reload.assert_called_once()

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
        dropdown.open.assert_called_with(word_button)

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
        # noinspection PyUnresolvedReferences
        focused_button.trigger_action.assert_called_once()

    def test_handle_tab_key_enter_on_word_stats(self, screen: StatisticsScreen) -> None:
        """Test activating the word stats tab, which should open the dropdown."""
        with patch.object(statistics_screen_module, "update_focus_in_list"):
            screen.enter_nav_focus(MagicMock())

        screen._nav_focused_idx = len(screen._stat_buttons) - 1
        word_button = screen._word_stat_button

        assert word_button is not None
        with (
            patch.object(statistics_screen_module.Clock, "schedule_once") as mock_schedule,
            patch.object(screen, "_enter_dropdown_nav") as mock_enter_dropdown,
        ):
            screen.handle_key(statistics_screen_module.KEY_ENTER)
            # noinspection PyUnresolvedReferences
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

        screen.handle_key(statistics_screen_module.KEY_ESCAPE)
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
