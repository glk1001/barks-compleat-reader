"""Kivy viewer for an OKF bundle — the UI layer of okf_reader.

Binds the Kivy-free core (okf_reader.core.render and .bundle) to native widgets: a lazily
populated tree of the bundle's tiers on the left, the rendered page on the right.
Links resolve via the core's ``resolve_link``; tapping a footnote marker shows its
definition (keyed by the page `Block`'s anchor) in a dismiss-on-tap popup.
``run(bundle)`` launches the standalone app; the CLI entry point is
scripts/read_okf.py.
"""

from __future__ import annotations

import io
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from okf_reader.core.bundle import resolve_link
from okf_reader.core.render import (
    Block,
    TableBlock,
    TableRewriter,
    render_page,
)
from okf_reader.core.search import BundleSearcher
from okf_reader.core.session import resolve_start_page, save_session_state
from okf_reader.core.theme import ViewerThemeSpec
from okf_reader.core.top_bar import TopBarSpec
from okf_reader.ui import trace

from .bar import TopBar
from .focus_ring import (
    SIDEBAR_RING_GROUP,
    clear_focus_ring,
    draw_focus_ring,
)
from .keynav import (
    KEY_DOWN,
    KEY_END,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_F,
    KEY_HOME,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
    NAV_NOOP_KEYS,
    FocusRegion,
    step_index,
)
from .page_links import PageLinks
from .tree_panel import TREE_PANEL_FONT_SIZE, TreePanel
from .widgets import (
    BLOCK_BG_COLOR,
    TABLE_FONT_NAME,
    FlatButton,
    LazyTable,
    PageLabel,
    add_text_backing,
    result_markup,
    scroll_view,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Collection
    from pathlib import Path

    from kivy.input.motionevent import MotionEvent
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.togglebutton import ToggleButton

    from okf_reader.core.actions import PageActionProvider
    from okf_reader.core.backgrounds import ImageProvider
    from okf_reader.core.search import SearchHit, SearchProvider

BODY_LINE_HEIGHT = 1.25
# Space between a table's last row and its horizontal scrollbar (see _table_widget).
TABLE_BAR_GAP = dp(4)
# A table this long, with no links, keeps Labels only for the rows near the viewport
# (see LazyTable). Kivy frees a widget only on a full garbage collection, which the
# app runs rarely, so each visit to a page of a thousand row Labels left them all as
# garbage: on Windows, a few visits to the bibliography took the app past 6 GB.
LAZY_TABLE_MIN_ROWS = 100
BODY_PADDING = (16, 8, 24, 16)  # left, top, right, bottom
# The sidebar and reading pane's inset below the top bar (px), on every side; an
# embedding app may set others (`set_content_padding`), as the Barks Reader does on
# its two-page spread.
CONTENT_PADDING = 8
# Between the sidebar's edge and the reading pane's scrim (px): none, the two
# scrims meet (2026-10-31).
PANEL_GAP = 0
BODY_BLOCK_SPACING = 12
POPUP_PADDING = 12
TREE_PANEL_WIDTH = 0.22  # fraction of the window; the page panel gets the rest
# The background image shows at full strength: each panel's own scrim darkens it
# (once a whole-window tint of 0.30, folded into the two scrims below, 2026-10-31),
# so the art round the panels stays bright.
# Translucent black drawn over the background image behind the whole sidebar
# column (the search field and the tree), giving the tree text and the
# search-field seam a legibility floor over a vivid background panel. Near-black,
# so a page with no background image is unchanged (black over the plain window).
# Fixed, the Contrast toggle leaving it be: the sidebar always shows some of the
# background, and the toggle governs the article panel alone (2026-10-31).
SIDEBAR_SCRIM = (0, 0, 0, 0.79)
# Band alpha while the Contrast toggle is down: near-opaque, so the text reads
# as if on a plain dark page whatever the background image is doing.
BLOCK_BG_CONTRAST_ALPHA = 0.9
# Continuous near-black scrim behind the whole reading column (self.body), under
# the per-section bands: it floors the inter-section gaps and the column padding
# so a busy background panel cannot bleed bright art through the gaps the bands
# leave between them. Near-black, so a page with no background image (the plain
# standalone case) is unchanged. Its alpha tracks the Contrast toggle
# (READING_PANE_SCRIM_CONTRAST_ALPHA) alongside the bands, so pressing Contrast
# darkens the whole reading pane — the gaps included — not just the text bands.
# The alpha is the article panel's see-through knob: 0 shows the art at full
# strength under the text, 1 hides it.
READING_PANE_SCRIM = (0.0, 0.0, 0.0, 0.76)
# A light scrim over the art at the sides: left of the sidebar and right of the
# reading column, below the top bar, so the panels stand out from the art beside
# them while it still shows (2026-11-09). Near-black, so a page with no background
# image is unchanged.
SIDE_SCRIM = (0.0, 0.0, 0.0, 0.30)
READING_PANE_SCRIM_CONTRAST_ALPHA = 0.955
SECTION_PADDING = (10, 8)  # inset of a section's text from its band edge
SECTION_BLOCK_SPACING = 8  # between blocks inside one banded section
# The action-bar strip across the top mirrors the Barks Reader's kv idiom
# (ui/action_bar.kv): a dark opaque band holding the app icon, the markup
# heading, and the right-aligned action buttons behind a thin separator. What
# fills it — content and style — comes from the embedding app via TopBarSpec
# (the style defaults live on the spec).
# The tree selection band, row text (dir white / concept gold), striping and
# the search-result title/breadcrumb/hint colors are themable — they live on
# `ViewerThemeSpec` (okf_reader.core.theme), read here via `self._theme` so an
# embedding app can recolor them; the defaults there reproduce this look.
# Cap on the reading column: past this the body column stops growing, keeping
# the measure comfortable (~90 characters at the body size) on maximized
# windows. Wide tables scroll within it. An embedding app may set another
# (`set_body_max_width`), as the Barks Reader does on its two-page spread.
BODY_MAX_WIDTH = 760  # dp
# Hanging-indent geometry for list items and blockquote paragraphs
# (Block.indent > 0): the marker glyph sits right-aligned in its own fixed
# column, so a wrapped line aligns under the item's text instead of returning
# to the margin. Deeper nesting shifts the whole row right one step per level.
LIST_MARKER_WIDTH = 24  # dp — fits "99." at body size
LIST_MARKER_GAP = 6  # dp, between the marker column and the text
LIST_INDENT_STEP = 20  # dp per nesting level past the first
# Search field pinned atop the tree column: typing swaps the tree out for a
# results list, clearing swaps it back (see _on_search_text). Results reuse the
# navigation column so a pick lands in the tree via the existing show_page sync.
SEARCH_FIELD_HEIGHT = 32  # dp
SEARCH_FIELD_GAP = 6  # dp between the field and the tree/results below it
SEARCH_FIELD_BG = (0.16, 0.16, 0.16, 1)
# A faint light outline round the search field, so it stands off the sidebar scrim
# over any background art (2026-10-31); a lighter fill would cost the text contrast.
SEARCH_FIELD_BORDER = (1.0, 1.0, 1.0, 0.25)
SEARCH_FIELD_BORDER_WIDTH = 1  # px
SEARCH_RESULT_HEIGHT = 48  # dp — two lines: title over a dim breadcrumb
# A text hit's row: its title over two lines of snippet. The label's text height
# is held to the row's, so a snippet that wraps further loses its later lines
# rather than running into the next row (max_lines is not honored with markup).
SEARCH_SNIPPET_RESULT_HEIGHT = 66  # dp
SEARCH_SNIPPET_TEXT_INSET = 4  # dp — the text box sits this far inside the row, top and bottom
SEARCH_ERROR_TEXT = "Search unavailable"  # shown if the index build failed
SEARCH_CLEAR_BTN_WIDTH = 28  # dp — the "clear search" button inside the field's right end
SEARCH_CLEAR_GLYPH_SIZE = 22  # dp — big/bold enough to read in the small button
SEARCH_CLEAR_GLYPH_COLOR = (0.9, 0.9, 0.9, 1)  # light glyph on the dark (tinted) button
# The open page's result row gets the theme selection band (self._theme.selection):
# with the results kept up (to open several pages in a row) it shows which one you
# are reading. Inactive rows are transparent (unthemed).
SEARCH_RESULT_INACTIVE_COLOR = (0, 0, 0, 0)


@dataclass
class _HistoryEntry:
    """One visited page, remembering where it was scrolled to when left (1.0 == top)."""

    path: Path
    scroll_y: float = 1.0


class OKFViewer(RelativeLayout):
    def __init__(
        self,
        bundle: Path,
        image_provider: ImageProvider | None = None,
        table_rewriter: TableRewriter | None = None,
        start_page: Path | None = None,
        action_provider: PageActionProvider | None = None,
        top_bar: TopBarSpec | None = None,
        theme: ViewerThemeSpec | None = None,
        state_path: Path | None = None,
        on_exit: Callable[[], None] | None = None,
        search_provider: SearchProvider | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.bundle = bundle
        # Colors the embedding app may theme (tree, search, focus ring, article
        # markup); the default reproduces the standalone reader's palette.
        self._theme = theme if theme is not None else ViewerThemeSpec()
        self.history: list[_HistoryEntry] = []
        self._anchors: dict[str, str] = {}  # "fn:<label>" -> the definition block's markup
        self._image_provider = image_provider
        self._table_rewriter = table_rewriter
        self._action_provider = action_provider
        self._state_path = state_path
        # Title, heading and text search over the bundle. The built-in searcher
        # needs no app knowledge (unlike the image/table/action providers) and
        # builds its index lazily on the first query, so defaulting it here costs
        # nothing up front; an embedding app may inject a different backend.
        self._searcher: SearchProvider = search_provider or BundleSearcher(bundle)
        self._body_max_width: float = BODY_MAX_WIDTH  # dp
        self._content_padding: tuple[float, ...] = (CONTENT_PADDING,) * 4  # l, t, r, b
        self._centre_block = False
        # Building the index walks the whole bundle, so it is warmed off the UI
        # thread (see warm_search), by the field's first focus or by the host
        # sooner; until it is ready a query shows a "Searching…" note rather than
        # freezing the field.
        # _search_failed is set if the off-thread index build raised: search is
        # "ready" (the field stops waiting) but disabled, showing an error note
        # instead of hanging on "Searching…". It guards every search() call, since
        # a failed BundleSearcher would re-raise the build on the UI thread if
        # queried again.
        self._search_ready = self._search_failed = False
        self._search_warming = False
        # Where Back falls through to at the root of the history: the hosting app's
        # "leave the reader" action. None (the standalone case) leaves Back a no-op
        # at the root, since the reader is the whole app.
        self._on_exit = on_exit
        self._band_colors: list[Color] = []  # the current page's section-band Colors
        self._init_keyboard_nav()

        # The whole window layers over a context background image (RelativeLayout
        # children stack in add order): image below, the action bar and both
        # panels above.
        self.bg_image = Image(fit_mode="cover", size_hint=(1, 1))
        self.add_widget(self.bg_image)
        root = BoxLayout(orientation="vertical", size_hint=(1, 1))
        self.add_widget(root)
        self._bar = TopBar(
            top_bar if top_bar is not None else TopBarSpec(),
            self._theme.icon_tint,
            on_home=lambda: self._show(self.bundle / "index.md", push=True),
            on_back=self.go_back,
            on_contrast_state=self._on_contrast_state,
            on_leave=lambda: self._set_focus_region(self._bar_return_region),
        )
        root.add_widget(self._bar.widget)
        self._content = BoxLayout(
            orientation="horizontal", spacing=PANEL_GAP, padding=CONTENT_PADDING, size_hint=(1, 1)
        )
        root.add_widget(self._content)

        self._tree_panel = TreePanel(
            bundle,
            self._theme,
            on_open_page=lambda page: self._show(page, push=True),
            on_cross_to_page=lambda: self._set_focus_region(FocusRegion.PAGE),
            on_up_off_top=self.focus_search,
        )
        self.tree = self._tree_panel.tree
        self.tree_scroll = self._tree_panel.scroll

        self._left_column = self._build_left_column()
        self._content.add_widget(self._left_column)

        self.body_scroll = scroll_view(
            self._theme, size_hint=(1 - TREE_PANEL_WIDTH, 1), do_scroll_x=False
        )
        self.body = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            spacing=BODY_BLOCK_SPACING,
            padding=BODY_PADDING,
        )
        self.body.bind(minimum_height=self.body.setter("height"))
        self._links = PageLinks(self.body, self.body_scroll, self._theme.link_hex, self._on_ref)
        self._add_scrims()
        # The scroll child is a full-width anchor holding the body column against
        # the sidebar, its width capped at BODY_MAX_WIDTH so the measure stays
        # readable on wide windows (below the cap the column just fills the pane).
        # Centred, the column floated between two bands of art on the two-page
        # spread, away from the contents beside it (2026-10-30).
        body_anchor = AnchorLayout(anchor_x="left", size_hint_y=None)
        body_anchor.add_widget(self.body)
        self.body.bind(height=body_anchor.setter("height"))
        self.body_scroll.bind(width=lambda *_args: self._fit_body_width())
        self.bind(width=lambda *_args: self._fit_content())
        self.body_scroll.add_widget(body_anchor)
        self._content.add_widget(self.body_scroll)

        # Startup, before any page is shown: empty frontmatter matches no title, so
        # the provider's fallback pool supplies a random story image.
        self._update_background({}, bundle)

        self._show_start_page(start_page)

        # A cold open hands the keys to the sidebar (ring + banded current-page
        # node): a visible, predictable starting focus for the 6-button remote,
        # matching the main screen's tree-first model. But when the caller named
        # a landing page — a "go read THIS page" entry — start in the reading
        # pane instead, so Up/Down reads it straight away: the intent was the
        # page, not the navigator. No link is ringed on arrival; PAGE focus
        # leaves the hybrid Up/Down walk to acquire links as they scroll past
        # (see `PageLinks.line_step`), so the ring never lands on an arbitrary
        # breadcrumb link.
        self._set_focus_region(FocusRegion.PAGE if start_page is not None else FocusRegion.SIDEBAR)

    @property
    def bar_drag_region(self) -> Label:
        """The bar's heading: the window-drag region when the bar replaces the OS titlebar."""
        return self._bar.drag_region

    @property
    def back_btn(self) -> Button:
        """The bar's Back button."""
        return self._bar.back_btn

    @property
    def contrast_btn(self) -> ToggleButton:
        """The bar's Contrast toggle."""
        return self._bar.contrast_btn

    @property
    def action_btn(self) -> Button | None:
        """The bar's button for the page's action, when the page has one."""
        return self._bar.action_btn

    def _show_start_page(self, start_page: Path | None) -> None:
        """Show the opening page: the caller's choice, else the session's, else home.

        See ``resolve_start_page``. The tree syncs itself to whatever is shown.
        """
        page, scroll_y = resolve_start_page(self.bundle, start_page, self._state_path)
        self._show(page, push=True, scroll_y=scroll_y)

    def _build_left_column(self) -> BoxLayout:
        """Build the left column: a search field over the tree/results body slot.

        The search field swaps the body slot between ``tree_scroll`` (default)
        and the results list as its text changes (see `_on_search_text`). Assumes
        ``self.tree_scroll`` is already built.
        """
        # Results stay up after a hit is opened (open several in a row); the open
        # page's row is highlighted, cleared to the tree via the clear button / Escape.
        self._result_rows: list[tuple[Path, Button]] = []
        self._active_result_path: Path | None = None
        left = BoxLayout(
            orientation="vertical",
            size_hint=(TREE_PANEL_WIDTH, 1),
            spacing=dp(SEARCH_FIELD_GAP),
        )
        # Scrim over the background image behind the whole sidebar column
        # (canvas.before renders under the column's widgets), kept glued to it, so
        # the tree text and the search-field seam keep a legibility floor over a
        # vivid background panel.
        with left.canvas.before:  # ty: ignore[missing-union-attribute]
            self._sidebar_scrim_color = Color(rgba=SIDEBAR_SCRIM)
            sidebar_scrim = Rectangle(pos=left.pos, size=left.size)
        left.bind(
            pos=lambda _inst, pos: setattr(sidebar_scrim, "pos", pos),
            size=lambda _inst, size: setattr(sidebar_scrim, "size", size),
        )
        self.search_field = TextInput(
            hint_text="Search pages…",
            font_size=sp(TREE_PANEL_FONT_SIZE),
            multiline=False,
            write_tab=False,
            background_color=SEARCH_FIELD_BG,
            foreground_color=(1, 1, 1, 1),
            hint_text_color=self._theme.secondary_text,
            cursor_color=(1, 1, 1, 1),
            # The right padding keeps the text clear of the button over that end.
            padding=(dp(8), dp(6), dp(8) + dp(SEARCH_CLEAR_BTN_WIDTH), dp(6)),
            # A FloatLayout places only a child with a pos_hint: without one the
            # field sat at the window's origin, away from its row.
            pos_hint={"x": 0, "y": 0},
        )
        self.search_field.bind(
            text=self._on_search_text,
            on_text_validate=self._on_search_enter,
            focus=self._on_search_focus,
        )
        with self.search_field.canvas.after:  # ty: ignore[missing-union-attribute]
            Color(rgba=SEARCH_FIELD_BORDER)
            field_border = Line(width=SEARCH_FIELD_BORDER_WIDTH, close=True)

        def fit_border(field: Widget, _value: object) -> None:
            x, y, w, h = (*field.pos, *field.size)
            field_border.points = [x, y, x + w, y, x + w, y + h, x, y + h]

        self.search_field.bind(pos=fit_border, size=fit_border)
        # The field spans the sidebar, and a "clear" button over its right end shows
        # only while there is text — a one-tap return to the tree when done searching.
        # Hidden, it has no width: a disabled widget still swallows the touches it
        # covers, which would leave that end of the field dead to a click.
        search_row = FloatLayout(size_hint_y=None, height=dp(SEARCH_FIELD_HEIGHT))
        search_row.add_widget(self.search_field)
        self.search_clear_btn = FlatButton(
            text="×",  # noqa: RUF001 — the multiplication sign renders in every font (unlike ✕)
            font_size=dp(SEARCH_CLEAR_GLYPH_SIZE),
            bold=True,
            color=SEARCH_CLEAR_GLYPH_COLOR,
            size_hint=(None, 1),
            pos_hint={"right": 1, "y": 0},
            width=0,
            opacity=0,
            disabled=True,
        )
        self.search_clear_btn.bind(on_release=lambda *_: self._clear_search())
        search_row.add_widget(self.search_clear_btn)
        left.add_widget(search_row)
        self._left_body = BoxLayout(size_hint=(1, 1))
        self._left_body.add_widget(self.tree_scroll)
        left.add_widget(self._left_body)
        return left

    def _on_search_focus(self, _field: TextInput, focused: bool) -> None:
        """On the field's first focus, warm the search index (`warm_search`).

        Starting it on focus (before the user has typed) keeps the field
        responsive and usually has results ready by the first keystroke, where the
        host has not started it already.

        Every focus is logged here, however it came - a key (`focus_search`) or a
        tap - so a test can wait for the field to take the keyboard before typing.
        """
        if focused:
            trace.search_focused()
            self.warm_search()

    def warm_search(self) -> None:
        """Start building the search index off the UI thread, once.

        The build walks the whole bundle. The field's first focus starts it; a host
        that opens the reader for the user can start it then instead, so a query
        typed soon after finds the index ready (the Barks Reader does, as on a
        Windows VM the build took over 5 s). A provider without a ``warm`` method
        is assumed to manage its own readiness, so it is marked ready at once.
        Later calls do nothing.
        """
        if self._search_warming:
            return
        self._search_warming = True
        warm = getattr(self._searcher, "warm", None)
        if warm is None:
            self._search_ready = True
            return
        threading.Thread(target=self._warm_search_index, args=(warm,), daemon=True).start()

    def set_body_max_width(self, width_dp: float) -> None:
        """Cap the reading column at `width_dp` (density-independent pixels).

        The default is BODY_MAX_WIDTH; a wider window may afford a wider measure.
        """
        self._body_max_width = width_dp
        self._fit_body_width()
        self._fit_content()

    def set_content_padding(self, left: float, top: float, right: float, bottom: float) -> None:
        """Inset the sidebar and reading pane below the top bar by these pixels.

        The default is CONTENT_PADDING on every side. A centred block (see
        `set_centre_block`) takes `left` as its smallest margin.
        """
        self._content_padding = (left, top, right, bottom)
        self._fit_content()

    def set_centre_block(self, on: bool) -> None:
        """Centre the sidebar and the capped reading column together, or not.

        Centred, the sidebar keeps its fraction of the whole viewer and the art
        left beside the pair is split evenly into the row's padding on either side,
        so the reading pane is the column's width and its scroll bar sits at the
        column's edge, as the sidebar's does at its own (in the pane, the bar stood
        a margin away at the window's edge, 2026-10-31). A viewer too narrow for a
        margin wider than the left padding falls back to the plain layout.
        """
        self._centre_block = on
        self._fit_content()

    def _fit_content(self) -> None:
        """Lay the row out to the padding, centring the pair if asked and it fits."""
        left, top, right, bottom = self._content_padding
        if self._centre_block:
            sidebar_width = self.width * TREE_PANEL_WIDTH
            column_width = dp(self._body_max_width)
            margin = (self.width - sidebar_width - PANEL_GAP - column_width) / 2
            if margin > left:
                self._left_column.size_hint_x = None
                self._left_column.width = sidebar_width
                self.body_scroll.size_hint_x = 1
                self._content.padding = (margin, top, margin, bottom)
                return
        self._left_column.size_hint_x = TREE_PANEL_WIDTH
        self.body_scroll.size_hint_x = 1 - TREE_PANEL_WIDTH
        self._content.padding = (left, top, right, bottom)

    def _fit_body_width(self) -> None:
        """Size the body column to its pane, no wider than the cap."""
        self.body.width = min(self.body_scroll.width, dp(self._body_max_width))

    def _warm_search_index(self, warm: Callable[[], None]) -> None:
        """Worker thread: build the index, then flip readiness on the UI thread.

        A build failure still flips readiness (with the failed flag) so the field
        recovers to an error note rather than hanging on "Searching…" forever; the
        exception must not escape here or the daemon thread would die silently.
        """
        trace.search_index_building()
        start = time.perf_counter()
        try:
            warm()
        except Exception as error:  # noqa: BLE001 — any build failure must surface, not hang
            trace.search_index_failed(time.perf_counter() - start, error)
            Clock.schedule_once(lambda _dt: self._mark_search_ready(failed=True), 0)
            return
        trace.search_index_built(time.perf_counter() - start)
        Clock.schedule_once(lambda _dt: self._mark_search_ready(failed=False), 0)

    def _mark_search_ready(self, *, failed: bool) -> None:
        """Mark the index ready (or failed) and refresh any query typed while warming."""
        trace.search_ready(failed=failed, text=self.search_field.text)
        self._search_ready = True
        self._search_failed = failed
        if self.search_field.text.strip():
            if failed:
                self._show_search_error()
            else:
                text = self.search_field.text
                self._show_results(self._searcher.search(text), text)

    def _on_search_text(self, _field: TextInput, text: str) -> None:
        """Swap the left column between the tree, a wait note, the results, or an error."""
        has_text = bool(text)
        self.search_clear_btn.opacity = 1 if has_text else 0
        self.search_clear_btn.disabled = not has_text
        self.search_clear_btn.width = dp(SEARCH_CLEAR_BTN_WIDTH) if has_text else 0
        if not text.strip():
            self._show_tree_panel()
        elif not self._search_ready:
            self._show_searching()
        elif self._search_failed:
            self._show_search_error()
        else:
            self._show_results(self._searcher.search(text), text)

    def _clear_search(self) -> None:
        """Clear the search field, restoring the tree (the clear button / done searching)."""
        self.search_field.text = ""
        self.search_field.focus = False
        trace.search_cleared()

    def _on_search_enter(self, _field: TextInput) -> None:
        """Open the top hit when the search field is submitted (Enter), once ready."""
        if not self._search_ready or self._search_failed:
            return
        hits = self._searcher.search(self.search_field.text)
        if hits:
            self._open_search_hit(hits[0])

    def _show_tree_panel(self) -> None:
        """Restore the tree to the left column's body slot (empty/cleared search)."""
        if self.tree_scroll.parent is not self._left_body:
            self._result_rows = []
            self._sidebar_index = None  # the ringed row is being discarded
            self._results_scroll = None
            self._left_body.clear_widgets()
            self._left_body.add_widget(self.tree_scroll)
            # Reveal the current page's node, which was kept selected while the
            # results hid the tree (its scroll offset can go stale while hidden).
            if self.tree.selected_node is not None:
                Clock.schedule_once(
                    lambda _dt: self._tree_panel.scroll_node_into_view(self.tree.selected_node), 0
                )

    def _show_searching(self) -> None:
        """Show a wait note while the index warms (first query before it is ready)."""
        self._sidebar_index = None
        self._left_body.clear_widgets()
        self._left_body.add_widget(
            Label(
                text="Searching…", color=self._theme.secondary_text, valign="top", halign="center"
            )
        )

    def _show_search_error(self) -> None:
        """Show an error note when the index build failed (search stays disabled)."""
        self._sidebar_index = None
        self._left_body.clear_widgets()
        self._left_body.add_widget(
            Label(
                text=SEARCH_ERROR_TEXT,
                color=self._theme.secondary_text,
                valign="top",
                halign="center",
            )
        )

    def _show_results(self, hits: list[SearchHit], text: str) -> None:
        """Put the results list for query `text` in the left column, replacing the tree."""
        self._sidebar_index = None  # rows are rebuilt; any ringed row is discarded
        self._left_body.clear_widgets()
        self._left_body.add_widget(self._results_widget(hits))
        trace.search_results(len(hits), text)

    def _results_widget(self, hits: list[SearchHit]) -> ScrollView:
        """Build the scrollable results list — one row per hit, or a no-match note."""
        scroll = scroll_view(self._theme, size_hint=(1, 1), do_scroll_x=False)
        column = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(2), padding=(0, dp(2))
        )
        column.bind(minimum_height=column.setter("height"))
        self._result_rows = []
        if not hits:
            note = Label(
                text="No matches",
                font_size=sp(TREE_PANEL_FONT_SIZE),
                color=self._theme.secondary_text,
                size_hint_y=None,
                height=dp(SEARCH_RESULT_HEIGHT),
            )
            column.add_widget(note)
        for hit in hits:
            btn = self._result_button(hit)
            self._result_rows.append((hit.path, btn))
            column.add_widget(btn)
        scroll.add_widget(column)
        self._results_scroll = scroll  # keyboard nav scrolls the focused row into view
        self._highlight_active_result()  # mark the open page if it is in this list
        return scroll

    def _highlight_active_result(self) -> None:
        """Tint the open page's result row (a no-op when no results are showing)."""
        for path, btn in self._result_rows:
            active = path == self._active_result_path
            btn.background_color = self._theme.selection if active else SEARCH_RESULT_INACTIVE_COLOR

    def _result_button(self, hit: SearchHit) -> Button:
        """Build one result row: gold title over a dim breadcrumb or snippet, opening the page."""
        btn = Button(
            text=result_markup(hit, self._theme.title_hex, self._theme.crumb_hex),
            font_size=sp(TREE_PANEL_FONT_SIZE),
            markup=True,
            halign="left",
            # Top, for a snippet: a clipped label drops lines from both ends when centered.
            valign="top" if hit.snippet else "middle",
            size_hint_y=None,
            height=dp(SEARCH_SNIPPET_RESULT_HEIGHT if hit.snippet else SEARCH_RESULT_HEIGHT),
            background_color=SEARCH_RESULT_INACTIVE_COLOR,
            background_normal="",
        )
        text_height = (
            btn.height - 2 * dp(SEARCH_SNIPPET_TEXT_INSET) if hit.snippet else None
        )  # a snippet's lines past the row's are dropped
        btn.bind(width=lambda inst, w: inst.setter("text_size")(inst, (w - dp(12), text_height)))
        btn.bind(on_release=lambda *_: self._open_search_hit(hit))
        return btn

    def _open_search_hit(self, hit: SearchHit) -> None:
        """Open a picked result, keeping the results list up to open several in a row.

        The field only loses focus (so page keys work); the results stay so the
        next hit is one tap away, with the opened row highlighted (via ``_show``).
        The tree stays synced underneath, so clearing the search (the clear button
        or Escape) returns to it on the last page viewed.
        """
        self.search_field.focus = False
        self.show_page(hit.path)

    @property
    def search_focused(self) -> bool:
        """Whether the search field currently owns the keyboard.

        The hosting app checks this so that while the user is typing a search,
        keystrokes reach the field instead of driving navigation (e.g. a
        configurable alternate-Escape key that is an ordinary letter).
        """
        return bool(self.search_field.focus)

    def focus_search(self) -> None:
        """Focus the search field: Ctrl+F from the host, or Up off the sidebar's top."""
        self._clear_result_focus()
        self.search_field.focus = True  # logged by _on_search_focus

    def leave_search(self) -> None:
        """Leave the search field for the sidebar: its results if any, else the tree."""
        self.search_field.focus = False
        self._set_focus_region(FocusRegion.SIDEBAR)
        trace.search_left()

    def escape_search(self) -> bool:
        """Clear and unfocus the search field if active; report whether it consumed Escape.

        The hosting app calls this before its Back handling, so Escape backs out
        of an active search first and only navigates back once search is idle.
        """
        if self.search_field.text or self.search_field.focus:
            self.search_field.text = ""
            self.search_field.focus = False
            trace.search_cleared()
            return True
        return False

    def go_back(self) -> None:
        """Navigate to the previous page, or leave the reader at the history's root.

        Public: besides the bar's Back button (mouse, or Enter with the bar's
        keyboard focus on it), the hosting app routes its own back gestures here
        (mouse button 4, Alt+Left). At the root the ``on_exit`` seam fires when the hosting app
        supplied one (embedded: return to the host screen); otherwise it is a
        no-op (standalone: the reader is the whole app).
        """
        if len(self.history) > 1:
            self.history.pop()
            entry = self.history[-1]
            trace.back_to(self.bundle, entry.path)
            self._show(entry.path, push=False, scroll_y=entry.scroll_y)
        elif self._on_exit is not None:
            trace.back_exit()
            self._on_exit()

    def reset_to(self, path: Path | None = None) -> None:
        """Discard the back history, re-rooting it at ``path``.

        The hosting app calls this when the reader is re-entered so that Back from
        the landing page falls through to ``on_exit`` (leaving the reader) instead
        of walking a previous visit's history.

        Args:
            path: The page to make the new root. None keeps the current page (and
                its scroll offset) on screen as the root; if nothing has been shown
                yet, the bundle's home page is used.

        """
        scroll_y = 1.0
        caller_page = path is not None  # an explicit "go read THIS" landing page
        if path is None:
            if self.history:
                path, scroll_y = self.history[-1].path, self.body_scroll.scroll_y
            else:
                path = self.bundle / "index.md"
        self.history.clear()
        self._show(path, push=True, scroll_y=scroll_y)
        # Re-entry starts over with the sidebar focused, like a fresh open —
        # unless the caller named a landing page, then start in the reading pane
        # (the same intent split as a fresh open with a start_page; see __init__).
        self._set_focus_region(FocusRegion.PAGE if caller_page else FocusRegion.SIDEBAR)

    def save_session(self) -> None:
        """Persist the current page and scroll offset for the next launch.

        A no-op without a state path or before any page has been shown. The
        hosting app decides when — the standalone app calls this on stop.
        """
        if self._state_path is None or not self.history:
            return
        save_session_state(
            self._state_path, self.bundle, self.history[-1].path, self.body_scroll.scroll_y
        )

    def on_touch_down(self, touch: MotionEvent) -> bool:
        """Route the mouse's back button (button 4) to Back, wherever it lands."""
        if self._focus_region is FocusRegion.TOP_BAR:
            # A pointer press takes over from the keyboard (the comic reader's
            # menu-mode convention): drop the bar focus back down, then let the
            # touch dispatch normally — also keeping a click-navigation from
            # swapping the bar's buttons under a live keyboard focus.
            self._set_focus_region(self._bar_return_region)
        if getattr(touch, "button", "") == "mouse4":
            self.go_back()
            return True
        return bool(super().on_touch_down(touch))

    # ------------------------------------------------------------------
    # Keyboard navigation (see okf_reader.ui.keynav for the pure logic)
    # ------------------------------------------------------------------

    def _init_keyboard_nav(self) -> None:
        """Initialize keyboard-navigation state (see `handle_key`).

        Link focus is the page links' own (`PageLinks`); sidebar focus is the tree's
        own selection band in tree mode and ``_sidebar_index`` over the result rows
        in results mode.
        """
        self._focus_region = FocusRegion.PAGE
        self._sidebar_index: int | None = None
        self._results_scroll: ScrollView | None = None
        self._footnote_popup: ModalView | None = None
        self._bar_return_region = FocusRegion.SIDEBAR  # where leaving the bar drops the focus

    def handle_key(self, key: int, modifiers: Collection[str] = ()) -> bool:
        """Handle one navigation key press; return whether it was consumed.

        The hosting apps delegate here from their window keyboard handlers (the
        standalone ``OKFApp``, an embedding screen) after their own shortcut
        handling. Keys carrying command modifiers (Ctrl/Alt/Meta), and all but Down
        while the search field has the keyboard, are refused, so host shortcuts (Ctrl+F,
        Alt+Left) and search typing are never stolen. Escape is otherwise always
        consumed, unwinding one layer per press: it dismisses an open footnote
        popup, backs out of an active search, and then toggles the keyboard
        focus up to the top action bar and back (see `_handle_escape_key`) —
        going back through the history is the bar's Back button (or Alt+Left,
        or mouse button 4), not Escape.

        The map is built for a 6-button remote (Esc, Enter, and the arrows —
        the 10-foot TV case): Up/Down walk the page's links and scroll its
        link-free stretches; Left/Right move spatially between the sidebar and
        the page (Left goes leftward, Right drills rightward); Enter activates;
        Esc reaches the top bar's buttons; Up off the top of the sidebar (its
        tree or its results) goes into the search box, and Down comes back out
        of it (while typing, the field takes every other key). Tab (region toggle) and
        PageUp/PageDown/Home/End (page scrolling) are desktop extras. Mouse
        interaction is deliberately not tracked: a click that navigates rebuilds
        the page, which resets the keyboard focus state anyway.

        Args:
            key: The SDL2 keycode from the window keyboard event.
            modifiers: The event's active modifier names (e.g. ``{"ctrl"}``).

        Returns:
            True when the key was consumed.

        """
        if {"ctrl", "alt", "meta"} & set(modifiers):
            return False
        if self.search_focused:
            return self._handle_search_key(key)
        if self._footnote_popup is not None:
            return self._handle_popup_key(key)
        if key == KEY_ESCAPE:
            return self._handle_escape_key()
        if key == KEY_TAB:
            self._toggle_focus_region()
            return True
        region_handlers = {
            FocusRegion.TOP_BAR: self._bar.handle_key,
            FocusRegion.SIDEBAR: self._handle_sidebar_key,
            FocusRegion.PAGE: self._handle_page_key,
        }
        return region_handlers[self._focus_region](key)

    def _handle_search_key(self, key: int) -> bool:
        """While the field types: Down leaves it for the sidebar; it keeps every other key.

        Down is the remote's way out (Enter opens the top hit; Escape, the host's,
        clears the search).
        """
        if key == KEY_DOWN:
            self.leave_search()
            return True
        return False

    def _handle_escape_key(self) -> bool:
        """One Escape press: unwind an active search, else toggle the top-bar focus.

        The unwind ladder (an open footnote popup, handled before this, sits on
        top): an active search clears back to the tree first; then Escape lifts
        the keyboard focus to the top action bar — the 6-button remote's only
        route to the bar's buttons (Back, Contrast, the page action, Quit) —
        and from the bar it drops the focus back where it came from.
        """
        if self.escape_search():
            return True
        if self._focus_region is FocusRegion.TOP_BAR:
            self._set_focus_region(self._bar_return_region)
        else:
            self._enter_bar_focus()
        return True

    def _enter_bar_focus(self) -> None:
        """Lift the keyboard focus to the top bar, starting on the Back button.

        Back starts focused so the remote's back gesture stays two presses
        (Escape, Enter); when Back is disabled (the standalone reader at its
        history root) the focus starts on the bar's first button instead.
        """
        if not self._bar.nav_buttons():
            return
        self._bar_return_region = self._focus_region
        self._set_focus_region(FocusRegion.TOP_BAR)
        self._bar.enter_focus()

    def _handle_popup_key(self, key: int) -> bool:
        """Escape/Enter dismiss the footnote popup; nav keys are inert under it."""
        assert self._footnote_popup is not None
        if key in (KEY_ESCAPE, KEY_ENTER, KEY_NUMPAD_ENTER):
            self._footnote_popup.dismiss()
            return True
        # Nothing may scroll or refocus under the modal.
        return key in NAV_NOOP_KEYS or key == KEY_TAB

    def _handle_page_key(self, key: int) -> bool:
        """Walk the page with Up/Down (hybrid link/scroll) and follow links with Enter.

        The 10-foot model: Up/Down is the only reading control a 6-button
        remote has, so it walks the links while they pass through the viewport
        and scrolls through the link-free stretches (see `hybrid_link_step`).
        Left moves leftward to the sidebar; PageUp/PageDown/Home/End are
        desktop extras. Escape never reaches here — `handle_key` routes it to
        the top-bar focus toggle (`_handle_escape_key`) for every region.
        """
        if self._links.handle_key(key):
            return True
        if key == KEY_LEFT:
            self._set_focus_region(FocusRegion.SIDEBAR)
            return True
        # Nothing further right; consumed so it cannot leak.
        return key == KEY_RIGHT

    def _handle_sidebar_key(self, key: int) -> bool:
        """Drive the contents tree, or the search-result rows while results show."""
        if self._result_rows:
            return self._handle_results_key(key)
        if self.tree_scroll.parent is self._left_body:
            return self._tree_panel.handle_key(key)
        # "Searching…" / search-error / no-match states: nothing to navigate —
        # Right still crosses to the page panel, and the rest of the keys must
        # not leak to the host while the sidebar owns them.
        if key == KEY_RIGHT:
            self._set_focus_region(FocusRegion.PAGE)
            return True
        return key in NAV_NOOP_KEYS or key in (KEY_ENTER, KEY_NUMPAD_ENTER)

    def _handle_results_key(self, key: int) -> bool:
        """Walk the search-result rows with a drawn focus ring."""
        count = len(self._result_rows)
        if key == KEY_UP and self._sidebar_index == 0:
            self.focus_search()  # back up into the box the results came from
            return True
        if key in (KEY_UP, KEY_DOWN, KEY_HOME, KEY_END):
            if key == KEY_HOME:
                idx = 0
            elif key == KEY_END:
                idx = count - 1
            elif self._sidebar_index is None:
                idx = self._initial_result_index()
            else:
                idx = step_index(self._sidebar_index, count, 1 if key == KEY_DOWN else -1)
            self._set_result_focus(idx)
            return True
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            if self._sidebar_index is not None:
                self._result_rows[self._sidebar_index][1].trigger_action(duration=0)
            return True
        if key == KEY_RIGHT:
            self._set_focus_region(FocusRegion.PAGE)
            return True
        return key == KEY_LEFT

    def _initial_result_index(self) -> int:
        """Return the row to focus first: the open page's row when listed, else the top hit."""
        for i, (path, _btn) in enumerate(self._result_rows):
            if path == self._active_result_path:
                return i
        return 0

    def _set_result_focus(self, idx: int) -> None:
        """Move the gold ring to result row ``idx``, scrolling it into view."""
        self._clear_result_focus()
        self._sidebar_index = idx
        btn = self._result_rows[idx][1]
        draw_focus_ring(btn)
        scroll = self._results_scroll
        if scroll is not None and scroll.children and scroll.children[0].height > scroll.height:
            scroll.scroll_to(btn, padding=8)  # scroll_to applies dp() itself

    def _clear_result_focus(self) -> None:
        if self._sidebar_index is not None and self._sidebar_index < len(self._result_rows):
            clear_focus_ring(self._result_rows[self._sidebar_index][1])
        self._sidebar_index = None

    def _toggle_focus_region(self) -> None:
        if self._focus_region is FocusRegion.TOP_BAR:  # Tab drops out of the bar, like Down
            self._set_focus_region(self._bar_return_region)
            return
        self._set_focus_region(
            FocusRegion.SIDEBAR if self._focus_region is FocusRegion.PAGE else FocusRegion.PAGE
        )

    def _set_focus_region(self, region: FocusRegion) -> None:
        """Hand the navigation keys to ``region``, updating the visible indicators.

        Entering the sidebar rings it in blue and seeds a focus (the active
        result row, or the tree's selected node scrolled into view). Entering
        the top bar clears the pane indicators; `TopBar.enter_focus` then rings a
        button in gold. Returning to the page clears the rings and re-syncs the
        tree's selection band to the page on display, so a focus band wandered
        by Up/Down snaps back to reality.
        """
        self._focus_region = region
        trace.focus_region(region.name)
        self._bar.clear_focus()  # a no-op unless the bar was the outgoing region
        if region is FocusRegion.TOP_BAR:
            self._links.clear_focus()
            clear_focus_ring(self._left_body, group=SIDEBAR_RING_GROUP)
            self._clear_result_focus()
        elif region is FocusRegion.SIDEBAR:
            self._links.clear_focus()
            draw_focus_ring(self._left_body, group=SIDEBAR_RING_GROUP, color=self._theme.focus_ring)
            if self._result_rows:
                self._set_result_focus(self._initial_result_index())
            elif self.tree_scroll.parent is self._left_body and self.tree.selected_node is not None:
                self._tree_panel.reveal_when_settled(self.tree.selected_node)
        else:
            clear_focus_ring(self._left_body, group=SIDEBAR_RING_GROUP)
            self._clear_result_focus()
            if self.history:
                self._tree_panel.sync_to(self.history[-1].path)

    def _update_background(self, frontmatter: dict[str, Any], path: Path) -> None:
        """Set the page panel's background to an image suiting the page, if any.

        The provider owns selection and repeat-avoidance; this method only
        renders its answer — a plain file by filename, or in-memory bytes
        (e.g. a decrypted archive member) decoded to a texture.
        """
        if self._image_provider is None:
            return
        bg = self._image_provider.background_for(frontmatter, path)
        if bg is None:
            self.bg_image.source = ""
            self.bg_image.texture = None
        elif bg.path is not None:
            self.bg_image.source = str(bg.path)
        else:
            assert bg.data is not None
            self.bg_image.source = ""  # or kivy would reload the old file over the texture
            self.bg_image.texture = CoreImage(io.BytesIO(bg.data), ext=bg.ext.lstrip(".")).texture

    def show_page(self, path: Path, *, scroll_y: float = 1.0) -> None:
        """Open ``path`` as the current page, pushing it onto the back history.

        The public equivalent of following a link: the outgoing page's scroll
        position is remembered, Back returns to it, and the tree panel syncs
        itself to the new page. Re-showing the page already on display
        refreshes it without growing the history.

        Args:
            path: Absolute path of the bundle page (.md) to show.
            scroll_y: Normalized scroll offset to open at (1.0 = top).

        """
        self._show(path, push=True, scroll_y=scroll_y)

    def _push_history(self, path: Path) -> None:
        """Append ``path`` to the back history, unless it is already on top.

        Re-showing the page already on display (a self-link, a double-clicked
        link, the home icon pressed on the home page, a search hit for the
        current page) must not grow the stack: the duplicate would turn a
        later Back press into a visible no-op.
        """
        if self.history and self.history[-1].path.resolve() == path.resolve():
            return
        if self.history:  # remember where the outgoing page was scrolled to
            self.history[-1].scroll_y = self.body_scroll.scroll_y
        self.history.append(_HistoryEntry(path))

    def _show(self, path: Path, *, push: bool, scroll_y: float = 1.0) -> None:
        if push:
            self._push_history(path)
        # At the root the button stays live when Back exits the reader (on_exit set),
        # so clicking it leaves — a unified back stack. Standalone (no on_exit) keeps
        # it disabled at the root.
        self.back_btn.disabled = len(self.history) <= 1 and self._on_exit is None
        self._tree_panel.sync_to(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as err:
            # Tolerant consumption (SPEC §9): a page deleted or made unreadable
            # after the tree was populated (e.g. the wiki being regenerated)
            # degrades to an error page instead of crashing the event handler.
            text = f"# Page unavailable\n\n`{path.name}`: {err.strerror or err}\n"
        page = render_page(
            text,
            table_rewriter=self._table_rewriter,
            heading_color=self._theme.heading_hex,
            link_color=self._theme.link_hex,
        )
        self._update_background(page.frontmatter, path)
        self._bar.set_page_action(
            self._action_provider.action_for(page.frontmatter, path)
            if self._action_provider is not None
            else None
        )
        self.body.clear_widgets()
        self._band_colors.clear()  # their sections were just discarded
        self._links.start_page()  # ditto their link labels, and the focus on one
        self._anchors = {}
        # Blocks group into banded sections: each heading starts a new section
        # box holding it and everything up to the next heading (see BLOCK_BG_COLOR).
        section: BoxLayout | None = None
        for blk in page.blocks:
            if isinstance(blk, TableBlock):
                if section is None:
                    section = self._new_section()
                section.add_widget(self._table_widget(blk, path))
                continue
            lbl = self._body_label(blk, path)
            if blk.anchor:
                self._anchors[blk.anchor] = blk.markup
            if section is None or blk.heading:
                section = self._new_section()
            section.add_widget(self._hanging_row(lbl, blk) if blk.indent else lbl)
        self._links.page_built()
        # Fresh pages open at the top; Back passes the offset the page was left at.
        self.body_scroll.scroll_y = scroll_y
        if scroll_y != 1:
            # The labels take their texture sizes over the next frame, shifting the
            # normalized offset; re-assert it once the layout has settled.
            Clock.schedule_once(lambda _dt: setattr(self.body_scroll, "scroll_y", scroll_y), 0)
        # Keep the results list's highlight on the page now showing, however reached.
        self._active_result_path = path
        self._highlight_active_result()
        # A click-navigation swaps the page under a stationary mouse; re-evaluate
        # the cursor once the new labels' textures have settled.
        Clock.schedule_once(lambda _dt: self._links.refresh_cursor(), 0)
        trace.page_shown(self.bundle, path, len(self.history))

    def _new_section(self) -> BoxLayout:
        """Append and return a fresh banded section box for the next run of blocks."""
        box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=SECTION_BLOCK_SPACING,
            padding=SECTION_PADDING,
        )
        box.bind(minimum_height=box.setter("height"))
        self._band_colors.append(add_text_backing(box, self._band_alpha()))
        self.body.add_widget(box)
        return box

    def _body_label(self, blk: Block, path: Path) -> PageLabel:
        """Build one body block's self-sizing, ref-navigable Label."""
        lbl = PageLabel(
            path,
            text=blk.markup,
            markup=True,
            font_size=blk.font_size,
            line_height=BODY_LINE_HEIGHT,
            halign="left",
            valign="top",
            size_hint_y=None,
        )
        lbl.bind(width=lambda inst, w: inst.setter("text_size")(inst, (w, None)))
        lbl.bind(texture_size=lambda inst, ts: inst.setter("height")(inst, ts[1]))
        lbl.bind(on_ref_press=self._on_ref)
        if "[ref=" in blk.markup:
            self._links.labels.append(lbl)
        return lbl

    @staticmethod
    def _hanging_row(lbl: Label, blk: Block) -> BoxLayout:
        """Wrap a list-item/blockquote label in a hanging-indent row.

        The marker glyph sits right-aligned in its own fixed column, so ``lbl``'s
        wrapped lines align under the item's text instead of returning to the
        margin (see LIST_MARKER_WIDTH). A continuation paragraph or blockquote
        carries an empty marker and just gets the alignment. The row and marker
        track the text label's height, which the layout resolves after this
        returns — hence the bind rather than a one-off read.
        """
        row = BoxLayout(size_hint_y=None, spacing=dp(LIST_MARKER_GAP))
        if blk.indent > 1:
            step = dp((blk.indent - 1) * LIST_INDENT_STEP)
            row.add_widget(Widget(size_hint=(None, None), width=step, height=1))
        marker = Label(
            text=blk.marker,
            markup=True,
            font_size=blk.font_size,
            line_height=BODY_LINE_HEIGHT,
            halign="right",
            valign="top",
            size_hint=(None, None),
            width=dp(LIST_MARKER_WIDTH),
        )
        marker.bind(size=lambda inst, size: inst.setter("text_size")(inst, size))
        row.add_widget(marker)
        row.add_widget(lbl)

        def sync_height(_lbl: Label, height: float) -> None:
            row.height = height
            marker.height = height

        lbl.bind(height=sync_height)
        return row

    def _band_alpha(self) -> float:
        """Return the section-band alpha the Contrast toggle currently calls for."""
        if self.contrast_btn.state == "down":
            return BLOCK_BG_CONTRAST_ALPHA
        return BLOCK_BG_COLOR[3]

    def _pane_scrim_alpha(self) -> float:
        """Return the reading-pane scrim alpha the Contrast toggle currently calls for."""
        if self.contrast_btn.state == "down":
            return READING_PANE_SCRIM_CONTRAST_ALPHA
        return READING_PANE_SCRIM[3]

    def _add_scrims(self) -> None:
        """Draw the scrims over the background art: the reading pane's and the sides'."""
        self._add_reading_pane_scrim()
        self._add_side_scrims()

    def _add_reading_pane_scrim(self) -> None:
        """Draw the continuous scrim behind the reading column (see READING_PANE_SCRIM).

        Spans the body column's width and the whole reading pane's height under the
        per-section bands, so the inter-section gaps, the column padding and the
        pane below a short page keep a legibility floor over a vivid background
        panel (sized to the body, the scrim ended with a short page and the art
        showed below it, 2026-10-30). Drawn on the pane, not the body, so it stays
        put while the body scrolls; the pane keeps its content at the origin and
        draws it through a translation, so the body's x is an offset in the pane.
        Its Color is kept so the Contrast toggle can dial it up alongside the bands
        (see _apply_band_alpha).
        """
        with self.body_scroll.canvas.before:
            self._pane_scrim_color = Color(rgba=(*READING_PANE_SCRIM[:3], self._pane_scrim_alpha()))
            self._pane_scrim_rect = Rectangle()

        def fit_scrim(*_args: object) -> None:
            pane = self.body_scroll
            self._pane_scrim_rect.pos = (pane.x + self.body.x, pane.y)
            self._pane_scrim_rect.size = (self.body.width, pane.height)

        self.body.bind(x=fit_scrim, width=fit_scrim)
        self.body_scroll.bind(pos=fit_scrim, size=fit_scrim)
        fit_scrim()

    def _add_side_scrims(self) -> None:
        """Draw SIDE_SCRIM over the art left of the sidebar and right of the column.

        On the content row's canvas, under both panels, from the row's foot to its
        top: the top bar is left as it is. The left strip ends at the sidebar, the
        right one starts at the reading column's edge, which on a wide pane is short
        of the pane's own (the column is capped and held against the sidebar).
        """
        with self._content.canvas.before:
            Color(rgba=SIDE_SCRIM)
            self._left_side_scrim = Rectangle()
            self._right_side_scrim = Rectangle()

        def fit_side_scrims(*_args: object) -> None:
            row = self._content
            sidebar_x = self._left_column.x
            self._left_side_scrim.pos = (row.x, row.y)
            self._left_side_scrim.size = (max(0.0, sidebar_x - row.x), row.height)
            column_end = self.body_scroll.x + self.body.x + self.body.width
            self._right_side_scrim.pos = (column_end, row.y)
            self._right_side_scrim.size = (max(0.0, row.x + row.width - column_end), row.height)

        self._content.bind(pos=fit_side_scrims, size=fit_side_scrims)
        self._left_column.bind(x=fit_side_scrims)
        self.body.bind(x=fit_side_scrims, width=fit_side_scrims)
        self.body_scroll.bind(x=fit_side_scrims)
        fit_side_scrims()

    def set_contrast(self, on: bool) -> None:
        """Set the Contrast toggle, as a press on it would: a darker article panel when on."""
        self.contrast_btn.state = "down" if on else "normal"

    def _on_contrast_state(self, _button: Widget, state: str) -> None:
        self._apply_band_alpha()
        trace.contrast(on=state == "down")

    def _apply_band_alpha(self) -> None:
        """Retune the page's section bands and the reading pane's scrim to the toggle."""
        alpha = self._band_alpha()
        for color in self._band_colors:
            color.a = alpha
        self._pane_scrim_color.a = self._pane_scrim_alpha()

    def _table_widget(self, blk: TableBlock, path: Path) -> ScrollView:
        """Build the widget for a table: monospace rows, tightly stacked, one per Label.

        One Label per row (not one for the whole table) keeps each texture small —
        a several-hundred-row table in a single Label would exceed the GPU texture
        size limit. Each label takes its natural (texture) size so the columns'
        space padding is preserved, and the stack sits in its own horizontal
        ScrollView so a wide table scrolls instead of clipping. Cells can carry
        links (the core's ``_inline`` renders them like any other), so rows join
        the same ref-press and hover machinery as body labels.

        A long table with no links is a LazyTable instead: Labels only for the rows
        near the viewport (see LAZY_TABLE_MIN_ROWS).
        """
        if len(blk.rows) >= LAZY_TABLE_MIN_ROWS and not any("[ref=" in r for r in blk.rows):
            return self._table_scroller(LazyTable(blk.rows, blk.font_size, self.body_scroll))
        stack = BoxLayout(orientation="vertical", size_hint=(None, None))
        stack.bind(
            minimum_height=stack.setter("height"),
            minimum_width=stack.setter("width"),
        )
        for row in blk.rows:
            lbl = PageLabel(
                path,
                text=row,
                markup=True,
                font_name=TABLE_FONT_NAME,
                font_size=blk.font_size,
                size_hint=(None, None),
            )
            lbl.bind(texture_size=lbl.setter("size"))
            lbl.bind(on_ref_press=self._on_ref)
            if "[ref=" in row:
                self._links.labels.append(lbl)
            stack.add_widget(lbl)
        return self._table_scroller(stack)

    def _table_scroller(self, table: Widget) -> ScrollView:
        """Put a table's rows in a horizontal ScrollView, so a wide table scrolls."""
        scroller = scroll_view(self._theme, size_hint=(1, None), do_scroll_y=False, height=0)

        def fit_height(*_args: object) -> None:
            # Kivy draws the horizontal bar inside the ScrollView's bounds, so when
            # the table overflows, reserve room below the rows — otherwise the bar
            # covers the last row. (The bar is only drawn when the table overflows,
            # so fitting tables get no dead strip.)
            overflows = table.width > scroller.width
            scroller.height = table.height + (
                scroller.bar_width + TABLE_BAR_GAP if overflows else 0
            )

        table.bind(height=fit_height, width=fit_height)
        scroller.bind(width=fit_height)
        scroller.add_widget(table)
        fit_height()
        return scroller

    def _on_ref(self, label: PageLabel, ref: str) -> None:
        if ref.startswith("fn:"):
            markup = self._anchors.get(ref)  # tapped [id] → its definition, in a popup
            if markup is not None:
                self._show_footnote_popup(markup, label.page_path)
                trace.footnote_opened(ref)
            return
        target = resolve_link(label.page_path, ref, self.bundle)
        if target:
            self._show(target, push=True)

    def _show_footnote_popup(self, markup: str, page_path: Path) -> None:
        """Show a footnote definition in a tap-anywhere-to-dismiss popup bubble."""
        popup = ModalView(size_hint=(0.75, None), height=100, auto_dismiss=True)
        lbl = Label(
            text=markup,
            markup=True,
            line_height=BODY_LINE_HEIGHT,
            halign="left",
            valign="middle",
            padding=(POPUP_PADDING, POPUP_PADDING),
        )
        lbl.bind(width=lambda inst, w: inst.setter("text_size")(inst, (w, None)))
        # The popup wraps its height to the rendered footnote text.
        lbl.bind(texture_size=lambda _inst, ts: popup.setter("height")(popup, ts[1]))

        def _follow_link(_lbl: Label, ref: str) -> None:
            popup.dismiss()  # a link inside the footnote navigates like any page link
            target = resolve_link(page_path, ref, self.bundle)
            if target:
                self._show(target, push=True)

        lbl.bind(on_ref_press=_follow_link)
        popup.add_widget(lbl)
        # While the popup is up it is modal, so it owns link hover exclusively;
        # dismissing hands hover back to the page (and rechecks the cursor, since
        # dismissal itself moves no mouse). It also owns the keyboard — tracked
        # so handle_key can dismiss it on Escape/Enter (the hosting app consumes
        # window key events, so the ModalView's own Escape handling never fires).
        self._links.popup_label = lbl
        self._footnote_popup = popup

        def _release_hover(_popup: ModalView) -> None:
            self._links.popup_label = None
            self._footnote_popup = None
            self._links.refresh_cursor()
            trace.footnote_closed()

        popup.bind(on_dismiss=_release_hover)
        popup.open()


class OKFApp(App):
    def __init__(
        self,
        bundle: Path,
        image_provider: ImageProvider | None = None,
        table_rewriter: TableRewriter | None = None,
        start_page: Path | None = None,
        action_provider: PageActionProvider | None = None,
        top_bar: TopBarSpec | None = None,
        state_path: Path | None = None,
        search_provider: SearchProvider | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._bundle = bundle
        self._image_provider = image_provider
        self._table_rewriter = table_rewriter
        self._start_page = start_page
        self._action_provider = action_provider
        self._top_bar = top_bar
        self._state_path = state_path
        self._search_provider = search_provider
        self._viewer: OKFViewer | None = None

    def build(self) -> OKFViewer:
        self.title = f"OKF Reader — {self._bundle.name}"
        self._viewer = OKFViewer(
            self._bundle,
            image_provider=self._image_provider,
            table_rewriter=self._table_rewriter,
            start_page=self._start_page,
            action_provider=self._action_provider,
            top_bar=self._top_bar,
            state_path=self._state_path,
            search_provider=self._search_provider,
        )
        return self._viewer

    def on_start(self) -> None:
        """Replace the OS window titlebar with the viewer's action bar.

        The Barks Reader convention (BarksReaderApp._set_custom_title_bar):
        only the bar's title area becomes the drag region, so the icon and
        buttons stay clickable. Kivy needs the realized window, hence on_start;
        where the system disallows it, the OS titlebar simply stays.

        Also binds the window's back gestures — app-level, not viewer-level,
        because an embedding app owns its own key routing.
        """
        from kivy.core.window import Window  # noqa: PLC0415 — needs the realized window

        assert self._viewer is not None
        Window.bind(on_keyboard=self._on_keyboard)
        Window.custom_titlebar = True
        if not Window.set_custom_titlebar(self._viewer.bar_drag_region):
            print("warning: custom titlebar not allowed on this system")  # noqa: T201

    def on_stop(self) -> None:
        """Remember the page (and scroll) being read, for the next launch."""
        if self._viewer is not None:
            self._viewer.save_session()

    def _on_keyboard(
        self,
        _window: object,
        key: int,
        _scancode: int,
        _codepoint: str | None,
        modifiers: list[str],
    ) -> bool:
        """Ctrl+F focuses search; Alt+Left navigates back; the viewer owns the rest.

        Everything else defers to the viewer's own keyboard navigation
        (``OKFViewer.handle_key``): page scrolling, link traversal, the
        sidebar, and Escape — which unwinds an active search, else toggles the
        keyboard focus up to the action bar (where Enter on the Back button
        goes back) — so the standalone reader navigates exactly like the
        embedded one. Escape is always consumed: kivy's default would close the
        window, and an accidental Escape must not kill the reader (the same
        overshoot hazard the Quit button was moved to the corner for). While
        the search field owns the keyboard the viewer refuses every key, so
        Escape backs out of the typed search here instead, and Alt+Left is not
        stolen, so it can move the cursor within the query.
        """
        assert self._viewer is not None
        if key == KEY_F and "ctrl" in modifiers:
            self._viewer.focus_search()
            return True
        if self._viewer.handle_key(key, set(modifiers)):
            return True
        return self._handle_back_key(key, modifiers)

    def _handle_back_key(self, key: int, modifiers: list[str]) -> bool:
        """Handle the keys the viewer's handle_key refused.

        Alt+Left goes back; Escape arrives here only while the search field
        owns the keyboard, and backs out of the typed query.
        """
        assert self._viewer is not None
        if key == KEY_ESCAPE:
            # Reached only while the search field owns the keyboard (the viewer
            # consumes Escape otherwise); still always consumed — see above.
            self._viewer.escape_search()
            return True
        if key == KEY_LEFT and "alt" in modifiers:
            if self._viewer.search_focused:
                return False
            self._viewer.go_back()
            return True
        return False


def run(
    bundle: Path,
    image_provider: ImageProvider | None = None,
    table_rewriter: TableRewriter | None = None,
    start_page: Path | None = None,
    action_provider: PageActionProvider | None = None,
    top_bar: TopBarSpec | None = None,
    state_path: Path | None = None,
    search_provider: SearchProvider | None = None,
) -> None:
    """Launch the standalone OKF reader on ``bundle`` (blocks until the window closes)."""
    OKFApp(
        bundle,
        image_provider=image_provider,
        table_rewriter=table_rewriter,
        start_page=start_page,
        action_provider=action_provider,
        top_bar=top_bar,
        state_path=state_path,
        search_provider=search_provider,
    ).run()
