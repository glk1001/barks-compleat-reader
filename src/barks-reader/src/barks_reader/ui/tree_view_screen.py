from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ColorProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout

from barks_reader.core.random_title_images import FIT_MODE_COVER
from barks_reader.core.reader_settings import BARKS_READER_SECTION, SHOW_TOP_VIEW_TITLE_INFO
from barks_reader.core.settings_notifier import settings_notifier
from barks_reader.ui.reader_tree_view_utils import find_node_by_path
from barks_reader.ui.reader_ui_classes import ARROW_WIDTH, BaseTreeViewNode

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_reader.core.reader_settings import ReaderSettings

TREE_VIEW_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")


class TreeViewScreen(BoxLayout):
    """Screen for displaying the main tree view."""

    top_view_image_texture = ObjectProperty()
    top_view_image_fit_mode = StringProperty(FIT_MODE_COVER)
    top_view_image_color = ColorProperty()
    top_view_image_opacity = NumericProperty(0.0)
    current_title_str = StringProperty()
    show_current_title = BooleanProperty(defaultvalue=False)

    DOWN_ARROW_WIDTH = ARROW_WIDTH

    main_files_not_loaded = BooleanProperty(defaultvalue=False)
    main_files_not_loaded_msg = StringProperty()

    def __init__(self, reader_settings: ReaderSettings, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.on_goto_title: Callable[[], None] | None = None
        self._reader_settings = reader_settings
        self.show_current_title = self._reader_settings.show_top_view_title_info

        settings_notifier.register_callback(
            BARKS_READER_SECTION, SHOW_TOP_VIEW_TITLE_INFO, self.on_change_show_current_title
        )

    def set_title(self, title: Titles | None) -> None:
        self.current_title_str = "" if title is None else BARKS_TITLES[title]

    def get_selected_node(self) -> BaseTreeViewNode | None:
        return self.ids.reader_tree_view.selected_node

    def find_node_by_path(self, path_from_root: list[str]) -> BaseTreeViewNode | None:
        return find_node_by_path(self.ids.reader_tree_view, list(reversed(path_from_root)))

    def select_node(self, node: BaseTreeViewNode) -> None:
        self.ids.reader_tree_view.select_node(node)

    def scroll_to_node(self, node: BaseTreeViewNode) -> None:
        self.ids.scroll_view.scroll_to(node, padding=50)

    def open_all_parent_nodes(self, node: BaseTreeViewNode) -> None:
        # Get all the parent nodes first, then open from top parent down to last child.
        parent_nodes = []
        parent_node = node
        while parent_node and isinstance(parent_node, BaseTreeViewNode):
            parent_nodes.append(parent_node)
            parent_node = parent_node.parent_node

        for parent_node in reversed(parent_nodes):
            if not parent_node.is_open:
                self.ids.reader_tree_view.toggle_node(parent_node)

    def deselect_and_close_open_nodes(self) -> int:
        selected_node = self.ids.reader_tree_view.selected_node
        if selected_node:
            self.ids.reader_tree_view.deselect_node(selected_node)

        num_opened_nodes = self._close_open_nodes(self.ids.reader_tree_view.root)

        self.ids.reader_tree_view.reset_selection_tracking()

        return num_opened_nodes

    def _close_open_nodes(self, start_node: BaseTreeViewNode) -> int:
        count = 0
        for node in start_node.nodes:
            if node.is_open:
                count += 1
                count += self._close_open_nodes(node)
                self.ids.reader_tree_view.toggle_node(node)
        return count

    def on_change_show_current_title(self) -> None:
        self.show_current_title = self._reader_settings.show_top_view_title_info
