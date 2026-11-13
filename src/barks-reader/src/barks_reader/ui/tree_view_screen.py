from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[import-not-found]
    BooleanProperty,
    ColorProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout

from barks_reader.core.image_selector import FIT_MODE_COVER
from barks_reader.core.main_layout import MainLayoutMode
from barks_reader.core.reader_formatter import get_display_title_str
from barks_reader.core.reader_settings import BARKS_READER_SECTION, SHOW_TOP_VIEW_TITLE_INFO
from barks_reader.core.reader_tree_view_utils import find_and_expand_node_by_path
from barks_reader.core.settings_notifier import settings_notifier

# CollapseParentOverlay must be imported (Factory-registered) before tree_view_screen.kv's
# rule that instantiates it is loaded: it has no kv file of its own to bring it in.
from .collapse_parent_overlay import CollapseParentOverlay  # noqa: F401
from .reader_keyboard_nav import clear_focus_highlight, draw_focus_highlight
from .tree_view_nodes import BaseTreeViewNode

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_titles import Titles

    from barks_reader.core.reader_settings import ReaderSettings

    from .tree_view_nodes import ButtonTreeViewNode

TREE_VIEW_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

_TOP_GOTO_FOCUS_GROUP = "top_goto_focus"


class TreeViewScreen(BoxLayout):
    """Screen for displaying the main tree view."""

    top_view_image_texture = ObjectProperty()
    top_view_image_fit_mode = StringProperty(FIT_MODE_COVER)
    top_view_image_color = ColorProperty()
    top_view_image_opacity = NumericProperty(0.0)
    # The book's layout (core.main_layout), and whether the tree is shut to its top rows.
    layout_mode = StringProperty(MainLayoutMode.SINGLE.value)
    tree_collapsed = BooleanProperty(defaultvalue=False)
    current_title_str = StringProperty()
    show_current_title = BooleanProperty(defaultvalue=False)

    main_files_not_loaded = BooleanProperty(defaultvalue=False)
    main_files_not_loaded_msg = StringProperty()

    def __init__(self, reader_settings: ReaderSettings, **kwargs: object) -> None:
        super().__init__(**kwargs)
        # Takes a ``from_keyboard`` keyword (defaulted by the handler) so it can tell the
        # kv-wired pointer press from a keyboard activation. See activate_top_goto.
        self.on_goto_title: Callable[..., None] | None = None
        self._reader_settings = reader_settings
        self.show_current_title = self._reader_settings.show_top_view_title_info

        settings_notifier.register_callback(
            BARKS_READER_SECTION, SHOW_TOP_VIEW_TITLE_INFO, self.on_change_show_current_title
        )

    def setup_collapse_overlay(self, on_collapse: Callable[[ButtonTreeViewNode], None]) -> None:
        """Wire up the collapse-parent overlay after KV post-init."""
        overlay = self.ids.collapse_parent_overlay
        overlay.setup(self.ids.scroll_view)
        overlay.on_collapse_request = on_collapse

    def set_title(self, title: Titles | None) -> None:
        """Caption the top view with the title its image is from, or with nothing."""
        self.current_title_str = get_display_title_str(title)

    # --- Top-view "Goto Title" keyboard nav ---
    # A thin API driven by MainScreenNavigation: the top-view goto arrow is a focus
    # sub-stop of the tree region, reached by Up from the first tree node.

    @property
    def is_top_goto_active(self) -> bool:
        """Whether the top-view goto arrow can be activated (a real title is present).

        Gates keyboard entry; independent of the ``show_current_title`` label setting.
        """
        return self.current_title_str != ""

    def enter_top_goto_focus(self) -> None:
        """Draw the keyboard focus ring on the top-view goto arrow button."""
        draw_focus_highlight(self.ids.goto_title_overlay.goto_button, _TOP_GOTO_FOCUS_GROUP)

    def exit_top_goto_focus(self) -> None:
        """Clear the keyboard focus ring from the top-view goto arrow button."""
        clear_focus_highlight(self.ids.goto_title_overlay.goto_button, _TOP_GOTO_FOCUS_GROUP)

    def activate_top_goto(self) -> None:
        """Fire the top-view goto arrow from the keyboard.

        Calls the kv-wired ``on_goto_title`` directly, flagged as a keyboard
        activation, rather than dispatching the overlay's ``on_goto_press`` — that
        event is the pointer path, and the handler must tell the two apart to keep a
        mouse click in mouse mode.
        """
        if self.on_goto_title is not None:
            self.on_goto_title(from_keyboard=True)

    def press_top_goto(self) -> None:
        """Fire the top-view goto arrow from a mouse press or a touch.

        The handler is wired once the main screen is built: a press before then,
        with the arrow already on show, does nothing.
        """
        if self.on_goto_title is not None:
            self.on_goto_title()

    def get_selected_node(self) -> BaseTreeViewNode | None:
        """Return the tree's selected node, or None."""
        return self.ids.reader_tree_view.selected_node

    def find_node_by_path(self, path_from_root: list[str]) -> BaseTreeViewNode | None:
        """Return the node at `path_from_root` (leaf first), opening the nodes on the way."""
        # noinspection PyUnnecessaryCast
        return cast(
            "BaseTreeViewNode | None",
            find_and_expand_node_by_path(self.ids.reader_tree_view, list(reversed(path_from_root))),
        )

    def select_node(self, node: BaseTreeViewNode) -> None:
        """Select `node` in the tree."""
        self.ids.reader_tree_view.select_node(node)

    def open_node(self, node: BaseTreeViewNode) -> None:
        """Open `node` if it is closed."""
        if not node.is_open:
            self.ids.reader_tree_view.toggle_node(node)

    def scroll_to_node(self, node: BaseTreeViewNode) -> None:
        """Scroll the tree so `node` shows, clear of the view's edge."""
        self.ids.scroll_view.scroll_to(node, padding=dp(50))

    def is_node_shown(self, node: ButtonTreeViewNode) -> bool:
        """Return whether `node`'s row lies wholly within the tree's viewport."""
        scroll_view = self.ids.scroll_view
        view_bottom = scroll_view.to_window(0, scroll_view.y)[1]
        view_top = scroll_view.to_window(0, scroll_view.top)[1]
        row_bottom = node.to_window(0, node.y)[1]
        row_top = node.to_window(0, node.top)[1]
        return view_bottom <= row_bottom and row_top <= view_top

    def open_all_parent_nodes(self, node: BaseTreeViewNode) -> None:
        """Open every parent of `node`, from the top down; `node` itself is left as it is."""
        # Get all the parent nodes first, then open from top parent down to last parent.
        parent_nodes = []
        parent_node = node.parent_node
        while parent_node and isinstance(parent_node, BaseTreeViewNode):
            parent_nodes.append(parent_node)
            parent_node = parent_node.parent_node

        for parent_node in reversed(parent_nodes):
            if not parent_node.is_open:
                self.ids.reader_tree_view.toggle_node(parent_node)

    def open_node_and_all_parent_nodes(self, node: BaseTreeViewNode) -> None:
        """Open every parent of `node`, from the top down, then `node`."""
        self.open_all_parent_nodes(node)
        self.open_node(node)

    def deselect_and_close_open_nodes(self) -> int:
        """Deselect the selected node and close every open one.

        Returns:
            How many nodes were open.

        """
        selected_node = self.ids.reader_tree_view.selected_node
        if selected_node:
            self.ids.reader_tree_view.deselect_node(selected_node)

        num_opened_nodes = self._close_open_nodes(self.ids.reader_tree_view.root)

        self.ids.reader_tree_view.reset_selection_tracking()

        return num_opened_nodes

    def _close_open_nodes(self, start_node: BaseTreeViewNode) -> int:
        count = 0
        for node in start_node.nodes:
            # A closed node's children are looked at too: closing it left them open,
            # to show open again the next time it is.
            count += self._close_open_nodes(node)
            if node.is_open:
                count += 1
                self.ids.reader_tree_view.toggle_node(node)
        return count

    def get_visible_nodes(self) -> list[BaseTreeViewNode]:
        """Return all currently visible (open), selectable nodes in display order.

        Nodes flagged `no_selection` (the playlist intro paragraphs) are skipped:
        this list drives keyboard navigation, which must never land on a node the
        tree view refuses to select.
        """
        nodes: list[BaseTreeViewNode] = []

        def collect(parent: BaseTreeViewNode) -> None:
            for child in parent.nodes:
                if isinstance(child, BaseTreeViewNode) and not child.no_selection:
                    nodes.append(child)
                    if child.is_open:
                        collect(child)

        collect(self.ids.reader_tree_view.root)
        return nodes

    def on_change_show_current_title(self) -> None:
        """Take up the setting for showing the top view's title."""
        self.show_current_title = self._reader_settings.show_top_view_title_info
