from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from comic_utils.timing import Timing
from kivy.clock import Clock
from kivy.uix.treeview import TreeViewNode
from loguru import logger

from barks_reader.core.reader_formatter import get_clean_text_without_extra
from barks_reader.ui.reader_ui_classes import (
    BaseTreeViewNode,
    ButtonTreeViewNode,
    MainTreeViewNode,
    TagGroupStoryGroupTreeViewNode,
    TagSearchBoxTreeViewNode,
    TagStoryGroupTreeViewNode,
    TitleSearchBoxTreeViewNode,
    TitleTreeViewNode,
)
from barks_reader.ui.view_states import (
    ViewStates,
    get_view_state_and_article_title_from_node,
    get_view_state_from_node,
)

if TYPE_CHECKING:
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from kivy.uix.button import Button
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.spinner import Spinner

    from barks_reader.ui.background_views import BackgroundViews
    from barks_reader.ui.main_index_screen import MainIndexScreen
    from barks_reader.ui.reader_ui_classes import ReaderTreeView
    from barks_reader.ui.speech_index_screen import SpeechIndexScreen
    from barks_reader.ui.tree_view_screen import TreeViewScreen
    from barks_reader.ui.view_state_manager import ViewStateManager

UpdateTitleCallable = Callable[[str], bool]
ReadArticleCallable = Callable[[Titles, ViewStates], None]
ReadIntroCompleatBarksReaderCallable = Callable[[], None]
ScrollToNodeCallable = Callable[[TreeViewNode], None]
SetTagGotoPageCheckboxCallable = Callable[[Tags | TagGroups, str], None]


class TreeViewManager:
    """Manage all interactions and events related to the TreeView."""

    def __init__(
        self,
        background_views: BackgroundViews,
        view_state_manager: ViewStateManager,
        tree_view_screen: TreeViewScreen,
        main_index_screen: MainIndexScreen,
        speech_index_screen: SpeechIndexScreen,
        update_title_func: UpdateTitleCallable,
        read_article_func: ReadArticleCallable,
        read_intro_compleat_barks_reader_func: ReadIntroCompleatBarksReaderCallable,
        set_tag_goto_page_checkbox_func: SetTagGotoPageCheckboxCallable,
        set_next_title_func: Callable[[FantaComicBookInfo, Tags | TagGroups | None], None],
    ) -> None:
        self._background_views = background_views
        self._view_state_manager = view_state_manager
        self._tree_view_screen = tree_view_screen
        self._main_index_screen = main_index_screen
        self._speech_index_screen = speech_index_screen

        self._tree_view_screen.ids.reader_tree_view.bind(on_node_expand=self.on_node_expanded)
        self._tree_view_screen.ids.reader_tree_view.bind(on_node_collapse=self.on_node_collapsed)

        self._update_title_func = update_title_func
        self._read_article_func = read_article_func
        self._read_intro_compleat_barks_reader_func = read_intro_compleat_barks_reader_func
        self._set_tag_goto_page_checkbox_func = set_tag_goto_page_checkbox_func
        self._set_next_title_func = set_next_title_func

        self._allow_view_state_change = True

        assert self._update_title_func
        assert self._read_article_func
        assert self._read_intro_compleat_barks_reader_func
        assert self._set_tag_goto_page_checkbox_func
        assert self._set_next_title_func

    def setup_and_select_node(self, node: BaseTreeViewNode) -> None:
        logger.debug(f'Selecting and setting up node "{node.get_name()}".')

        # noinspection PyArgumentList
        with self.suppress_view_state_changes():
            self._tree_view_screen.deselect_and_close_open_nodes()
            self._tree_view_screen.open_all_parent_nodes(node)
            self._tree_view_screen.select_node(node)

        if isinstance(node, TitleTreeViewNode):
            self._handle_title_node_selection(node)
        elif isinstance(node, (TitleSearchBoxTreeViewNode, TagSearchBoxTreeViewNode)):
            self._handle_search_box_node_selection(node)
        elif isinstance(node, ButtonTreeViewNode):
            self._handle_button_node_selection(node)

    def _handle_title_node_selection(self, node: TitleTreeViewNode) -> None:
        fanta_info = node.ids.num_label.parent.fanta_info
        self._set_next_title_func(fanta_info, None)
        self.scroll_to_node(node)

    @staticmethod
    def _handle_search_box_node_selection(
        node: TitleSearchBoxTreeViewNode | TagSearchBoxTreeViewNode,
    ) -> None:
        def set_text() -> None:
            node.text = node.saved_state.get("text", "")

        Clock.schedule_once(lambda _dt: set_text(), 1)
        node.press_search_box()

    def _handle_button_node_selection(self, node: ButtonTreeViewNode) -> None:
        if node.saved_state.get("open", True):
            node.trigger_action()
        else:
            saved_view_state, _ = get_view_state_from_node(node)
            if saved_view_state is not None:
                self._view_state_manager.set_view_state(saved_view_state)

    def deselect_and_close_open_nodes(self) -> None:
        # noinspection PyArgumentList
        with self.suppress_view_state_changes():
            num_opened_nodes = self._tree_view_screen.deselect_and_close_open_nodes()

        if num_opened_nodes > 0:
            self._view_state_manager.set_view_state(ViewStates.INITIAL)

    def open_all_parent_nodes(self, node: ButtonTreeViewNode) -> None:
        # noinspection PyArgumentList
        with self.suppress_view_state_changes():
            self._tree_view_screen.open_all_parent_nodes(node)

    def go_back_to_previous_node(self) -> None:
        if not self._tree_view_screen.ids.reader_tree_view.previous_selected_node:
            self.deselect_and_close_open_nodes()
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
        # Check allow state change flag or is leaf/title row.
        if not self._allow_view_state_change or isinstance(node, TitleTreeViewNode):
            logger.info(f"Node collapsed but not allowing state change: '{node.get_name()}'.")
            return

        logger.info(f"Node collapsed: '{node.get_name()}'.")

        self.set_view_state_for_node(node)

    def set_view_state_for_node(self, node: ButtonTreeViewNode) -> None:
        new_view_state, view_state_params = get_view_state_from_node(node)
        if new_view_state is None:
            msg = f"No view state mapping found for node: '{node.get_name()}' ({type(node)})"
            raise RuntimeError(msg)
        # noinspection LongLine
        self._view_state_manager.set_view_state(new_view_state, **view_state_params)  # ty: ignore[invalid-argument-type]

    def on_node_expanded(self, _tree: ReaderTreeView, node: ButtonTreeViewNode) -> None:
        logger.info(f"Node expanded: '{node.get_name()}'.")

        if not self._allow_view_state_change or isinstance(node, TitleTreeViewNode):
            logger.info(f"Node opened but not allowing state change: '{node.get_name()}'.")
            return

        # 1) Collapse any previously-open group (reduces height shocks).
        self._close_siblings(node)

        # 2) Lazy populate ONCE, while pinning the parent's position to avoid a jump.
        if node.populate_callback and not node.populated:
            self._pin_parent_position_while_populating(node, run_populate=True)
            node.populated = True
        else:
            # If already populated, we still pin during expand so second (and later) expansions
            # keep the parent row stationary.
            self._pin_parent_position_while_populating(node, run_populate=False)

        # 3) View-state logic
        self.set_view_state_for_node(node)

        # 4) NOTE: Do not call scroll_to_node() here — that causes the “snap-to-top/bottom” jump.

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
            return  # nothing to adjust

        # Convert pixel delta to normalized scroll_y delta:
        #  - Kivy uses scroll_y 0..1 where 1 = top, 0 = bottom.
        #  - Moving content up by +delta_px means increase scroll_y.
        denominator = cont_h - viewport_h
        if denominator <= 0:
            return

        delta_norm = delta_px / denominator
        new_scroll_y = self._clamp01(scroll_view.scroll_y + delta_norm)

        # Apply in one shot (no animation to avoid visible bounce)
        scroll_view.scroll_y = new_scroll_y

    @staticmethod
    def _clamp01(v: float) -> float:
        return 0.0 if v < 0.0 else (min(v, 1.0))

    def on_title_row_button_pressed(self, button: Button) -> None:
        fanta_info = button.parent.fanta_info

        tag = (
            None
            if not isinstance(
                button.parent.parent_node,
                (TagStoryGroupTreeViewNode, TagGroupStoryGroupTreeViewNode),
            )
            else button.parent.parent_node.tag
        )

        self._set_next_title_func(fanta_info, tag)

    def on_intro_compleat_barks_reader_pressed(self, _button: Button) -> None:
        self._read_intro_compleat_barks_reader_func()

    def on_article_node_pressed(self, node: ButtonTreeViewNode) -> None:
        """Consolidate handling of all simple article nodes."""
        view_state, article_title = get_view_state_and_article_title_from_node(node)

        logger.info(f"Article node pressed: Reading '{article_title.name}'.")

        self._read_article_func(article_title, view_state)

    def on_main_index_node_created(self, main_index_node: MainTreeViewNode) -> None:
        self._main_index_screen.treeview_index_node = main_index_node

    def on_main_index_node_pressed(self, _node: ButtonTreeViewNode) -> None:
        logger.info("Main index node pressed.")
        self._view_state_manager.update_view_for_node(ViewStates.ON_INDEX_MAIN_NODE)

    def on_speech_index_node_created(self, speech_index_node: MainTreeViewNode) -> None:
        self._speech_index_screen.treeview_index_node = speech_index_node

    def on_speech_index_node_pressed(self, _node: ButtonTreeViewNode) -> None:
        logger.info("Speech index node pressed.")
        self._view_state_manager.update_view_for_node(ViewStates.ON_INDEX_SPEECH_NODE)

    def on_title_search_box_pressed(self, instance: TitleSearchBoxTreeViewNode) -> None:
        logger.debug(f"Title search box pressed: {instance}.")

        if not instance.get_current_title():
            logger.debug("Have not got title search box text yet.")
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET
            )
        elif self._background_views.get_view_state() != ViewStates.ON_TITLE_SEARCH_BOX_NODE:
            logger.debug(
                f"Forcing title search box change:"
                f" view state = {self._background_views.get_view_state()},"
                f' title search box text = "{instance.get_current_title()}",'
                f' title spinner text = "{instance.ids.title_spinner.text}"',
            )
            self.on_title_search_box_title_changed(
                instance.ids.title_spinner,
                instance.ids.title_spinner.text,
            )

    def on_title_search_box_title_changed(self, _spinner: Spinner, title_str: str) -> None:
        logger.debug(f'Title search box title changed: "{title_str}".')

        if not title_str:
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET
            )
        elif self._update_title_func(title_str):
            self._view_state_manager.update_view_for_node_with_title(
                ViewStates.ON_TITLE_SEARCH_BOX_NODE
            )
        else:
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TITLE_SEARCH_BOX_NODE_NO_TITLE_YET
            )

    def on_tag_search_box_pressed(self, instance: TagSearchBoxTreeViewNode) -> None:
        logger.debug(f"Tag search box pressed: {instance}.")

        if not instance.get_current_tag_str():
            logger.debug("Have not got tag search box text yet.")
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
            )
        elif self._background_views.get_view_state() != ViewStates.ON_TAG_SEARCH_BOX_NODE:
            logger.debug(
                f"Forcing tag search box change:"
                f" view state = {self._background_views.get_view_state()},"
                f' tag search box text = "{instance.get_current_tag_str()}",'
                f' tag title spinner text = "{instance.ids.tag_title_spinner.text}"',
            )
            self.on_tag_search_box_title_changed(instance, instance.ids.tag_title_spinner.text)

    def on_tag_search_box_text_changed(self, instance: TagSearchBoxTreeViewNode, text: str) -> None:
        logger.debug(f'Tag search box text changed: text: "{text}".')

        if not instance.get_current_title():
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
            )

    def on_tag_search_box_tag_changed(
        self,
        instance: TagSearchBoxTreeViewNode,
        tag_str: str,
    ) -> None:
        logger.debug(f'Tag search box tag changed: "{tag_str}".')

        if not tag_str:
            return

        if not instance.get_current_title():
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
            )

    def on_tag_search_box_title_changed(
        self,
        instance: TagSearchBoxTreeViewNode,
        title_str: str,
    ) -> None:
        logger.debug(
            f'Tag search box title changed: "{title_str}".'
            f' Tag: "{instance.get_current_tag().value}".',
        )

        if not title_str:
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
            )
        elif self._update_title_func(title_str):
            self._view_state_manager.update_view_for_node_with_title(
                ViewStates.ON_TAG_SEARCH_BOX_NODE
            )
            self._set_tag_goto_page_checkbox_func(instance.get_current_tag(), title_str)
        else:
            self._view_state_manager.update_view_for_node(
                ViewStates.ON_TAG_SEARCH_BOX_NODE_NO_TITLE_YET
            )
