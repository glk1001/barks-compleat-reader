from __future__ import annotations

from pathlib import Path

from kivy.properties import (
    BooleanProperty,
    ColorProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.treeview import TreeViewNode

from barks_reader.random_title_images import FIT_MODE_COVER
from barks_reader.reader_tree_view_utils import find_node_by_path, find_tree_view_node

TREE_VIEW_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")


class TreeViewScreen(BoxLayout):
    """Screen for displaying the main tree view."""

    top_view_image_texture = ObjectProperty()
    top_view_image_fit_mode = StringProperty(FIT_MODE_COVER)
    top_view_image_color = ColorProperty()
    top_view_image_opacity = NumericProperty(0.0)

    main_files_not_loaded = BooleanProperty(defaultvalue=False)
    main_files_not_loaded_msg = StringProperty()

    def get_selected_node(self) -> TreeViewNode:
        return self.ids.reader_tree_view.selected_node

    def find_node_by_path(self, path_from_root: list[str]) -> TreeViewNode | None:
        return find_node_by_path(self.ids.reader_tree_view, list(reversed(path_from_root)))

    def goto_node(self, node_text: str) -> None:
        node = find_tree_view_node(self.ids.reader_tree_view.root, node_text)
        if node:
            self._close_open_nodes(self.ids.reader_tree_view.root)
            self._open_all_parent_nodes(node)
            self._goto_node(node)

    def select_node(self, node: TreeViewNode) -> None:
        self.ids.reader_tree_view.select_node(node)

    def scroll_to_node(self, node: TreeViewNode) -> None:
        self.ids.scroll_view.scroll_to(node, padding=50)

    def open_all_parent_nodes(self, node: TreeViewNode) -> None:
        # Get all the parent nodes first, then open from top parent down to last child.
        parent_nodes = []
        parent_node = node
        while parent_node and isinstance(parent_node, TreeViewNode):
            parent_nodes.append(parent_node)
            parent_node = parent_node.parent_node

        for parent_node in reversed(parent_nodes):
            if not parent_node.is_open:
                self.ids.reader_tree_view.toggle_node(parent_node)

    def deselect_and_close_open_nodes(self) -> None:
        for node in self.ids.reader_tree_view.iterate_open_nodes():
            self.ids.reader_tree_view.deselect_node(node)

            if node.is_open:
                self.ids.reader_tree_view.toggle_node(node)
                self._close_open_nodes(node)

    def _close_open_nodes(self, start_node: TreeViewNode) -> None:
        for node in start_node.nodes:
            if node.is_open:
                self.ids.reader_tree_view.toggle_node(node)
                self._close_open_nodes(node)
