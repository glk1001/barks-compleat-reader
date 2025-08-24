from barks_fantagraphics.comics_consts import CARL_BARKS_FONT_NAME
from kivy.event import EventDispatcher
from kivy.metrics import sp
from kivy.properties import NumericProperty
from loguru import logger

HI_RES_WINDOW_HEIGHT_CUTOFF = 1050


class FontManager(EventDispatcher):
    main_title_font_size = NumericProperty()
    title_info_font_size = NumericProperty()
    title_extra_info_font_size = NumericProperty()
    check_box_font_size = NumericProperty()
    error_main_view_font_size = NumericProperty()
    error_popup_font_size = NumericProperty()
    error_popup_button_font_size = NumericProperty()
    text_block_heading_font_size = NumericProperty()

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

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self.app_title_font_size = 0

    def update_font_sizes(self, window_height: int) -> None:
        """Calculate and set all font sizes based on window height."""
        logger.debug(f"Updating all font sizes based on window height {window_height}.")

        if window_height <= HI_RES_WINDOW_HEIGHT_CUTOFF:
            main_title_font_size = sp(30)
            title_info_font_size = sp(16)
            title_extra_info_font_size = sp(14)
            year_range_font_size = sp(14)
            loading_title_size = sp(16)
            checkbox_font_size = sp(14)
            default_font_size = sp(15)
            error_main_view_font_size = sp(40)
            error_popup_font_size = sp(16)
            error_popup_button_font_size = sp(13)
            text_block_heading_font_size = sp(20)
            self.app_title_font_size = sp(12)
        else:
            main_title_font_size = sp(40)
            title_info_font_size = sp(20)
            title_extra_info_font_size = sp(18)
            year_range_font_size = sp(18)
            loading_title_size = sp(20)
            checkbox_font_size = sp(19)
            default_font_size = sp(19)
            error_main_view_font_size = sp(50)
            error_popup_font_size = sp(25)
            error_popup_button_font_size = sp(18)
            text_block_heading_font_size = sp(25)
            self.app_title_font_size = sp(17)

        self.main_title_font_size = main_title_font_size
        self.title_info_font_size = title_info_font_size
        self.title_extra_info_font_size = title_extra_info_font_size
        self.check_box_font_size = checkbox_font_size
        self.error_main_view_font_size = error_main_view_font_size
        self.error_popup_font_size = error_popup_font_size
        self.error_popup_button_font_size = error_popup_button_font_size
        self.text_block_heading_font_size = text_block_heading_font_size

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
