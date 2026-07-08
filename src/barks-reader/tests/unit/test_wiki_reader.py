# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import wiki_reader
from barks_reader.ui.reader_keyboard_nav import KEY_ESCAPE, KEY_LEFT
from barks_reader.ui.wiki_reader import WikiReaderScreen
from kivy.uix.screenmanager import Screen

if TYPE_CHECKING:
    from collections.abc import Iterator


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


@pytest.fixture(autouse=True)
def mock_window() -> Iterator[MagicMock]:
    # The screen binds/unbinds the window's key handler on open/close; keep the
    # real Window singleton out of the unit tests.
    with patch.object(wiki_reader, "Window") as window:
        yield window


class TestWikiReaderScreenOpenWiki:
    BUNDLE = Path("/bundle")
    PAGE = Path("/bundle/concept/stories/donald-duck/lost-in-the-andes.md")

    def test_first_open_builds_viewer_with_start_page(self, wiki_screen: WikiReaderScreen) -> None:
        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True) as build_mock:
            wiki_screen.open_wiki(self.BUNDLE, self.PAGE)

        build_mock.assert_called_once_with(wiki_screen, self.BUNDLE, start_page=self.PAGE)

    def test_existing_viewer_resets_history_to_page(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._bundle = self.BUNDLE

        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True) as build_mock:
            wiki_screen.open_wiki(self.BUNDLE, self.PAGE)

        build_mock.assert_not_called()
        wiki_screen._viewer.reset_to.assert_called_once_with(self.PAGE)
        wiki_screen._viewer.show_page.assert_not_called()

    def test_existing_viewer_without_page_resets_history(
        self, wiki_screen: WikiReaderScreen
    ) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._bundle = self.BUNDLE

        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True) as build_mock:
            wiki_screen.open_wiki(self.BUNDLE)

        build_mock.assert_not_called()
        wiki_screen._viewer.reset_to.assert_called_once_with(None)

    def test_bundle_change_rebuilds_viewer_with_start_page(
        self, wiki_screen: WikiReaderScreen
    ) -> None:
        wiki_screen._viewer = MagicMock()
        wiki_screen._bundle = Path("/old-bundle")

        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True) as build_mock:
            wiki_screen.open_wiki(self.BUNDLE, self.PAGE)

        build_mock.assert_called_once_with(wiki_screen, self.BUNDLE, start_page=self.PAGE)


class TestWikiReaderScreenKeyboard:
    def test_escape_routes_to_go_back_and_consumes(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = MagicMock()

        consumed = wiki_screen._on_key_down(None, KEY_ESCAPE, 0, "", [])

        assert consumed is True
        wiki_screen._viewer.go_back.assert_called_once_with()

    def test_alt_left_routes_to_go_back_and_consumes(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = MagicMock()

        consumed = wiki_screen._on_key_down(None, KEY_LEFT, 0, "", ["alt"])

        assert consumed is True
        wiki_screen._viewer.go_back.assert_called_once_with()

    def test_left_without_alt_is_ignored(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = MagicMock()

        consumed = wiki_screen._on_key_down(None, KEY_LEFT, 0, "", [])

        assert consumed is False
        wiki_screen._viewer.go_back.assert_not_called()

    def test_other_key_is_ignored(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = MagicMock()

        consumed = wiki_screen._on_key_down(None, ord("a"), 0, "a", [])

        assert consumed is False
        wiki_screen._viewer.go_back.assert_not_called()

    def test_no_viewer_is_ignored(self, wiki_screen: WikiReaderScreen) -> None:
        wiki_screen._viewer = None

        assert wiki_screen._on_key_down(None, KEY_ESCAPE, 0, "", []) is False


class TestWikiReaderScreenKeyBinding:
    BUNDLE = Path("/bundle")

    def test_open_binds_key_handler(
        self, wiki_screen: WikiReaderScreen, mock_window: MagicMock
    ) -> None:
        with patch.object(WikiReaderScreen, "_build_viewer", autospec=True):
            wiki_screen.open_wiki(self.BUNDLE)

        mock_window.bind.assert_called_once_with(on_key_down=wiki_screen._on_key_down)
        # Unbind first, so a re-open without an intervening close can't double-bind.
        mock_window.unbind.assert_called_once_with(on_key_down=wiki_screen._on_key_down)

    def test_close_unbinds_key_handler(
        self, wiki_screen: WikiReaderScreen, mock_window: MagicMock
    ) -> None:
        wiki_screen.close()

        mock_window.unbind.assert_called_once_with(on_key_down=wiki_screen._on_key_down)
        wiki_screen._on_close_screen.assert_called_once_with()


class TestWikiReaderScreenBuildViewer:
    BUNDLE = Path("/bundle")

    def test_build_viewer_passes_close_as_on_exit(self, wiki_screen: WikiReaderScreen) -> None:
        with (
            patch.object(wiki_reader, "OKFViewer") as viewer_cls,
            patch.object(wiki_reader, "wiki_top_bar_spec"),
            patch.object(wiki_reader, "wiki_session_path"),
            patch.object(wiki_reader, "BarksPanelsImageProvider"),
            patch.object(wiki_reader, "BarksTableRewriter"),
            patch.object(wiki_screen, "add_widget"),
        ):
            wiki_screen._build_viewer(self.BUNDLE)

        assert viewer_cls.call_args.kwargs["on_exit"] == wiki_screen.close
