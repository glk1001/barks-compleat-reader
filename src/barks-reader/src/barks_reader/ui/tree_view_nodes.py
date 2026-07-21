from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, override

from kivy.app import App
from kivy.event import EventDispatcher
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    NumericProperty,
    ObjectProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.treeview import TreeView, TreeViewNode
from loguru import logger

from barks_reader.core.navigation import TitleDestination
from barks_reader.core.reader_formatter import (
    ReaderFormatter,
    get_clean_text_without_extra,
)
from barks_reader.core.reader_palette import color_to_markup_hex, theme
from barks_reader.core.reader_utils import title_needs_footnote

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

    from barks_reader.core.navigation import Destination

    from .font_manager import FontManager

READER_TREE_VIEW_KV_FILE = Path(__file__).parent / "reader-tree-view.kv"

TREE_VIEW_NODE_TEXT_COLOR = (1, 1, 1, 1)
TREE_VIEW_NODE_BACKGROUND_COLOR = (0.0, 0.0, 0.0, 0.0)


class ReaderTreeView(TreeView):
    TREE_VIEW_INDENT_LEVEL = dp(30)

    previous_selected_node = ObjectProperty(None, allownone=True)
    # Internal variable to track the state
    _current_selection_tracker: BaseTreeViewNode | None = None

    def reset_selection_tracking(self) -> None:
        self._current_selection_tracker = None
        self.previous_selected_node = None

    def set_back_node(self, node: BaseTreeViewNode | None) -> None:
        """Set the node that 'go back' will return to."""
        self._current_selection_tracker = node

    def on_selected_node(self, _instance: ReaderTreeView, new_node: BaseTreeViewNode) -> None:
        """Triggered automatically when 'selected_node' changes."""
        # 1. Assign the OLD current node to previous_node
        self.previous_selected_node = self._current_selection_tracker

        # 2. Update the tracker to the NEW node for next time
        self._current_selection_tracker = new_node

        # --- Debug Print ---
        prev_name = (
            self.previous_selected_node.get_name() if self.previous_selected_node else "None"
        )
        curr_name = new_node.get_name() if new_node else "None"
        logger.info(f'New selected node: "{curr_name}". Previous node: "{prev_name}".')


class ReaderTreeBuilderEventDispatcher(EventDispatcher):
    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        self.register_event_type(self.on_finished_building_event.__name__)
        super().__init__(**kwargs)

    def on_finished_building_event(self) -> None:
        pass

    def finished_building(self) -> None:
        logger.debug(
            f"Finished treeview build: dispatching '{self.on_finished_building_event.__name__}'."
        )
        self.dispatch(self.on_finished_building_event.__name__)


class BaseTreeViewNode(TreeViewNode):
    def __init__(self, destination: Destination | None = None, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.saved_state: dict[str, Any] = {}
        self.destination: Destination | None = destination

    def get_name(self) -> str:
        return "<unknown>"


class ButtonTreeViewNode(Button, BaseTreeViewNode):
    TEXT_COLOR = TREE_VIEW_NODE_TEXT_COLOR
    BACKGROUND_COLOR = TREE_VIEW_NODE_BACKGROUND_COLOR

    # Has this node lazily created its children?
    populated = BooleanProperty(defaultvalue=False)
    # A zero-arg function to create children.
    populate_callback = ObjectProperty(defaultvalue=None, allownone=True)
    # Should expansion always rebuild the lazily-created children?
    repopulate_on_expand = BooleanProperty(defaultvalue=False)

    @override
    def get_name(self) -> str:
        return get_clean_text_without_extra(self.text)

    def on_press(self) -> None:
        # Node press will also toggle expand/collapse.
        nodes_treeview = self._get_nodes_treeview(self)
        if not nodes_treeview:
            return
        nodes_treeview.toggle_node(self)

    @staticmethod
    def _get_nodes_treeview(node: ButtonTreeViewNode) -> TreeView | None:
        parent = node.parent
        while parent:
            if isinstance(parent, TreeView):
                return parent
            parent = parent.parent

        return None

    def ensure_populated(self) -> None:
        if self.populate_callback and not self.populated:
            self.populate_callback()


class MainTreeViewNode(ButtonTreeViewNode):
    NODE_SIZE = (dp(400), dp(30))


class StoryGroupTreeViewNode(ButtonTreeViewNode):
    NODE_WIDTH = dp(350)
    NODE_HEIGHT = dp(30)


class YearRangeTreeViewNode(ButtonTreeViewNode):
    # NumericProperty so callers can pass a wider NODE_WIDTH=dp(250) for CS/US ranges.
    NODE_WIDTH = NumericProperty(dp(150))
    NODE_HEIGHT = NumericProperty(dp(30))


class TitleTreeViewNode(BoxLayout, BaseTreeViewNode):
    TEXT_COLOR = TREE_VIEW_NODE_TEXT_COLOR
    BACKGROUND_COLOR = TREE_VIEW_NODE_BACKGROUND_COLOR
    ROW_BACKGROUND_COLOR = BACKGROUND_COLOR

    ROW_HEIGHT = dp(30)
    NUM_LABEL_WIDTH = dp(40)
    TITLE_LABEL_WIDTH = dp(400)
    ISSUE_LABEL_WIDTH = TITLE_LABEL_WIDTH

    NUM_LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)
    ISSUE_LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)

    def __init__(self, fanta_info: FantaComicBookInfo, **kwargs) -> None:  # noqa: ANN003
        kwargs.setdefault("destination", TitleDestination(fanta_info=fanta_info))
        super().__init__(**kwargs)
        self.fanta_info = fanta_info

    @override
    def get_name(self) -> str:
        return self.get_title().name

    def get_title(self) -> Titles:
        return self.fanta_info.comic_book_info.title

    @classmethod
    def create_from_fanta_info(
        cls, fanta_info: FantaComicBookInfo, on_press_callback: Callable
    ) -> TitleTreeViewNode:
        """Create and configure a new TitleTreeViewNode."""
        node = cls(fanta_info)

        node.ids.num_label.text = str(fanta_info.fanta_chronological_number)
        node.ids.num_label.bind(on_press=on_press_callback)

        node.ids.title_label.text = fanta_info.comic_book_info.get_display_title()
        node.ids.title_label.bind(on_press=on_press_callback)

        add_footnote = title_needs_footnote(fanta_info)
        if not add_footnote:
            sup_font_size = 0
        else:
            font_manager: FontManager = App.get_running_app().font_manager
            sup_font_size = round(2.0 * font_manager.tree_view_issue_label_font_size)

        node.ids.issue_label.text = ReaderFormatter.get_issue_info(
            fanta_info,
            add_footnote,
            sup_font_size,
            color_to_markup_hex(theme().text_secondary),
        )
        node.ids.issue_label.bind(on_press=on_press_callback)

        return node


class TreeViewButton(Button):
    pass


class TitleTreeViewLabel(Button):
    pass
