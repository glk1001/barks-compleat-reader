from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.core.window import Window
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.reader_utils import get_win_dimensions

from .action_bar_helpers import (
    ACTION_BAR_SIZE_Y,
    ActionBarVisibility,
    set_action_bar_visibility,
    set_fullscreen_button,
)
from .platform_window_utils import (
    WindowManager,
    WindowModeCallbacks,
    WindowModeController,
    log_window_geometry,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.screenmanager import Screen
    from kivy.uix.widget import Widget


class MainScreenWindowHelper:
    """Handles fullscreen/windowed mode toggling and action bar visibility for MainScreen."""

    def __init__(
        self,
        host_screen: Screen,
        window_manager: WindowManager,
        action_bar: Widget,
        fullscreen_button: Widget,
        fullscreen_icon: str,
        fullscreen_exit_icon: str,
        main_layout: Widget,
        fun_image_view_screen: Widget,
        update_fonts: Callable[[int], None],
    ) -> None:
        self._host = host_screen
        self._action_bar = action_bar
        self._fullscreen_button = fullscreen_button
        self._fullscreen_icon = fullscreen_icon
        self._fullscreen_exit_icon = fullscreen_exit_icon
        self._main_layout = main_layout
        self._fun_image_view_screen = fun_image_view_screen
        self._update_fonts = update_fonts

        # The window-mode engine is shared with the comic reader (one geometry
        # store); this controller carries the toggle policy + this screen's
        # completion callbacks.
        self._mode = WindowModeController(
            "MainScreen",
            window_manager,
            WindowModeCallbacks(
                on_windowed_first_resize=self._set_hints_for_windowed_mode,
                on_finished_windowed=self._on_finished_goto_windowed_mode,
                on_finished_fullscreen=self._on_finished_goto_fullscreen_mode,
            ),
        )

    def toggle_screen_mode(self) -> None:
        self._mode.toggle()

    def force_fullscreen(self) -> None:
        self._mode.force_fullscreen()

    def exit_fullscreen(self) -> None:
        """Ensure the app is windowed.

        Delegates unconditionally: if the window is already windowed the manager
        skips the transition but still fires the completion callback, so every
        caller gets the same single completion path.
        """
        self._mode.goto_windowed()

    def _set_hints_for_windowed_mode(self) -> None:
        logger.debug(
            f"MainScreen: restoring size hints for windowed mode (host size = {self._host.size})."
        )
        self._host.size_hint = (1, 1)

    def _on_finished_goto_windowed_mode(self) -> None:
        set_fullscreen_button(
            self._fullscreen_button,
            is_fullscreen=False,
            fullscreen_icon=self._fullscreen_icon,
            fullscreen_exit_icon=self._fullscreen_exit_icon,
        )
        self._update_fonts(Window.height)
        self.show_action_bar()
        logger.info(log_markers.ENTERED_WINDOWED.format(screen="MainScreen"))
        log_window_geometry("MainScreen windowed")

    def _on_finished_goto_fullscreen_mode(self) -> None:
        is_fullscreen_now = bool(WindowManager.is_fullscreen_now())
        if not is_fullscreen_now:
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
        # The actual mode, not an assumed True: if the transition failed, the
        # button label must keep matching the real window.
        set_fullscreen_button(
            self._fullscreen_button,
            is_fullscreen=is_fullscreen_now,
            fullscreen_icon=self._fullscreen_icon,
            fullscreen_exit_icon=self._fullscreen_exit_icon,
        )
        logger.info(log_markers.ENTERED_FULLSCREEN.format(screen="MainScreen"))
        log_window_geometry("MainScreen fullscreen")

    def on_main_layout_size_changed(self, _instance: Widget, size: tuple[int, int]) -> None:
        logger.info(
            f"Main layout size changed: size = {size},"
            f" fullscreen = '{WindowManager.get_screen_mode_now()}'."
        )
        self._fun_image_view_screen.on_resized(size)
        if not WindowManager.is_fullscreen_now():
            if self._host.size_hint_x is None and self._host.size_hint_y is None:
                # Only this screen's own windowed transition restores the hints
                # (_set_hints_for_windowed_mode); a fullscreen exit driven by
                # another screen leaves the fixed fullscreen size behind.
                logger.warning(
                    f"Main layout resized while windowed but the host size is still fixed"
                    f" at {self._host.size}: a fullscreen exit did not restore its size hints."
                )
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
        set_action_bar_visibility(self._action_bar, ActionBarVisibility.HIDDEN)
        logger.debug(
            f"MainScreen actionbar is hidden: self._action_bar.height = {self._action_bar.height}"
        )

    def show_action_bar(self) -> None:
        set_action_bar_visibility(self._action_bar, ActionBarVisibility.VISIBLE)
        logger.debug(
            f"MainScreen actionbar is visible: self.action_bar.height = {self._action_bar.height}"
        )
