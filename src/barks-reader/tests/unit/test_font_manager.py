# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# noinspection PyProtectedMember
from barks_reader.font_manager import (
    HI_RES_FONTS,
    HI_RES_WINDOW_HEIGHT_CUTOFF,
    LOW_RES_FONTS,
    FontManager,
    _FontGroup,
)


@pytest.fixture
def font_manager() -> FontManager:
    return FontManager()


def test_initialization(font_manager: FontManager) -> None:
    # Check initial state
    assert font_manager.app_title_font_size == 0
    # Check internal state
    # noinspection PyProtectedMember
    assert font_manager._previous_font_group == _FontGroup.NOT_SET


def test_update_font_sizes_low_res(font_manager: FontManager) -> None:
    # Height <= 1090  # noqa: ERA001
    height = HI_RES_WINDOW_HEIGHT_CUTOFF
    font_manager.update_font_sizes(height)

    # Check a few properties to ensure LOW_RES_FONTS were applied
    assert font_manager.main_title_font_size == LOW_RES_FONTS.main_title
    assert font_manager.index_item_font_size == LOW_RES_FONTS.index_item
    assert font_manager.app_title_font_size == LOW_RES_FONTS.app_title

    # Check internal state
    # noinspection PyProtectedMember
    assert font_manager._previous_font_group == _FontGroup.LOW_RES


def test_update_font_sizes_hi_res(font_manager: FontManager) -> None:
    # Height > 1090
    height = HI_RES_WINDOW_HEIGHT_CUTOFF + 1
    font_manager.update_font_sizes(height)

    # Check a few properties to ensure HI_RES_FONTS were applied
    assert font_manager.main_title_font_size == HI_RES_FONTS.main_title
    assert font_manager.index_item_font_size == HI_RES_FONTS.index_item
    assert font_manager.app_title_font_size == HI_RES_FONTS.app_title

    # Check internal state
    # noinspection PyProtectedMember
    assert font_manager._previous_font_group == _FontGroup.HI_RES


def test_update_font_sizes_optimization(font_manager: FontManager) -> None:
    # 1. Set to Low Res
    font_manager.update_font_sizes(1000)
    # noinspection PyProtectedMember
    assert font_manager._previous_font_group == _FontGroup.LOW_RES

    # Mock _apply_font_theme to verify it's not called again
    with patch.object(font_manager, "_apply_font_theme") as mock_apply:
        # 2. Update with another Low Res height
        font_manager.update_font_sizes(800)

        mock_apply.assert_not_called()

        # 3. Update with Hi Res height
        font_manager.update_font_sizes(2000)

        mock_apply.assert_called_once()
        # noinspection PyProtectedMember
        assert font_manager._previous_font_group == _FontGroup.HI_RES


def test_apply_font_theme_mapping(font_manager: FontManager) -> None:  # noqa: PLR0915
    # Create a dummy theme with distinct values to verify mapping
    mock_theme = MagicMock()
    mock_theme.main_title = 10
    mock_theme.main_title_footnote = 11
    mock_theme.title_info = 12
    mock_theme.title_extra_info = 13
    mock_theme.index_menu = 14
    mock_theme.index_item = 15
    mock_theme.index_title_item = 16
    mock_theme.speech_bubble_popup_title = 17
    mock_theme.speech_bubble_text = 18
    mock_theme.year_range = 19
    mock_theme.message_title = 20
    mock_theme.checkbox = 21
    mock_theme.default = 22
    mock_theme.error_main_view = 23
    mock_theme.error_popup = 24
    mock_theme.error_popup_button = 25
    mock_theme.text_block_heading = 26
    mock_theme.app_title = 27
    mock_theme.about_box_title = 28
    mock_theme.about_box_version = 29
    mock_theme.about_box_fine_print = 30

    # noinspection PyProtectedMember
    font_manager._apply_font_theme(mock_theme)

    assert font_manager.main_title_font_size == 10
    assert font_manager.main_title_footnote_font_size == 11
    assert font_manager.title_info_font_size == 12
    assert font_manager.title_extra_info_font_size == 13
    assert font_manager.index_menu_font_size == 14
    assert font_manager.index_item_font_size == 15
    assert font_manager.index_title_item_font_size == 16
    assert font_manager.speech_bubble_popup_title_font_size == 17
    assert font_manager.speech_bubble_text_font_size == 18
    assert font_manager.tree_view_year_range_node_font_size == 19
    assert font_manager.message_title_size == 20
    assert font_manager.check_box_font_size == 21

    # Defaults
    assert font_manager.tree_view_main_node_font_size == 22
    assert font_manager.tree_view_story_node_font_size == 22
    assert font_manager.tree_view_num_label_font_size == 22
    assert font_manager.tree_view_title_label_font_size == 22
    assert font_manager.tree_view_issue_label_font_size == 22
    assert font_manager.tree_view_title_search_label_font_size == 22
    assert font_manager.tree_view_title_search_box_font_size == 22
    assert font_manager.tree_view_title_spinner_font_size == 22
    assert font_manager.tree_view_tag_search_label_font_size == 22
    assert font_manager.tree_view_tag_search_box_font_size == 22
    assert font_manager.tree_view_tag_spinner_font_size == 22
    assert font_manager.tree_view_tag_title_spinner_font_size == 22

    assert font_manager.error_main_view_font_size == 23
    assert font_manager.error_popup_font_size == 24
    assert font_manager.error_popup_button_font_size == 25
    assert font_manager.text_block_heading_font_size == 26
    assert font_manager.app_title_font_size == 27
    assert font_manager.about_box_title_font_size == 28
    assert font_manager.about_box_version_font_size == 29
    assert font_manager.about_box_fine_print_font_size == 30
