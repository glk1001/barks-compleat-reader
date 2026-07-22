# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.ui import bottom_title_view_screen
from barks_reader.ui.bottom_title_view_screen import BottomTitleViewScreen
from barks_reader.ui.reader_keyboard_nav import KEY_DOWN, KEY_ENTER, KEY_ESCAPE, KEY_UP

if TYPE_CHECKING:
    from collections.abc import Generator

    from kivy.uix.widget import Widget


class ScreenFixtureBase:
    @pytest.fixture(autouse=True)
    def setup(self) -> Generator[None, Any]:
        self.mock_settings = MagicMock()
        self.mock_settings.is_first_use_of_reader = False
        self.mock_settings.wiki_bundle_dir = None
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

        self.patcher_update_focus = patch.object(bottom_title_view_screen, "update_focus_in_list")
        self.mock_update_focus = self.patcher_update_focus.start()
        self.patcher_clear_focus = patch.object(bottom_title_view_screen, "clear_focus_in_list")
        self.mock_clear_focus = self.patcher_clear_focus.start()

        # Patch FloatLayout.__init__ to inject mock ids
        self.patcher_layout = patch.object(
            bottom_title_view_screen.FloatLayout, "__init__", autospec=True
        )
        self.mock_layout_init = self.patcher_layout.start()

        def side_effect(instance: Widget, **_kwargs) -> None:  # noqa: ANN003
            instance.ids = MagicMock()
            instance.ids.use_overrides_checkbox = MagicMock()
            instance.ids.use_overrides_layout = MagicMock()
            instance.ids.goto_page_checkbox = MagicMock()
            instance.ids.goto_page_layout = MagicMock()
            instance.ids.wiki_page_button = MagicMock()
            instance.ids.title_portal_image_button = MagicMock()
            instance.ids.bottom_view_box = MagicMock()
            instance.ids.bottom_view_box.opacity = 1.0
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
        self.patcher_update_focus.stop()
        self.patcher_clear_focus.stop()
        self.patcher_layout.stop()


class TestBottomTitleViewScreen(ScreenFixtureBase):
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

    def test_on_wiki_page_button_pressed(self) -> None:
        mock_callback = MagicMock()
        self.screen.on_wiki_page_button_pressed_func = mock_callback

        self.screen.on_wiki_page_button_pressed()
        mock_callback.assert_called_once()

    def test_wiki_button_hidden_when_no_bundle(self) -> None:
        mock_info = MagicMock()
        mock_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD

        self.screen.set_title_view(mock_info)

        assert not self.screen.wiki_button_visible

    def test_wiki_button_visible_when_page_exists(self) -> None:
        self.mock_settings.wiki_bundle_dir = Path("/bundle")
        mock_info = MagicMock()
        mock_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD

        with patch.object(
            bottom_title_view_screen,
            "wiki_page_for_title",
            return_value=Path("/bundle/concept/stories/donald-duck/pirate-gold.md"),
        ) as wiki_page_mock:
            self.screen.set_title_view(mock_info)

        wiki_page_mock.assert_called_with(Path("/bundle"), Titles.DONALD_DUCK_FINDS_PIRATE_GOLD)
        assert self.screen.wiki_button_visible

    def test_wiki_button_hidden_when_page_missing(self) -> None:
        self.mock_settings.wiki_bundle_dir = Path("/bundle")
        mock_info = MagicMock()
        mock_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD

        with patch.object(bottom_title_view_screen, "wiki_page_for_title", return_value=None):
            self.screen.set_title_view(mock_info)

        assert not self.screen.wiki_button_visible

    def test_get_main_title_str(self) -> None:
        # Case 1: Barks title
        mock_info = MagicMock()
        mock_info.comic_book_info.is_barks_title = True
        mock_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        assert "Donald Duck\nFinds" in self.screen._get_main_title_str(mock_info)

        # Case 2: Non-Barks title
        mock_info.comic_book_info.is_barks_title = False
        mock_info.comic_book_info.get_title_from_issue_name.return_value = "Issue Title"
        assert self.screen._get_main_title_str(mock_info) == "Issue Title"


class TestBottomTitleViewNav(ScreenFixtureBase):
    def _make_all_widgets_visible(self) -> None:
        self.screen.wiki_button_visible = True
        self.screen.use_overrides_description = "Use censorship fixes"
        self.screen.goto_page_num = "5"

    def test_focusable_widgets_defaults_to_eye_and_portal(self) -> None:
        ids = self.screen.ids
        assert self.screen._focusable_widgets() == [
            ids.title_show_button,
            ids.title_portal_image_button,
        ]

    def test_focusable_widgets_all_visible_in_visual_order(self) -> None:
        self._make_all_widgets_visible()
        ids = self.screen.ids
        assert self.screen._focusable_widgets() == [
            ids.title_show_button,
            ids.wiki_page_button,
            ids.use_overrides_layout,
            ids.goto_page_layout,
            ids.title_portal_image_button,
        ]

    def test_focusable_widgets_only_eye_when_peeked(self) -> None:
        self._make_all_widgets_visible()
        self.screen.ids.bottom_view_box.opacity = 0
        assert self.screen._focusable_widgets() == [self.screen.ids.title_show_button]

    def test_enter_nav_focus_defaults_to_portal(self) -> None:
        self.screen.enter_nav_focus(MagicMock())

        (widgets, focused_idx, group), _ = self.mock_update_focus.call_args
        assert widgets == self.screen._all_nav_widgets()
        assert widgets[focused_idx] is self.screen.ids.title_portal_image_button
        assert group == bottom_title_view_screen._NAV_FOCUS_GROUP

    def test_enter_nav_focus_while_peeked_focuses_eye(self) -> None:
        self.screen.ids.bottom_view_box.opacity = 0

        self.screen.enter_nav_focus(MagicMock())

        assert self.screen._nav_focused_widget is self.screen.ids.title_show_button

    def test_up_cycles_through_widgets_and_wraps(self) -> None:
        self._make_all_widgets_visible()
        self.screen.enter_nav_focus(MagicMock())
        ids = self.screen.ids

        expected = [
            ids.goto_page_layout,
            ids.use_overrides_layout,
            ids.wiki_page_button,
            ids.title_show_button,
            ids.title_portal_image_button,  # Wrapped back around.
        ]
        for widget in expected:
            assert self.screen.handle_key(KEY_UP) is True
            assert self.screen._nav_focused_widget is widget

    def test_down_from_portal_wraps_to_eye(self) -> None:
        self._make_all_widgets_visible()
        self.screen.enter_nav_focus(MagicMock())

        assert self.screen.handle_key(KEY_DOWN) is True
        assert self.screen._nav_focused_widget is self.screen.ids.title_show_button

    def test_up_skips_hidden_rows(self) -> None:
        # Only the wiki chip is visible above the portal.
        self.screen.wiki_button_visible = True
        self.screen.enter_nav_focus(MagicMock())

        self.screen.handle_key(KEY_UP)

        assert self.screen._nav_focused_widget is self.screen.ids.wiki_page_button

    def test_enter_on_portal_opens_comic(self) -> None:
        callback = MagicMock()
        self.screen.on_title_portal_image_pressed_func = callback
        self.screen.enter_nav_focus(MagicMock())

        assert self.screen.handle_key(KEY_ENTER) is True
        callback.assert_called_once()

    def test_enter_toggles_goto_page_checkbox(self) -> None:
        self._make_all_widgets_visible()
        self.screen.ids.goto_page_checkbox.active = True
        self.screen.enter_nav_focus(MagicMock())

        self.screen.handle_key(KEY_UP)  # Portal -> goto-page row.
        self.screen.handle_key(KEY_ENTER)

        assert self.screen.ids.goto_page_checkbox.active is False

    def test_enter_toggles_use_overrides_checkbox(self) -> None:
        self._make_all_widgets_visible()
        self.screen.ids.use_overrides_checkbox.active = False
        self.screen.enter_nav_focus(MagicMock())

        self.screen.handle_key(KEY_UP)
        self.screen.handle_key(KEY_UP)  # Portal -> goto-page row -> overrides row.
        self.screen.handle_key(KEY_ENTER)

        assert self.screen.ids.use_overrides_checkbox.active is True

    def test_enter_on_wiki_chip_triggers_button(self) -> None:
        self._make_all_widgets_visible()
        self.screen.enter_nav_focus(MagicMock())

        for _ in range(3):  # Portal -> goto -> overrides -> wiki chip.
            self.screen.handle_key(KEY_UP)
        self.screen.handle_key(KEY_ENTER)

        self.screen.ids.wiki_page_button.trigger_action.assert_called_once()

    def test_enter_on_eye_triggers_peek_and_keeps_focus(self) -> None:
        self._make_all_widgets_visible()
        self.screen.enter_nav_focus(MagicMock())

        for _ in range(4):  # Portal -> goto -> overrides -> wiki -> eye.
            self.screen.handle_key(KEY_UP)
        assert self.screen._nav_focused_widget is self.screen.ids.title_show_button
        self.screen.handle_key(KEY_ENTER)

        self.screen.ids.title_show_button.trigger_action.assert_called_once()
        assert self.screen._nav_focused_widget is self.screen.ids.title_show_button

    def test_peek_under_focus_clamps_to_eye(self) -> None:
        self._make_all_widgets_visible()
        self.screen.enter_nav_focus(MagicMock())  # Focused on the portal.

        # Simulate a mouse-click peek hiding the panel under the keyboard focus.
        self.screen.ids.bottom_view_box.opacity = 0
        self.screen.handle_key(KEY_UP)

        assert self.screen._nav_focused_widget is self.screen.ids.title_show_button

    def test_escape_requests_exit(self) -> None:
        on_exit = MagicMock()
        self.screen.enter_nav_focus(on_exit)

        assert self.screen.handle_key(KEY_ESCAPE) is True
        on_exit.assert_called_once()

    def test_handle_key_inactive_returns_false(self) -> None:
        assert self.screen.handle_key(KEY_UP) is False

        self.screen.enter_nav_focus(MagicMock())
        self.screen.exit_nav_focus()

        assert self.screen.handle_key(KEY_UP) is False

    def test_exit_nav_focus_clears_highlights_and_is_idempotent(self) -> None:
        self.screen.enter_nav_focus(MagicMock())

        self.screen.exit_nav_focus()
        self.mock_clear_focus.assert_called_once()

        self.screen.exit_nav_focus()  # No-op second time.
        self.mock_clear_focus.assert_called_once()

    def test_unhandled_key_returns_false(self) -> None:
        self.screen.enter_nav_focus(MagicMock())
        assert self.screen.handle_key(999) is False

    def test_is_nav_active_property(self) -> None:
        assert not self.screen.is_nav_active
        self.screen.enter_nav_focus(MagicMock())
        assert self.screen.is_nav_active
        self.screen.exit_nav_focus()
        assert not self.screen.is_nav_active

    def _focus_wiki_chip(self) -> None:
        self.screen.enter_nav_focus(MagicMock(side_effect=self.screen.exit_nav_focus))
        for _ in range(3):  # Portal -> goto -> overrides -> wiki chip.
            self.screen.handle_key(KEY_UP)
        assert self.screen._nav_focused_widget is self.screen.ids.wiki_page_button

    def test_reentry_restores_last_widget_after_screen_switch_exit(self) -> None:
        """E.g. back from the wiki reader: focus returns to the wiki chip."""
        self._make_all_widgets_visible()
        self._focus_wiki_chip()
        self.screen.exit_nav_focus()  # The wiki reader taking over auto-exits nav.

        self.screen.enter_nav_focus(MagicMock())

        assert self.screen._nav_focused_widget is self.screen.ids.wiki_page_button

    def test_escape_exit_forgets_last_widget(self) -> None:
        self._make_all_widgets_visible()
        self._focus_wiki_chip()
        self.screen.handle_key(KEY_ESCAPE)  # Deliberate exit.

        self.screen.enter_nav_focus(MagicMock())

        assert self.screen._nav_focused_widget is self.screen.ids.title_portal_image_button

    def test_reentry_falls_back_to_portal_when_last_widget_hidden(self) -> None:
        self._make_all_widgets_visible()
        self._focus_wiki_chip()
        self.screen.exit_nav_focus()
        self.screen.wiki_button_visible = False

        self.screen.enter_nav_focus(MagicMock())

        assert self.screen._nav_focused_widget is self.screen.ids.title_portal_image_button

    def test_set_title_view_forgets_last_widget(self) -> None:
        self._make_all_widgets_visible()
        self._focus_wiki_chip()
        self.screen.exit_nav_focus()

        mock_info = MagicMock()
        mock_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        self.screen.set_title_view(mock_info)
        self._make_all_widgets_visible()

        self.screen.enter_nav_focus(MagicMock())

        assert self.screen._nav_focused_widget is self.screen.ids.title_portal_image_button
