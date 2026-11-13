from dataclasses import fields, replace

from barks_fantagraphics.comics_consts import (
    CARL_BARKS_FONT_FILE,
    EXTRA_INFO_FONT,
    FONT_DIR,
    ROBOTO_FONT,
    SPEECH_FONT,
)
from kivy.core.text import LabelBase
from kivy.event import EventDispatcher
from kivy.metrics import sp
from kivy.properties import NumericProperty  # ty: ignore[import-not-found]
from loguru import logger

from barks_reader.core.font_sizes import (
    HI_RES_FONT_SIZES,
    LOW_RES_FONT_SIZES,
    FontGroup,
    FontTheme,
    font_group_for_height,
    title_text_sizes_for_height,
)

# Set up custom fonts.
LabelBase.register(
    name=SPEECH_FONT,
    fn_regular=str(FONT_DIR / "DejaVuSansCondensed.ttf"),
    fn_bold=str(FONT_DIR / "DejaVuSansCondensed-Bold.ttf"),
    fn_italic=str(FONT_DIR / "DejaVuSansCondensed-Oblique.ttf"),
    fn_bolditalic=str(FONT_DIR / "DejaVuSansCondensed-BoldOblique.ttf"),
)
LabelBase.register(
    name=EXTRA_INFO_FONT,
    fn_regular=str(FONT_DIR / "SourceSerif4SmText-Regular.ttf"),
    fn_bold=str(FONT_DIR / "SourceSerif4SmText-Bold.ttf"),
    fn_italic=str(FONT_DIR / "SourceSerif4SmText-It.ttf"),
    fn_bolditalic=str(FONT_DIR / "SourceSerif4SmText-BoldIt.ttf"),
)


def _scaled(sizes: FontTheme) -> FontTheme:
    """Return `sizes` in Kivy's scaled pixels, as the display takes them."""
    return replace(sizes, **{f.name: sp(getattr(sizes, f.name)) for f in fields(sizes)})


# Scaled once, at import, where `popup_fonts` (`ui.popup_frame`) scales at every call: were
# the display's density or font scale to change under the running app (its window moved
# to a monitor of another DPI), the app's text and the popups' would part. Nothing does
# that today, and left so on purpose (2026-11-10): scaling in `update_font_sizes` is not
# enough, which returns early while the font group is unchanged, so it wants a hook on the
# density change too.
LOW_RES_FONTS = _scaled(LOW_RES_FONT_SIZES)
HI_RES_FONTS = _scaled(HI_RES_FONT_SIZES)


class FontManager(EventDispatcher):
    main_title_font_size = NumericProperty()
    main_title_footnote_font_size = NumericProperty()
    title_info_font_size = NumericProperty()
    title_extra_info_font_size = NumericProperty()
    index_menu_font_size = NumericProperty()
    index_prefix_font_size = NumericProperty()
    main_index_item_font_size = NumericProperty()
    speech_index_item_font_size = NumericProperty()
    index_title_item_font_size = NumericProperty()
    speech_bubble_text_font_size = NumericProperty()
    check_box_font_size = NumericProperty()
    error_main_view_font_size = NumericProperty()
    text_block_heading_font_size = NumericProperty()
    search_result_font_size = NumericProperty()
    search_input_font_size = NumericProperty()
    search_tag_chip_font_size = NumericProperty()
    search_label_font_size = NumericProperty()
    search_clear_button_font_size = NumericProperty()
    search_button_font_size = NumericProperty()
    history_bar_button_font_size = NumericProperty()
    statistics_tab_font_size = NumericProperty()

    tree_view_main_node_font_size = NumericProperty()
    tree_view_story_node_font_size = NumericProperty()
    tree_view_year_range_node_font_size = NumericProperty()
    tree_view_num_label_font_size = NumericProperty()
    tree_view_title_label_font_size = NumericProperty()
    tree_view_issue_label_font_size = NumericProperty()
    tree_view_playlist_intro_font_size = NumericProperty()
    tree_view_title_search_label_font_size = NumericProperty()
    tree_view_title_search_box_font_size = NumericProperty()
    tree_view_title_spinner_font_size = NumericProperty()
    tree_view_tag_search_label_font_size = NumericProperty()
    tree_view_tag_search_box_font_size = NumericProperty()
    tree_view_tag_spinner_font_size = NumericProperty()
    tree_view_tag_title_spinner_font_size = NumericProperty()

    main_title_font_name = str(CARL_BARKS_FONT_FILE)
    title_extra_info_font_name = EXTRA_INFO_FONT
    main_index_item_font_name = ROBOTO_FONT
    speech_index_item_font_name = SPEECH_FONT  # Allows for words like H2O and music notes
    speech_bubble_text_font_name = SPEECH_FONT
    speech_bubble_popup_title_font_name = SPEECH_FONT
    index_title_item_font_name = ROBOTO_FONT

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.app_title_font_size = 0.0

        self.about_box_title_font_name = str(CARL_BARKS_FONT_FILE)
        self.about_box_title_font_size = 0.0
        self.about_box_version_font_size = 0.0

        self._previous_font_group = FontGroup.NOT_SET

    def update_font_sizes(self, window_height: int) -> None:
        """Calculate and set all font sizes based on window height."""
        # Before the check below: these follow every change of height, not the font group.
        title_text = title_text_sizes_for_height(window_height)
        self.title_info_font_size = title_text.info
        self.title_extra_info_font_size = title_text.notes

        required_font_group = font_group_for_height(window_height)

        if required_font_group == self._previous_font_group:
            logger.debug(
                f"Font group {required_font_group.name} is unchanged:"
                f" only the title text sizes follow this height."
            )
            return

        logger.debug(
            f"Updating font sizes based on window height {window_height}."
            f" Required font group is {required_font_group.name}."
        )

        theme = LOW_RES_FONTS if required_font_group == FontGroup.LOW_RES else HI_RES_FONTS
        self._apply_font_theme(theme)

        self._previous_font_group = required_font_group

    def _apply_font_theme(self, theme: FontTheme) -> None:
        """Assign all font sizes from a theme object."""
        self.main_title_font_size = theme.main_title
        self.main_title_footnote_font_size = theme.main_title_footnote
        self.index_menu_font_size = theme.index_menu
        self.index_prefix_font_size = theme.index_prefix
        self.main_index_item_font_size = theme.main_index_item
        self.speech_index_item_font_size = theme.speech_index_item
        self.index_title_item_font_size = theme.index_title_item
        self.speech_bubble_text_font_size = theme.speech_bubble_text
        self.check_box_font_size = theme.checkbox
        self.error_main_view_font_size = theme.error_main_view
        self.text_block_heading_font_size = theme.text_block_heading
        self.app_title_font_size = theme.app_title
        self.about_box_title_font_size = theme.about_box_title
        self.about_box_version_font_size = theme.about_box_version
        self.search_result_font_size = theme.search_result
        self.search_input_font_size = theme.search_input
        self.search_tag_chip_font_size = theme.search_tag_chip
        self.search_label_font_size = theme.search_label
        self.search_clear_button_font_size = theme.search_clear_button
        self.search_button_font_size = theme.search_button
        self.history_bar_button_font_size = theme.history_bar_button
        self.statistics_tab_font_size = theme.statistics_tab

        # Apply default and specific sizes for tree view
        self.tree_view_main_node_font_size = theme.default
        self.tree_view_story_node_font_size = theme.default
        self.tree_view_year_range_node_font_size = theme.year_range
        self.tree_view_num_label_font_size = theme.default
        self.tree_view_title_label_font_size = theme.default
        self.tree_view_issue_label_font_size = theme.default
        # Prose, not a tree label.
        self.tree_view_playlist_intro_font_size = theme.playlist_intro
        self.tree_view_title_search_label_font_size = theme.default
        self.tree_view_title_search_box_font_size = theme.default
        self.tree_view_title_spinner_font_size = theme.default
        self.tree_view_tag_search_label_font_size = theme.default
        self.tree_view_tag_search_box_font_size = theme.default
        self.tree_view_tag_spinner_font_size = theme.default
        self.tree_view_tag_title_spinner_font_size = theme.default
