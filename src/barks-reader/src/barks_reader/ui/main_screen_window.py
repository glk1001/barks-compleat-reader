from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.core.window import Window
from loguru import logger

from barks_reader.core.reader_utils import get_win_dimensions
from barks_reader.ui.platform_window_utils import WindowManager
from barks_reader.ui.reader_ui_classes import ACTION_BAR_SIZE_Y, hide_action_bar, show_action_bar

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.screenmanager import Screen
    from kivy.uix.widget import Widget

    from barks_reader.ui.comic_reader_manager import ComicReaderManager


class MainScreenWindowHelper:
    """Handles fullscreen/windowed mode toggling and action bar visibility for MainScreen."""

    def __init__(
        self,
        host_screen: Screen,
        comic_reader_manager: ComicReaderManager,
        action_bar: Widget,
        fullscreen_button: Widget,
        fullscreen_icon: str,
        fullscreen_exit_icon: str,
        main_layout: Widget,
        fun_image_view_screen: Widget,
        update_fonts: Callable[[int], None],
    ) -> None:
        self._host = host_screen
        self._comic_reader_manager = comic_reader_manager
        self._action_bar = action_bar
        self._fullscreen_button = fullscreen_button
        self._fullscreen_icon = fullscreen_icon
        self._fullscreen_exit_icon = fullscreen_exit_icon
        self._main_layout = main_layout
        self._fun_image_view_screen = fun_image_view_screen
        self._update_fonts = update_fonts

        self._window_manager = WindowManager(
            "MainScreen",
            self._set_hints_for_windowed_mode,
            self._on_finished_goto_windowed_mode,
            self._on_finished_goto_fullscreen_mode,
        )

    def toggle_screen_mode(self) -> None:
        if WindowManager.is_fullscreen_now():
            logger.info("Toggle screen mode to windowed mode.")
            Clock.schedule_once(lambda _dt: self._goto_windowed_mode(), 0)
        else:
            logger.info("Toggle screen mode to fullscreen mode.")
            Clock.schedule_once(lambda _dt: self._goto_fullscreen_mode(), 0)

    def force_fullscreen(self) -> None:
        Clock.schedule_once(lambda _dt: self._goto_fullscreen_mode(), 0)

    def exit_fullscreen(self) -> None:
        if not WindowManager.is_fullscreen_now():
            return
        self._goto_windowed_mode()

    def _goto_windowed_mode(self) -> None:
        logger.info("Exiting fullscreen mode on MainScreen.")
        self._comic_reader_manager.clear_window_state()
        self._window_manager.goto_windowed_mode()

    def _set_hints_for_windowed_mode(self) -> None:
        self._host.size_hint = (1, 1)

    def _on_finished_goto_windowed_mode(self) -> None:
        self._fullscreen_button.text = "Fullscreen"
        self._fullscreen_button.icon = self._fullscreen_icon
        self._update_fonts(Window.height)
        self.show_action_bar()
        logger.info("Entered windowed mode on MainScreen.")

    def _goto_fullscreen_mode(self) -> None:
        logger.info("Entering fullscreen mode on MainScreen.")
        self._comic_reader_manager.save_window_state_now()
        self._window_manager.goto_fullscreen_mode()

    def _on_finished_goto_fullscreen_mode(self) -> None:
        if not WindowManager.is_fullscreen_now():
            logger.error(
                f"Finishing goto fullscreen on MainScreen but Window fullscreen"
                f" = '{WindowManager.get_screen_mode_now()}'. "
            )
        if self._host.height < Window.height:
            logger.info(
                f"Finishing goto fullscreen on MainScreen but self.height"
                f" = {self._host.height} < Window.height = {Window.height} = Window.height."
            )
            self._host.height = Window.height
            logger.info(
                f"New height too low: adjusted new fullscreen height = {self._host.height}."
            )
        self._update_fonts(Window.height)
        self._fullscreen_button.text = "Windowed"
        self._fullscreen_button.icon = self._fullscreen_exit_icon
        logger.info("Entered fullscreen mode on MainScreen.")

    def on_main_layout_size_changed(self, _instance: Widget, size: tuple[int, int]) -> None:
        logger.info(
            f"Main layout size changed: size = {size},"
            f" fullscreen = '{WindowManager.get_screen_mode_now()}'."
        )
        self._fun_image_view_screen.on_resized(size)
        if not WindowManager.is_fullscreen_now():
            return
        self._change_fullscreen_win_size(size[1])

    def _change_fullscreen_win_size(self, height: int) -> None:
        logger.info(f"New fullscreen height = {height}.")
        if height < Window.height:
            height = Window.height
            logger.info(f"New height too low: adjusted new fullscreen height = {height}.")
        self._host.size_hint = None, None
        width, content_h = get_win_dimensions(height - ACTION_BAR_SIZE_Y, Window.width)
        self._host.size = width, content_h + ACTION_BAR_SIZE_Y
        assert WindowManager.is_fullscreen_now()
        logger.info(
            f"New fullscreen window settings:"
            f" Window.pos = ({Window.left}, {Window.top}),"
            f" Window.size = {Window.size},"
            f" self.size = {self._host.size},"
            f" Screen mode = {WindowManager.get_screen_mode_now()},"
            f" self._action_bar.height = {self._action_bar.height}"
        )

    def resize_binding(self) -> None:
        self._main_layout.bind(size=self.on_main_layout_size_changed)

    def hide_action_bar(self) -> None:
        hide_action_bar(self._action_bar)
        logger.debug(
            f"MainScreen actionbar is hidden: self._action_bar.height = {self._action_bar.height}"
        )

    def show_action_bar(self) -> None:
        show_action_bar(self._action_bar)
        logger.debug(
            f"MainScreen actionbar is visible: self.action_bar.height = {self._action_bar.height}"
        )
