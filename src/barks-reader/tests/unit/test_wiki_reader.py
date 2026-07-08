# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui.wiki_reader import WikiReaderScreen
from kivy.uix.screenmanager import Screen


@pytest.fixture
def wiki_screen() -> WikiReaderScreen:
    # Patch Screen.__init__ to avoid Kivy window creation/interaction.
    with patch.object(Screen, "__init__", autospec=True):
        return WikiReaderScreen(
            reader_settings=MagicMock(),
            font_manager=MagicMock(),
            image_selector=MagicMock(),
            app_data_dir=Path("/app-data"),
            on_goto_title=MagicMock(),
            on_close_screen=MagicMock(),
        )


class TestWikiReaderScreenOpenWiki:
    BUNDLE = Path("/bundle")
    PAGE = Path("/bundle/concept/stories/donald-duck/lost-in-the-andes.md")

    def test_first_open_builds_viewer_with_start_page(self, wiki_screen: WikiReaderScreen) -> None:
        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True) as build_mock:
            wiki_screen.open_wiki(self.BUNDLE, self.PAGE)

        build_mock.assert_called_once_with(wiki_screen, self.BUNDLE, start_page=self.PAGE)

    def test_existing_viewer_shows_page(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._bundle = self.BUNDLE

        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True) as build_mock:
            wiki_screen.open_wiki(self.BUNDLE, self.PAGE)

        build_mock.assert_not_called()
        wiki_screen._viewer.show_page.assert_called_once_with(self.PAGE)

    def test_existing_viewer_without_page_is_untouched(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._bundle = self.BUNDLE

        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True) as build_mock:
            wiki_screen.open_wiki(self.BUNDLE)

        build_mock.assert_not_called()
        wiki_screen._viewer.show_page.assert_not_called()

    def test_bundle_change_rebuilds_viewer_with_start_page(
        self, wiki_screen: WikiReaderScreen
    ) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._bundle = Path("/old-bundle")

        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True) as build_mock:
            wiki_screen.open_wiki(self.BUNDLE, self.PAGE)

        build_mock.assert_called_once_with(wiki_screen, self.BUNDLE, start_page=self.PAGE)
