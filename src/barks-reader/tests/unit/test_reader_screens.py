# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast, no_type_check
from unittest.mock import MagicMock, patch

import barks_reader.ui.reader_screens
import pytest
from barks_reader.ui.reader_screens import (
    COMIC_BOOK_READER_SCREEN,
    DOCUMENT_READER_SCREEN,
    MAIN_READER_SCREEN,
    WIKI_READER_SCREEN,
    ReaderScreen,
    ReaderScreenManager,
    ReaderScreens,
)
from kivy.uix.screenmanager import Screen, TransitionBase


@pytest.fixture
def mock_open_settings() -> MagicMock:
    return MagicMock()


@pytest.fixture
def reader_screen_manager(mock_open_settings: MagicMock) -> ReaderScreenManager:
    # Patch ScreenManager to avoid Kivy window creation/interaction
    with patch.object(barks_reader.ui.reader_screens, "ScreenManager"):
        return ReaderScreenManager(mock_open_settings)


@pytest.fixture
def mock_reader_screens() -> ReaderScreens:
    # Create mock screens. We mock ReaderScreen to avoid Kivy init issues.
    main_screen = MagicMock(spec=ReaderScreen)
    main_screen.app_icon_filepath = "icon.png"

    comic_reader_screen = MagicMock(spec=ReaderScreen)
    document_reader_screen = MagicMock()
    wiki_reader_screen = MagicMock()
    corpus_stats_screen = MagicMock()

    return ReaderScreens(
        main_screen=main_screen,
        comic_reader_screen=comic_reader_screen,
        document_reader_screen=document_reader_screen,
        wiki_reader_screen=wiki_reader_screen,
        corpus_stats_screen=corpus_stats_screen,
    )


class TestReaderScreenManager:
    def test_init(self, reader_screen_manager: ReaderScreenManager) -> None:
        assert reader_screen_manager.screen_switchers is not None
        # Check that callbacks are correctly assigned
        assert (
            reader_screen_manager.screen_switchers.switch_to_comic_book_reader
            == reader_screen_manager._switch_to_comic_book_reader
        )

    @no_type_check
    def test_add_screens(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
    ) -> None:
        root = reader_screen_manager.add_screens(mock_reader_screens)

        mock_sm = reader_screen_manager._screen_manager

        assert mock_sm.add_widget.call_count == 5  # noqa: PLR2004
        mock_sm.add_widget.assert_any_call(mock_reader_screens.main_screen)
        mock_sm.add_widget.assert_any_call(mock_reader_screens.comic_reader_screen)
        mock_sm.add_widget.assert_any_call(mock_reader_screens.document_reader_screen)
        mock_sm.add_widget.assert_any_call(mock_reader_screens.wiki_reader_screen)
        mock_sm.add_widget.assert_any_call(mock_reader_screens.corpus_stats_screen)

        assert mock_sm.current == MAIN_READER_SCREEN
        assert root == mock_sm

    def test_get_next_main_screen_transition(
        self, reader_screen_manager: ReaderScreenManager
    ) -> None:
        transition = reader_screen_manager._get_next_main_screen_transition()
        assert isinstance(transition, TransitionBase)

    def test_get_next_reader_screen_transition(
        self, reader_screen_manager: ReaderScreenManager
    ) -> None:
        transition = reader_screen_manager._get_next_reader_screen_transition()
        assert isinstance(transition, TransitionBase)

    def test_switch_to_comic_book_reader(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)

        reader_screen_manager._switch_to_comic_book_reader()

        mock_sm = reader_screen_manager._screen_manager

        assert isinstance(mock_sm.transition, TransitionBase)
        assert mock_sm.current == COMIC_BOOK_READER_SCREEN

        assert mock_reader_screens.comic_reader_screen.app_icon_filepath == "icon.png"

        is_active_mock = cast("MagicMock", mock_reader_screens.comic_reader_screen.is_active)
        is_active_mock.assert_called_with(active=True)

    def test_close_comic_book_reader(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)

        reader_screen_manager._close_comic_book_reader()

        on_comic_closed_mock = cast("MagicMock", mock_reader_screens.main_screen.on_comic_closed)
        on_comic_closed_mock.assert_called_once()

        mock_sm = reader_screen_manager._screen_manager
        assert isinstance(mock_sm.transition, TransitionBase)
        assert mock_sm.current == MAIN_READER_SCREEN

        is_active_mock = cast("MagicMock", mock_reader_screens.comic_reader_screen.is_active)
        is_active_mock.assert_called_with(active=False)

    @pytest.mark.parametrize("switch", ["_switch_to_comic_book_reader", "_close_comic_book_reader"])
    def test_a_transition_still_running_at_a_switch_is_finished_first(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
        loguru_sink: list[str],
        switch: str,
    ) -> None:
        """Kivy would let it run on and remove the new current screen when it ends; stop it."""
        reader_screen_manager.add_screens(mock_reader_screens)
        running = reader_screen_manager._screen_manager.transition
        running.is_active = True
        running.__class__.__name__ = "SwapTransition"

        getattr(reader_screen_manager, switch)()

        running.stop.assert_called_once_with()
        # What a finished animation would have fired, and stop() does not.
        running.screen_in.dispatch.assert_called_once_with("on_enter")
        running.screen_out.dispatch.assert_called_once_with("on_leave")
        assert reader_screen_manager._screen_manager.transition is not running
        assert any(
            "Screen transition 'SwapTransition' still running" in line for line in loguru_sink
        )

    def test_a_finished_transition_at_a_switch_is_quiet(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
        loguru_sink: list[str],
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)
        idle = reader_screen_manager._screen_manager.transition
        idle.is_active = False

        reader_screen_manager._close_comic_book_reader()

        idle.stop.assert_not_called()
        assert not any("still running" in line for line in loguru_sink)

    def test_switch_to_document_reader(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)

        doc_dir = Path("/test-doc")
        reader_screen_manager._switch_to_document_reader(doc_dir, "Test Title")

        mock_sm = reader_screen_manager._screen_manager
        assert mock_sm.current == DOCUMENT_READER_SCREEN

        open_document_mock = cast(
            "MagicMock", mock_reader_screens.document_reader_screen.open_document
        )
        open_document_mock.assert_called_with(doc_dir, "Test Title")

    def test_close_document_reader(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)

        reader_screen_manager._close_document_reader()

        on_document_reader_closed_mock = cast(
            "MagicMock", mock_reader_screens.main_screen.on_document_reader_closed
        )
        on_document_reader_closed_mock.assert_called_once()

        mock_sm = reader_screen_manager._screen_manager
        assert isinstance(mock_sm.transition, TransitionBase)
        assert mock_sm.current == MAIN_READER_SCREEN

    def test_switch_to_wiki_reader(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)

        bundle = Path("/test-bundle")
        reader_screen_manager._switch_to_wiki_reader(bundle, None)

        mock_sm = reader_screen_manager._screen_manager
        assert mock_sm.current == WIKI_READER_SCREEN

        open_wiki_mock = cast("MagicMock", mock_reader_screens.wiki_reader_screen.open_wiki)
        open_wiki_mock.assert_called_with(bundle, None)

    def test_switch_to_wiki_reader_with_page(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)

        bundle = Path("/test-bundle")
        page = bundle / "concept" / "stories" / "misc" / "test-story.md"
        reader_screen_manager._switch_to_wiki_reader(bundle, page)

        mock_sm = reader_screen_manager._screen_manager
        assert mock_sm.current == WIKI_READER_SCREEN

        open_wiki_mock = cast("MagicMock", mock_reader_screens.wiki_reader_screen.open_wiki)
        open_wiki_mock.assert_called_with(bundle, page)

    def test_each_close_names_where_the_main_screen_came_back_from(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
        loguru_sink: list[str],
    ) -> None:
        """Four sites log the same event; a test counting one must tell them apart."""
        reader_screen_manager.add_screens(mock_reader_screens)
        reader_screen_manager._close_comic_book_reader()
        reader_screen_manager._close_document_reader()
        reader_screen_manager._close_corpus_stats()
        reader_screen_manager._close_wiki_reader()
        joined = "\n".join(loguru_sink)
        for origin in ("comic reader", "document reader", "By the Numbers", "wiki reader"):
            assert f"Main screen is active (from {origin})." in joined

    def test_switching_to_document_and_corpus_stats_announces_them(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
        loguru_sink: list[str],
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)
        reader_screen_manager._switch_to_document_reader(Path("/doc"), "How To")
        reader_screen_manager._switch_to_corpus_stats()
        assert 'Document reader screen is active: "How To".' in loguru_sink
        assert "By the Numbers screen is active." in loguru_sink

    def test_close_wiki_reader(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)

        reader_screen_manager._close_wiki_reader()

        on_wiki_reader_closed_mock = cast(
            "MagicMock", mock_reader_screens.main_screen.on_wiki_reader_closed
        )
        on_wiki_reader_closed_mock.assert_called_once()

        mock_sm = reader_screen_manager._screen_manager
        assert isinstance(mock_sm.transition, TransitionBase)
        assert mock_sm.current == MAIN_READER_SCREEN


class TestReaderScreen:
    def test_init(self) -> None:
        # We need to patch Screen.__init__ because ReaderScreen inherits from it
        with patch.object(Screen, "__init__", autospec=True) as mock_init:
            screen = ReaderScreen()
            mock_init.assert_called_once()
            assert screen.app_icon_filepath == ""

    def test_methods_exist(self) -> None:
        # Just verifying the interface exists and doesn't crash
        with patch.object(Screen, "__init__", autospec=True):
            screen = ReaderScreen()
            screen.is_active(active=True)
            screen.on_comic_closed()
            screen.on_document_reader_closed()
            screen.on_wiki_reader_closed()

    def test_entering_and_leaving_log_the_screen_name(self, loguru_sink: list[str]) -> None:
        """Kivy fires these when a transition completes: the one marker for that."""
        screen = cast("ReaderScreen", SimpleNamespace(name="wiki_reader"))
        ReaderScreen.on_enter(screen)
        ReaderScreen.on_leave(screen)
        assert "Screen 'wiki_reader' entered." in loguru_sink
        assert "Screen 'wiki_reader' left." in loguru_sink
