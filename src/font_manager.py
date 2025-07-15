import logging

from kivy.event import EventDispatcher
from kivy.metrics import sp
from kivy.properties import NumericProperty


class FontManager(EventDispatcher):
    MAIN_TITLE_FONT_SIZE = NumericProperty()
    TITLE_INFO_FONT_SIZE = NumericProperty()
    TITLE_EXTRA_INFO_FONT_SIZE = NumericProperty()
    GOTO_PAGE_FONT_SIZE = NumericProperty()
    TREE_VIEW_MAIN_NODE_FONT_SIZE = NumericProperty()
    TREE_VIEW_STORY_NODE_FONT_SIZE = NumericProperty()
    TREE_VIEW_YEAR_RANGE_NODE_FONT_SIZE = NumericProperty()
    TREE_VIEW_NUM_LABEL_FONT_SIZE = NumericProperty()
    TREE_VIEW_TITLE_LABEL_FONT_SIZE = NumericProperty()
    TREE_VIEW_ISSUE_LABEL_FONT_SIZE = NumericProperty()
    TREE_VIEW_TITLE_SEARCH_LABEL_FONT_SIZE = NumericProperty()
    TREE_VIEW_TITLE_SEARCH_BOX_FONT_SIZE = NumericProperty()
    TREE_VIEW_TITLE_SPINNER_FONT_SIZE = NumericProperty()
    TREE_VIEW_TAG_SEARCH_LABEL_FONT_SIZE = NumericProperty()
    TREE_VIEW_TAG_SEARCH_BOX_FONT_SIZE = NumericProperty()
    TREE_VIEW_TAG_SPINNER_FONT_SIZE = NumericProperty()
    TREE_VIEW_TAG_TITLE_SPINNER_FONT_SIZE = NumericProperty()

    def update_font_sizes(self, window_height: int):
        """Calculates and sets all font sizes based on window height."""
        logging.debug(f"Updating all font sizes based on window height {window_height}.")

        if window_height <= 1050:
            main_title_font_size = sp(30)
            title_info_font_size = sp(16)
            title_extra_info_font_size = sp(14)
            year_range_font_size = sp(14)
            default_font_size = sp(15)
        else:
            main_title_font_size = sp(40)
            title_info_font_size = sp(20)
            title_extra_info_font_size = sp(18)
            year_range_font_size = sp(18)
            default_font_size = sp(19)

        self.MAIN_TITLE_FONT_SIZE = main_title_font_size
        self.TITLE_INFO_FONT_SIZE = title_info_font_size
        self.TITLE_EXTRA_INFO_FONT_SIZE = title_extra_info_font_size
        self.GOTO_PAGE_FONT_SIZE = default_font_size
        self.TREE_VIEW_MAIN_NODE_FONT_SIZE = default_font_size
        self.TREE_VIEW_STORY_NODE_FONT_SIZE = default_font_size
        self.TREE_VIEW_YEAR_RANGE_NODE_FONT_SIZE = year_range_font_size
        self.TREE_VIEW_NUM_LABEL_FONT_SIZE = default_font_size
        self.TREE_VIEW_TITLE_LABEL_FONT_SIZE = default_font_size
        self.TREE_VIEW_ISSUE_LABEL_FONT_SIZE = default_font_size
        self.TREE_VIEW_TITLE_SEARCH_LABEL_FONT_SIZE = default_font_size
        self.TREE_VIEW_TITLE_SEARCH_BOX_FONT_SIZE = default_font_size
        self.TREE_VIEW_TITLE_SPINNER_FONT_SIZE = default_font_size
        self.TREE_VIEW_TAG_SEARCH_LABEL_FONT_SIZE = default_font_size
        self.TREE_VIEW_TAG_SEARCH_BOX_FONT_SIZE = default_font_size
        self.TREE_VIEW_TAG_SPINNER_FONT_SIZE = default_font_size
        self.TREE_VIEW_TAG_TITLE_SPINNER_FONT_SIZE = default_font_size
