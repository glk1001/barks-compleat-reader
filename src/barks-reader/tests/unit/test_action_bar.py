"""Unit tests for the shared action-bar widget (barks_reader.ui.action_bar).

Per the repo test pattern the kv rule itself is never loaded here; these pin
the Python-side behavior the rule relies on — the add_widget redirect that
sends consumer-declared buttons into the skeleton's buttons box.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from barks_reader.core.reader_palette import theme
from barks_reader.ui.action_bar import ReaderActionBar
from kivy.uix.widget import Widget


class TestReaderActionBarRedirect:
    def test_children_land_on_self_while_rule_is_building(self) -> None:
        """With button_container unset (mid-rule), children go to the FloatLayout."""
        bar = ReaderActionBar()
        child = Widget()
        bar.add_widget(child)
        assert child in bar.children

    def test_children_redirect_to_button_container_once_set(self) -> None:
        """Once the rule assigns button_container, children go into the buttons box."""
        bar = ReaderActionBar()
        bar.button_container = MagicMock()
        child = Widget()
        bar.add_widget(child)
        bar.button_container.add_widget.assert_called_once_with(child)
        assert child not in bar.children


class TestReaderActionBarDefaults:
    def test_icon_not_clickable_by_default(self) -> None:
        """Only the main screen opts in to a clickable app icon."""
        assert not ReaderActionBar().icon_clickable

    def test_title_color_defaults_to_theme_app_title(self) -> None:
        """The title color single-sources from the active color theme."""
        assert tuple(ReaderActionBar().title_color) == theme().app_title
