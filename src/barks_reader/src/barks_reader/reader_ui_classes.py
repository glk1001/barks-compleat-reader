# ruff: noqa: ERA001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from barks_fantagraphics.comics_utils import (
    get_short_formatted_first_published_str,
    get_short_submitted_day_and_month,
)
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.event import EventDispatcher
from kivy.metrics import dp
from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.treeview import TreeView, TreeViewNode
from kivy.utils import escape_markup
from loguru import logger

from barks_reader.reader_formatter import get_markup_text_with_num_titles, text_includes_num_titles
from barks_reader.reader_utils import unique_extend

if TYPE_CHECKING:
    from collections.abc import Callable
    from tkinter import Widget

    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from barks_fantagraphics.barks_titles import ComicBookInfo, Titles
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
    from barks_fantagraphics.title_search import BarksTitleSearch
    from kivy.input import MotionEvent
    from kivy.uix.spinner import Spinner

READER_TREE_VIEW_KV_FILE = Path(__file__).parent / "reader-tree-view.kv"

TREE_VIEW_NODE_TEXT_COLOR = (1, 1, 1, 1)
TREE_VIEW_NODE_SELECTED_COLOR = (1, 0, 1, 0.8)
TREE_VIEW_NODE_BACKGROUND_COLOR = (0.0, 0.0, 0.0, 0.0)

ACTION_BAR_SIZE_Y = dp(45)


def set_kivy_busy_cursor() -> None:
    Clock.schedule_once(lambda _dt: Window.set_system_cursor("wait"), 0)


def set_kivy_normal_cursor() -> None:
    Clock.schedule_once(lambda _dt: Window.set_system_cursor("arrow"), 0)


class ReaderTreeView(TreeView):
    TREE_VIEW_INDENT_LEVEL = dp(30)


class ReaderTreeBuilderEventDispatcher(EventDispatcher):
    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        # noinspection PyUnresolvedReferences
        self.register_event_type(self.on_finished_building_event.__name__)
        super().__init__(**kwargs)

    def on_finished_building_event(self) -> None:
        pass

    def finished_building(self) -> None:
        logger.debug(
            f"Finished treeview build: dispatching '{self.on_finished_building_event.__name__}'."
        )
        # noinspection PyUnresolvedReferences
        self.dispatch(self.on_finished_building_event.__name__)


class LoadingDataPopup(Popup):
    progress_bar_value = NumericProperty(0)
    splash_image_texture = ObjectProperty()


class MessagePopup(Popup):
    msg_text = StringProperty()
    ok_text = StringProperty()
    cancel_text = StringProperty()

    # noinspection PyUnresolvedReferences
    def __init__(
        self,
        text: str,
        ok_func: None | Callable[[], None],
        ok_text: str,
        cancel_func: Callable[[], None],
        cancel_text: str,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)

        self.msg_text = text
        self.ok_text = ok_text
        self.cancel_text = cancel_text

        self.ok = ok_func
        self.cancel = cancel_func


class TitlePageImage(ButtonBehavior, Image):
    TITLE_IMAGE_X_FRAC_OF_PARENT = 0.95
    TITLE_IMAGE_Y_FRAC_OF_PARENT = 0.95


class BaseSearchBoxTreeViewNode(FloatLayout, TreeViewNode):
    """Base class for search boxes in the TreeView."""

    @staticmethod
    def _set_spinner_values(spinner: Spinner, values: list[str]) -> None:
        """Set value and state for a spinner."""
        if not values:
            spinner.values = []
            spinner.text = ""
            spinner.is_open = False
        elif len(values) == 1:
            spinner.values = values
            spinner.text = values[0]
            spinner.is_open = False
        else:
            spinner.values = values
            spinner.text = ""
            spinner.is_open = True


class TitleSearchBoxTreeViewNode(BaseSearchBoxTreeViewNode):
    def on_title_search_box_pressed(self) -> None:
        pass

    def on_title_search_box_title_pressed(self) -> None:
        pass

    def on_title_search_box_title_changed(self, _value: str) -> None:
        pass

    __events__ = (
        on_title_search_box_pressed.__name__,
        on_title_search_box_title_changed.__name__,
    )

    name = "Title Search Box"
    text = StringProperty("")
    SELECTED_COLOR = (0, 0, 0, 0.0)
    TEXT_COLOR = (1, 1, 1, 1)
    TEXT_BACKGROUND_COLOR = (0.5, 0.5, 0.5, 0.8)
    SPINNER_TEXT_COLOR = (1, 1, 0, 1)
    SPINNER_BACKGROUND_COLOR = (0, 0, 1, 1)
    NODE_SIZE = (dp(100), dp(30))

    def __init__(self, title_search: BarksTitleSearch) -> None:
        super().__init__()
        self.title_search = title_search
        self.bind(text=self._on_internal_search_box_text_changed)
        self.ids.title_spinner.bind(text=self._on_internal_title_search_box_title_changed)

    @override
    def on_touch_down(self, touch: MotionEvent) -> bool:
        self.dispatch(self.on_title_search_box_pressed.__name__)
        return super().on_touch_down(touch)

    def get_current_title(self) -> str:
        return self.ids.title_search_box.text

    def _on_internal_search_box_text_changed(self, instance: Widget, value: str) -> None:
        logger.debug(f'**Title search box text changed: {instance}, text: "{value}".')

        titles = [] if len(value) <= 1 else self._get_titles_matching_search_title_str(str(value))

        self._set_spinner_values(self.ids.title_spinner, titles)

    def _on_internal_title_search_box_title_changed(self, spinner: Spinner, title_str: str) -> None:
        logger.debug(
            f'**Title search box title spinner text changed: {spinner}, text: "{title_str}".'
        )
        self.dispatch(self.on_title_search_box_title_changed.__name__, title_str)

    def _get_titles_matching_search_title_str(self, value: str) -> list[str]:
        title_list = self.title_search.get_titles_matching_prefix(value)
        min_title_chars_len = 2
        if len(value) > min_title_chars_len:
            if not title_list:
                title_list = self.title_search.get_titles_from_issue_num(value)
            if not title_list:
                unique_extend(title_list, self.title_search.get_titles_containing(value))

        return self.title_search.get_titles_as_strings(title_list)


class TagSearchBoxTreeViewNode(BaseSearchBoxTreeViewNode):
    def on_tag_search_box_pressed(self) -> None:
        pass

    def on_tag_search_box_text_changed(self, _value: str) -> None:
        pass

    def on_tag_search_box_tag_changed(self, _value: str) -> None:
        pass

    def on_tag_search_box_title_changed(self, _value: str) -> None:
        pass

    __events__ = (
        on_tag_search_box_pressed.__name__,
        on_tag_search_box_text_changed.__name__,
        on_tag_search_box_tag_changed.__name__,
        on_tag_search_box_title_changed.__name__,
    )

    name = "Tag Search Box"
    text = StringProperty("")
    SELECTED_COLOR = (0, 0, 0, 0.0)
    TAG_LABEL_COLOR = (1, 1, 1, 1)
    TAG_LABEL_BACKGROUND_COLOR = (0.5, 0.5, 0.5, 0.8)
    TAG_TEXT_COLOR = (1, 1, 1, 1)
    TAG_TEXT_BACKGROUND_COLOR = (0.5, 0.5, 0.5, 0.8)
    TAG_SPINNER_TEXT_COLOR = (0, 1, 0, 1)
    TAG_SPINNER_BACKGROUND_COLOR = (1, 0, 1, 1)
    TAG_TITLE_SPINNER_TEXT_COLOR = (1, 1, 0, 1)
    TAG_TITLE_SPINNER_BACKGROUND_COLOR = (0, 0, 1, 1)
    NODE_SIZE = (dp(100), dp(60))

    def __init__(self, title_search: BarksTitleSearch) -> None:
        super().__init__()
        self._title_search = title_search
        self.bind(text=self._on_internal_tag_search_box_text_changed)
        self.ids.tag_spinner.bind(text=self._on_internal_tag_search_box_tag_changed)
        self.ids.tag_title_spinner.bind(text=self._on_internal_tag_search_box_title_changed)
        self._current_tag = None

    @override
    def on_touch_down(self, touch: MotionEvent) -> bool:
        self.dispatch(self.on_tag_search_box_pressed.__name__)
        return super().on_touch_down(touch)

    def get_current_tag(self) -> Tags | TagGroups:
        return self._current_tag

    def get_current_tag_str(self) -> str:
        return self.ids.tag_spinner.text

    def get_current_title(self) -> str:
        return self.ids.tag_title_spinner.text

    def _on_internal_tag_search_box_text_changed(self, instance: Widget, value: str) -> None:
        logger.debug(f'**Tag search box text changed: {instance}, text: "{value}".')

        self.dispatch(self.on_tag_search_box_text_changed.__name__, value)

        if len(value) <= 1:
            tags = []
            titles = []
        else:
            found_tags = self._get_tags_matching_search_tag_str(str(value))
            tags = sorted([str(t.value) for t in found_tags]) if found_tags else []
            titles = []

        self._set_spinner_values(self.ids.tag_spinner, tags)
        self._set_spinner_values(self.ids.tag_title_spinner, titles)

    def _on_internal_tag_search_box_tag_changed(self, spinner: Spinner, tag_str: str) -> None:
        logger.debug(f'**Tag search box tag spinner text changed: {spinner}, text: "{tag_str}".')
        if text_includes_num_titles(tag_str):
            return

        self.dispatch(self.on_tag_search_box_tag_changed.__name__, tag_str)

        if not tag_str:
            return

        self._current_tag, titles = self._title_search.get_titles_from_alias_tag(tag_str.lower())
        self.ids.tag_spinner.text = get_markup_text_with_num_titles(tag_str, len(titles))

        str_titles = None if not titles else self._title_search.get_titles_as_strings(titles)
        self._set_spinner_values(self.ids.tag_title_spinner, str_titles)

    def _on_internal_tag_search_box_title_changed(self, spinner: Spinner, title_str: str) -> None:
        logger.debug(
            f'**Tag search box tag title spinner text changed: {spinner}, text: "{title_str}".'
        )
        self.dispatch(self.on_tag_search_box_title_changed.__name__, title_str)

    def _get_tags_matching_search_tag_str(self, value: str) -> list[Tags | TagGroups]:
        return self._title_search.get_tags_matching_prefix(value)
        # if len(value) > 2:
        #     unique_extend(title_list, self.title_search.get_titles_containing(value))


class ButtonTreeViewNode(Button, TreeViewNode):
    TEXT_COLOR = TREE_VIEW_NODE_TEXT_COLOR
    SELECTED_COLOR = TREE_VIEW_NODE_SELECTED_COLOR
    BACKGROUND_COLOR = TREE_VIEW_NODE_BACKGROUND_COLOR

    def on_touch_down(self, touch: MotionEvent) -> bool:
        # Node press will also toggle expand/collapse.
        nodes_treeview = self._get_nodes_treeview(self)
        assert nodes_treeview is not None
        nodes_treeview.toggle_node(self)

        return super().on_touch_down(touch)

    @staticmethod
    def _get_nodes_treeview(node: TreeViewNode) -> TreeView | None:
        # noinspection PyUnresolvedReferences
        parent = node.parent
        while parent:
            if isinstance(parent, TreeView):
                return parent
            parent = parent.parent

        return None


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


class TitleTreeViewNode(BoxLayout, TreeViewNode):
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

    def get_title(self) -> Titles:
        return self.fanta_info.comic_book_info.title

    @classmethod
    def get_formatted_submitted_str(cls, comic_book_info: ComicBookInfo) -> str:
        left_sq_bracket = escape_markup("[")
        right_sq_bracket = escape_markup("]")

        return (
            f" {left_sq_bracket}"
            f"{get_short_submitted_day_and_month(comic_book_info)}"
            f" [b][color={TitleTreeViewNode.ISSUE_LABEL_SUBMITTED_YEAR_COLOR}]"
            f"{comic_book_info.submitted_year}"
            f"[/color][/b]"
            f"{right_sq_bracket}"
        )

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

        first_published = get_short_formatted_first_published_str(fanta_info.comic_book_info)
        submitted_date = cls.get_formatted_submitted_str(fanta_info.comic_book_info)
        issue_info = f"[i]{first_published}{submitted_date}[/i]"
        node.ids.issue_label.text = issue_info
        node.ids.issue_label.bind(on_press=on_press_callback)

        return node


class TreeViewButton(Button):
    pass


class TitleTreeViewLabel(Button):
    pass
