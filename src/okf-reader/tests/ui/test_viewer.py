# ruff: noqa: SLF001
# cspell:ignore ffcc pytestmark
"""The viewer's paths, on a real viewer over a small bundle.

First what a remote cannot reach: the standalone app's keys, PageUp/PageDown/Home/End,
the mouse's hover and back button, a link inside a footnote, and the search index
failing to build. Then the remote's own paths, which the GUI suite walks in the real app
(``src/barks-reader/tests/gui/test_wiki.py``): here each is one step, so a failure names
the line. A viewer needs a Kivy window, so these are skipped where there is none
(KIVY_HEADLESS_CI); every CI runner draws one now (macOS on Apple's software renderer,
Windows through ANGLE) and runs them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from okf_reader.core.backgrounds import PageBackground
from okf_reader.core.render import Block, TableBlock
from okf_reader.core.session import load_session_state
from okf_reader.ui import page_links, sidebar
from okf_reader.ui import viewer as viewer_module
from okf_reader.ui.keynav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_F,
    KEY_LEFT,
)
from okf_reader.ui.viewer import (
    LAZY_TABLE_MIN_ROWS,
    FocusRegion,
    OKFApp,
    OKFViewer,
)
from okf_reader.ui.widgets import LazyTable
from PIL import Image as PilImage
from viewer_test_helpers import (
    LONG_TABLE_ROWS,
    NEEDS_A_WINDOW,
    clock_patched,
    open_footnote,
    page_of,
    run_scheduled,
    window_patched,
)

if TYPE_CHECKING:
    from pathlib import Path

    from kivy.uix.widget import Widget

pytestmark = NEEDS_A_WINDOW


class TestFootnoteLink:
    def test_a_link_inside_a_footnote_closes_it_and_opens_the_page(self, viewer: OKFViewer) -> None:
        open_footnote(viewer)
        popup = viewer._footnote_popup
        assert popup is not None
        popup_label = viewer._links.popup_label
        assert popup_label is not None
        with patch.object(popup, "dismiss", wraps=popup.dismiss) as dismiss:
            popup_label.dispatch("on_ref_press", "concept/a.md")
        dismiss.assert_called_once()
        assert page_of(viewer) == "concept/a.md"
        assert len(viewer.history) == 2  # noqa: PLR2004

    def test_the_popup_takes_escape_and_holds_the_arrows(self, viewer: OKFViewer) -> None:
        open_footnote(viewer)
        popup = viewer._footnote_popup
        assert popup is not None
        with patch.object(popup, "dismiss") as dismiss:
            assert viewer.handle_key(KEY_DOWN) is True  # nothing moves under the modal
            dismiss.assert_not_called()
            assert viewer.handle_key(KEY_ESCAPE) is True
            dismiss.assert_called_once()


class TestUnreadablePage:
    def test_a_page_gone_since_the_tree_was_built_shows_page_unavailable(
        self, viewer: OKFViewer
    ) -> None:
        """The wiki regenerated under the reader: an error page, not a crash."""
        gone = viewer.bundle / "concept" / "a.md"
        gone.unlink()
        with patch.object(viewer_module, "render_page", wraps=viewer_module.render_page) as render:
            viewer.show_page(gone)
        text = render.call_args.args[0]
        assert text.startswith("# Page unavailable")
        assert "`a.md`" in text
        assert page_of(viewer) == "concept/a.md"


class TestMouse:
    def test_the_back_button_goes_back(self, viewer: OKFViewer) -> None:
        viewer.show_page(viewer.bundle / "concept" / "a.md")
        assert viewer.on_touch_down(MagicMock(button="mouse4")) is True
        assert page_of(viewer) == "index.md"

    def test_a_press_drops_the_keyboard_focus_out_of_the_bar(self, viewer: OKFViewer) -> None:
        viewer.handle_key(KEY_ESCAPE)  # up to the bar
        assert viewer._focus_region is FocusRegion.TOP_BAR
        touch = MagicMock(button="left", pos=(-1000, -1000))
        viewer.on_touch_down(touch)
        assert viewer._focus_region is FocusRegion.SIDEBAR

    def test_no_link_is_under_the_mouse_when_the_viewer_is_not_on_screen(
        self, viewer: OKFViewer
    ) -> None:
        assert viewer._links.over_link((10, 10)) is False

    def test_an_open_footnote_owns_the_hover(self, viewer: OKFViewer) -> None:
        label = Label()
        viewer._links.popup_label = label
        with (
            patch.object(viewer.body_scroll, "get_root_window", return_value=object()),
            patch.object(page_links, "ref_under", return_value="concept/a.md") as under,
        ):
            assert viewer._links.over_link((10, 10)) is True
        under.assert_called_once_with(label, 10, 10)

    def test_the_cursor_changes_only_on_a_change(self, viewer: OKFViewer) -> None:
        with window_patched() as window:
            viewer._links.set_hand_cursor(over=True)
            viewer._links.set_hand_cursor(over=True)
            viewer._links.set_hand_cursor(over=False)
        assert [c.args[0] for c in window.set_system_cursor.call_args_list] == ["hand", "arrow"]


class TestStandaloneApp:
    """The standalone reader's own keys: Ctrl+F, Alt+Left, and Escape while typing."""

    @pytest.fixture
    def app(self, bundle: Path, tmp_path: Path) -> OKFApp:
        app = OKFApp(bundle, state_path=tmp_path / "session.json")
        app.build()
        return app

    def _key(self, app: OKFApp, key: int, *modifiers: str) -> bool:
        return app._on_keyboard(None, key, 0, "", list(modifiers))

    def test_ctrl_f_focuses_the_search_box(self, app: OKFApp) -> None:
        assert app._viewer is not None
        with patch.object(app._viewer, "focus_search") as focus:
            assert self._key(app, KEY_F, "ctrl") is True
        focus.assert_called_once()

    def test_alt_left_goes_back(self, app: OKFApp) -> None:
        assert app._viewer is not None
        app._viewer.show_page(app._viewer.bundle / "concept" / "a.md")
        assert self._key(app, KEY_LEFT, "alt") is True
        assert page_of(app._viewer) == "index.md"

    def test_alt_left_is_left_to_the_search_box_while_it_types(self, app: OKFApp) -> None:
        assert app._viewer is not None
        with patch.object(type(app._viewer), "search_focused", new=True):
            assert self._key(app, KEY_LEFT, "alt") is False

    def test_escape_while_typing_backs_out_of_the_search(self, app: OKFApp) -> None:
        assert app._viewer is not None
        with (
            patch.object(type(app._viewer), "search_focused", new=True),
            patch.object(app._viewer, "escape_search") as escape,
        ):
            assert self._key(app, KEY_ESCAPE) is True
        escape.assert_called_once()

    def test_the_viewer_takes_the_rest(self, app: OKFApp) -> None:
        assert self._key(app, KEY_ENTER) is True  # the sidebar's Enter

    def test_on_stop_saves_where_the_reader_was(self, app: OKFApp, tmp_path: Path) -> None:
        assert app._viewer is not None
        app._viewer.show_page(app._viewer.bundle / "concept" / "a.md")
        app.on_stop()
        state = load_session_state(tmp_path / "session.json", app._viewer.bundle)
        assert state is not None
        assert state.page.name == "a.md"


class TestTableWidget:
    """Which tables the viewer builds lazily: long ones without a link."""

    def _table(self, viewer: OKFViewer, rows: list[str]) -> Widget:
        return viewer._table_widget(TableBlock(rows), viewer.bundle / "index.md").children[0]

    def test_a_long_table_without_links_is_lazy(self, viewer: OKFViewer) -> None:
        assert isinstance(self._table(viewer, LONG_TABLE_ROWS), LazyTable)

    def test_a_short_table_is_built_whole(self, viewer: OKFViewer) -> None:
        table = self._table(viewer, LONG_TABLE_ROWS[: LAZY_TABLE_MIN_ROWS - 1])
        assert not isinstance(table, LazyTable)
        assert len(table.children) == LAZY_TABLE_MIN_ROWS - 1

    def test_a_long_table_with_a_link_is_built_whole(self, viewer: OKFViewer) -> None:
        rows = [*LONG_TABLE_ROWS, "[ref=concept/a.md]A[/ref]"]
        assert not isinstance(self._table(viewer, rows), LazyTable)


class TestHistory:
    def test_back_at_the_root_without_an_exit_does_nothing(self, viewer: OKFViewer) -> None:
        viewer.go_back()
        assert page_of(viewer) == "index.md"

    def test_reset_before_any_page_lands_on_the_home_page(self, viewer: OKFViewer) -> None:
        viewer.history.clear()
        viewer.reset_to()
        assert page_of(viewer) == "index.md"
        assert len(viewer.history) == 1

    def test_without_a_state_file_nothing_is_saved(self, viewer: OKFViewer) -> None:
        with patch.object(viewer_module, "save_session_state") as save:
            viewer.save_session()
        save.assert_not_called()


class TestBackground:
    """The art behind a page is the provider's answer for that page, each time one is shown."""

    @pytest.fixture
    def art(self, tmp_path: Path) -> Path:
        path = tmp_path / "art.png"
        PilImage.new("RGB", (4, 2), "red").save(path)
        return path

    @staticmethod
    def _viewer(
        bundle: Path, home: PageBackground | None, a_page: PageBackground | None = None
    ) -> tuple[OKFViewer, MagicMock]:
        """Open a viewer (on the home page) whose provider answers for each of the two pages."""
        answers = {"index.md": home, "a.md": a_page}
        provider = MagicMock()
        provider.background_for.side_effect = lambda _frontmatter, page: answers.get(page.name)
        return OKFViewer(bundle, image_provider=provider), provider

    def test_a_file_is_shown_by_its_path(self, bundle: Path, art: Path) -> None:
        viewer, provider = self._viewer(bundle, PageBackground(ext=".png", path=art))

        assert viewer.bg_image.source == str(art)
        provider.background_for.assert_called_with({}, bundle / "index.md")

    def test_the_provider_is_given_the_page_s_frontmatter(self, bundle: Path) -> None:
        viewer, provider = self._viewer(bundle, None)

        viewer.show_page(bundle / "concept" / "a.md")

        provider.background_for.assert_called_with({"title": "A"}, bundle / "concept" / "a.md")

    def test_bytes_are_decoded_to_a_texture_with_no_file_named(
        self, bundle: Path, art: Path
    ) -> None:
        viewer, _ = self._viewer(bundle, PageBackground(ext=".png", data=art.read_bytes()))

        assert viewer.bg_image.source == ""
        assert viewer.bg_image.texture.size == (4, 2)

    def test_a_page_with_no_background_clears_the_last(self, bundle: Path, art: Path) -> None:
        viewer, _ = self._viewer(bundle, PageBackground(ext=".png", data=art.read_bytes()))
        assert viewer.bg_image.texture is not None

        viewer.show_page(bundle / "concept" / "a.md")

        assert viewer.bg_image.source == ""
        assert viewer.bg_image.texture is None

    def test_bytes_after_a_file_drop_the_file_s_name(self, bundle: Path, art: Path) -> None:
        """Or Kivy would load the old file again over the new texture."""
        viewer, _ = self._viewer(
            bundle,
            PageBackground(ext=".png", path=art),
            PageBackground(ext=".png", data=art.read_bytes()),
        )
        assert viewer.bg_image.source == str(art)

        viewer.show_page(bundle / "concept" / "a.md")

        assert viewer.bg_image.source == ""
        assert viewer.bg_image.texture.size == (4, 2)


class TestBlocks:
    def test_a_page_that_starts_with_a_table_puts_it_in_a_section(self, viewer: OKFViewer) -> None:
        page = viewer.bundle / "concept" / "table.md"
        page.write_text("| a | b |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
        viewer.show_page(page)

        (section,) = viewer.body.children  # one banded box, as a run of text gets
        assert isinstance(section, BoxLayout)
        assert [type(w) for w in section.walk(restrict=True) if isinstance(w, Label)]
        assert not any(isinstance(w, Label) for w in viewer.body.children)

    def test_a_nested_list_item_is_indented(self, viewer: OKFViewer) -> None:
        page = viewer.bundle / "concept" / "list.md"
        page.write_text("- outer\n  - inner\n", encoding="utf-8")
        with patch.object(viewer_module, "Widget", wraps=viewer_module.Widget) as spacer:
            viewer.show_page(page)
        assert any(c.kwargs.get("height") == 1 for c in spacer.call_args_list)


class TestStandaloneAppWindow:
    @pytest.fixture
    def app(self, bundle: Path) -> OKFApp:
        app = OKFApp(bundle)
        app.build()
        return app

    def test_on_start_takes_the_titlebar_and_the_keys(self, app: OKFApp) -> None:
        with window_patched() as window:
            window.set_custom_titlebar.return_value = True
            app.on_start()
        assert window.custom_titlebar is True
        window.bind.assert_called_once_with(on_keyboard=app._on_keyboard)

    def test_a_system_refusing_a_custom_title_bar_keeps_its_own(
        self, app: OKFApp, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with window_patched() as window:
            window.set_custom_titlebar.return_value = False
            app.on_start()
        assert "custom titlebar not allowed" in capsys.readouterr().out

    def test_on_stop_before_a_build_saves_nothing(self, bundle: Path, tmp_path: Path) -> None:
        state_path = tmp_path / "session.json"
        with patch.object(viewer_module, "save_session_state") as save:
            OKFApp(bundle, state_path=state_path).on_stop()
        save.assert_not_called()
        assert not state_path.exists()

    def test_a_key_neither_takes_is_left_to_kivy(self, app: OKFApp) -> None:
        assert app._on_keyboard(None, KEY_F, 0, "", []) is False

    def test_run_starts_the_app(self, bundle: Path) -> None:
        with patch.object(OKFApp, "run") as run:
            viewer_module.run(bundle)
        run.assert_called_once_with()


class TestContrast:
    """The toggle darkens the article panel alone: the sidebar's scrim stays put."""

    def test_down_darkens_the_article_and_up_restores_it(self, viewer: OKFViewer) -> None:
        viewer.contrast_btn.state = "down"
        assert viewer._pane_scrim_color.a == pytest.approx(
            viewer_module.READING_PANE_SCRIM_CONTRAST_ALPHA
        )
        viewer.contrast_btn.state = "normal"
        assert viewer._pane_scrim_color.a == pytest.approx(viewer_module.READING_PANE_SCRIM[3])

    def test_the_sidebar_scrim_ignores_the_toggle(self, viewer: OKFViewer) -> None:
        assert viewer._sidebar.scrim_color.a == pytest.approx(sidebar.SIDEBAR_SCRIM[3])
        viewer.contrast_btn.state = "down"
        assert viewer._sidebar.scrim_color.a == pytest.approx(sidebar.SIDEBAR_SCRIM[3])


class TestTheReadingColumnsCap:
    """The body column fills its pane up to a cap an embedding app may move."""

    def test_the_column_fills_a_narrow_pane_and_stops_at_the_cap(self, viewer: OKFViewer) -> None:
        narrow = 500
        viewer.body_scroll.width = narrow
        assert viewer.body.width == narrow
        viewer.body_scroll.width = 5000
        assert viewer.body.width == viewer_module.dp(viewer_module.BODY_MAX_WIDTH)

    def test_a_wider_cap_widens_the_column_at_once(self, viewer: OKFViewer) -> None:
        viewer.body_scroll.width = 5000
        viewer.set_body_max_width(880)
        assert viewer.body.width == viewer_module.dp(880)
        viewer.set_body_max_width(viewer_module.BODY_MAX_WIDTH)
        assert viewer.body.width == viewer_module.dp(viewer_module.BODY_MAX_WIDTH)


class TestTheContentPadding:
    """The panels sit CONTENT_PADDING in from every side until an app moves them."""

    def test_the_default_and_an_apps_padding(self, viewer: OKFViewer) -> None:
        assert list(viewer._content.padding) == [viewer_module.CONTENT_PADDING] * 4
        viewer.set_content_padding(40, 0, 8, 2)
        assert list(viewer._content.padding) == [40, 0, 8, 2]


class TestTheCentredBlock:
    """Centred, the sidebar and the capped column sit with even art either side."""

    def _lay_out(self, viewer: OKFViewer, width: float) -> None:
        viewer.size = (width, 800)
        viewer._content.size = (width, 700)
        viewer._content.do_layout()  # the scroll's new width refits the column

    def test_the_pair_is_centred_with_the_sidebars_share_kept(self, viewer: OKFViewer) -> None:
        viewer.set_body_max_width(880)
        viewer.set_centre_block(True)
        self._lay_out(viewer, 1876)
        sidebar = viewer._left_column
        assert sidebar.width == pytest.approx(1876 * viewer_module.TREE_PANEL_WIDTH)
        pane = viewer.body_scroll
        assert sidebar.x == pytest.approx(viewer._content.right - pane.right)
        assert viewer.body.width == viewer_module.dp(880)

    def test_centred_the_pane_is_the_columns_width(self, viewer: OKFViewer) -> None:
        """So its scroll bar sits at the column's edge, not a margin away."""
        viewer.set_body_max_width(880)
        viewer.set_centre_block(True)
        self._lay_out(viewer, 1876)
        assert viewer.body_scroll.width == pytest.approx(viewer_module.dp(880))

    def test_too_narrow_to_centre_it_keeps_the_plain_layout(self, viewer: OKFViewer) -> None:
        viewer.set_content_padding(40, 0, 8, 0)
        viewer.set_centre_block(True)
        self._lay_out(viewer, 1000)
        assert viewer._left_column.size_hint_x == viewer_module.TREE_PANEL_WIDTH
        assert list(viewer._content.padding) == [40, 0, 8, 0]

    def test_off_restores_the_plain_layout(self, viewer: OKFViewer) -> None:
        viewer.set_centre_block(True)
        self._lay_out(viewer, 1876)
        viewer.set_centre_block(False)
        assert viewer._left_column.size_hint_x == viewer_module.TREE_PANEL_WIDTH
        assert list(viewer._content.padding) == [viewer_module.CONTENT_PADDING] * 4


class TestContrastSetByTheApp:
    def test_set_contrast_presses_the_toggle_and_resets_the_scrims(self, viewer: OKFViewer) -> None:
        viewer.set_contrast(True)
        assert viewer.contrast_btn.state == "down"
        assert viewer._pane_scrim_color.a == viewer_module.READING_PANE_SCRIM_CONTRAST_ALPHA
        viewer.set_contrast(False)
        assert viewer.contrast_btn.state == "normal"
        assert viewer._pane_scrim_color.a == viewer_module.READING_PANE_SCRIM[3]


class TestTheReadingPaneScrim:
    """The scrim behind the column is the pane's height, the column's width."""

    def test_the_scrim_reaches_the_panes_bottom_under_a_short_page(self, viewer: OKFViewer) -> None:
        viewer.body_scroll.pos = (300, 50)
        viewer.body_scroll.size = (1000, 900)
        viewer.body.height = 120  # A short page.
        viewer.body.x = 40  # An offset in the pane: its content is kept at the origin.
        assert viewer._pane_scrim_rect.pos == (340, 50)
        assert viewer._pane_scrim_rect.size == (viewer.body.width, 900)

    def test_the_scrim_is_the_columns_width(self, viewer: OKFViewer) -> None:
        viewer.body_scroll.width = 5000
        assert viewer._pane_scrim_rect.size[0] == viewer_module.dp(viewer_module.BODY_MAX_WIDTH)


class TestTheSideScrims:
    """The art beside the panels is dimmed a little; the panels' own scrims are not changed."""

    def test_the_left_strip_runs_from_the_rows_edge_to_the_sidebar(self, viewer: OKFViewer) -> None:
        viewer._content.pos = (0, 20)
        viewer._content.size = (2000, 900)
        viewer._left_column.x = 300

        assert viewer._left_side_scrim.pos == (0, 20)
        assert viewer._left_side_scrim.size == (300, 900)

    def test_the_right_strip_starts_at_the_columns_edge(self, viewer: OKFViewer) -> None:
        viewer._content.pos = (0, 20)
        viewer._content.size = (2000, 900)
        viewer.body_scroll.x = 500
        viewer.body.x = 0
        viewer.body.width = 760

        assert viewer._right_side_scrim.pos == (1260, 20)
        assert viewer._right_side_scrim.size == (740, 900)

    def test_no_room_at_a_side_draws_nothing_there(self, viewer: OKFViewer) -> None:
        viewer._content.pos = (0, 0)
        viewer._content.size = (1000, 900)
        viewer._left_column.x = 0
        viewer.body_scroll.x = 300
        viewer.body.width = 800

        assert viewer._left_side_scrim.size[0] == 0
        assert viewer._right_side_scrim.size[0] == 0

    def test_the_side_scrims_are_light(self) -> None:
        assert viewer_module.SIDE_SCRIM[3] < viewer_module.READING_PANE_SCRIM[3]


class TestHistoryRoot:
    def test_back_at_the_root_leaves_the_reader(self, bundle: Path) -> None:
        on_exit = MagicMock()
        viewer = OKFViewer(bundle, on_exit=on_exit)

        viewer.go_back()

        on_exit.assert_called_once_with()
        assert page_of(viewer) == "index.md"

    def test_back_from_a_second_page_returns_to_the_first(self, bundle: Path) -> None:
        on_exit = MagicMock()
        viewer = OKFViewer(bundle, on_exit=on_exit)
        viewer.show_page(bundle / "concept" / "a.md")

        viewer.go_back()

        on_exit.assert_not_called()
        assert page_of(viewer) == "index.md"

    def test_a_reset_keeps_the_page_showing_as_the_new_root(self, bundle: Path) -> None:
        """Re-entered, the reader's Back leaves it and does not walk the last visit."""
        on_exit = MagicMock()
        viewer = OKFViewer(bundle, on_exit=on_exit)
        viewer.show_page(bundle / "concept" / "a.md")

        viewer.reset_to(None)

        assert [e.path for e in viewer.history] == [bundle / "concept" / "a.md"]
        viewer.go_back()
        on_exit.assert_called_once_with()

    def test_a_reset_to_a_page_roots_the_history_there(self, bundle: Path) -> None:
        viewer = OKFViewer(bundle)

        viewer.reset_to(bundle / "concept" / "a.md")

        assert [e.path for e in viewer.history] == [bundle / "concept" / "a.md"]


def test_run_hands_every_option_to_the_app(bundle: Path) -> None:
    options = {
        "image_provider": MagicMock(),
        "table_rewriter": MagicMock(),
        "start_page": bundle / "concept" / "a.md",
        "action_provider": MagicMock(),
        "top_bar": MagicMock(),
        "state_path": bundle / "session.json",
        "search_provider": MagicMock(),
    }
    with patch.object(viewer_module, "OKFApp") as app:
        viewer_module.run(bundle, **options)

    app.assert_called_once_with(bundle, **options)
    app.return_value.run.assert_called_once_with()


# What follows is the remote's paths again, at the size of a unit test: the GUI suite
# walks them in the real app, and these say which line broke when it fails.


class TestEscape:
    def test_it_clears_a_search_before_it_goes_to_the_bar(self, viewer: OKFViewer) -> None:
        viewer.search_field.text = "a"

        assert viewer.handle_key(KEY_ESCAPE) is True

        assert viewer.search_field.text == ""
        assert viewer._focus_region is not FocusRegion.TOP_BAR

    def test_a_second_escape_drops_out_of_the_bar_to_where_it_came_from(
        self, viewer: OKFViewer
    ) -> None:
        viewer._set_focus_region(FocusRegion.PAGE)
        viewer.handle_key(KEY_ESCAPE)
        assert viewer._focus_region is FocusRegion.TOP_BAR

        viewer.handle_key(KEY_ESCAPE)

        assert viewer._focus_region is FocusRegion.PAGE


class TestAPageShownAgain:
    def test_the_page_already_showing_adds_nothing_to_the_history(self, viewer: OKFViewer) -> None:
        viewer.show_page(viewer.bundle / "index.md")
        assert len(viewer.history) == 1

    def test_the_page_left_remembers_how_far_it_was_scrolled(self, viewer: OKFViewer) -> None:
        viewer.body_scroll.scroll_y = 0.4
        viewer.show_page(viewer.bundle / "concept" / "a.md")
        assert viewer.history[0].scroll_y == pytest.approx(0.4)

    def test_a_page_opened_part_way_down_is_put_there_again_once_laid_out(
        self, viewer: OKFViewer
    ) -> None:
        with clock_patched() as clock:
            viewer.show_page(viewer.bundle / "concept" / "a.md", scroll_y=0.25)
            assert viewer.body_scroll.scroll_y == pytest.approx(0.25)
            viewer.body_scroll.scroll_y = 0.9  # the labels' sizes arriving shift it
            run_scheduled(clock)

        assert viewer.body_scroll.scroll_y == pytest.approx(0.25)


class TestATableUnderAHeading:
    def test_it_goes_in_the_headings_section_and_starts_none(self, viewer: OKFViewer) -> None:
        page = viewer.bundle / "table.md"
        page.write_text("# Table\n\n| a |\n|---|\n| 1 |\n", encoding="utf-8")
        with patch.object(viewer, "_new_section", wraps=viewer._new_section) as new_section:
            viewer.show_page(page)
        assert new_section.call_count == 1


class TestAListItem:
    """A list item's marker sits in its own column and keeps the text's height."""

    def test_the_row_and_its_marker_follow_the_texts_height(self) -> None:
        text = Label(size_hint_y=None)
        row = OKFViewer._hanging_row(text, Block(markup="item", indent=1, marker="•"))

        text.height = 77

        marker = next(w for w in row.children if isinstance(w, Label) and w is not text)
        assert (row.height, marker.height) == (77, 77)
        assert marker.text == "•"

    def test_a_nested_item_is_stepped_in_by_its_depth(self) -> None:
        text = Label(size_hint_y=None)
        row = OKFViewer._hanging_row(text, Block(markup="item", indent=3, marker="1."))

        spacer = row.children[-1]  # added first: the leftmost
        assert spacer.width == dp(2 * viewer_module.LIST_INDENT_STEP)
        assert row.children[0] is text
