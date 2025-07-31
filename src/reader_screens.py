from dataclasses import dataclass
from random import randrange
from typing import List, Callable, Union

from kivy.uix.screenmanager import (
    Screen,
    ScreenManager,
    RiseInTransition,
    FallOutTransition,
    FadeTransition,
    WipeTransition,
    SlideTransition,
    NoTransition,
    SwapTransition,
    CardTransition,
    TransitionBase,
)

MAIN_READER_SCREEN = "main_screen"
COMIC_BOOK_READER_SCREEN = "comic_book_reader"
CENSORSHIP_FIXES_SCREEN = "censorship_fixes"


@dataclass
class ReaderScreens:
    main_screen: Screen
    comic_reader: Screen
    censorship_fixes: Screen


@dataclass
class ScreenSwitchers:
    switch_to_settings: Callable

    switch_to_comic_book_reader: Callable[[], None]
    close_comic_book_reader: Callable[[], None]

    switch_to_censorship_fixes: Callable[[], None]
    close_censorship_fixes: Callable[[], None]


class ReaderScreenManager:
    _MAIN_SCREEN_TRANSITIONS: List[TransitionBase] = [
        NoTransition(duration=0),
        FadeTransition(),
        FallOutTransition(),
        RiseInTransition(),
        SwapTransition(),
        WipeTransition(),
        SlideTransition(direction="left"),
        CardTransition(direction="left", mode="push"),
    ]
    _READER_SCREEN_TRANSITIONS: List[TransitionBase] = [
        NoTransition(duration=0),
        FadeTransition(),
        FallOutTransition(),
        RiseInTransition(),
        SwapTransition(),
        WipeTransition(),
        SlideTransition(direction="right"),
        CardTransition(direction="right", mode="pop"),
    ]

    def __init__(self, open_settings: Callable):
        self._screen_manager = ScreenManager()

        self._screen_manager = ScreenManager()
        self._reader_screens: Union[ReaderScreens, None] = None

        self.screen_switchers = ScreenSwitchers(
            open_settings,
            self._switch_to_comic_book_reader,
            self._close_comic_book_reader,
            self._switch_to_censorship_fixes,
            self._close_censorship_fixes,
        )

    def add_screens(self, reader_screens: ReaderScreens) -> ScreenManager:
        self._reader_screens = reader_screens

        root = self._screen_manager

        root.add_widget(self._reader_screens.main_screen)
        root.add_widget(self._reader_screens.comic_reader)
        root.add_widget(self._reader_screens.censorship_fixes)

        root.current = MAIN_READER_SCREEN

        return root

    def _get_next_main_screen_transition(self) -> TransitionBase:
        return self._MAIN_SCREEN_TRANSITIONS[randrange(0, len(self._MAIN_SCREEN_TRANSITIONS))]

    def _get_next_reader_screen_transition(self) -> TransitionBase:
        return self._READER_SCREEN_TRANSITIONS[randrange(0, len(self._READER_SCREEN_TRANSITIONS))]

    def _switch_to_comic_book_reader(self):
        self._screen_manager.transition = self._get_next_reader_screen_transition()
        self._screen_manager.current = COMIC_BOOK_READER_SCREEN

    def _close_comic_book_reader(self):
        self._reader_screens.main_screen.comic_closed()

        self._screen_manager.transition = self._get_next_main_screen_transition()
        self._screen_manager.current = MAIN_READER_SCREEN

    def _switch_to_censorship_fixes(self):
        self._screen_manager.current = CENSORSHIP_FIXES_SCREEN

    def _close_censorship_fixes(self):
        self._reader_screens.main_screen.appendix_censorship_fixes_closed()

        self._screen_manager.transition = self._get_next_main_screen_transition()
        self._screen_manager.current = MAIN_READER_SCREEN
