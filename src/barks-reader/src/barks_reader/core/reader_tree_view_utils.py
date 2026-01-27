from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

from loguru import logger

if TYPE_CHECKING:
    from barks_fantagraphics.barks_titles import Titles


class BaseTreeViewNodeProtocol(Protocol):
    parent_node: BaseTreeViewNodeProtocol
    nodes: list[BaseTreeViewNodeProtocol]
    level: int
    is_open: bool

    def get_name(self) -> str: ...


class TitleTreeViewNodeProtocol(BaseTreeViewNodeProtocol):
    def get_title(self) -> Titles: ...  # ty:ignore[empty-body]


class ReaderTreeViewProtocol(Protocol):
    root: BaseTreeViewNodeProtocol

    def toggle_node(self, node: BaseTreeViewNodeProtocol) -> None: ...


def get_tree_view_node_path(node: BaseTreeViewNodeProtocol) -> list[str]:
    node_path = [node.get_name()]
    current = node.parent_node
    while current:
        if current.level == 0:
            node_path.append("root")
        else:
            node_path.append(current.get_name())
        current = current.parent_node

    return node_path


def find_and_expand_node_by_path(
    tree: ReaderTreeViewProtocol, path_from_root: list[str]
) -> BaseTreeViewNodeProtocol | None:
    """Find a node in a TreeView by its path from the root.

    Expands parent nodes along the way to make the target node visible.
    """
    if not path_from_root:
        return None

    current_nodes = tree.root.nodes
    node_path = path_from_root[1:]
    found_node = None

    # Iterate through each text component in the path (e.g., "Chronological", "1942-1943", ...)
    for i, node_text in enumerate(node_path):
        node_in_path = next((n for n in current_nodes if n.get_name() == node_text), None)

        if not node_in_path:
            logger.warning(
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


def find_tree_view_node(
    start_node: BaseTreeViewNodeProtocol, node_text: str
) -> BaseTreeViewNodeProtocol | None:
    nodes_to_visit = start_node.nodes.copy()

    while nodes_to_visit:
        current_node = nodes_to_visit.pop()
        if current_node.get_name() == node_text:
            return current_node
        nodes_to_visit.extend(current_node.nodes)

    return None


def find_tree_view_title_node(
    nodes: list[TitleTreeViewNodeProtocol], target_title: Titles
) -> BaseTreeViewNodeProtocol | None:
    nodes_to_visit = nodes.copy()

    while nodes_to_visit:
        current_node = nodes_to_visit.pop()
        if current_node.get_title() == target_title:
            return current_node
        nodes_to_visit.extend(cast("list[TitleTreeViewNodeProtocol]", current_node.nodes))

    return None
