from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from kivy.app import App
from kivy.uix.screenmanager import (
    CardTransition,
    FadeTransition,
    FallOutTransition,
    NoTransition,
    RiseInTransition,
    Screen,
    ScreenManager,
    SlideTransition,
    SwapTransition,
    TransitionBase,
    WipeTransition,
)
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from barks_reader.ui.document_reader import DocumentReaderScreen

MAIN_READER_SCREEN = "main_screen"
COMIC_BOOK_READER_SCREEN = "comic_book_reader"
DOCUMENT_READER_SCREEN = "document_reader"


class ReaderScreen(Screen):
    app_icon_filepath: str = ""

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)

    def is_active(self, active: bool) -> None:
        pass

    def on_comic_closed(self) -> None:
        pass

    def on_document_reader_closed(self) -> None:
        pass


@dataclass(frozen=True, slots=True)
class ReaderScreens:
    main_screen: ReaderScreen
    comic_reader_screen: ReaderScreen
    document_reader_screen: DocumentReaderScreen


@dataclass(frozen=True, slots=True)
class ScreenSwitchers:
    switch_to_settings: Callable[[], None]

    switch_to_comic_book_reader: Callable[[], None]
    close_comic_book_reader: Callable[[], None]

    switch_to_document_reader: Callable[[Path, str], None]
    close_document_reader: Callable[[], None]


class ReaderScreenManager:
    _MAIN_SCREEN_TRANSITIONS: ClassVar[list[TransitionBase]] = [
        NoTransition(duration=0),
        FadeTransition(),
        FallOutTransition(),
        RiseInTransition(),
        SwapTransition(),
        WipeTransition(),
        SlideTransition(direction="left"),
        CardTransition(direction="left", mode="push"),
    ]
    _READER_SCREEN_TRANSITIONS: ClassVar[list[TransitionBase]] = [
        NoTransition(duration=0),
        FadeTransition(),
        FallOutTransition(),
        RiseInTransition(),
        SwapTransition(),
        WipeTransition(),
        SlideTransition(direction="right"),
        CardTransition(direction="right", mode="pop"),
    ]

    def __init__(self, open_settings: Callable) -> None:
        self._screen_manager = ScreenManager()
        self._reader_screens: ReaderScreens | None = None

        self.screen_switchers = ScreenSwitchers(
            open_settings,
            self._switch_to_comic_book_reader,
            self._close_comic_book_reader,
            self._switch_to_document_reader,
            self._close_document_reader,
        )

    def add_screens(self, reader_screens: ReaderScreens) -> ScreenManager:
        self._reader_screens = reader_screens

        root = self._screen_manager

        root.add_widget(self._reader_screens.main_screen)
        root.add_widget(self._reader_screens.comic_reader_screen)
        root.add_widget(self._reader_screens.document_reader_screen)

        root.current = MAIN_READER_SCREEN

        return root

    def _get_next_main_screen_transition(self) -> TransitionBase:
        return random.choice(self._MAIN_SCREEN_TRANSITIONS)

    def _get_next_reader_screen_transition(self) -> TransitionBase:
        return random.choice(self._READER_SCREEN_TRANSITIONS)

    def _switch_to_comic_book_reader(self) -> None:
        logger.debug("Switching to comic book reader...")

        self._screen_manager.transition = self._get_next_reader_screen_transition()
        self._screen_manager.current = COMIC_BOOK_READER_SCREEN

        logger.debug(
            f"Using screen transition '{self._screen_manager.transition.__class__.__name__}'."
        )

        assert self._reader_screens
        self._reader_screens.comic_reader_screen.app_icon_filepath = (
            self._reader_screens.main_screen.app_icon_filepath
        )
        self._reader_screens.comic_reader_screen.is_active(active=True)

        logger.debug("Comic book reader screen is active.")

    def _close_comic_book_reader(self) -> None:
        logger.debug("Closing comic and switching back to main screen...")

        # Suppress aspect ratio corrections during the window restore that follows closing.
        # On Windows, the transition fires spurious resize events (DPI scaling artifacts)
        # that would otherwise trigger a correction feedback loop.
        app = App.get_running_app()
        if hasattr(app, "suppress_aspect_ratio_correction"):
            app.suppress_aspect_ratio_correction()

        assert self._reader_screens
        self._reader_screens.main_screen.on_comic_closed()

        self._screen_manager.transition = self._get_next_main_screen_transition()
        self._screen_manager.current = MAIN_READER_SCREEN

        logger.debug(
            f"Using screen transition '{self._screen_manager.transition.__class__.__name__}'."
        )

        self._reader_screens.comic_reader_screen.is_active(active=False)

        logger.info("Main screen is active.")

    def _switch_to_document_reader(self, doc_dir: Path, title: str) -> None:
        logger.debug(f'Switching to document reader for "{title}"...')
        assert self._reader_screens
        self._reader_screens.document_reader_screen.app_icon_filepath = (
            self._reader_screens.main_screen.app_icon_filepath
        )
        self._reader_screens.document_reader_screen.open_document(doc_dir, title)
        self._screen_manager.current = DOCUMENT_READER_SCREEN

    def _close_document_reader(self) -> None:
        logger.debug("Closing document reader and switching back to main screen...")
        assert self._reader_screens
        self._reader_screens.main_screen.on_document_reader_closed()

        self._screen_manager.transition = self._get_next_main_screen_transition()
        self._screen_manager.current = MAIN_READER_SCREEN

        logger.debug(
            f"Using screen transition '{self._screen_manager.transition.__class__.__name__}'."
        )
        logger.info("Main screen is active.")
