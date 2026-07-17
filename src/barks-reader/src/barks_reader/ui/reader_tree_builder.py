"""Walk the core navigation-tree spec and build the Kivy tree-view widgets.

All tree *structure* (node texts, destinations, press behavior, lazy title
rows) is composed by `core.navigation.build_reader_tree_spec`; this module
only instantiates widgets from the specs, binds press handlers, and calls the
`TreeViewManager` 'node created' registration hooks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from comic_utils.timing import Timing
from kivy.metrics import dp
from loguru import logger

from barks_reader.core.navigation import (
    NodeKind,
    NodeRegistration,
    PressAction,
    SeriesDestination,
    YearRangeDestination,
    YearRangeKind,
    build_reader_tree_spec,
)

from .tree_view_nodes import (
    ButtonTreeViewNode,
    MainTreeViewNode,
    StoryGroupTreeViewNode,
    TitleTreeViewNode,
    YearRangeTreeViewNode,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

    from barks_reader.core.navigation import NodeSpec
    from barks_reader.core.reader_settings import ReaderSettings

    from .tree_view_manager import TreeViewManager
    from .tree_view_nodes import ReaderTreeBuilderEventDispatcher, ReaderTreeView

_YEAR_RANGE_KIND_TO_WIDTH: dict[YearRangeKind, float] = {
    YearRangeKind.CHRONO: dp(150),
    YearRangeKind.CS: dp(250),
    YearRangeKind.US: dp(250),
}

_NODE_CLASSES: dict[NodeKind, type[ButtonTreeViewNode]] = {
    NodeKind.MAIN: MainTreeViewNode,
    NodeKind.STORY_GROUP: StoryGroupTreeViewNode,
}


class ReaderTreeBuilder:
    def __init__(
        self,
        reader_settings: ReaderSettings,
        reader_tree_view: ReaderTreeView,
        reader_tree_events: ReaderTreeBuilderEventDispatcher,
        tree_view_manager: TreeViewManager,
        title_lists: dict[str, list[FantaComicBookInfo]],
        *,
        include_one_pagers_in_chrono: bool = False,
    ) -> None:
        self._reader_settings = reader_settings
        self._reader_tree_view = reader_tree_view
        self._reader_tree_events = reader_tree_events
        self._tree_view_manager = tree_view_manager
        self._title_lists = title_lists
        self._include_one_pagers_in_chrono = include_one_pagers_in_chrono
        self._tree_build_timing = Timing()
        self.chrono_year_range_nodes: dict[tuple[int, int], ButtonTreeViewNode] = {}
        self.series_nodes: dict[str, ButtonTreeViewNode] = {}

        self._press_handlers: dict[PressAction, Callable | None] = {
            PressAction.TOGGLE_ONLY: None,
            PressAction.SET_VIEW_STATE: tree_view_manager.set_view_state_for_node,
            PressAction.OPEN_INTRO_DOC: tree_view_manager.on_intro_doc_pressed,
            PressAction.OPEN_ARTICLE: tree_view_manager.on_article_node_pressed,
            PressAction.OPEN_CENSORSHIP_FIXES_DOC: (
                tree_view_manager.on_censorship_fixes_doc_pressed
            ),
            PressAction.OPEN_SPEECH_INDEX: tree_view_manager.on_speech_index_node_pressed,
            PressAction.OPEN_SPEECH_WORDS: tree_view_manager.on_speech_words_node_pressed,
            PressAction.OPEN_WIKI_INDEX: tree_view_manager.on_wiki_index_node_pressed,
        }
        assert set(self._press_handlers) == set(PressAction), (
            "every PressAction needs a press-handler entry (TOGGLE_ONLY maps to None)"
        )
        self._registration_hooks: dict[NodeRegistration, Callable] = {
            NodeRegistration.SEARCH: tree_view_manager.on_search_node_created,
            NodeRegistration.HISTORY: tree_view_manager.on_history_node_created,
            NodeRegistration.STATISTICS: tree_view_manager.on_statistics_node_created,
            NodeRegistration.MAIN_INDEX: tree_view_manager.on_main_index_node_created,
            NodeRegistration.SPEECH_INDEX: tree_view_manager.on_speech_index_node_created,
            NodeRegistration.SPEECH_WORDS: tree_view_manager.on_speech_words_node_created,
            NodeRegistration.NAMES_INDEX: tree_view_manager.on_names_index_node_created,
            NodeRegistration.LOCATIONS_INDEX: tree_view_manager.on_locations_index_node_created,
        }

    def build_main_screen_tree(self) -> None:
        """Build the whole tree-view widget hierarchy from the core tree spec."""
        self._tree_build_timing.restart()

        logger.debug("Building the reader tree from the navigation tree spec...")
        specs = build_reader_tree_spec(
            self._reader_settings,
            self._title_lists,
            include_one_pagers_in_chrono=self._include_one_pagers_in_chrono,
        )
        for spec in specs:
            self._add_node(spec, parent=None)

        self._reader_tree_view.bind(minimum_height=self._reader_tree_view.setter("height"))

        elapsed_time = self._tree_build_timing.get_elapsed_time_with_unit()
        logger.info(f"Finished loading all nodes in {elapsed_time}.")

        self._reader_tree_events.finished_building()

    def _add_node(self, spec: NodeSpec, parent: ButtonTreeViewNode | None) -> None:
        if spec.kind is NodeKind.TITLE_ROW:
            assert spec.fanta_info is not None
            title_node = TitleTreeViewNode.create_from_fanta_info(
                spec.fanta_info, self._tree_view_manager.on_title_row_button_pressed
            )
            self._reader_tree_view.add_node(title_node, parent=parent)
            return

        node = self._make_button_node(spec)

        handler = self._press_handlers[spec.press_action]
        if handler is not None:
            node.bind(on_press=handler)

        node = self._reader_tree_view.add_node(node, parent=parent)

        if spec.start_closed:
            node.saved_state["open"] = False

        if spec.register_as is not None:
            self._registration_hooks[spec.register_as](node)

        self._collect_lookup_node(spec, node)

        for child_spec in spec.children:
            self._add_node(child_spec, parent=node)

        if spec.lazy_children is not None:
            self._defer_node_population(node, spec.lazy_children)

    @staticmethod
    def _make_button_node(spec: NodeSpec) -> ButtonTreeViewNode:
        if spec.kind is NodeKind.YEAR_RANGE:
            assert spec.year_range_kind is not None
            return YearRangeTreeViewNode(
                text=spec.text,
                destination=spec.destination,
                NODE_WIDTH=_YEAR_RANGE_KIND_TO_WIDTH[spec.year_range_kind],
            )

        return _NODE_CLASSES[spec.kind](text=spec.text, destination=spec.destination)

    def _collect_lookup_node(self, spec: NodeSpec, node: ButtonTreeViewNode) -> None:
        """Index the nodes the `NavigationCoordinator` needs for goto-title flows."""
        destination = spec.destination
        if (
            isinstance(destination, YearRangeDestination)
            and destination.kind is YearRangeKind.CHRONO
        ):
            self.chrono_year_range_nodes[(destination.start, destination.end)] = node
        elif isinstance(destination, SeriesDestination):
            self.series_nodes[destination.series_name] = node

    def _defer_node_population(
        self,
        node: ButtonTreeViewNode,
        make_children_specs: Callable[[], tuple[NodeSpec, ...]],
    ) -> None:
        """Defer creating *node*'s title children until the node is first expanded."""

        def _populate() -> None:
            for child_spec in make_children_specs():
                self._add_node(child_spec, parent=node)

        node.populate_callback = _populate
        node.populated = False
        node.is_leaf = False
