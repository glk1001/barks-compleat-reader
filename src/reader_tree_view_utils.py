import logging
from typing import List, Union, cast

from kivy.uix.treeview import TreeViewNode

from barks_fantagraphics.barks_titles import Titles
from reader_formatter import get_clean_text_without_extra
from reader_ui_classes import (
    ReaderTreeView,
    TitleTreeViewNode,
    TitleSearchBoxTreeViewNode,
    TagSearchBoxTreeViewNode,
    ButtonTreeViewNode,
)


def get_tree_view_node_path(node: TreeViewNode) -> List[str]:
    node_path = [get_tree_view_node_id_text(node)]
    node = node.parent_node
    while node:
        node_path.append(get_tree_view_node_id_text(node))
        node = node.parent_node

    return node_path


def find_node_by_path(tree: ReaderTreeView, path_from_root: List[str]) -> Union[TreeViewNode, None]:
    """
    Finds a node in a TreeView by its path from the root.
    Expands parent nodes along the way to make the target node visible.
    """
    if not path_from_root:
        return None

    current_nodes = tree.root.nodes
    node_path = path_from_root[1:]
    found_node = None

    # Iterate through each text component in the path (e.g., "Chronological", "1942-1943", ...)
    for i, node_text in enumerate(node_path):
        node_in_path = None
        for node in current_nodes:
            if get_tree_view_node_id_text(node) == node_text:
                node_in_path = node
                break

        if not node_in_path:
            logging.warning(
                f"Could not find node '{node_text}' in path. The tree structure may have changed."
            )
            return None

        # If this is the last node in the path, we've found our target.
        if i == (len(node_path) - 1):
            found_node = node_in_path
            break

        # Otherwise, expand the current node to make its children accessible and visible.
        if not node_in_path.is_open:
            tree.toggle_node(node_in_path)

        current_nodes = node_in_path.nodes

    return found_node


def get_tree_view_node_id_text(node: TreeViewNode) -> str:
    if type(node) == TitleTreeViewNode:
        return cast(TitleTreeViewNode, node).get_title().name
    if type(node) == TitleSearchBoxTreeViewNode:
        return cast(TitleSearchBoxTreeViewNode, node).name
    if type(node) == TagSearchBoxTreeViewNode:
        return cast(TagSearchBoxTreeViewNode, node).name

    return get_clean_text_without_extra(cast(ButtonTreeViewNode, node).text)


def find_tree_view_node(start_node: TreeViewNode, node_text: str):
    nodes_to_visit = start_node.nodes.copy()

    while nodes_to_visit:
        current_node = nodes_to_visit.pop()
        if not hasattr(current_node, "text"):
            continue
        current_node_text = get_clean_text_without_extra(current_node.text)
        if current_node_text == node_text:
            return current_node
        nodes_to_visit.extend(current_node.nodes)

    return None


def find_tree_view_title_node(start_node: TreeViewNode, target_title: Titles):
    nodes_to_visit = start_node.nodes.copy()

    while nodes_to_visit:
        current_node = nodes_to_visit.pop()
        node_title = current_node.get_title()
        if node_title == target_title:
            return current_node
        nodes_to_visit.extend(current_node.nodes)

    return None
