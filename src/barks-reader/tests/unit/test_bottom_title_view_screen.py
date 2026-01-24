# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.ui import bottom_title_view_screen
from barks_reader.ui.bottom_title_view_screen import BottomTitleViewScreen

if TYPE_CHECKING:
    from collections.abc import Generator

    from kivy.uix.widget import Widget


class TestBottomTitleViewScreen:
    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, Any]:
        self.mock_settings = MagicMock()
        self.mock_settings.is_first_use_of_reader = False
        self.mock_settings.file_paths.barks_panels_are_encrypted = False
        self.mock_settings.file_paths.get_comic_inset_file.return_value = "inset.png"

        self.mock_font_manager = MagicMock()

        # Patch dependencies
        self.patcher_loader = patch.object(bottom_title_view_screen, "PanelTextureLoader")
        self.mock_loader_cls = self.patcher_loader.start()
        self.mock_loader = self.mock_loader_cls.return_value

        self.patcher_formatter = patch.object(bottom_title_view_screen, "ReaderFormatter")
        self.mock_formatter_cls = self.patcher_formatter.start()
        self.mock_formatter = self.mock_formatter_cls.return_value
        self.mock_formatter.get_main_title.return_value = "Main Title"
        self.mock_formatter.get_title_info.return_value = "Title Info"
        self.mock_formatter.get_title_extra_info.return_value = "Extra Info"

        self.patcher_anim = patch.object(bottom_title_view_screen, "Animation")
        self.mock_anim_cls = self.patcher_anim.start()
        self.mock_anim = self.mock_anim_cls.return_value

        self.patcher_utils = patch.object(bottom_title_view_screen, "title_needs_footnote")
        self.mock_needs_footnote = self.patcher_utils.start()
        self.mock_needs_footnote.return_value = False

        # Patch FloatLayout.__init__ to inject mock ids
        self.patcher_layout = patch.object(
            bottom_title_view_screen.FloatLayout, "__init__", autospec=True
        )
        self.mock_layout_init = self.patcher_layout.start()

        def side_effect(instance: Widget, **_kwargs) -> None:  # noqa: ANN003
            instance.ids = MagicMock()
            instance.ids.use_overrides_checkbox = MagicMock()
            instance.ids.bottom_view_box = MagicMock()
            instance.ids.title_show_button = MagicMock()

        self.mock_layout_init.side_effect = side_effect

        self.screen = BottomTitleViewScreen(self.mock_settings, self.mock_font_manager)

        self.mock_overrides = MagicMock()
        self.screen.set_special_fanta_overrides(self.mock_overrides)

        yield

        self.patcher_loader.stop()
        self.patcher_formatter.stop()
        self.patcher_anim.stop()
        self.patcher_utils.stop()
        self.patcher_layout.stop()

    def test_set_title_view(self) -> None:
        mock_info = MagicMock()
        mock_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        mock_info.comic_book_info.is_barks_title = True
        mock_info.comic_book_info.get_title_str.return_value = "Donald Duck Finds Pirate Gold"

        self.screen.set_title_view(mock_info)

        assert self.screen.main_title_text == "Main Title"
        assert self.screen.title_info_text == "Title Info"
        assert self.screen.title_extra_info_text == "Extra Info"
        assert self.screen.main_title_footnote == ""

        # Verify image loading
        self.mock_loader.load_texture.assert_called()
        args, _ = self.mock_loader.load_texture.call_args
        assert args[0] == "inset.png"

    def test_set_title_view_with_footnote(self) -> None:
        self.mock_needs_footnote.return_value = True
        mock_info = MagicMock()
        mock_info.get_short_issue_title.return_value = "FC 9"
        mock_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD

        self.screen.set_title_view(mock_info)

        assert "[*] Rejected by Western" in self.screen.main_title_footnote

    def test_on_use_overrides_checkbox_changed(self) -> None:
        # Setup state
        mock_info = MagicMock()
        mock_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        self.screen.set_title_view(mock_info)

        self.mock_overrides.get_title_page_inset_file.return_value = "override.png"

        # Trigger change
        # noinspection PyProtectedMember
        self.screen._on_use_overrides_checkbox_changed(None, use_overrides=True)

        self.mock_overrides.get_title_page_inset_file.assert_called_with(
            Titles.DONALD_DUCK_FINDS_PIRATE_GOLD,
            True,  # noqa: FBT003
        )
        # Should load the new image
        args, _ = self.mock_loader.load_texture.call_args
        assert args[0] == "override.png"

    def test_fade_in_bottom_view_title(self) -> None:
        self.screen.fade_in_bottom_view_title()
        self.mock_anim.start.assert_called_with(self.screen.ids.bottom_view_box)
        assert self.screen.ids.title_show_button.opacity == 1

    def test_set_goto_page_state(self) -> None:
        # Active with page
        self.screen.set_goto_page_state("5", active=True)
        assert self.screen.goto_page_num == "5"
        assert self.screen.goto_page_active

        # Inactive
        self.screen.set_goto_page_state(active=False)
        assert not self.screen.goto_page_active

        # Comic begin page
        self.screen.set_goto_page_state(COMIC_BEGIN_PAGE, active=True)
        assert self.screen.goto_page_num == ""

    def test_set_overrides_state(self) -> None:
        self.screen.set_overrides_state("Description", active=False)
        assert self.screen.use_overrides_description == "Description"
        assert not self.screen.use_overrides_active

    def test_on_title_portal_image_pressed(self) -> None:
        mock_callback = MagicMock()
        self.screen.on_title_portal_image_pressed_func = mock_callback

        self.screen.on_title_portal_image_pressed()
        mock_callback.assert_called_once()

    def test_get_main_title_str(self) -> None:
        # Case 1: Barks title
        mock_info = MagicMock()
        mock_info.comic_book_info.is_barks_title = True
        mock_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        # noinspection PyProtectedMember
        assert "Donald Duck\nFinds" in self.screen._get_main_title_str(mock_info)

        # Case 2: Non-Barks title
        mock_info.comic_book_info.is_barks_title = False
        mock_info.comic_book_info.get_title_from_issue_name.return_value = "Issue Title"
        # noinspection PyProtectedMember
        assert self.screen._get_main_title_str(mock_info) == "Issue Title"
