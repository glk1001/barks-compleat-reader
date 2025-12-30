from dataclasses import dataclass
from enum import Enum, auto

from barks_fantagraphics.comics_consts import CARL_BARKS_FONT, FREE_SANS_FONT
from kivy.event import EventDispatcher
from kivy.metrics import sp
from kivy.properties import NumericProperty  # ty: ignore[unresolved-import]
from loguru import logger

HI_RES_WINDOW_HEIGHT_CUTOFF = 1090


class _FontGroup(Enum):
    NOT_SET = auto()
    LOW_RES = auto()
    HI_RES = auto()


@dataclass
class FontTheme:
    """A data class to hold all font sizes for a given theme."""

    main_title: float
    main_title_footnote: float
    title_info: float
    title_extra_info: float
    index_menu: float
    index_item: float
    index_title: float
    speech_bubble_text: float
    year_range: float
    message_title: float
    checkbox: float
    default: float
    error_main_view: float
    error_popup: float
    error_popup_button: float
    text_block_heading: float
    app_title: float
    about_box_title: float
    about_box_version: float
    about_box_fine_print: float


LOW_RES_FONTS = FontTheme(
    main_title=sp(30),
    main_title_footnote=sp(9),
    title_info=sp(16),
    title_extra_info=sp(14),
    index_menu=sp(13),
    index_item=sp(12),
    index_title=sp(12),
    speech_bubble_text=sp(12),
    year_range=sp(14),
    message_title=sp(16),
    checkbox=sp(14),
    default=sp(15),
    error_main_view=sp(40),
    error_popup=sp(16),
    error_popup_button=sp(13),
    text_block_heading=sp(20),
    app_title=sp(12),
    about_box_title=sp(20),
    about_box_version=sp(15),
    about_box_fine_print=sp(12),
)
HI_RES_FONTS = FontTheme(
    main_title=sp(40),
    main_title_footnote=sp(10),
    title_info=sp(20),
    title_extra_info=sp(18),
    index_menu=sp(17),
    index_item=sp(16),
    index_title=sp(16),
    speech_bubble_text=sp(14),
    year_range=sp(18),
    message_title=sp(20),
    checkbox=sp(19),
    default=sp(19),
    error_main_view=sp(40),
    error_popup=sp(23),
    error_popup_button=sp(18),
    text_block_heading=sp(25),
    app_title=sp(17),
    about_box_title=sp(25),
    about_box_version=sp(20),
    about_box_fine_print=sp(14),
)


class FontManager(EventDispatcher):
    main_title_font_size = NumericProperty()
    main_title_footnote_font_size = NumericProperty()
    title_info_font_size = NumericProperty()
    title_extra_info_font_size = NumericProperty()
    index_menu_font_size = NumericProperty()
    index_item_font_size = NumericProperty()
    index_title_font_size = NumericProperty()
    speech_bubble_text_font_size = NumericProperty()
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

    message_title_size = NumericProperty()

    main_title_font_name = str(CARL_BARKS_FONT)
    message_title_font_name = main_title_font_name
    speech_bubble_text_font_name = main_title_font_name

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self.app_title_font_size = 0

        self.about_box_title_font_name = str(CARL_BARKS_FONT)
        self.about_box_title_font_size = 0
        self.about_box_version_font_size = 0
        self.about_box_fine_print_font_size = 0

        self.speech_index_items_font_name = str(FREE_SANS_FONT)

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

        theme = LOW_RES_FONTS if required_font_group == _FontGroup.LOW_RES else HI_RES_FONTS
        self._apply_font_theme(theme)

        self._previous_font_group = required_font_group

    def _apply_font_theme(self, theme: FontTheme) -> None:
        """Assign all font sizes from a theme object."""
        self.main_title_font_size = theme.main_title
        self.main_title_footnote_font_size = theme.main_title_footnote
        self.title_info_font_size = theme.title_info
        self.title_extra_info_font_size = theme.title_extra_info
        self.index_menu_font_size = theme.index_menu
        self.index_item_font_size = theme.index_item
        self.index_title_font_size = theme.index_title
        self.speech_bubble_text_font_size = theme.speech_bubble_text
        self.check_box_font_size = theme.checkbox
        self.error_main_view_font_size = theme.error_main_view
        self.error_popup_font_size = theme.error_popup
        self.error_popup_button_font_size = theme.error_popup_button
        self.text_block_heading_font_size = theme.text_block_heading
        self.app_title_font_size = theme.app_title
        self.about_box_title_font_size = theme.about_box_title
        self.about_box_version_font_size = theme.about_box_version
        self.about_box_fine_print_font_size = theme.about_box_fine_print
        self.message_title_size = theme.message_title

        # Apply default and specific sizes for tree view
        self.tree_view_main_node_font_size = theme.default
        self.tree_view_story_node_font_size = theme.default
        self.tree_view_year_range_node_font_size = theme.year_range
        self.tree_view_num_label_font_size = theme.default
        self.tree_view_title_label_font_size = theme.default
        self.tree_view_issue_label_font_size = theme.default
        self.tree_view_title_search_label_font_size = theme.default
        self.tree_view_title_search_box_font_size = theme.default
        self.tree_view_title_spinner_font_size = theme.default
        self.tree_view_tag_search_label_font_size = theme.default
        self.tree_view_tag_search_box_font_size = theme.default
        self.tree_view_tag_spinner_font_size = theme.default
        self.tree_view_tag_title_spinner_font_size = theme.default
