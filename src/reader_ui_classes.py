import logging
from typing import List, Union

from kivy.event import EventDispatcher
from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.uix.treeview import TreeView, TreeViewNode

from barks_fantagraphics.barks_tags import Tags, TagGroups
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
from barks_fantagraphics.title_search import unique_extend, BarksTitleSearch
from reader_formatter import get_markup_text_with_num_titles, text_includes_num_titles

TREE_VIEW_NODE_TEXT_COLOR = (1, 1, 1, 1)
TREE_VIEW_NODE_SELECTED_COLOR = (1, 0, 1, 0.8)
TREE_VIEW_NODE_BACKGROUND_COLOR = (0.0, 0.0, 0.0, 0.0)


class ReaderTreeView(TreeView):
    TREE_VIEW_INDENT_LEVEL = dp(30)


class ReaderTreeBuilderEventDispatcher(EventDispatcher):
    def __init__(self, **kwargs):
        self.register_event_type(self.on_finished_building_event.__name__)
        super(ReaderTreeBuilderEventDispatcher, self).__init__(**kwargs)

    def on_finished_building_event(self):
        pass

    def finished_building(self):
        logging.debug(f"Dispatching '{self.on_finished_building_event.__name__}'.")
        self.dispatch(self.on_finished_building_event.__name__)


class LoadingDataPopup(Popup):
    progress_bar_value = NumericProperty(0)
    splash_image_path = StringProperty()
    pass


class TitlePageImage(ButtonBehavior, Image):
    TITLE_IMAGE_X_FRAC_OF_PARENT = 0.98
    TITLE_IMAGE_Y_FRAC_OF_PARENT = 0.98 * 0.97


class TitleSearchBoxTreeViewNode(FloatLayout, TreeViewNode):
    def on_title_search_box_pressed(self):
        pass

    def on_title_search_box_title_pressed(self):
        pass

    def on_title_search_box_title_changed(self, _value: str):
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

    def __init__(self, title_search: BarksTitleSearch):
        super().__init__()
        self.title_search = title_search
        self.bind(text=self._on_internal_search_box_text_changed)
        self.ids.title_spinner.bind(text=self._on_internal_title_search_box_title_changed)

    def on_touch_down(self, touch):
        self.dispatch(self.on_title_search_box_pressed.__name__)
        return super().on_touch_down(touch)

    def get_current_title(self) -> str:
        return self.ids.title_search_box.text

    def _on_internal_search_box_text_changed(self, instance, value: str):
        logging.debug(f'**Title search box text changed: {instance}, text: "{value}".')

        if len(value) <= 1:
            instance.__set_empty_title_spinner_text()
        else:
            titles = self.__get_titles_matching_search_title_str(str(value))
            instance.__set_title_spinner_values(titles)

    def _on_internal_title_search_box_title_changed(self, spinner: Spinner, title_str: str) -> None:
        logging.debug(
            f'**Title search box title spinner text changed: {spinner}, text: "{title_str}".'
        )
        self.dispatch(self.on_title_search_box_title_changed.__name__, title_str)

    def __get_titles_matching_search_title_str(self, value: str) -> List[str]:
        title_list = self.title_search.get_titles_matching_prefix(value)
        if len(value) > 2:
            unique_extend(title_list, self.title_search.get_titles_containing(value))

        return self.title_search.get_titles_as_strings(title_list)

    def __set_empty_title_spinner_text(self):
        self.ids.title_spinner.text = ""
        self.ids.title_spinner.is_open = False

    def __set_empty_title_spinner_values(self):
        self.ids.title_spinner.values = []
        self.ids.title_spinner.text = ""
        self.ids.title_spinner.is_open = False

    def __set_title_spinner_values(self, titles: List[str]):
        if not titles:
            self.__set_empty_title_spinner_values()
        elif len(titles) == 1:
            self.ids.title_spinner.values = titles
            self.ids.title_spinner.text = titles[0]
            self.ids.title_spinner.is_open = False
        else:
            self.ids.title_spinner.values = titles
            self.ids.title_spinner.is_open = True


class TagSearchBoxTreeViewNode(FloatLayout, TreeViewNode):
    def on_tag_search_box_pressed(self):
        pass

    def on_tag_search_box_text_changed(self, _value: str):
        pass

    def on_tag_search_box_tag_changed(self, _value: str):
        pass

    def on_tag_search_box_title_changed(self, _value: str):
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

    def __init__(self, title_search: BarksTitleSearch):
        super().__init__()
        self.__title_search = title_search
        self.bind(text=self._on_internal_tag_search_box_text_changed)
        self.ids.tag_spinner.bind(text=self._on_internal_tag_search_box_tag_changed)
        self.ids.tag_title_spinner.bind(text=self._on_internal_tag_search_box_title_changed)

    def on_touch_down(self, touch):
        self.dispatch(self.on_tag_search_box_pressed.__name__)
        return super().on_touch_down(touch)

    def get_current_tag(self) -> str:
        return self.ids.tag_spinner.text

    def get_current_title(self) -> str:
        return self.ids.tag_title_spinner.text

    def _on_internal_tag_search_box_text_changed(self, instance, value):
        logging.debug(f'**Tag search box text changed: {instance}, text: "{value}".')

        self.dispatch(self.on_tag_search_box_text_changed.__name__, value)

        if len(value) <= 1:
            instance.__set_empty_tag_spinner_values()
            instance.__set_empty_title_spinner_values()
        else:
            tags = self.__get_tags_matching_search_tag_str(str(value))
            if tags:
                instance.__set_tag_spinner_values(sorted([str(t.value) for t in tags]))
            else:
                instance.__set_empty_tag_spinner_values()
                instance.__set_empty_title_spinner_values()

    def _on_internal_tag_search_box_tag_changed(self, spinner: Spinner, tag_str: str):
        logging.debug(f'**Tag search box tag spinner text changed: {spinner}, text: "{tag_str}".')
        if text_includes_num_titles(tag_str):
            return

        self.dispatch(self.on_tag_search_box_tag_changed.__name__, tag_str)

        if not tag_str:
            return

        titles = self.__title_search.get_titles_from_alias_tag(tag_str.lower())

        self.ids.tag_spinner.text = get_markup_text_with_num_titles(tag_str, len(titles))

        if not titles:
            self.__set_empty_title_spinner_values()
            return

        self.__set_title_spinner_values(self.__title_search.get_titles_as_strings(titles))

    def _on_internal_tag_search_box_title_changed(self, spinner: Spinner, title_str: str) -> None:
        logging.debug(
            f'**Tag search box tag title spinner text changed: {spinner}, text: "{title_str}".'
        )
        self.dispatch(self.on_tag_search_box_title_changed.__name__, title_str)

    def __get_tags_matching_search_tag_str(self, value: str) -> List[Union[Tags, TagGroups]]:
        tag_list = self.__title_search.get_tags_matching_prefix(value)
        # if len(value) > 2:
        #     unique_extend(title_list, self.title_search.get_titles_containing(value))

        return tag_list

    def __set_empty_tag_spinner_values(self):
        self.ids.tag_spinner.values = []
        self.ids.tag_spinner.text = ""
        self.ids.tag_spinner.is_open = False

    def __set_tag_spinner_values(self, tags: List[str]):
        if not tags:
            self.__set_empty_tag_spinner_values()
        elif len(tags) == 1:
            self.ids.tag_spinner.values = tags
            self.ids.tag_spinner.text = tags[0]
            self.ids.tag_spinner.is_open = False
        else:
            self.ids.tag_spinner.values = tags
            self.ids.tag_spinner.is_open = True

    def __set_empty_title_spinner_text(self):
        self.ids.tag_title_spinner.text = ""
        self.ids.tag_title_spinner.is_open = False

    def __set_empty_title_spinner_values(self):
        self.ids.tag_title_spinner.values = []
        self.ids.tag_title_spinner.text = ""
        self.ids.tag_title_spinner.is_open = False

    def __set_title_spinner_values(self, titles: List[str]):
        if not titles:
            self.__set_empty_title_spinner_values()
        elif len(titles) == 1:
            self.ids.tag_title_spinner.values = titles
            self.ids.tag_title_spinner.text = titles[0]
            self.ids.tag_title_spinner.is_open = False
        else:
            self.ids.tag_title_spinner.values = titles
            self.ids.tag_title_spinner.is_open = True


class ButtonTreeViewNode(Button, TreeViewNode):
    pass


class MainTreeViewNode(ButtonTreeViewNode):
    TEXT_COLOR = TREE_VIEW_NODE_TEXT_COLOR
    SELECTED_COLOR = TREE_VIEW_NODE_SELECTED_COLOR
    BACKGROUND_COLOR = TREE_VIEW_NODE_BACKGROUND_COLOR
    NODE_SIZE = (dp(100), dp(30))


class StoryGroupTreeViewNode(ButtonTreeViewNode):
    TEXT_COLOR = TREE_VIEW_NODE_TEXT_COLOR
    SELECTED_COLOR = TREE_VIEW_NODE_SELECTED_COLOR
    BACKGROUND_COLOR = TREE_VIEW_NODE_BACKGROUND_COLOR
    NODE_WIDTH = dp(250)
    NODE_HEIGHT = dp(30)


class YearRangeTreeViewNode(ButtonTreeViewNode):
    TEXT_COLOR = TREE_VIEW_NODE_TEXT_COLOR
    SELECTED_COLOR = TREE_VIEW_NODE_SELECTED_COLOR
    BACKGROUND_COLOR = TREE_VIEW_NODE_BACKGROUND_COLOR
    NODE_WIDTH = dp(150)
    NODE_HEIGHT = dp(30)


class CsYearRangeTreeViewNode(YearRangeTreeViewNode):
    TEXT_COLOR = TREE_VIEW_NODE_TEXT_COLOR
    SELECTED_COLOR = TREE_VIEW_NODE_SELECTED_COLOR
    BACKGROUND_COLOR = TREE_VIEW_NODE_BACKGROUND_COLOR
    NODE_WIDTH = dp(250)
    NODE_HEIGHT = dp(30)


class UsYearRangeTreeViewNode(YearRangeTreeViewNode):
    TEXT_COLOR = TREE_VIEW_NODE_TEXT_COLOR
    SELECTED_COLOR = TREE_VIEW_NODE_SELECTED_COLOR
    BACKGROUND_COLOR = TREE_VIEW_NODE_BACKGROUND_COLOR
    NODE_WIDTH = dp(250)
    NODE_HEIGHT = dp(30)


class TitleTreeViewNode(BoxLayout, TreeViewNode):
    TEXT_COLOR = TREE_VIEW_NODE_TEXT_COLOR
    SELECTED_COLOR = TREE_VIEW_NODE_SELECTED_COLOR
    BACKGROUND_COLOR = TREE_VIEW_NODE_BACKGROUND_COLOR
    ROW_BACKGROUND_COLOR = BACKGROUND_COLOR
    EVEN_COLOR = [0, 0, 0.4, 0.4]
    ODD_COLOR = [0, 0, 1.0, 0.4]

    ROW_HEIGHT = dp(30)
    NUM_LABEL_WIDTH = dp(40)
    TITLE_LABEL_WIDTH = dp(400)
    ISSUE_LABEL_WIDTH = TITLE_LABEL_WIDTH

    NUM_LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)
    TITLE_LABEL_COLOR = (1.0, 1.0, 0.0, 1.0)
    ISSUE_LABEL_COLOR = (1.0, 1.0, 1.0, 1.0)
    ISSUE_LABEL_SUBMITTED_YEAR_COLOR = "#FCFABE"  # "#FFFF00"

    def __init__(self, fanta_info: FantaComicBookInfo, **kwargs):
        super().__init__(**kwargs)
        self.fanta_info = fanta_info

    def get_title(self) -> Titles:
        return self.fanta_info.comic_book_info.title


class TreeViewButton(Button):
    pass


class TitleTreeViewLabel(Button):
    pass
