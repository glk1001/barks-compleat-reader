from enum import Enum, auto

from barks_fantagraphics.comics_consts import CARL_BARKS_FONT
from kivy.event import EventDispatcher
from kivy.metrics import sp
from kivy.properties import NumericProperty
from loguru import logger

HI_RES_WINDOW_HEIGHT_CUTOFF = 1050


class _FontGroup(Enum):
    NOT_SET = auto()
    LOW_RES = auto()
    HI_RES = auto()


class FontManager(EventDispatcher):
    main_title_font_size = NumericProperty()
    title_info_font_size = NumericProperty()
    title_extra_info_font_size = NumericProperty()
    index_menu_font_size = NumericProperty()
    index_item_font_size = NumericProperty()
    index_title_font_size = NumericProperty()
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

    main_title_font_name = CARL_BARKS_FONT
    loading_title_font_name = main_title_font_name

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self.app_title_font_size = 0
        self._previous_font_group: _FontGroup = _FontGroup.NOT_SET

    def update_font_sizes(self, window_height: int) -> None:
        """Calculate and set all font sizes based on window height."""
        required_font_group = (
            _FontGroup.LOW_RES
            if window_height <= HI_RES_WINDOW_HEIGHT_CUTOFF
            else _FontGroup.HI_RES
        )

        if required_font_group == self._previous_font_group:
            logger.debug(
                f"Updating font sizes requested but the required font group"
                f" {required_font_group.name}, is the same as the previously"
                f" requested font group. So nothing to do!"
            )
            return

        logger.debug(
            f"Updating font sizes based on window height {window_height}."
            f" Required font group is {required_font_group.name}."
        )

        if required_font_group == _FontGroup.LOW_RES:
            main_title_font_size = sp(30)
            title_info_font_size = sp(16)
            title_extra_info_font_size = sp(14)
            index_menu_font_size = sp(13)
            index_item_font_size = sp(12)
            index_title_font_size = sp(12)
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
            index_menu_font_size = sp(17)
            index_item_font_size = sp(16)
            index_title_font_size = sp(16)
            year_range_font_size = sp(18)
            loading_title_size = sp(20)
            checkbox_font_size = sp(19)
            default_font_size = sp(19)
            error_main_view_font_size = sp(40)
            error_popup_font_size = sp(23)
            error_popup_button_font_size = sp(18)
            text_block_heading_font_size = sp(25)
            self.app_title_font_size = sp(17)

        self.main_title_font_size = main_title_font_size
        self.title_info_font_size = title_info_font_size
        self.title_extra_info_font_size = title_extra_info_font_size
        self.index_menu_font_size = index_menu_font_size
        self.index_item_font_size = index_item_font_size
        self.index_title_font_size = index_title_font_size
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

        self._previous_font_group = required_font_group
