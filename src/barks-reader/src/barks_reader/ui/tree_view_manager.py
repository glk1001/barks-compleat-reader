from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from comic_utils.timing import Timing
from kivy.clock import Clock
from loguru import logger

from barks_reader.core.navigation import (
    ArticleDestination,
    NavigationModel,
    TitleDestination,
)
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.reader_consts_and_types import (
    APPENDIX_CENSORSHIP_FIXES_NODE_TEXT,
    INTRO_COMPLEAT_BARKS_READER_TEXT,
)
from barks_reader.core.reader_formatter import get_clean_text_without_extra

from .tree_view_nodes import (
    BaseTreeViewNode,
    ButtonTreeViewNode,
    MainTreeViewNode,
    TitleTreeViewNode,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from kivy.uix.button import Button
    from kivy.uix.scrollview import ScrollView

    from barks_reader.core.system_file_paths import SystemFilePaths

    from .collapse_parent_overlay import CollapseParentOverlay
    from .navigation_coordinator import NavigationCoordinator
    from .screen_bundle import ScreenBundle
    from .tree_view_nodes import ReaderTreeView
    from .view_renderer import ViewRenderer


class TreeViewManager:
    """Manage all interactions and events related to the TreeView."""

    def __init__(
        self,
        renderer: ViewRenderer,
        screens: ScreenBundle,
        nav_coordinator: NavigationCoordinator,
        sys_file_paths: SystemFilePaths | None = None,
        nav_model: NavigationModel | None = None,
    ) -> None:
        self._renderer = renderer
        self._tree_view_screen = screens.tree_view
        self._main_index_screen = screens.main_index
        self._speech_index_screen = screens.speech_index
        self._names_index_screen = screens.names_index
        self._locations_index_screen = screens.locations_index

        self._tree_view_screen.ids.reader_tree_view.bind(on_node_expand=self.on_node_expanded)
        self._tree_view_screen.ids.reader_tree_view.bind(on_node_collapse=self.on_node_collapsed)

        self._nav = nav_coordinator
        self._sys_file_paths = sys_file_paths
        self._nav_model = nav_model or NavigationModel()

        self._allow_view_state_change = True
        self._search_node: MainTreeViewNode | None = None
        self._speech_words_node: ButtonTreeViewNode | None = None

        self._statistics_node: ButtonTreeViewNode | None = None

        self._tree_view_screen.setup_collapse_overlay(self._on_collapse_overlay_pressed)

    @property
    def _collapse_overlay(self) -> CollapseParentOverlay:
        return self._tree_view_screen.ids.collapse_parent_overlay

    def activate_node(self, node: BaseTreeViewNode) -> None:
        """Activate a node as if pressed, without collapsing the rest of the tree."""
        self._tree_view_screen.select_node(node)
        if isinstance(node, TitleTreeViewNode):
            self._handle_title_node_selection(node)
        elif isinstance(node, ButtonTreeViewNode):
            node.trigger_action()

    def setup_and_select_node(self, node: BaseTreeViewNode) -> None:
        logger.debug(f'Selecting and setting up node "{node.get_name()}".')

        # noinspection PyArgumentList
        with self.suppress_view_state_changes():
            self._tree_view_screen.deselect_and_close_open_nodes()
            self._tree_view_screen.open_all_parent_nodes(node)

        self._tree_view_screen.open_node(node)
        self._tree_view_screen.select_node(node)

        if isinstance(node, TitleTreeViewNode):
            self._handle_title_node_selection(node)
        elif isinstance(node, ButtonTreeViewNode):
            self._handle_button_node_selection(node)

    def _handle_title_node_selection(self, node: TitleTreeViewNode) -> None:
        from .navigation_coordinator import TitleTarget  # noqa: PLC0415

        assert isinstance(node.destination, TitleDestination)
        self._nav.select_title(TitleTarget(fanta_info=node.destination.fanta_info))
        self.scroll_to_node(node)

    def _handle_button_node_selection(self, node: ButtonTreeViewNode) -> None:
        if node.saved_state.get("open", True):
            node.trigger_action()
        elif node.destination is not None:
            self._renderer.render(node.destination)

    def deselect_and_close_open_nodes(self, *, from_collapse_all: bool = False) -> None:
        # noinspection PyArgumentList
        with self.suppress_view_state_changes():
            num_opened_nodes = self._tree_view_screen.deselect_and_close_open_nodes()

        if num_opened_nodes > 0:
            self._renderer.render_state(ViewStates.INITIAL)

        if from_collapse_all:
            self._collapse_overlay.clear_tracking()

    def _on_collapse_overlay_pressed(self, node: ButtonTreeViewNode) -> None:
        """Handle a tap on the collapse-parent overlay bar."""
        if node.is_open:
            self._tree_view_screen.ids.reader_tree_view.toggle_node(node)
        self._tree_view_screen.select_node(node)
        self._tree_view_screen.scroll_to_node(node)

    def open_node_and_parent_nodes(self, node: ButtonTreeViewNode) -> None:
        # noinspection PyArgumentList
        with self.suppress_view_state_changes():
            self._tree_view_screen.open_node_and_all_parent_nodes(node)

    def go_back_to_previous_node(self) -> None:
        if not self._tree_view_screen.ids.reader_tree_view.previous_selected_node:
            self.deselect_and_close_open_nodes(from_collapse_all=True)
            return

        logger.info(
            f"Going back to previous node"
            f' "{self._tree_view_screen.ids.reader_tree_view.previous_selected_node.get_name()}".'
        )
        self.setup_and_select_node(
            self._tree_view_screen.ids.reader_tree_view.previous_selected_node
        )

    def goto_node(self, node: BaseTreeViewNode, scroll_to: bool = False) -> None:
        def show_node(n: BaseTreeViewNode) -> None:
            self._tree_view_screen.select_node(n)
            if scroll_to:
                self.scroll_to_node(n)

        Clock.schedule_once(lambda _dt, item=node: show_node(item), 0)

    def scroll_to_node(self, node: BaseTreeViewNode) -> None:
        Clock.schedule_once(lambda _dt: self._tree_view_screen.scroll_to_node(node), 0)

    def allow_view_state_change(self) -> None:
        self._allow_view_state_change = True

    def disallow_view_state_change(self) -> None:
        self._allow_view_state_change = False

    @contextmanager
    def suppress_view_state_changes(self) -> Iterator[None]:
        self.disallow_view_state_change()
        try:
            yield
        finally:
            self.allow_view_state_change()

    def on_node_collapsed(self, _tree: ReaderTreeView, node: ButtonTreeViewNode) -> None:
        # The tracked node may have been collapsed (e.g. via left-arrow key).
        self._collapse_overlay.recheck_visibility()

        # Check allow state change flag or is leaf/title row.
        if not self._allow_view_state_change or isinstance(node, TitleTreeViewNode):
            logger.info(f"Node collapsed but not allowing state change: '{node.get_name()}'.")
            return

        logger.info(f"Node collapsed: '{node.get_name()}'.")

        self.set_view_state_for_node(node)

    def set_view_state_for_node(self, node: ButtonTreeViewNode) -> None:
        if node.destination is None:
            msg = f"Node has no destination: '{node.get_name()}' ({type(node)})"
            raise RuntimeError(msg)
        self._renderer.render(node.destination)

    def on_node_expanded(self, _tree: ReaderTreeView, node: ButtonTreeViewNode) -> None:
        logger.info(f"Node expanded: '{node.get_name()}'.")

        # Always track the expanded node for the collapse overlay, even when
        # view-state changes are suppressed (e.g. during goto-title navigation).
        if not isinstance(node, TitleTreeViewNode):
            self._collapse_overlay.track_node(node)

        if not self._allow_view_state_change or isinstance(node, TitleTreeViewNode):
            logger.info(f"Node opened but not allowing state change: '{node.get_name()}'.")
            # No stabilization will run on this path, so lift the suppression
            # that track_node just set — otherwise end_suppression is never called.
            self._collapse_overlay.end_suppression()
            return

        # 1) Collapse any previously-open group (reduces height shocks).
        #    Suppress view-state changes so the sibling collapse doesn't update
        #    the top background image before we get to step 3.
        # noinspection PyArgumentList
        with self.suppress_view_state_changes():
            self._close_siblings(node)

        # 2) Lazy populate ONCE, while pinning the parent's position to avoid a jump.
        if node.populate_callback and not node.populated:
            self._pin_parent_position_while_populating(node, run_populate=True)
            node.populated = True
        else:
            # If already populated, we still pin during expand so second (and later) expansions
            # keep the parent row stationary.
            self._pin_parent_position_while_populating(node, run_populate=False)

        # 3) View-state logic.
        if self._has_single_title_child(node):
            # Single-child node: skip the intermediate tag view state and go straight
            # to selecting the title.  This avoids a visible flicker where the tag's
            # fun-image briefly appears before the title view replaces it.
            logger.info(f"Single-child node '{node.get_name()}': auto-selecting only title.")
            self._auto_select_single_child(node)
        else:
            self.set_view_state_for_node(node)

        # 4) NOTE: Do not call scroll_to_node() here — that causes the "snap-to-top/bottom" jump.

    @staticmethod
    def _has_single_title_child(node: ButtonTreeViewNode) -> bool:
        """Return True if the node has exactly one TitleTreeViewNode child."""
        title_children = [c for c in node.nodes if isinstance(c, TitleTreeViewNode)]
        return len(title_children) == 1

    def _auto_select_single_child(self, node: ButtonTreeViewNode) -> None:
        """Auto-select the only TitleTreeViewNode child synchronously.

        Caller must have already verified that the node has exactly one title child.
        Skips the intermediate tag view state and goes directly to the title,
        preserving the top background image.
        """
        from .navigation_coordinator import TitleTarget  # noqa: PLC0415

        only_child = next(c for c in node.nodes if isinstance(c, TitleTreeViewNode))
        self._tree_view_screen.select_node(only_child)
        assert isinstance(only_child.destination, TitleDestination)
        fanta_info = only_child.destination.fanta_info
        tag = (
            self._nav_model.tag_context(node.destination) if node.destination is not None else None
        )
        self._nav.select_title(TitleTarget(fanta_info=fanta_info, tag=tag), preserve_top_view=True)
        # Don't call scroll_to_node here — the parent is already being pinned in view
        # by _pin_parent_position_while_populating and the child is right below it.

    def _close_siblings(self, node: ButtonTreeViewNode) -> None:
        parent = node.parent_node
        if not parent:
            return
        for sibling in parent.nodes:
            if sibling != node and sibling.is_open:
                self._tree_view_screen.ids.reader_tree_view.toggle_node(sibling)

    def _pin_parent_position_while_populating(
        self, parent_node: ButtonTreeViewNode, run_populate: bool
    ) -> None:
        """Keep the expanding parent row visually pinned while its children are created.

        This should make it behave like a dropdown (no jump).
        """
        scroll_view = self._tree_view_screen.ids.scroll_view

        # Container inside the ScrollView (the thing whose height changes).
        if not scroll_view.children:
            return

        timing = Timing()
        try:
            # Compute current offset of the parent row's *top* relative to the ScrollView's top.
            sv_top_win_y = scroll_view.to_window(0, scroll_view.top)[1]
            parent_top_win_y = parent_node.to_window(0, parent_node.top)[1]
            target_offset_px = parent_top_win_y - sv_top_win_y  # we want to keep this constant

            # Optionally populate children now (lazy load for first expand).
            if run_populate and parent_node.populate_callback:
                parent_node.populate_callback()

            checks: dict[str, float] = {"count": 0, "last_h": -1, "stable": 0}

            Clock.schedule_once(
                lambda dt: self._stabilize_scroll_after_layout(
                    dt, parent_node, scroll_view, target_offset_px, checks
                ),
                0,
            )
        finally:
            logger.debug(
                f"Populated node '{get_clean_text_without_extra(parent_node.text)}'"
                f" in {timing.get_elapsed_time_with_unit()}."
            )

    def _stabilize_scroll_after_layout(
        self,
        _dt: float,
        parent_node: ButtonTreeViewNode,
        scroll_view: ScrollView,
        target_offset_px: float,
        checks: dict[str, float],
    ) -> None:
        # If user collapsed or navigated away, stop.
        if not parent_node.is_open:
            self._collapse_overlay.end_suppression()
            return

        def _resched() -> None:
            checks["count"] += 1
            if checks["count"] < 180:  # ~3 seconds worst-case @ 60fps  # noqa: PLR2004
                Clock.schedule_once(
                    lambda dt: self._stabilize_scroll_after_layout(
                        dt, parent_node, scroll_view, target_offset_px, checks
                    ),
                    0,
                )
            else:
                self._collapse_overlay.end_suppression()

        if not scroll_view.children:
            _resched()
            return

        cont = scroll_view.children[0]
        viewport_h = scroll_view.height
        cont_h = cont.height

        # Require non-trivial content to avoid div-by-zero and false positives.
        if (cont_h <= 1) or (viewport_h <= 1) or (cont_h <= viewport_h):
            _resched()
            return

        # Check stabilization of container height
        if abs(cont_h - checks["last_h"]) < 0.5:  # noqa: PLR2004
            checks["stable"] += 1
        else:
            checks["stable"] = 0
        checks["last_h"] = cont_h

        if checks["stable"] < 2:  # noqa: PLR2004
            _resched()
            return

        # Current offset (parent top relative to SV top) *after* expansion
        sv_top = scroll_view.to_window(0, scroll_view.top)[1]
        new_parent_top = parent_node.to_window(0, parent_node.top)[1]
        current_offset_px = new_parent_top - sv_top

        # How far did the parent drift? Positive means it moved DOWN on screen.
        delta_px = current_offset_px - target_offset_px
        if abs(delta_px) < 0.5:  # noqa: PLR2004
            self._collapse_overlay.end_suppression()
            return  # nothing to adjust

        # Convert pixel delta to normalized scroll_y delta:
        #  - Kivy uses scroll_y 0..1 where 1 = top, 0 = bottom.
        #  - Moving content up by +delta_px means increase scroll_y.
        denominator = cont_h - viewport_h
        if denominator <= 0:
            self._collapse_overlay.end_suppression()
            return

        delta_norm = delta_px / denominator
        new_scroll_y = self._clamp01(scroll_view.scroll_y + delta_norm)

        # Apply in one shot (no animation to avoid visible bounce)
        scroll_view.scroll_y = new_scroll_y
        self._collapse_overlay.end_suppression()

    @staticmethod
    def _clamp01(v: float) -> float:
        return 0.0 if v < 0.0 else (min(v, 1.0))

    def on_title_row_button_pressed(self, button: Button) -> None:
        from .navigation_coordinator import TitleTarget  # noqa: PLC0415

        title_node = button.parent
        assert isinstance(title_node.destination, TitleDestination)
        fanta_info = title_node.destination.fanta_info

        parent_node = title_node.parent_node
        parent_destination = getattr(parent_node, "destination", None)
        tag = (
            self._nav_model.tag_context(parent_destination)
            if parent_destination is not None
            else None
        )

        self._nav.select_title(TitleTarget(fanta_info=fanta_info, tag=tag))

    def on_intro_doc_pressed(self, _button: Button) -> None:
        assert self._sys_file_paths
        self._nav.open_document(
            self._sys_file_paths.get_intro_doc_dir(),
            INTRO_COMPLEAT_BARKS_READER_TEXT,
            ViewStates.ON_INTRO_COMPLEAT_BARKS_READER_NODE,
        )

    def on_censorship_fixes_doc_pressed(self, _button: Button) -> None:
        assert self._sys_file_paths
        self._nav.open_document(
            self._sys_file_paths.get_censorship_fixes_doc_dir(),
            APPENDIX_CENSORSHIP_FIXES_NODE_TEXT,
            ViewStates.ON_APPENDIX_CENSORSHIP_FIXES_NODE,
        )

    def on_article_node_pressed(self, node: ButtonTreeViewNode) -> None:
        """Consolidate handling of all simple article nodes."""
        assert isinstance(node.destination, ArticleDestination)
        view_state = node.destination.view_state
        article_title = node.destination.article_title

        logger.info(f"Article node pressed: Reading '{article_title.name}'.")

        self._nav.read_article(article_title, view_state)

    def on_main_index_node_created(self, main_index_node: MainTreeViewNode) -> None:
        self._main_index_screen.treeview_index_node = main_index_node

    def on_main_index_node_pressed(self, _node: ButtonTreeViewNode) -> None:
        logger.info("Main index node pressed.")
        self._renderer.render_state(ViewStates.ON_INDEX_MAIN_NODE)

    def on_speech_index_node_created(self, speech_index_node: MainTreeViewNode) -> None:
        self._speech_index_screen.treeview_index_node = speech_index_node

    def on_speech_index_node_pressed(self, _node: ButtonTreeViewNode) -> None:
        logger.info("Speech index node pressed.")
        self._renderer.render_state(ViewStates.ON_INDEX_SPEECH_NODE)
        # Auto-select the Words child node in the tree view to match the default bottom view.
        if self._speech_words_node is not None:
            self._tree_view_screen.select_node(self._speech_words_node)

    def on_speech_words_node_created(self, node: MainTreeViewNode) -> None:
        # Words child shares the same speech index screen's treeview node.
        self._speech_words_node = node

    @property
    def speech_words_node(self) -> ButtonTreeViewNode | None:
        return self._speech_words_node

    def on_speech_words_node_pressed(self, _node: ButtonTreeViewNode) -> None:
        logger.info("Speech Words node pressed.")
        self.disallow_view_state_change()
        self._renderer.render_state(ViewStates.ON_INDEX_SPEECH_WORDS_NODE)
        Clock.schedule_once(lambda _dt: self.allow_view_state_change(), 0)

    def on_names_index_node_created(self, names_index_node: MainTreeViewNode) -> None:
        self._names_index_screen.treeview_index_node = names_index_node

    def on_names_index_node_pressed(self, _node: ButtonTreeViewNode) -> None:
        logger.info("Names index node pressed.")
        self._renderer.render_state(ViewStates.ON_INDEX_NAMES_NODE)

    def on_locations_index_node_created(self, locations_index_node: MainTreeViewNode) -> None:
        self._locations_index_screen.treeview_index_node = locations_index_node

    def on_locations_index_node_pressed(self, _node: ButtonTreeViewNode) -> None:
        logger.info("Locations index node pressed.")
        self._renderer.render_state(ViewStates.ON_INDEX_LOCATIONS_NODE)

    def on_statistics_node_created(self, node: ButtonTreeViewNode) -> None:
        """Handle creation of the Statistics tree node."""
        self._statistics_node = node

    @property
    def statistics_node(self) -> ButtonTreeViewNode | None:
        return getattr(self, "_statistics_node", None)

    def on_statistics_node_pressed(self, _node: ButtonTreeViewNode) -> None:
        """Handle a press on the Statistics tree node."""
        logger.info("Statistics node pressed.")
        self._renderer.render_state(ViewStates.ON_APPENDIX_STATISTICS_NODE)

    def on_search_node_created(self, node: MainTreeViewNode) -> None:
        """Handle creation of the Search tree node."""
        self._search_node = node

    @property
    def search_node(self) -> MainTreeViewNode | None:
        return self._search_node

    def on_title_search_node_pressed(self, _node: ButtonTreeViewNode) -> None:
        logger.info("Title Search node pressed.")
        self._renderer.render_state(ViewStates.ON_TITLE_SEARCH_NODE)

    def on_tag_search_node_pressed(self, _node: ButtonTreeViewNode) -> None:
        logger.info("Tag Search node pressed.")
        self._renderer.render_state(ViewStates.ON_TAG_SEARCH_NODE)

    def on_word_search_node_pressed(self, _node: ButtonTreeViewNode) -> None:
        logger.info("Word Search node pressed.")
        self._renderer.render_state(ViewStates.ON_WORD_SEARCH_NODE)
