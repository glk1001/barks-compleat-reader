from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, override

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.event import EventDispatcher
from kivy.metrics import dp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.dropdown import DropDown
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.treeview import TreeView, TreeViewNode
from loguru import logger

from barks_reader.core.reader_consts_and_types import RAW_ACTION_BAR_SIZE_Y
from barks_reader.core.reader_formatter import (
    ReaderFormatter,
    get_clean_text_without_extra,
)
from barks_reader.core.reader_utils import title_needs_footnote

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from kivy.uix.actionbar import ActionBar

    from barks_reader.ui.font_manager import FontManager

KIVY_HELPERS_KV_FILE = Path(__file__).parent / "kivy_helpers.kv"
READER_TREE_VIEW_KV_FILE = Path(__file__).parent / "reader-tree-view.kv"
READER_POPUPS_KV_FILE = Path(__file__).parent / "reader_popups.kv"

TREE_VIEW_NODE_TEXT_COLOR = (1, 1, 1, 1)
TREE_VIEW_NODE_SELECTED_COLOR = (1, 0, 1, 0.8)
TREE_VIEW_NODE_BACKGROUND_COLOR = (0.0, 0.0, 0.0, 0.0)


class ScrollableDropDown(DropDown):
    """DropDown that doesn't consume touches when dismissing.

    Kivy's default DropDown returns True (consuming the touch) when the user
    clicks outside it, which prevents the clicked widget from receiving the
    event. Returning False after dismiss lets the touch fall through so that,
    for example, pressing the clear button while a dropdown is open both closes the dropdown
    and clears the search box in a single tap.
    """

    def on_touch_down(self, touch: object) -> bool:
        if not self.collide_point(*touch.pos) and self.auto_dismiss:  # ty: ignore[unresolved-attribute]
            self.dismiss()
            return False
        return super().on_touch_down(touch)


_ACTION_BAR_SIZE_Y: int | None = None
_ARROW_WIDTH: int | None = None


def _ensure_dp_constants() -> None:
    global _ACTION_BAR_SIZE_Y, _ARROW_WIDTH  # noqa: PLW0603
    if _ACTION_BAR_SIZE_Y is None:
        _ACTION_BAR_SIZE_Y = round(dp(RAW_ACTION_BAR_SIZE_Y))
        _ARROW_WIDTH = round(dp(20))


# Lazy properties so dp() is not called at import time (requires a Kivy window).


def __getattr__(name: str) -> int:
    if name == "ACTION_BAR_SIZE_Y":
        _ensure_dp_constants()
        assert _ACTION_BAR_SIZE_Y is not None
        return _ACTION_BAR_SIZE_Y
    if name == "ARROW_WIDTH":
        _ensure_dp_constants()
        assert _ARROW_WIDTH is not None
        return _ARROW_WIDTH
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def set_kivy_busy_cursor() -> None:
    Clock.schedule_once(lambda _dt: Window.set_system_cursor("wait"), 0)


def set_kivy_normal_cursor() -> None:
    Clock.schedule_once(lambda _dt: Window.set_system_cursor("arrow"), 0)


def show_action_bar(action_bar: ActionBar) -> None:
    _ensure_dp_constants()
    action_bar.height = _ACTION_BAR_SIZE_Y
    action_bar.opacity = 1
    action_bar.disabled = False


def hide_action_bar(action_bar: ActionBar) -> None:
    action_bar.height = 0
    action_bar.opacity = 0
    action_bar.disabled = True


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


# A button with an image and an expanded touch region around the image.
class TouchExpandedButton(Button):
    # Defining these properties here prevents a "NoneType" error on initialization.
    visual_size = NumericProperty(40)
    touch_padding = NumericProperty(10)
    source = StringProperty("")
    is_active = BooleanProperty(defaultvalue=True)


class LoadingDataPopup(Popup):
    progress_bar_value = NumericProperty(0)
    splash_image_texture = ObjectProperty()


class MessagePopup(Popup):
    msg_text = StringProperty()
    ok_text = StringProperty()
    cancel_text = StringProperty()
    ok = ObjectProperty(None, allownone=True)
    cancel = ObjectProperty(None, allownone=True)

    def __init__(
        self,
        text: str,
        ok_func: Callable[[], None] | None,
        ok_text: str,
        cancel_func: Callable[[], None] | None,
        cancel_text: str,
        msg_halign: str,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)

        self.msg_text = text
        self.ok_text = ok_text
        self.cancel_text = cancel_text
        self.msg_halign = msg_halign

        self.ok = ok_func
        self.cancel = cancel_func


class TitlePageImage(ButtonBehavior, Image):
    TITLE_IMAGE_X_FRAC_OF_PARENT = 0.95
    TITLE_IMAGE_Y_FRAC_OF_PARENT = 0.95


class BaseTreeViewNode(TreeViewNode):
    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.saved_state: dict[str, Any] = {}

    def get_name(self) -> str:
        return "<unknown>"


class ButtonTreeViewNode(Button, BaseTreeViewNode):
    TEXT_COLOR = TREE_VIEW_NODE_TEXT_COLOR
    SELECTED_COLOR = TREE_VIEW_NODE_SELECTED_COLOR
    BACKGROUND_COLOR = TREE_VIEW_NODE_BACKGROUND_COLOR

    # Has this node lazily created its children?
    populated = BooleanProperty(defaultvalue=False)
    # A zero-arg function to create children.
    populate_callback = ObjectProperty(defaultvalue=None, allownone=True)

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


class TagStoryGroupTreeViewNode(StoryGroupTreeViewNode):
    def __init__(self, tag: Tags, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.tag = tag


class TagGroupStoryGroupTreeViewNode(StoryGroupTreeViewNode):
    def __init__(self, tag_group: TagGroups, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self.tag = tag_group


class YearRangeTreeViewNode(ButtonTreeViewNode):
    NODE_WIDTH = dp(150)
    NODE_HEIGHT = dp(30)


class CsYearRangeTreeViewNode(YearRangeTreeViewNode):
    NODE_WIDTH = dp(250)
    NODE_HEIGHT = dp(30)


class UsYearRangeTreeViewNode(YearRangeTreeViewNode):
    NODE_WIDTH = dp(250)
    NODE_HEIGHT = dp(30)


class TitleTreeViewNode(BoxLayout, BaseTreeViewNode):
    TEXT_COLOR = TREE_VIEW_NODE_TEXT_COLOR
    SELECTED_COLOR = TREE_VIEW_NODE_SELECTED_COLOR
    BACKGROUND_COLOR = TREE_VIEW_NODE_BACKGROUND_COLOR
    ROW_BACKGROUND_COLOR = BACKGROUND_COLOR
    EVEN_COLOR: ClassVar[list[float]] = [0, 0, 0.4, 0.4]
    ODD_COLOR: ClassVar[list[float]] = [0, 0, 1.0, 0.4]

    ROW_HEIGHT = dp(30)
    NUM_LABEL_WIDTH = dp(40)
    TITLE_LABEL_WIDTH = dp(400)
    ISSUE_LABEL_WIDTH = TITLE_LABEL_WIDTH

    NUM_LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)
    TITLE_LABEL_COLOR = (1.0, 1.0, 0.0, 1.0)
    ISSUE_LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)
    ISSUE_LABEL_SUBMITTED_YEAR_COLOR = "#FCFABE"  # "#FFFF00"

    def __init__(self, fanta_info: FantaComicBookInfo, **kwargs) -> None:  # noqa: ANN003
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
            TitleTreeViewNode.ISSUE_LABEL_SUBMITTED_YEAR_COLOR,
        )
        node.ids.issue_label.bind(on_press=on_press_callback)

        return node


class TreeViewButton(Button):
    pass


class TitleTreeViewLabel(Button):
    pass
