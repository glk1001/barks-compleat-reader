# ruff: noqa: SLF001
# cspell:ignore getbbox getmetrics

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_covers import COVER_BY_TITLE, get_cover_display_title
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import (
    BARKS_TITLE_INFO,
    ONE_PAGERS,
    get_one_pager_display_title,
)
from barks_fantagraphics.comics_consts import FONT_DIR
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_reader.core import log_markers
from barks_reader.core.goto_page import GotoPageOffer
from barks_reader.core.keys import KEY_DOWN, KEY_ENTER, KEY_ESCAPE, KEY_LEFT, KEY_RIGHT, KEY_UP
from barks_reader.core.log_markers import pattern
from barks_reader.core.main_layout import MainLayoutMode
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.ui import bottom_title_view_screen
from barks_reader.ui.bottom_title_view_screen import BottomTitleViewScreen
from kivy.core.text.markup import MarkupLabel
from kivy.lang import Builder
from kivy.lang.parser import Parser
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from PIL import ImageFont

if TYPE_CHECKING:
    from collections.abc import Generator

    from kivy.lang.parser import ParserRule
    from kivy.uix.widget import Widget

_KV_FILE = Path(bottom_title_view_screen.__file__).with_suffix(".kv")


def _kv_expression(prop: str, widget_id: str | None = None) -> str:
    """Return the expression the screen's real kv rule gives `prop`, on the widget `widget_id`."""

    def found_in(rule: ParserRule) -> str | None:
        if prop in rule.properties and widget_id in (None, rule.id):
            return rule.properties[prop].value
        return next(filter(None, map(found_in, rule.children)), None)

    parser = Parser(content=_KV_FILE.read_text(encoding="utf-8"), filename=str(_KV_FILE))
    expression = next(filter(None, (found_in(rule) for _, rule in parser.rules)), None)
    assert expression is not None
    return expression


def _show(
    screen: BottomTitleViewScreen,
    page_to_goto: str = "",
    *,
    active: bool = False,
    tagged_pages: list[str] | None = None,
    kept_page: str = "",
) -> None:
    """Show the offer of `page_to_goto` on the goto-page row, as the coordinator does."""
    screen.show_goto_page(
        GotoPageOffer.make(
            page_to_goto, active=active, tagged_pages=tagged_pages or (), kept_page=kept_page
        )
    )


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
    def test_before_any_title_the_goto_box_is_off_and_the_overrides_box_on(self) -> None:
        """Ticked with no page in it, the goto box would fail `assert page_to_first_goto`."""
        assert self.screen.goto_page_active is False
        assert self.screen.use_overrides_active is True

    def test_the_colophon_is_compact_on_the_spread_for_a_title_without_notes(self) -> None:
        seen: list[bool] = []
        self.screen.bind(compact_colophon=lambda _instance, compact: seen.append(compact))
        assert self.screen.compact_colophon is False

        self.screen.layout_mode = MainLayoutMode.SPREAD.value
        assert self.screen.compact_colophon is True
        self.screen.title_extra_info_text = "Extra Info"
        assert self.screen.compact_colophon is False
        self.screen.title_extra_info_text = ""
        assert self.screen.compact_colophon is True
        self.screen.layout_mode = MainLayoutMode.SINGLE.value
        assert self.screen.compact_colophon is False

        assert seen == [True, False, True, False]

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

    def test_a_story_barks_titled_has_no_subtitle(self) -> None:
        mock_info = MagicMock()
        mock_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        mock_info.comic_book_info.is_barks_title = True

        self.screen.set_title_view(mock_info)

        assert self.screen.main_title_subtitle == ""

    def test_an_untitled_story_shows_its_assigned_name_under_its_issue(self) -> None:
        mock_info = MagicMock()
        mock_info.comic_book_info = BARKS_TITLE_INFO[Titles.HYPNO_GUN_THE]

        self.screen.set_title_view(mock_info)

        assert self.screen.main_title_subtitle == "(The Hypno-Gun)"

    def test_the_subtitle_goes_when_a_titled_story_follows_an_untitled_one(self) -> None:
        untitled = MagicMock()
        untitled.comic_book_info = BARKS_TITLE_INFO[Titles.HYPNO_GUN_THE]
        titled = MagicMock()
        titled.comic_book_info = BARKS_TITLE_INFO[Titles.LOST_IN_THE_ANDES]

        self.screen.set_title_view(untitled)
        self.screen.set_title_view(titled)

        assert self.screen.main_title_subtitle == ""

    def test_the_title_info_is_rebuilt_when_its_font_size_changes(self) -> None:
        """The footnote star's size is in the text, and the rows' size follows the window."""
        on_font_size = self.mock_font_manager.bind.call_args.kwargs["title_info_font_size"]
        self.screen.set_title_view(MagicMock())
        self.mock_formatter.get_title_info.return_value = "Title Info, a larger star"

        on_font_size(self.mock_font_manager, 38)

        assert self.screen.title_info_text == "Title Info, a larger star"

    def test_a_font_size_change_before_any_title_builds_nothing(self) -> None:
        on_font_size = self.mock_font_manager.bind.call_args.kwargs["title_info_font_size"]

        on_font_size(self.mock_font_manager, 38)

        self.mock_formatter.get_title_info.assert_not_called()

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

    def test_setting_the_inset_image_logs_how_long_it_took(self, loguru_sink: list[str]) -> None:
        """The GUI suite holds this duration to a budget (TITLE_INSET_IMAGE_SET)."""
        self.mock_loader.load_texture.side_effect = lambda _src, on_ready: on_ready(
            MagicMock(), None
        )
        self.screen._set_title_inset_image(Path("inset.png"))
        assert any(re.search(pattern(log_markers.TITLE_INSET_IMAGE_SET), m) for m in loguru_sink)

    def test_fade_in_bottom_view_title(self) -> None:
        self.screen.fade_in_bottom_view_title()
        self.mock_anim.start.assert_called_with(self.screen.ids.bottom_view_box)
        assert self.screen.ids.title_show_button.opacity == 1

    def test_fade_logs_its_start_and_its_finish(self, loguru_sink: list[str]) -> None:
        """The finish line is the only signal the panel is fully drawn.

        Only the animation that actually ran may fire it, never a stale one.
        """
        self.screen.fade_in_bottom_view_title()
        assert any(m.startswith("Title view fade started: ") for m in loguru_sink)
        self.screen._on_panel_fade_finished(MagicMock(), MagicMock())  # a stale animation
        assert "Title view fade finished." not in loguru_sink
        self.screen._on_panel_fade_finished(self.screen._panel_fade_anim, MagicMock())
        assert "Title view fade finished." in loguru_sink

    def test_the_eye_hides_the_panel_and_brings_it_back_and_says_so(
        self, loguru_sink: list[str]
    ) -> None:
        box = self.screen.ids.bottom_view_box
        box.opacity = 1
        self.screen.toggle_panel_peek()
        assert box.opacity == 0
        assert "Title view panel toggled by the eye: shown = False." in loguru_sink
        self.screen.toggle_panel_peek()
        assert box.opacity == 1
        assert "Title view panel toggled by the eye: shown = True." in loguru_sink

    def test_the_eye_brings_back_a_panel_still_fading_in(self) -> None:
        box = self.screen.ids.bottom_view_box
        box.opacity = bottom_title_view_screen.PANEL_VISIBLE_OPACITY
        self.screen.toggle_panel_peek()
        assert box.opacity == 1

    def test_show_goto_page(self) -> None:
        # Active with page
        _show(self.screen, "5", active=True)
        assert self.screen.goto_page_num == "5"
        assert self.screen.goto_page_active

        # Inactive
        _show(self.screen, active=False)
        assert not self.screen.goto_page_active

        # Comic begin page
        _show(self.screen, COMIC_BEGIN_PAGE, active=True)
        assert self.screen.goto_page_num == ""

    def test_an_offered_goto_page_is_logged_and_none_is_not(self, loguru_sink: list[str]) -> None:
        _show(self.screen, "2", active=True)
        assert loguru_sink[-1] == (
            'Goto page "2" offered: active = True; the row reads "Goto page 2:".'
        )
        loguru_sink.clear()
        _show(self.screen, active=False)
        _show(self.screen, COMIC_BEGIN_PAGE, active=True)  # the front: no box
        assert not [line for line in loguru_sink if "offered" in line]

    def test_set_overrides_state(self) -> None:
        self.screen.set_overrides_state("Description", active=False)
        assert self.screen.use_overrides_description == "Description"
        assert not self.screen.use_overrides_active

    def test_a_title_with_its_overrides_off_after_another_shows_its_no_overrides_inset(
        self,
    ) -> None:
        """The checkbox stays off, so no change event: the screen must swap the inset itself."""
        self.screen.set_title_view(MagicMock())
        self.screen.set_overrides_state("Use GLK alternate ending", active=False)

        next_title = MagicMock()
        next_title.comic_book_info.title = Titles.LOST_IN_THE_ANDES
        self.mock_overrides.get_title_page_inset_file.return_value = "no-overrides.png"
        self.screen.set_title_view(next_title)
        assert self.mock_loader.load_texture.call_args.args[0] == "inset.png"

        self.screen.set_overrides_state("Use 'deah' instead of 'theah'", active=False)

        self.mock_overrides.get_title_page_inset_file.assert_called_once_with(
            Titles.LOST_IN_THE_ANDES,
            False,  # noqa: FBT003
        )
        assert self.mock_loader.load_texture.call_args.args[0] == "no-overrides.png"

    @pytest.mark.parametrize(
        ("was_description", "was_active", "description", "active"),
        [
            pytest.param("", True, "Use GLK alternate ending", False, id="on-to-off"),
            pytest.param("Use GLK alternate ending", False, "Use GLK", True, id="off-to-on"),
            pytest.param("Use GLK alternate ending", False, "", True, id="off-to-no-setting"),
            pytest.param("Use GLK alternate ending", True, "Use GLK", True, id="on-to-on"),
            pytest.param("", True, "", True, id="no-setting"),
        ],
    )
    def test_a_box_that_changes_or_stays_on_leaves_the_inset_to_its_own_event(
        self, was_description: str, was_active: bool, description: str, active: bool
    ) -> None:
        self.screen.set_title_view(MagicMock())
        self.screen.use_overrides_description = was_description
        self.screen.use_overrides_active = was_active

        self.screen.set_overrides_state(description, active=active)

        self.mock_overrides.get_title_page_inset_file.assert_not_called()

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
        mock_info.comic_book_info.title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD
        mock_info.comic_book_info.get_title_from_issue_name.return_value = "Issue Title"
        assert self.screen._get_main_title_str(mock_info) == "Issue Title"

        # Case 3: an article, named as its tree node is rather than by its issue
        article = ALL_FANTA_COMIC_BOOK_INFO[Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION]
        assert not article.comic_book_info.is_barks_title
        assert self.screen._get_main_title_str(article) == "Don Ault: Fantagraphics Introduction"

    def test_a_one_pager_shows_its_issue_and_page_rather_than_its_gag(self) -> None:
        one_pager = ONE_PAGERS[0]
        mock_info = MagicMock()
        mock_info.comic_book_info.title = one_pager
        assert self.screen._get_main_title_str(mock_info) == get_one_pager_display_title(one_pager)

    def test_a_cover_shows_its_issue_and_date(self) -> None:
        title, cover = next(iter(COVER_BY_TITLE.items()))
        mock_info = MagicMock()
        mock_info.comic_book_info.title = title
        assert self.screen._get_main_title_str(mock_info) == get_cover_display_title(cover)

    @pytest.mark.parametrize(
        ("name", "default"),
        [
            ("is_first_use_of_reader", False),
            ("is_one_pager_title", False),
            ("is_visible", False),
            ("wiki_button_visible", False),
            ("goto_page_active", False),
            ("use_overrides_active", True),
        ],
    )
    def test_the_flags_start_as_the_kv_rules_expect(self, name: str, *, default: bool) -> None:
        assert getattr(BottomTitleViewScreen, name).defaultvalue is default


class TestBottomTitleViewNav(ScreenFixtureBase):
    def test_an_exit_with_no_one_listening_still_forgets_the_position(self) -> None:
        self.screen._nav_on_exit_request = None
        self.screen._last_nav_focused_widget = MagicMock()
        self.screen._request_nav_exit()
        assert self.screen._last_nav_focused_widget is None

    def test_an_exit_leaves_the_focus_says_so_and_forgets_the_position(self) -> None:
        on_exit = MagicMock()
        self.screen._nav_active = True
        self.screen._nav_on_exit_request = on_exit
        self.screen._nav_focused_widget = MagicMock()

        with patch.object(self.screen, "_clear_nav_focus"):
            self.screen._request_nav_exit()

        on_exit.assert_called_once_with()
        assert self.screen._nav_active is False
        # Left by Escape, not by a goto: the next entry starts at the portal.
        assert self.screen._last_nav_focused_widget is None

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

    def test_panel_counts_as_visible_while_the_fade_runs(self) -> None:
        """A fade in progress must not read as "the user peeked the panel away".

        Opacity is the panel's only state, and the fade animates it up from 0 - so
        mid-fade the raw opacity says hidden. Focus would then land on the eye toggle,
        and an Enter after a mouse-driven goto-title would toggle the panel instead of
        opening the comic.
        """
        self.screen.fade_in_bottom_view_title()
        self.screen.ids.bottom_view_box.opacity = 0  # still early in the fade

        assert self.screen._is_panel_content_visible()
        assert self.screen.ids.title_portal_image_button in self.screen._focusable_widgets()

        self.screen.enter_nav_focus(MagicMock())

        assert self.screen._nav_focused_widget is self.screen.ids.title_portal_image_button

    def test_panel_reads_as_peeked_once_the_fade_has_finished(self) -> None:
        """With no fade running, opacity alone decides again - so the eye still works."""
        self.screen.fade_in_bottom_view_title()
        handler = self.mock_anim.bind.call_args.kwargs["on_complete"]
        handler(self.mock_anim, self.screen.ids.bottom_view_box)  # fade completes

        self.screen.ids.bottom_view_box.opacity = 0  # now a deliberate peek-away

        assert not self.screen._is_panel_content_visible()
        assert self.screen._focusable_widgets() == [self.screen.ids.title_show_button]

    def test_the_length_of_a_fade_varies_within_its_maximum(self) -> None:
        """Not all or nothing: most lengths lie strictly between no fade and the longest."""
        get_duration = self.screen._get_title_portal_opening_animation_duration_secs
        durations = [get_duration() for _ in range(50)]
        assert all(0 <= duration <= 1 for duration in durations)
        assert any(0 < duration < 1 for duration in durations)

    def test_a_new_fade_stops_the_one_still_running(self) -> None:
        """Else the old one drags a shorter new one's finished panel back down to hidden."""
        self.screen.fade_in_bottom_view_title()
        self.mock_anim.cancel.assert_not_called()

        self.screen.fade_in_bottom_view_title()

        self.mock_anim.cancel.assert_called_once_with(self.screen.ids.bottom_view_box)

    def test_a_fade_already_over_is_not_stopped_again(self) -> None:
        self.screen.fade_in_bottom_view_title()
        self.screen._on_panel_fade_finished(self.mock_anim, self.screen.ids.bottom_view_box)

        self.screen.fade_in_bottom_view_title()

        self.mock_anim.cancel.assert_not_called()

    def test_an_earlier_fade_finishing_does_not_clear_a_later_one(self) -> None:
        """Kivy's cancel() fires no on_complete, so a stale finish must not win."""
        self.screen.fade_in_bottom_view_title()
        stale = self.screen._panel_fade_anim
        self.mock_anim_cls.return_value = later = MagicMock()
        self.screen.fade_in_bottom_view_title()
        assert self.screen._panel_fade_anim is later

        self.screen._on_panel_fade_finished(stale, self.screen.ids.bottom_view_box)

        assert self.screen._panel_fade_anim is later
        assert self.screen._is_panel_content_visible()

    def test_enter_nav_focus_at_portal_targets_portal_during_fade(self) -> None:
        # Enter on a title restarts the panel fade (opacity 0) and may carry a remembered
        # widget; the read gesture must still land squarely on the portal, not the eye.
        self.screen.ids.bottom_view_box.opacity = 0
        self.screen._last_nav_focused_widget = self.screen.ids.wiki_page_button

        self.screen.enter_nav_focus_at_portal(MagicMock())

        assert self.screen._nav_focused_widget is self.screen.ids.title_portal_image_button
        (widgets, focused_idx, _group), _ = self.mock_update_focus.call_args
        assert widgets[focused_idx] is self.screen.ids.title_portal_image_button

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

    def test_enter_on_a_portal_peeked_away_only_moves_the_focus_to_the_eye(self) -> None:
        callback = MagicMock()
        self.screen.on_title_portal_image_pressed_func = callback
        self.screen.enter_nav_focus(MagicMock())
        self.screen.ids.bottom_view_box.opacity = 0  # the mouse hid the panel

        assert self.screen.handle_key(KEY_ENTER) is True

        callback.assert_not_called()
        assert self.screen._nav_focused_widget is self.screen.ids.title_show_button
        self.screen.ids.title_show_button.trigger_action.assert_not_called()

    def test_enter_on_a_row_peeked_away_leaves_its_checkbox_alone(self) -> None:
        self._make_all_widgets_visible()
        self.screen.ids.goto_page_checkbox.active = True
        self.screen.enter_nav_focus(MagicMock())
        self.screen.handle_key(KEY_UP)  # Portal -> goto-page row.
        self.screen.ids.bottom_view_box.opacity = 0

        self.screen.handle_key(KEY_ENTER)

        assert self.screen.ids.goto_page_checkbox.active is True
        assert self.screen._nav_focused_widget is self.screen.ids.title_show_button

    def test_enter_on_the_portal_during_a_fade_still_opens_the_comic(self) -> None:
        """Right after a goto-title the panel is fading in: Enter is the read gesture."""
        callback = MagicMock()
        self.screen.on_title_portal_image_pressed_func = callback
        self.screen.fade_in_bottom_view_title()
        self.screen.ids.bottom_view_box.opacity = 0  # still early in the fade
        self.screen.enter_nav_focus_at_portal(MagicMock())

        self.screen.handle_key(KEY_ENTER)

        callback.assert_called_once_with()

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


class TestGotoPageToggleLog(ScreenFixtureBase):
    """Toggling the goto-page row from the keyboard logs the new state."""

    def test_return_on_the_goto_page_row_logs_the_toggle(self, loguru_sink: list[str]) -> None:
        ids = self.screen.ids
        ids.goto_page_checkbox.active = True
        self.screen.goto_page_num = "5"  # the row is only there with a page in it
        self.screen._nav_focused_widget = ids.goto_page_layout
        self.screen._activate_focused_widget()
        assert ids.goto_page_checkbox.active is False
        assert "Goto page checkbox toggled: active = False." in loguru_sink


# Adventure Down Under under Australian Aboriginals: 7, 13 and 16 to 23.
_TAGGED_PAGES = ["7", "13", "16", "17", "18", "19", "20", "21", "22", "23"]


class TestGotoPageSteps(ScreenFixtureBase):
    """A tag's pages in the title: the goto-page row steps through each run's start."""

    def _offer(self, active: bool = True) -> None:
        _show(self.screen, "7", active=active, tagged_pages=_TAGGED_PAGES)

    def _focus_goto_row(self) -> None:
        self.screen.enter_nav_focus(MagicMock())
        self.screen._nav_focused_widget = self.screen.ids.goto_page_layout

    def test_a_tag_offers_the_start_of_each_run(self) -> None:
        self._offer()
        assert self.screen.goto_pages == ["7", "13", "16"]
        assert self.screen.tagged_pages == _TAGGED_PAGES
        assert self.screen.goto_page_text == "Goto page 7 (1 of 3):"

    def test_stepping_wraps_round_both_ways(self) -> None:
        self._offer()
        pages = []
        for _ in range(3):
            self.screen.step_goto_page(1)
            pages.append(self.screen.goto_page_num)
        assert pages == ["13", "16", "7"]
        self.screen.step_goto_page(-1)
        assert self.screen.goto_page_num == "16"
        assert self.screen.goto_page_text == "Goto pages 16-23 (3 of 3):"

    def test_stepping_ticks_the_box_and_is_logged(self, loguru_sink: list[str]) -> None:
        self._offer(active=False)
        self.screen.step_goto_page(1)
        assert self.screen.goto_page_active
        assert any(
            re.search(log_markers.pattern(log_markers.GOTO_PAGE_STEPPED), line)
            for line in loguru_sink
        )
        assert (
            'Goto page stepped to "13" (2 of 3); the row reads "Goto page 13 (2 of 3):".'
        ) in loguru_sink

    @pytest.mark.parametrize(("key", "page"), [(KEY_RIGHT, "13"), (KEY_LEFT, "16")])
    def test_left_and_right_step_on_the_goto_row(self, key: int, page: str) -> None:
        self._offer()
        self._focus_goto_row()
        assert self.screen.handle_key(key) is True
        assert self.screen.goto_page_num == page

    def test_left_and_right_are_not_taken_off_the_goto_row(self) -> None:
        self._offer()
        self.screen.enter_nav_focus(MagicMock())  # Focus on the portal.
        assert self.screen.handle_key(KEY_RIGHT) is False
        assert self.screen.goto_page_num == "7"

    def test_the_row_can_step_only_with_more_than_one_stop_and_says_so_when_that_changes(
        self,
    ) -> None:
        heard: list[bool] = []
        self.screen.bind(can_step_goto_page=lambda _s, can_step: heard.append(can_step))
        assert self.screen.can_step_goto_page is False
        self.screen.goto_pages = ["7", "13"]
        assert self.screen.can_step_goto_page is True
        self.screen.goto_pages = ["7"]
        assert self.screen.can_step_goto_page is False
        assert heard == [True, False]

    def test_one_run_has_nothing_to_step_through(self) -> None:
        _show(self.screen, "4", active=True, tagged_pages=["4", "5", "6"])
        self._focus_goto_row()
        assert self.screen.handle_key(KEY_RIGHT) is False
        self.screen.step_goto_page(1)
        assert self.screen.goto_page_num == "4"
        assert self.screen.goto_page_text == "Goto pages 4-6:"

    def test_a_run_reads_as_its_pages_and_a_lone_page_as_one(self) -> None:
        self._offer()
        assert self.screen.goto_page_text == "Goto page 7 (1 of 3):"
        self.screen.step_goto_page(-1)
        assert self.screen.goto_page_text == "Goto pages 16-23 (3 of 3):"

    def test_one_run_reads_as_its_pages(self) -> None:
        # Herbert in Ten Cents' Worth of Trouble: one stop, but three pages.
        _show(self.screen, "1", active=True, tagged_pages=["1", "2", "3"])
        assert self.screen.goto_page_text == "Goto pages 1-3:"

    def test_a_page_inside_a_run_names_no_run(self) -> None:
        _show(self.screen, "18", active=True, tagged_pages=_TAGGED_PAGES)
        assert self.screen.goto_page_text == "Goto page 18 (4 of 4):"

    def test_an_offer_with_no_tag_names_no_run(self) -> None:
        self._offer()
        _show(self.screen, "16", active=True)
        assert self.screen.goto_page_text == "Goto page 16:"

    def test_a_page_among_none_of_the_runs_is_a_stop_of_its_own(self) -> None:
        # E.g. the page the comic was closed on, read under the tag.
        _show(self.screen, "9", active=True, tagged_pages=_TAGGED_PAGES)
        assert self.screen.goto_pages == ["7", "9", "13", "16"]
        assert self.screen.tagged_pages == _TAGGED_PAGES
        assert self.screen.goto_page_text == "Goto page 9 (2 of 4):"
        self.screen.step_goto_page(1)
        assert self.screen.goto_page_num == "13"

    def test_a_page_inside_a_run_is_a_stop_too(self) -> None:
        _show(self.screen, "18", active=True, tagged_pages=_TAGGED_PAGES)
        assert self.screen.goto_pages == ["7", "13", "16", "18"]

    def test_a_runs_first_page_is_no_extra_stop(self) -> None:
        _show(self.screen, "13", active=True, tagged_pages=_TAGGED_PAGES)
        assert self.screen.goto_pages == ["7", "13", "16"]
        assert self.screen.goto_page_text == "Goto page 13 (2 of 3):"

    def test_a_kept_page_is_a_stop_though_the_tags_page_is_offered(self) -> None:
        # E.g. the page last read, when the title is reached under the tag.
        _show(self.screen, "7", active=True, tagged_pages=_TAGGED_PAGES, kept_page="9")
        assert self.screen.goto_page_num == "7"
        assert self.screen.goto_pages == ["7", "9", "13", "16"]
        assert self.screen.goto_page_text == "Goto page 7 (1 of 4):"
        self.screen.step_goto_page(1)
        assert self.screen.goto_page_num == "9"

    @pytest.mark.parametrize("kept_page", ["", COMIC_BEGIN_PAGE, "13"])
    def test_no_kept_page_or_one_already_a_stop_adds_none(self, kept_page: str) -> None:
        _show(self.screen, "7", active=True, tagged_pages=_TAGGED_PAGES, kept_page=kept_page)
        assert self.screen.goto_pages == ["7", "13", "16"]

    def test_a_kept_page_without_a_tag_is_no_stop(self) -> None:
        _show(self.screen, "12", active=True, kept_page="9")
        assert self.screen.goto_pages == []

    def test_any_other_offer_forgets_the_tag(self) -> None:
        self._offer()
        _show(self.screen, "12", active=True)  # E.g. the last page read.
        assert self.screen.goto_pages == []
        assert self.screen.tagged_pages == []
        assert self.screen.goto_page_text == "Goto page 12:"


class TestInsetImageEdges(ScreenFixtureBase):
    def test_toggling_overrides_with_no_title_shown_loads_nothing(
        self, loguru_sink: list[str]
    ) -> None:
        self.screen._on_use_overrides_checkbox_changed(None, use_overrides=True)

        assert log_markers.USE_OVERRIDES_CHANGED.format(value=True) in loguru_sink
        self.mock_overrides.get_title_page_inset_file.assert_not_called()
        self.mock_loader.load_texture.assert_not_called()

    def test_an_inset_image_that_failed_to_load_leaves_the_portal_blank_and_says_why(
        self, loguru_sink: list[str]
    ) -> None:
        """It must not end the app, nor leave the previous title's inset up as this one's."""
        self.screen.title_inset_image_texture = MagicMock()
        self.mock_loader.load_texture.side_effect = lambda _src, on_ready: on_ready(
            None, OSError("inset.png is gone")
        )

        self.screen._set_title_inset_image(Path("inset.png"))

        assert self.screen.title_inset_image_texture is None
        assert 'Could not load the title inset "inset.png": inset.png is gone' in loguru_sink


_NOTES_FONT_FILE = FONT_DIR / "SourceSerif4SmText-Regular.ttf"


def test_extra_info_line_height_is_the_fonts_own() -> None:
    # The panel divides its height by this to end the notes at a whole line. Too small a
    # share, after a change of font, and the last line runs off the foot of the panel.
    size = 1000
    ascent, descent = ImageFont.truetype(_NOTES_FONT_FILE, size).getmetrics()
    assert pytest.approx((ascent + descent) / size) == BottomTitleViewScreen.EXTRA_INFO_LINE_HEIGHT


def test_extra_info_text_leading_is_the_fonts_own() -> None:
    # The portal lines up with the glyphs of the notes' first line by this share of the size.
    size = 1000
    _left, capital_top, _right, _bottom = ImageFont.truetype(_NOTES_FONT_FILE, size).getbbox(
        "H", anchor="la"
    )
    assert pytest.approx(capital_top / size) == BottomTitleViewScreen.EXTRA_INFO_TEXT_LEADING


@pytest.mark.parametrize("font_size", [12, 13, 14, 17, 18, 24, 34])
def test_extra_info_line_pitch_is_the_one_kivy_lays_out(font_size: int) -> None:
    # Kivy rounds a line up to whole pixels: at 17 the font's 23.3 is laid out as 24, and
    # dividing by the 23.3 allows a line more than the panel holds.
    lines = 10
    label = MarkupLabel(
        text="\n".join(["Hg"] * lines),
        font_name=str(_NOTES_FONT_FILE),
        font_size=font_size,
        markup=True,
    )
    _width, height = label.render()
    assert BottomTitleViewScreen.extra_info_line_pitch(font_size) == height / lines


class _PeekedPanel(BoxLayout):
    """The title panel's box, given the `disabled` expression of the screen's real kv rule."""


class TestPeekingAtTheArt:
    KV_FILE = "test_peeked_panel.kv"

    @pytest.fixture
    def panel(self) -> Generator[_PeekedPanel]:
        expression = _kv_expression("disabled", "bottom_view_box")
        Builder.load_string(f"<_PeekedPanel>:\n    disabled: {expression}\n", filename=self.KV_FILE)
        try:
            yield _PeekedPanel(size=(100, 100))
        finally:
            Builder.unload_file(self.KV_FILE)

    @pytest.mark.parametrize(
        ("opacity", "presses"),
        [
            pytest.param(0, 0, id="hidden"),
            pytest.param(0.5, 1, id="fading-in"),
            pytest.param(1, 1, id="shown"),
        ],
    )
    def test_only_a_hidden_panel_keeps_its_widgets_from_a_touch(
        self, panel: _PeekedPanel, opacity: float, presses: int
    ) -> None:
        pressed = MagicMock()
        portal = Button(size=(100, 100), on_press=pressed)
        panel.add_widget(portal)
        panel.opacity = opacity

        panel.on_touch_down(
            MagicMock(x=50, y=50, pos=(50, 50), ud={}, is_mouse_scrolling=False),
        )

        assert pressed.call_count == presses

    def test_showing_the_panel_again_gives_its_widgets_back(self, panel: _PeekedPanel) -> None:
        panel.opacity = 0
        assert panel.disabled
        panel.opacity = 1
        assert not panel.disabled


class TestTitleBoxGaps:
    @pytest.mark.parametrize(
        ("prop", "layout_mode", "share"),
        [
            ("title_box_padding", MainLayoutMode.SPREAD, 0.044),
            ("title_box_padding", MainLayoutMode.SINGLE, 0.03),
            ("title_box_spacing", MainLayoutMode.SPREAD, 0.0275),
            ("title_box_spacing", MainLayoutMode.SINGLE, 0.055),
        ],
    )
    @pytest.mark.parametrize("density", [1, 2])
    def test_they_are_shares_of_the_view_whatever_the_density(
        self, prop: str, layout_mode: MainLayoutMode, share: float, density: int
    ) -> None:
        """The parent's size is already in pixels: `dp` here would apply the density twice."""
        namespace = {
            "dp": lambda value: value * density,
            "root": SimpleNamespace(layout_mode=layout_mode.value),
            "self": SimpleNamespace(parent=SimpleNamespace(width=1000, height=1000)),
        }

        value = eval(_kv_expression(prop), namespace)  # noqa: S307

        assert value == pytest.approx(share * 1000)
