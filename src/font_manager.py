import logging

from kivy.event import EventDispatcher
from kivy.metrics import sp
from kivy.properties import NumericProperty

from barks_fantagraphics.comics_consts import CARL_BARKS_FONT_NAME


class FontManager(EventDispatcher):
    main_title_font_size = NumericProperty()
    title_info_font_size = NumericProperty()
    title_extra_info_font_size = NumericProperty()
    goto_page_font_size = NumericProperty()

    tree_view_main_node_font_size = NumericProperty()
    tree_view_story_node_font_size = NumericProperty()
    tree_view_year_range_node_font_size = NumericProperty()
    tree_view_num_label_font_size = NumericProperty()
    tree_view_title_label_font_size = NumericProperty()
    tree_view_issue_label_font_size = NumericProperty()
    tree_view_title_search_label_font_size = NumericProperty()
    tree_view_title_search_box_font_size = NumericProperty()
    tree_view_title_spinner_font_size = NumericProperty()
    tree_view_tag_search_label_font_size = NumericProperty()
    tree_view_tag_search_box_font_size = NumericProperty()
    tree_view_tag_spinner_font_size = NumericProperty()
    tree_view_tag_title_spinner_font_size = NumericProperty()

    loading_title_size = NumericProperty()

    main_title_font_name = CARL_BARKS_FONT_NAME
    loading_title_font_name = CARL_BARKS_FONT_NAME

    def update_font_sizes(self, window_height: int):
        """Calculates and sets all font sizes based on window height."""
        logging.debug(f"Updating all font sizes based on window height {window_height}.")

        if window_height <= 1050:
            main_title_font_size = sp(30)
            title_info_font_size = sp(16)
            title_extra_info_font_size = sp(14)
            year_range_font_size = sp(14)
            loading_title_size = sp(16)
            default_font_size = sp(15)
        else:
            main_title_font_size = sp(40)
            title_info_font_size = sp(20)
            title_extra_info_font_size = sp(18)
            year_range_font_size = sp(18)
            loading_title_size = sp(20)
            default_font_size = sp(19)

        self.main_title_font_size = main_title_font_size
        self.title_info_font_size = title_info_font_size
        self.title_extra_info_font_size = title_extra_info_font_size
        self.goto_page_font_size = default_font_size

        self.tree_view_main_node_font_size = default_font_size
        self.tree_view_story_node_font_size = default_font_size
        self.tree_view_year_range_node_font_size = year_range_font_size
        self.tree_view_num_label_font_size = default_font_size
        self.tree_view_title_label_font_size = default_font_size
        self.tree_view_issue_label_font_size = default_font_size
        self.tree_view_title_search_label_font_size = default_font_size
        self.tree_view_title_search_box_font_size = default_font_size
        self.tree_view_title_spinner_font_size = default_font_size
        self.tree_view_tag_search_label_font_size = default_font_size
        self.tree_view_tag_search_box_font_size = default_font_size
        self.tree_view_tag_spinner_font_size = default_font_size
        self.tree_view_tag_title_spinner_font_size = default_font_size

        self.loading_title_size = loading_title_size
