# ruff: noqa: SLF001

from __future__ import annotations

from typing import no_type_check
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.reader_screens import (
    COMIC_BOOK_READER_SCREEN,
    INTRO_COMPLEAT_BARKS_READER_SCREEN,
    MAIN_READER_SCREEN,
    ReaderScreen,
    ReaderScreenManager,
    ReaderScreens,
)
from kivy.uix.screenmanager import TransitionBase


@pytest.fixture
def mock_open_settings() -> MagicMock:
    return MagicMock()


@pytest.fixture
def reader_screen_manager(mock_open_settings: MagicMock) -> ReaderScreenManager:
    # Patch ScreenManager to avoid Kivy window creation/interaction
    with patch("barks_reader.reader_screens.ScreenManager"):
        return ReaderScreenManager(mock_open_settings)


@pytest.fixture
def mock_reader_screens() -> ReaderScreens:
    # Create mock screens. We mock ReaderScreen to avoid Kivy init issues.
    main_screen = MagicMock(spec=ReaderScreen)
    main_screen.app_icon_filepath = "icon.png"

    comic_reader_screen = MagicMock(spec=ReaderScreen)
    intro_screen = MagicMock(spec=ReaderScreen)

    return ReaderScreens(
        main_screen=main_screen,
        comic_reader_screen=comic_reader_screen,
        intro_compleat_barks_reader_screen=intro_screen,
    )


class TestReaderScreenManager:
    def test_init(self, reader_screen_manager: ReaderScreenManager) -> None:
        assert reader_screen_manager.screen_switchers is not None
        # Check that callbacks are correctly assigned
        # noinspection PyProtectedMember
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

        # noinspection PyProtectedMember
        mock_sm = reader_screen_manager._screen_manager

        assert mock_sm.add_widget.call_count == 3  # noqa: PLR2004
        mock_sm.add_widget.assert_any_call(mock_reader_screens.main_screen)
        mock_sm.add_widget.assert_any_call(mock_reader_screens.comic_reader_screen)
        mock_sm.add_widget.assert_any_call(mock_reader_screens.intro_compleat_barks_reader_screen)

        assert mock_sm.current == MAIN_READER_SCREEN
        assert root == mock_sm

    def test_get_next_main_screen_transition(
        self, reader_screen_manager: ReaderScreenManager
    ) -> None:
        # noinspection PyProtectedMember
        transition = reader_screen_manager._get_next_main_screen_transition()
        assert isinstance(transition, TransitionBase)

    def test_get_next_reader_screen_transition(
        self, reader_screen_manager: ReaderScreenManager
    ) -> None:
        # noinspection PyProtectedMember
        transition = reader_screen_manager._get_next_reader_screen_transition()
        assert isinstance(transition, TransitionBase)

    def test_switch_to_comic_book_reader(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)

        # noinspection PyProtectedMember
        reader_screen_manager._switch_to_comic_book_reader()

        # noinspection PyProtectedMember
        mock_sm = reader_screen_manager._screen_manager

        assert isinstance(mock_sm.transition, TransitionBase)
        assert mock_sm.current == COMIC_BOOK_READER_SCREEN

        assert mock_reader_screens.comic_reader_screen.app_icon_filepath == "icon.png"
        # noinspection PyUnresolvedReferences
        mock_reader_screens.comic_reader_screen.is_active.assert_called_with(active=True)

    def test_close_comic_book_reader(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)

        # noinspection PyProtectedMember
        reader_screen_manager._close_comic_book_reader()

        # noinspection PyUnresolvedReferences
        mock_reader_screens.main_screen.on_comic_closed.assert_called_once()

        # noinspection PyProtectedMember
        mock_sm = reader_screen_manager._screen_manager
        assert isinstance(mock_sm.transition, TransitionBase)
        assert mock_sm.current == MAIN_READER_SCREEN

        # noinspection PyUnresolvedReferences
        mock_reader_screens.comic_reader_screen.is_active.assert_called_with(active=False)

    def test_switch_to_intro_compleat_barks_reader(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)

        # noinspection PyProtectedMember
        reader_screen_manager._switch_to_intro_compleat_barks_reader()

        # noinspection PyProtectedMember
        mock_sm = reader_screen_manager._screen_manager
        assert mock_sm.current == INTRO_COMPLEAT_BARKS_READER_SCREEN

    def test_close_intro_compleat_barks_reader(
        self,
        reader_screen_manager: ReaderScreenManager,
        mock_reader_screens: ReaderScreens,
    ) -> None:
        reader_screen_manager.add_screens(mock_reader_screens)

        # noinspection PyProtectedMember
        reader_screen_manager._close_intro_compleat_barks_reader()

        # noinspection PyUnresolvedReferences
        mock_reader_screens.main_screen.on_intro_compleat_barks_reader_closed.assert_called_once()

        # noinspection PyProtectedMember
        mock_sm = reader_screen_manager._screen_manager
        assert isinstance(mock_sm.transition, TransitionBase)
        assert mock_sm.current == MAIN_READER_SCREEN


class TestReaderScreen:
    def test_init(self) -> None:
        # We need to patch Screen.__init__ because ReaderScreen inherits from it
        with patch("kivy.uix.screenmanager.Screen.__init__", autospec=True) as mock_init:
            screen = ReaderScreen()
            mock_init.assert_called_once()
            assert screen.app_icon_filepath == ""

    def test_methods_exist(self) -> None:
        # Just verifying the interface exists and doesn't crash
        with patch("kivy.uix.screenmanager.Screen.__init__", autospec=True):
            screen = ReaderScreen()
            screen.is_active(active=True)
            screen.on_comic_closed()
            screen.on_intro_compleat_barks_reader_closed()
