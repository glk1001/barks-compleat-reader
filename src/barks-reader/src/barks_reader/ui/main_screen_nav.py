from __future__ import annotations

import time
from enum import Enum, auto
from typing import TYPE_CHECKING, Final, Protocol

from kivy.clock import Clock
from loguru import logger

from .reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
    clear_focus_highlight,
    draw_focus_highlight,
    is_escape_key,
)
from .tree_view_nodes import (
    BaseTreeViewNode,
    ButtonTreeViewNode,
    TitleTreeViewNode,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.screenmanager import Screen

    from .history_screen import HistoryScreen
    from .index_screen import IndexScreen
    from .screen_bundle import ScreenBundle
    from .search_screen import SearchScreen
    from .statistics_screen import StatisticsScreen
    from .tree_view_manager import TreeViewManager

_BOTTOM_FOCUS_HIGHLIGHT_GROUP = "bottom_focus_highlight"

# Successive tree-move key presses closer together than this are treated as rapid
# scrolling: the expensive title-view render is deferred until the presses settle.
_TITLE_RENDER_DEBOUNCE_SECS: Final = 0.2


class TriggerEvent(Protocol):
    """A restartable one-shot timer (matches `kivy.clock.ClockEvent`)."""

    def __call__(self) -> None: ...

    def cancel(self) -> None: ...


type TriggerFactory = Callable[[Callable[[float], None], float], TriggerEvent]


class _FocusRegion(Enum):
    TREE = auto()
    BOTTOM = auto()


class MainScreenNavigation:
    """Handles keyboard/focus navigation for MainScreen (composition helper)."""

    def __init__(
        self,
        screens: ScreenBundle,
        tree_view_manager: TreeViewManager,
        bottom_base_view_screen: Screen,
        on_title_activated: Callable[[], None],
        enter_menu_mode: Callable[[], None],
        handle_menu_key: Callable[[int], bool],
        is_in_menu_mode: Callable[[], bool],
        *,
        trigger_factory: TriggerFactory | None = None,
        now_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._tree_view_screen = screens.tree_view
        self._tree_view_manager = tree_view_manager
        self._bottom_title_view_screen = screens.bottom_title_view
        self._fun_image_view_screen = screens.fun_image_view
        self._main_index_screen = screens.main_index
        self._speech_index_screen = screens.speech_index
        self._names_index_screen = screens.names_index
        self._locations_index_screen = screens.locations_index
        self._statistics_screen = screens.statistics
        self._history_screen = screens.history
        self._search_screen = screens.search
        self._bottom_base_view_screen = bottom_base_view_screen
        self._on_title_activated = on_title_activated
        self._enter_menu_mode = enter_menu_mode
        self._handle_menu_key = handle_menu_key
        self._is_in_menu_mode = is_in_menu_mode

        self._focus_region = _FocusRegion.TREE
        self._focus_region_before_comic: _FocusRegion | None = None
        self._auto_exited_bottom_focus = False

        factory: TriggerFactory = trigger_factory or Clock.create_trigger
        self._title_render_trigger = factory(
            self._on_title_render_timeout, _TITLE_RENDER_DEBOUNCE_SECS
        )
        self._now = now_fn
        self._last_tree_move_time = float("-inf")
        self._pending_title_node: TitleTreeViewNode | None = None

    @property
    def is_in_bottom_focus(self) -> bool:
        return self._focus_region == _FocusRegion.BOTTOM

    @property
    def was_bottom_focus_auto_exited(self) -> bool:
        """True if bottom focus was exited because the active screen became invisible."""
        return self._auto_exited_bottom_focus

    def on_bottom_screen_visibility_changed(self) -> None:
        """Exit bottom focus if the active bottom screen is no longer visible."""
        if self._focus_region != _FocusRegion.BOTTOM:
            return
        visible = (
            self._fun_image_view_screen.is_visible
            or self._bottom_title_view_screen.is_visible
            or self._get_active_nav_screen() is not None
        )
        if not visible:
            self.exit_bottom_focus()
            # Set *after* exit_bottom_focus (which clears the flag).
            self._auto_exited_bottom_focus = True
            logger.debug("Auto-exited bottom focus: active screen no longer visible.")

    def save_focus_before_comic(self) -> None:
        self._focus_region_before_comic = self._focus_region
        logger.debug(f"Saved focus before comic: {self._focus_region_before_comic}.")

    def restore_focus_after_comic(self) -> None:
        logger.debug(f"Focus after comic: {self._focus_region_before_comic}.")
        if self._focus_region_before_comic == _FocusRegion.BOTTOM:
            self.enter_bottom_focus()
        self._focus_region_before_comic = None

    def handle_key(self, key: int) -> bool:
        if self._is_in_menu_mode():
            return self._handle_menu_key(key)
        if self._focus_region == _FocusRegion.BOTTOM:
            return self._handle_bottom_key(key)
        return self._handle_tree_key(key)

    def _handle_tree_key(self, key: int) -> bool:
        if is_escape_key(key):
            self._enter_menu_mode()
        elif key == KEY_TAB:
            self._flush_pending_title_render()
            self.enter_bottom_focus()
        elif key == KEY_UP:
            self._tree_nav_move(-1)
        elif key == KEY_DOWN:
            self._tree_nav_move(1)
        elif key == KEY_LEFT:
            self._tree_nav_collapse_to_parent()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._tree_nav_activate()
        else:
            return False
        return True

    def _handle_bottom_key(self, key: int) -> bool:
        nav_screen = self._get_active_nav_screen()
        if nav_screen is not None:
            if key == KEY_TAB:
                self.exit_bottom_focus()
                return True
            return nav_screen.handle_key(key)
        if is_escape_key(key) or key == KEY_TAB:
            self.exit_bottom_focus()
            return True
        if self._fun_image_view_screen.is_visible:
            return self._handle_fun_view_key(key)
        return self._bottom_title_view_screen.is_visible and self._handle_title_view_key(key)

    def _handle_fun_view_key(self, key: int) -> bool:
        if key == KEY_LEFT:
            self._fun_image_view_screen.prev_image()
        elif key == KEY_RIGHT:
            self._fun_image_view_screen.next_image()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._fun_image_view_screen.on_goto_title()
        else:
            return False
        return True

    def _handle_title_view_key(self, key: int) -> bool:
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._on_title_activated()
        else:
            return False
        return True

    def _get_active_nav_screen(
        self,
    ) -> HistoryScreen | IndexScreen | StatisticsScreen | SearchScreen | None:
        """Return the currently visible bottom screen that supports keyboard navigation."""
        screens: list[HistoryScreen | IndexScreen | StatisticsScreen | SearchScreen] = [
            self._main_index_screen,
            self._speech_index_screen,
            self._names_index_screen,
            self._locations_index_screen,
            self._statistics_screen,
            self._history_screen,
            self._search_screen,
        ]
        return next((s for s in screens if s.is_visible), None)

    def enter_bottom_focus(self) -> None:
        visible = (
            self._fun_image_view_screen.is_visible
            or self._bottom_title_view_screen.is_visible
            or self._main_index_screen.is_visible
            or self._speech_index_screen.is_visible
            or self._names_index_screen.is_visible
            or self._locations_index_screen.is_visible
            or self._statistics_screen.is_visible
            or self._history_screen.is_visible
            or self._search_screen.is_visible
        )
        if not visible:
            return
        self._auto_exited_bottom_focus = False
        self._focus_region = _FocusRegion.BOTTOM
        self._update_bottom_focus_highlight()
        nav_screen = self._get_active_nav_screen()
        if nav_screen is not None:
            nav_screen.enter_nav_focus(self.exit_bottom_focus)
        logger.debug("Entered bottom focus region.")

    def exit_bottom_focus(self) -> None:
        nav_screen = self._get_active_nav_screen()
        if nav_screen is not None:
            nav_screen.exit_nav_focus()
        self._focus_region = _FocusRegion.TREE
        self._auto_exited_bottom_focus = False
        self._clear_bottom_focus_highlight()
        logger.debug("Exited bottom focus region.")

    def _update_bottom_focus_highlight(self) -> None:
        draw_focus_highlight(self._bottom_base_view_screen, _BOTTOM_FOCUS_HIGHLIGHT_GROUP)

    def _clear_bottom_focus_highlight(self) -> None:
        clear_focus_highlight(self._bottom_base_view_screen, _BOTTOM_FOCUS_HIGHLIGHT_GROUP)

    def _tree_nav_move(self, delta: int) -> None:
        visible = self._tree_view_screen.get_visible_nodes()
        if not visible:
            return
        selected = self._tree_view_screen.get_selected_node()
        if selected is None or selected not in visible:
            idx = 0 if delta > 0 else len(visible) - 1
        else:
            idx = max(0, min(len(visible) - 1, visible.index(selected) + delta))
        now = self._now()
        rapid = (now - self._last_tree_move_time) < _TITLE_RENDER_DEBOUNCE_SECS
        self._last_tree_move_time = now

        node = visible[idx]
        self._tree_view_screen.select_node(node)
        self._tree_view_screen.scroll_to_node(node)
        if isinstance(node, TitleTreeViewNode):
            if rapid or self._pending_title_node is not None:
                # Rapid scrolling (held key): defer the expensive title-view render
                # until the key presses settle.
                self._pending_title_node = node
                self._title_render_trigger.cancel()
                self._title_render_trigger()
            else:
                self._tree_view_manager.render_title_node(node)

    def _on_title_render_timeout(self, _dt: float) -> None:
        node, self._pending_title_node = self._pending_title_node, None
        if node is not None and self._tree_view_screen.get_selected_node() is node:
            self._tree_view_manager.render_title_node(node)

    def _cancel_pending_title_render(self) -> None:
        self._title_render_trigger.cancel()
        self._pending_title_node = None

    def _flush_pending_title_render(self) -> None:
        self._title_render_trigger.cancel()
        self._on_title_render_timeout(0.0)

    def _enter_nav_screen_bottom_focus(
        self,
        screen: HistoryScreen | IndexScreen | StatisticsScreen,
        node: BaseTreeViewNode,
    ) -> None:
        if screen.is_visible:
            self.enter_bottom_focus()
        else:
            self._tree_view_manager.activate_node(node)
            Clock.schedule_once(lambda _dt: self.enter_bottom_focus(), 0)

    def _tree_nav_activate(self) -> None:
        # A pending debounced title render is superseded: for a title node,
        # activate_node below re-renders synchronously anyway.
        self._cancel_pending_title_render()

        selected = self._tree_view_screen.get_selected_node()
        if selected is None:
            return

        # Map special nodes to their index screen for direct focus entry.
        index_node_to_screen: dict[int, IndexScreen] = {
            id(self._main_index_screen.treeview_index_node): self._main_index_screen,
            id(self._speech_index_screen.treeview_index_node): self._speech_index_screen,
            id(self._names_index_screen.treeview_index_node): self._names_index_screen,
            id(self._locations_index_screen.treeview_index_node): self._locations_index_screen,
            id(self._tree_view_manager.speech_words_node): self._speech_index_screen,
        }

        screen = index_node_to_screen.get(id(selected))
        if screen is not None:
            self._enter_nav_screen_bottom_focus(screen, selected)
            return

        if selected is self._tree_view_manager.statistics_node:
            self._enter_nav_screen_bottom_focus(self._statistics_screen, selected)
            return

        if selected is self._tree_view_manager.history_node:
            self._enter_nav_screen_bottom_focus(self._history_screen, selected)
            return

        was_closed = isinstance(selected, ButtonTreeViewNode) and not selected.is_open
        self._tree_view_manager.activate_node(selected)
        if isinstance(selected, TitleTreeViewNode):
            self._on_title_activated()
        elif self._search_screen.is_visible:
            Clock.schedule_once(lambda _dt: self.enter_bottom_focus(), 0)
        elif was_closed and isinstance(selected, ButtonTreeViewNode) and selected.nodes:
            Clock.schedule_once(lambda _dt: self._select_first_child(selected), 0)

    def _select_first_child(self, parent: ButtonTreeViewNode) -> None:
        visible = self._tree_view_screen.get_visible_nodes()
        try:
            parent_idx = next(i for i, n in enumerate(visible) if n is parent)
        except StopIteration:
            return
        if parent_idx + 1 < len(visible):
            child = visible[parent_idx + 1]
            self._tree_view_screen.select_node(child)
            if isinstance(child, TitleTreeViewNode):
                # Selecting alone only sets the tree's selection state; activating the
                # title node renders its info and portal button in the bottom panel.
                self._tree_view_manager.activate_node(child)

    def _tree_nav_collapse_to_parent(self) -> None:
        selected = self._tree_view_screen.get_selected_node()
        if selected is None:
            return
        if isinstance(selected, ButtonTreeViewNode) and selected.is_open and selected.nodes:
            self._tree_view_manager.activate_node(selected)
            return
        parent = selected.parent_node
        if not isinstance(parent, ButtonTreeViewNode):
            return
        if parent.is_open:
            self._tree_view_manager.activate_node(parent)  # selects + collapses
        else:
            self._tree_view_screen.select_node(parent)
        self._tree_view_screen.scroll_to_node(parent)

    def enter_bottom_focus_if_index_visible(self) -> None:
        logger.debug(f"Current focus region: {self._focus_region}.")
        self._auto_exited_bottom_focus = False
        if self._search_screen.is_visible:
            self._focus_region = _FocusRegion.BOTTOM
            self._update_bottom_focus_highlight()
            self._search_screen.enter_nav_focus_at_last_result(self.exit_bottom_focus)
        elif (
            self._main_index_screen.is_visible
            or self._speech_index_screen.is_visible
            or self._names_index_screen.is_visible
            or self._locations_index_screen.is_visible
        ):
            self.enter_bottom_focus()
