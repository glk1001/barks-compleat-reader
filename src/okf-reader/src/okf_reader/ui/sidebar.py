"""The viewer's left column: a search box over the contents tree, or over what it found.

Typing in the box swaps the tree for the results and clearing it brings the tree back.
The index behind the search is built off the UI thread the first time the box is
focused. The viewer says what opening a page does and where the keys go on leaving.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

from okf_reader.core.search import BundleSearcher
from okf_reader.ui import trace

from .focus_ring import clear_focus_ring, draw_focus_ring
from .keynav import (
    KEY_DOWN,
    KEY_END,
    KEY_ENTER,
    KEY_HOME,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_UP,
    NAV_NOOP_KEYS,
    step_index,
)
from .tree_panel import TREE_PANEL_FONT_SIZE
from .widgets import FlatButton, result_markup, scroll_view

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from kivy.uix.scrollview import ScrollView
    from kivy.uix.widget import Widget

    from okf_reader.core.search import SearchHit, SearchProvider
    from okf_reader.core.theme import ViewerThemeSpec

    from .tree_panel import TreePanel


# The column's share of the window's width; the page panel gets the rest.
TREE_PANEL_WIDTH = 0.22
# Translucent black drawn over the background image behind the whole sidebar
# column (the search field and the tree), giving the tree text and the
# search-field seam a legibility floor over a vivid background panel. Near-black,
# so a page with no background image is unchanged (black over the plain window).
# Fixed, the Contrast toggle leaving it be: the sidebar always shows some of the
# background, and the toggle governs the article panel alone (2026-10-31).
SIDEBAR_SCRIM = (0, 0, 0, 0.79)
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


class Sidebar:
    """The search box over the tree-or-results slot, and the keys in both."""

    def __init__(
        self,
        bundle: Path,
        theme: ViewerThemeSpec,
        tree_panel: TreePanel,
        search_provider: SearchProvider | None,
        *,
        on_open_page: Callable[[Path], None],
        on_cross_to_page: Callable[[], None],
        on_leave_field: Callable[[], None],
    ) -> None:
        """Build the column round `tree_panel`'s tree; `widget` is the column to lay out.

        Args:
            bundle: The bundle's folder, which the built-in searcher indexes.
            theme: The colors the embedding app themes the column with.
            tree_panel: The contents tree, shown while nothing is searched for.
            search_provider: The embedding app's search backend, or None for the built-in.
            on_open_page: Shows the page of a picked result.
            on_cross_to_page: Hands the keys to the page panel.
            on_leave_field: Hands the keys to this column, on leaving the search box.

        """
        self._theme = theme
        self._tree_panel = tree_panel
        self._on_open_page = on_open_page
        self._on_cross_to_page = on_cross_to_page
        self._on_leave_field = on_leave_field
        # Title, heading and text search over the bundle. The built-in searcher
        # needs no app knowledge (unlike the image/table/action providers) and
        # builds its index lazily on the first query, so defaulting it here costs
        # nothing up front; an embedding app may inject a different backend.
        self.searcher: SearchProvider = search_provider or BundleSearcher(bundle)
        # Building the index walks the whole bundle, so it is warmed off the UI
        # thread (see `warm`), by the field's first focus or by the host sooner;
        # until it is ready a query shows a "Searching…" note rather than
        # freezing the field.
        # `failed` is set if the off-thread index build raised: search is
        # "ready" (the field stops waiting) but disabled, showing an error note
        # instead of hanging on "Searching…". It guards every search() call, since
        # a failed BundleSearcher would re-raise the build on the UI thread if
        # queried again.
        self.ready = self.failed = False
        self.warming = False
        self.index: int | None = None  # the result row wearing the focus ring
        self.results_scroll: ScrollView | None = None
        self.widget = self._build()

    def _build(self) -> BoxLayout:
        """Build the left column: a search field over the tree/results body slot.

        The search field swaps the body slot between ``tree_scroll`` (default)
        and the results list as its text changes (see `_on_search_text`). Assumes
        ``self._tree_panel.scroll`` is already built.
        """
        # Results stay up after a hit is opened (open several in a row); the open
        # page's row is highlighted, cleared to the tree via the clear button / Escape.
        self.result_rows: list[tuple[Path, Button]] = []
        self.active_result_path: Path | None = None
        left = BoxLayout(
            orientation="vertical",
            size_hint=(TREE_PANEL_WIDTH, 1),
            spacing=dp(SEARCH_FIELD_GAP),
        )
        # Scrim over the background image behind the whole sidebar column
        # (canvas.before renders under the column's widgets), kept glued to it, so
        # the tree text and the search-field seam keep a legibility floor over a
        # vivid background panel.
        # pyrefly: ignore[missing-attribute]  # Kivy sets `canvas` in Widget.__init__.
        with left.canvas.before:  # ty: ignore[missing-union-attribute]
            self.scrim_color = Color(rgba=SIDEBAR_SCRIM)
            sidebar_scrim = Rectangle(pos=left.pos, size=left.size)
        left.bind(
            pos=lambda _inst, pos: setattr(sidebar_scrim, "pos", pos),
            size=lambda _inst, size: setattr(sidebar_scrim, "size", size),
        )
        self.field = TextInput(
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
        self.field.bind(
            text=self._on_text,
            on_text_validate=self._on_enter,
            focus=self._on_focus,
        )
        # pyrefly: ignore[missing-attribute]  # Kivy sets `canvas` in Widget.__init__.
        with self.field.canvas.after:  # ty: ignore[missing-union-attribute]
            Color(rgba=SEARCH_FIELD_BORDER)
            field_border = Line(width=SEARCH_FIELD_BORDER_WIDTH, close=True)

        def fit_border(field: Widget, _value: object) -> None:
            x, y, w, h = (*field.pos, *field.size)
            field_border.points = [x, y, x + w, y, x + w, y + h, x, y + h]

        self.field.bind(pos=fit_border, size=fit_border)
        # The field spans the sidebar, and a "clear" button over its right end shows
        # only while there is text — a one-tap return to the tree when done searching.
        # Hidden, it has no width: a disabled widget still swallows the touches it
        # covers, which would leave that end of the field dead to a click.
        search_row = FloatLayout(size_hint_y=None, height=dp(SEARCH_FIELD_HEIGHT))
        search_row.add_widget(self.field)
        self.clear_btn = FlatButton(
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
        self.clear_btn.bind(on_release=lambda *_: self.clear())
        search_row.add_widget(self.clear_btn)
        left.add_widget(search_row)
        self.body = BoxLayout(size_hint=(1, 1))
        self.body.add_widget(self._tree_panel.scroll)
        left.add_widget(self.body)
        return left

    def _on_focus(self, _field: TextInput, focused: bool) -> None:
        """On the field's first focus, warm the search index (`warm_search`).

        Starting it on focus (before the user has typed) keeps the field
        responsive and usually has results ready by the first keystroke, where the
        host has not started it already.

        Every focus is logged here, however it came - a key (`focus_search`) or a
        tap - so a test can wait for the field to take the keyboard before typing.
        """
        if focused:
            trace.search_focused()
            self.warm()

    def warm(self) -> None:
        """Start building the search index off the UI thread, once.

        The build walks the whole bundle. The field's first focus starts it; a host
        that opens the reader for the user can start it then instead, so a query
        typed soon after finds the index ready (the Barks Reader does, as on a
        Windows VM the build took over 5 s). A provider without a ``warm`` method
        is assumed to manage its own readiness, so it is marked ready at once.
        Later calls do nothing.
        """
        if self.warming:
            return
        self.warming = True
        warm = getattr(self.searcher, "warm", None)
        if warm is None:
            self.ready = True
            return
        threading.Thread(target=self._warm_index, args=(warm,), daemon=True).start()

    def _warm_index(self, warm: Callable[[], None]) -> None:
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
            Clock.schedule_once(lambda _dt: self.mark_ready(failed=True), 0)
            return
        trace.search_index_built(time.perf_counter() - start)
        Clock.schedule_once(lambda _dt: self.mark_ready(failed=False), 0)

    def mark_ready(self, *, failed: bool) -> None:
        """Mark the index ready (or failed) and refresh any query typed while warming."""
        trace.search_ready(failed=failed, text=self.field.text)
        self.ready = True
        self.failed = failed
        if self.field.text.strip():
            if failed:
                self._show_error()
            else:
                text = self.field.text
                self.show_results(self.searcher.search(text), text)

    def _on_text(self, _field: TextInput, text: str) -> None:
        """Swap the left column between the tree, a wait note, the results, or an error."""
        has_text = bool(text)
        self.clear_btn.opacity = 1 if has_text else 0
        self.clear_btn.disabled = not has_text
        self.clear_btn.width = dp(SEARCH_CLEAR_BTN_WIDTH) if has_text else 0
        if not text.strip():
            self.show_tree()
        elif not self.ready:
            self._show_searching()
        elif self.failed:
            self._show_error()
        else:
            self.show_results(self.searcher.search(text), text)

    def clear(self) -> None:
        """Clear the search field, restoring the tree (the clear button / done searching)."""
        self.field.text = ""
        self.field.focus = False
        trace.search_cleared()

    def _on_enter(self, _field: TextInput) -> None:
        """Open the top hit when the search field is submitted (Enter), once ready."""
        if not self.ready or self.failed:
            return
        hits = self.searcher.search(self.field.text)
        if hits:
            self.open_hit(hits[0])

    @property
    def shows_tree(self) -> bool:
        """Whether the tree, and not a search's results or a note, fills the slot."""
        return self._tree_panel.scroll.parent is self.body

    def show_tree(self) -> None:
        """Restore the tree to the left column's body slot (empty/cleared search)."""
        if not self.shows_tree:
            self.result_rows = []
            self.index = None  # the ringed row is being discarded
            self.results_scroll = None
            self.body.clear_widgets()
            self.body.add_widget(self._tree_panel.scroll)
            # Reveal the current page's node, which was kept selected while the
            # results hid the tree (its scroll offset can go stale while hidden).
            if self._tree_panel.tree.selected_node is not None:
                Clock.schedule_once(
                    lambda _dt: self._tree_panel.scroll_node_into_view(
                        self._tree_panel.tree.selected_node
                    ),
                    0,
                )

    def _show_searching(self) -> None:
        """Show a wait note while the index warms (first query before it is ready)."""
        self.index = None
        self.body.clear_widgets()
        self.body.add_widget(
            Label(
                text="Searching…", color=self._theme.secondary_text, valign="top", halign="center"
            )
        )

    def _show_error(self) -> None:
        """Show an error note when the index build failed (search stays disabled)."""
        self.index = None
        self.body.clear_widgets()
        self.body.add_widget(
            Label(
                text=SEARCH_ERROR_TEXT,
                color=self._theme.secondary_text,
                valign="top",
                halign="center",
            )
        )

    def show_results(self, hits: list[SearchHit], text: str) -> None:
        """Put the results list for query `text` in the left column, replacing the tree."""
        self.index = None  # rows are rebuilt; any ringed row is discarded
        self.body.clear_widgets()
        self.body.add_widget(self._results_widget(hits))
        trace.search_results(len(hits), text)

    def _results_widget(self, hits: list[SearchHit]) -> ScrollView:
        """Build the scrollable results list — one row per hit, or a no-match note."""
        scroll = scroll_view(self._theme, size_hint=(1, 1), do_scroll_x=False)
        column = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(2), padding=(0, dp(2))
        )
        column.bind(minimum_height=column.setter("height"))
        self.result_rows = []
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
            self.result_rows.append((hit.path, btn))
            column.add_widget(btn)
        scroll.add_widget(column)
        self.results_scroll = scroll  # keyboard nav scrolls the focused row into view
        self.highlight_active_result()  # mark the open page if it is in this list
        return scroll

    def highlight_active_result(self) -> None:
        """Tint the open page's result row (a no-op when no results are showing)."""
        for path, btn in self.result_rows:
            active = path == self.active_result_path
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
        btn.bind(on_release=lambda *_: self.open_hit(hit))
        return btn

    def open_hit(self, hit: SearchHit) -> None:
        """Open a picked result, keeping the results list up to open several in a row.

        The field only loses focus (so page keys work); the results stay so the
        next hit is one tap away, with the opened row highlighted (via ``_show``).
        The tree stays synced underneath, so clearing the search (the clear button
        or Escape) returns to it on the last page viewed.
        """
        self.field.focus = False
        self._on_open_page(hit.path)

    @property
    def field_focused(self) -> bool:
        """Whether the search field currently owns the keyboard.

        The hosting app checks this so that while the user is typing a search,
        keystrokes reach the field instead of driving navigation (e.g. a
        configurable alternate-Escape key that is an ordinary letter).
        """
        return bool(self.field.focus)

    def focus_field(self) -> None:
        """Focus the search field: Ctrl+F from the host, or Up off the sidebar's top."""
        self.clear_result_focus()
        self.field.focus = True  # logged by _on_search_focus

    def leave_field(self) -> None:
        """Leave the search field for the sidebar: its results if any, else the tree."""
        self.field.focus = False
        self._on_leave_field()
        trace.search_left()

    def escape(self) -> bool:
        """Clear and unfocus the search field if active; report whether it consumed Escape.

        The hosting app calls this before its Back handling, so Escape backs out
        of an active search first and only navigates back once search is idle.
        """
        if self.field.text or self.field.focus:
            self.field.text = ""
            self.field.focus = False
            trace.search_cleared()
            return True
        return False

    def handle_field_key(self, key: int) -> bool:
        """While the field types: Down leaves it for the sidebar; it keeps every other key.

        Down is the remote's way out (Enter opens the top hit; Escape, the host's,
        clears the search).
        """
        if key == KEY_DOWN:
            self.leave_field()
            return True
        return False

    def handle_key(self, key: int) -> bool:
        """Drive the contents tree, or the search-result rows while results show."""
        if self.result_rows:
            return self._handle_results_key(key)
        if self.shows_tree:
            return self._tree_panel.handle_key(key)
        # "Searching…" / search-error / no-match states: nothing to navigate —
        # Right still crosses to the page panel, and the rest of the keys must
        # not leak to the host while the sidebar owns them.
        if key == KEY_RIGHT:
            self._on_cross_to_page()
            return True
        return key in NAV_NOOP_KEYS or key in (KEY_ENTER, KEY_NUMPAD_ENTER)

    def _handle_results_key(self, key: int) -> bool:
        """Walk the search-result rows with a drawn focus ring."""
        count = len(self.result_rows)
        if key == KEY_UP and self.index == 0:
            self.focus_field()  # back up into the box the results came from
            return True
        if key in (KEY_UP, KEY_DOWN, KEY_HOME, KEY_END):
            if key == KEY_HOME:
                idx = 0
            elif key == KEY_END:
                idx = count - 1
            elif self.index is None:
                idx = self.initial_result_index()
            else:
                idx = step_index(self.index, count, 1 if key == KEY_DOWN else -1)
            self.set_result_focus(idx)
            return True
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            if self.index is not None:
                self.result_rows[self.index][1].trigger_action(duration=0)
            return True
        if key == KEY_RIGHT:
            self._on_cross_to_page()
            return True
        return key == KEY_LEFT

    def initial_result_index(self) -> int:
        """Return the row to focus first: the open page's row when listed, else the top hit."""
        for i, (path, _btn) in enumerate(self.result_rows):
            if path == self.active_result_path:
                return i
        return 0

    def set_result_focus(self, idx: int) -> None:
        """Move the gold ring to result row ``idx``, scrolling it into view."""
        self.clear_result_focus()
        self.index = idx
        btn = self.result_rows[idx][1]
        draw_focus_ring(btn)
        scroll = self.results_scroll
        if scroll is not None and scroll.children and scroll.children[0].height > scroll.height:
            scroll.scroll_to(btn, padding=8)  # scroll_to applies dp() itself

    def clear_result_focus(self) -> None:
        if self.index is not None and self.index < len(self.result_rows):
            clear_focus_ring(self.result_rows[self.index][1])
        self.index = None
