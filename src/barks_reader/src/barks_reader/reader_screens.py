from __future__ import annotations

from dataclasses import dataclass
from random import randrange
from typing import TYPE_CHECKING, ClassVar

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

if TYPE_CHECKING:
    from collections.abc import Callable

MAIN_READER_SCREEN = "main_screen"
COMIC_BOOK_READER_SCREEN = "comic_book_reader"
INTRO_COMPLEAT_BARKS_READER_SCREEN = "intro_compleat_barks_reader"


@dataclass
class ReaderScreens:
    main_screen: Screen
    comic_reader: Screen
    intro_compleat_barks_reader: Screen


@dataclass
class ScreenSwitchers:
    switch_to_settings: Callable

    switch_to_comic_book_reader: Callable[[], None]
    close_comic_book_reader: Callable[[], None]

    switch_to_intro_compleat_barks_reader: Callable[[], None]
    close_intro_compleat_barks_reader: Callable[[], None]


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

        self._screen_manager = ScreenManager()
        self._reader_screens: ReaderScreens | None = None

        self.screen_switchers = ScreenSwitchers(
            open_settings,
            self._switch_to_comic_book_reader,
            self._close_comic_book_reader,
            self._switch_to_intro_compleat_barks_reader,
            self._close_intro_compleat_barks_reader,
        )

    def add_screens(self, reader_screens: ReaderScreens) -> ScreenManager:
        self._reader_screens = reader_screens

        root = self._screen_manager

        root.add_widget(self._reader_screens.main_screen)
        root.add_widget(self._reader_screens.comic_reader)
        root.add_widget(self._reader_screens.intro_compleat_barks_reader)

        root.current = MAIN_READER_SCREEN

        return root

    def _get_next_main_screen_transition(self) -> TransitionBase:
        return self._MAIN_SCREEN_TRANSITIONS[randrange(0, len(self._MAIN_SCREEN_TRANSITIONS))]

    def _get_next_reader_screen_transition(self) -> TransitionBase:
        return self._READER_SCREEN_TRANSITIONS[randrange(0, len(self._READER_SCREEN_TRANSITIONS))]

    def _switch_to_comic_book_reader(self) -> None:
        self._screen_manager.transition = self._get_next_reader_screen_transition()
        self._screen_manager.current = COMIC_BOOK_READER_SCREEN

    def _close_comic_book_reader(self) -> None:
        self._reader_screens.main_screen.on_comic_closed()

        self._screen_manager.transition = self._get_next_main_screen_transition()
        self._screen_manager.current = MAIN_READER_SCREEN

    def _switch_to_intro_compleat_barks_reader(self) -> None:
        self._screen_manager.current = INTRO_COMPLEAT_BARKS_READER_SCREEN

    def _close_intro_compleat_barks_reader(self) -> None:
        self._reader_screens.main_screen.on_intro_compleat_barks_reader_closed()

        self._screen_manager.transition = self._get_next_main_screen_transition()
        self._screen_manager.current = MAIN_READER_SCREEN
