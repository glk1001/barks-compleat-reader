"""Kivy viewer for an OKF bundle — the UI layer of okf_reader.

Binds the Kivy-free core (okf_reader.core.render) to native widgets: a lazily
populated tree of the bundle's tiers on the left, the rendered page on the right.
Links resolve via the core's ``resolve_link``; tapping a footnote marker shows its
definition (keyed by the page `Block`'s anchor) in a dismiss-on-tap popup.
``run(bundle)`` launches the standalone app; the CLI entry point is
scripts/read_okf.py.
"""

from __future__ import annotations

import io
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.effects.scroll import ScrollEffect
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.actionbar import ActionButton, ActionToggleButton
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.treeview import TreeView, TreeViewLabel
from kivy.uix.widget import Widget

from okf_reader.core.render import (
    LINK_COLOR,
    Block,
    BundleDir,
    TableBlock,
    TableRewriter,
    has_children,
    list_children,
    render_page,
    resolve_link,
)
from okf_reader.core.search import BundleSearcher
from okf_reader.core.session import load_session_state, save_session_state
from okf_reader.core.theme import ViewerThemeSpec
from okf_reader.core.top_bar import TopBarSpec

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
    KEY_PAGE_DOWN,
    KEY_PAGE_UP,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
    LINK_FOCUS_COLOR,
    PAGE_LINE_STEP,
    PAGE_STEP_OVERLAP,
    FocusRegion,
    enumerate_refs,
    highlight_ref_occurrence,
    hybrid_link_step,
    scroll_step,
    step_index,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

    from okf_reader.core.actions import PageAction, PageActionProvider
    from okf_reader.core.backgrounds import ImageProvider
    from okf_reader.core.search import SearchHit, SearchProvider

BODY_LINE_HEIGHT = 1.25
# Tables come from the core space-padded to aligned columns (see TableBlock), which
# only lines up in a monospace face. RobotoMono ships with Kivy (regular only —
# another reason table headers are colored, not bold).
TABLE_FONT_NAME = "RobotoMono-Regular"
# Space between a table's last row and its horizontal scrollbar (see _table_widget).
TABLE_BAR_GAP = dp(4)
BODY_PADDING = (16, 8, 24, 16)  # left, top, right, bottom
BODY_BLOCK_SPACING = 12
POPUP_PADDING = 12
TREE_PANEL_WIDTH = 0.25  # fraction of the window; the page panel gets the rest
# Multiplied into the background image (Kivy Image.color) so white text stays
# readable over it — the same darkening mechanism the Barks Reader's kv files use.
WINDOW_BG_TINT = (0.30, 0.30, 0.30, 1)
# Translucent black drawn over the background image behind the whole sidebar
# column (the search field and the tree), giving the tree text and the
# search-field seam a legibility floor over a vivid background panel. Near-black,
# so a page with no background image is unchanged (black over the plain window).
SIDEBAR_SCRIM = (0, 0, 0, 0.30)
# Translucent rounded band drawn behind each page *section* (a heading plus
# everything under it, up to the next heading) so body text keeps its contrast
# over vivid background panels — the Barks Reader's BgColorLabel idiom
# (main_screen.kv <BackgroundColor@Widget>), in Python. The alpha is the
# delineation-strength knob.
BLOCK_BG_COLOR = (0.01, 0.01, 0.01, 0.30)
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
READING_PANE_SCRIM = (0.0, 0.0, 0.0, 0.20)
READING_PANE_SCRIM_CONTRAST_ALPHA = 0.85
BLOCK_BG_RADIUS = 6  # dp
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
# Cap on the reading column: past this the body column stops growing and
# centers in its pane, keeping the measure comfortable (~90 characters at the
# body size) on maximized windows. Wide tables scroll within it.
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
SEARCH_RESULT_HEIGHT = 48  # dp — two lines: title over a dim breadcrumb
SEARCH_ERROR_TEXT = "Search unavailable"  # shown if the index build failed
SEARCH_CLEAR_BTN_WIDTH = 28  # dp — the "clear search" button beside the field
SEARCH_FIELD_ROW_GAP = 4  # dp between the field and the clear button
SEARCH_CLEAR_GLYPH_SIZE = 22  # dp — big/bold enough to read in the small button
SEARCH_CLEAR_GLYPH_COLOR = (0.9, 0.9, 0.9, 1)  # light glyph on the dark (tinted) button
# The open page's result row gets the theme selection band (self._theme.selection):
# with the results kept up (to open several pages in a row) it shows which one you
# are reading. Inactive rows are transparent (unthemed).
SEARCH_RESULT_INACTIVE_COLOR = (0, 0, 0, 0)


class _IconToggleButton(ActionToggleButton):
    """An icon bar button that holds its down state, swapping icons with it.

    The kv ActionButton style supplies the fixed dp(48) icon-button width and
    the pressed background (the same rendering as the bar's Back/Quit buttons);
    the icon pair shows what pressing will do — ``on_icon`` while up, ``off_icon``
    while down.
    """

    def __init__(self, on_icon: str, off_icon: str, **kwargs) -> None:  # noqa: ANN003
        self._on_icon = on_icon
        self._off_icon = off_icon
        super().__init__(icon=on_icon, mipmap=True, **kwargs)

    def on_state(self, _widget: Widget, value: str) -> None:
        self.icon = self._off_icon if value == "down" else self._on_icon


def _tint_bar_icon(button: ActionButton, tint: tuple[float, float, float, float]) -> None:
    """Overlay a theme-tinted copy of an ActionButton's icon glyph.

    The kv ActionButton style renders ``icon`` as a plain white child Image with
    no color hook, so a light glyph cannot be recolored in place. We lay a
    tinted copy of the same glyph over it (matching the style's dp(4) inset and
    ``contain`` fit), tracking ``icon`` so an ``_IconToggleButton``'s state swap
    is followed. A white tint is a no-op — the standalone bar keeps its plain
    white glyphs.
    """
    if tuple(tint) == (1.0, 1.0, 1.0, 1.0):
        return
    overlay = Image(
        source=button.icon,
        color=list(tint),
        fit_mode="contain",
        mipmap=True,
        size_hint=(None, None),
    )

    def _sync(*_args) -> None:  # noqa: ANN002
        overlay.pos = (button.x + dp(4), button.y + dp(4))
        overlay.size = (button.width - dp(8), button.height - dp(8))

    button.bind(pos=_sync, size=_sync, icon=lambda _inst, value: setattr(overlay, "source", value))
    button.add_widget(overlay)
    _sync()


def _add_text_backing(widget, alpha: float) -> Color:  # noqa: ANN001
    """Draw the translucent rounded band behind ``widget`` (see BLOCK_BG_COLOR),
    kept glued through pos/size changes. Returns the band's Color instruction so
    the caller can retune its alpha later (the Contrast toggle).
    """  # noqa: D205
    with widget.canvas.before:
        color = Color(rgba=(*BLOCK_BG_COLOR[:3], alpha))
        rect = RoundedRectangle(radius=[dp(BLOCK_BG_RADIUS)])

    def sync(_widget, _value) -> None:  # noqa: ANN001
        rect.pos = widget.pos
        rect.size = widget.size

    widget.bind(pos=sync, size=sync)
    sync(widget, None)
    return color


def _markup_escape(text: str) -> str:
    """Escape the characters special to Kivy markup, for text shown in a markup label."""
    return text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def _ref_under(lbl: Label, wx: float, wy: float) -> str | None:
    """Return the ``[ref=…]`` anchor under window point ``(wx, wy)`` in ``lbl``, if any.

    Kivy fills ``Label.refs`` for any markup label with ref tags: anchor name ->
    bounding boxes in texture coordinates (origin the texture's top-left, y down).
    The texture itself always sits centered in the widget box (halign/valign act
    *within* the texture), which is what the widget-to-texture shift relies on.
    """
    px, py = lbl.to_widget(wx, wy)  # window -> widget coords
    if not lbl.collide_point(px, py):
        return None
    tx = px - (lbl.center_x - lbl.texture_size[0] / 2)
    ty = (lbl.center_y + lbl.texture_size[1] / 2) - py
    for name, boxes in lbl.refs.items():
        if any(x1 <= tx <= x2 and y1 <= ty <= y2 for x1, y1, x2, y2 in boxes):
            return name
    return None


class _FlatButton(ButtonBehavior, Label):
    """A clickable glyph with no button chrome.

    A plain Kivy Button paints a fixed light-gray image that ignores
    ``background_color`` (swallowing a light glyph); a Label draws only its text
    over a transparent background, so the caller controls the backing entirely.
    """


def _bar_separator(color: tuple[float, float, float, float], width_dp: float = 1) -> Widget:
    """Build a top-bar separator: a centered 1dp vertical line in a ``width_dp`` slot.

    At the default width the slot is the line (the Barks bars' 1dp separator
    idiom); a wider slot adds dead space either side of the line — used to fence
    the Quit button off from the working buttons.
    """
    separator = Widget(size_hint_x=None, width=dp(width_dp))
    with separator.canvas:  # ty: ignore[invalid-context-manager]
        Color(rgba=color)
        line = Rectangle()

    def sync(_widget, _value) -> None:  # noqa: ANN001
        line.pos = (separator.center_x - dp(0.5), separator.y)
        line.size = (dp(1), separator.height)

    separator.bind(pos=sync, size=sync)
    sync(separator, None)
    return separator


def _scroll_view(**kwargs) -> ScrollView:  # noqa: ANN003
    """Build a ScrollView with the Barks Reader's scroll behavior (tree_view_screen.kv).

    ScrollEffect instead of the default DampedScrollEffect: scrolling stops dead
    at the edges rather than rubber-banding, and ``always_overscroll=False`` stops
    content that already fits from bouncing at all. The bar is widened from the
    2dp default, made draggable (``scroll_type`` includes "bars"), and colored
    like the Barks tree panel's.
    """
    return ScrollView(
        always_overscroll=False,
        effect_cls=ScrollEffect,
        scroll_type=["bars", "content"],
        bar_color=(0.7, 0.7, 1.0, 1),
        bar_inactive_color=(0.7, 0.7, 0.7, 0.9),
        bar_width=dp(12),
        **kwargs,
    )


# Frames the sidebar reveal will wait for the tree's geometry to stop moving
# before scrolling to the banded node anyway (a runaway backstop, ~0.5s at
# 60fps — settling normally takes a frame or three).
_TREE_REVEAL_MAX_FRAMES = 30

# Navigation keys consumed as no-ops where nothing can move (an open footnote
# popup, an empty sidebar state): they must not leak to the hosting app.
_NAV_NOOP_KEYS = frozenset(
    {KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_PAGE_UP, KEY_PAGE_DOWN, KEY_HOME, KEY_END}
)


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
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)
        self.bundle = bundle
        # Colors the embedding app may theme (tree, search, focus ring, article
        # markup); the default reproduces the standalone reader's palette.
        self._theme = theme if theme is not None else ViewerThemeSpec()
        self.history: list[_HistoryEntry] = []
        self._anchors: dict[str, str] = {}  # "fn:<label>" -> the definition block's markup
        self._syncing_tree = False  # True while _sync_tree_to selects programmatically
        self._image_provider = image_provider
        self._table_rewriter = table_rewriter
        self._action_provider = action_provider
        self._state_path = state_path
        # Title/heading search over the bundle. The built-in searcher needs no app
        # knowledge (unlike the image/table/action providers) and builds its index
        # lazily on the first query, so defaulting it here costs nothing up front;
        # an embedding app may inject a different backend (e.g. full-text).
        self._searcher: SearchProvider = search_provider or BundleSearcher(bundle)
        # Building the index walks the whole bundle, so it is warmed off the UI
        # thread on the field's first focus (see _on_search_focus); until it is
        # ready a query shows a "Searching…" note rather than freezing the field.
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
        self._page_action: PageAction | None = None
        self._band_colors: list[Color] = []  # the current page's section-band Colors
        self._init_link_hover()
        self._init_keyboard_nav()

        # The whole window layers over a context background image (RelativeLayout
        # children stack in add order): image below, the action bar and both
        # panels above.
        self.bg_image = Image(fit_mode="cover", color=WINDOW_BG_TINT, size_hint=(1, 1))
        self.add_widget(self.bg_image)
        root = BoxLayout(orientation="vertical", size_hint=(1, 1))
        self.add_widget(root)
        root.add_widget(self._build_top_bar(top_bar if top_bar is not None else TopBarSpec()))
        content = BoxLayout(orientation="horizontal", spacing=8, padding=8, size_hint=(1, 1))
        root.add_widget(content)

        self.tree_scroll = _scroll_view(size_hint=(1, 1), do_scroll_x=False)
        self.tree = TreeView(
            # No visible root: the bundle-root node spent an indent level (and a
            # row) on no information; the tiers are the effective top level.
            hide_root=True,
            # Grow with the content instead of squeezing into the viewport — a
            # ScrollView only scrolls a child that is taller than itself.
            size_hint_y=None,
        )
        self.tree.bind(minimum_height=self.tree.setter("height"))
        # bind passes (treeview, selected_node); we only want the node (2nd arg)
        self.tree.bind(selected_node=lambda *args: self._on_node(args[1]))
        self.tree_scroll.add_widget(self.tree)

        content.add_widget(self._build_left_column())

        self.body_scroll = _scroll_view(size_hint=(1 - TREE_PANEL_WIDTH, 1), do_scroll_x=False)
        self.body = BoxLayout(
            orientation="vertical",
            size_hint=(None, None),
            spacing=BODY_BLOCK_SPACING,
            padding=BODY_PADDING,
        )
        self.body.bind(minimum_height=self.body.setter("height"))
        self._add_reading_pane_scrim()
        # The scroll child is a full-width anchor that centers the body column,
        # whose width is capped at BODY_MAX_WIDTH so the measure stays readable
        # on maximized windows (below the cap the column just fills the pane).
        body_anchor = AnchorLayout(anchor_x="center", size_hint_y=None)
        body_anchor.add_widget(self.body)
        self.body.bind(height=body_anchor.setter("height"))
        self.body_scroll.bind(
            width=lambda _inst, w: setattr(self.body, "width", min(w, dp(BODY_MAX_WIDTH)))
        )
        self.body_scroll.add_widget(body_anchor)
        content.add_widget(self.body_scroll)

        # Lazy: load only the bundle's top level (all tiers) now; each directory's
        # children are read on first expansion (see _on_dir_open). This keeps startup
        # cheap even though the full bundle is ~900 files across ~200 dirs.
        self._add_tree_nodes(list_children(bundle), None)

        # Startup, before any page is shown: empty frontmatter matches no title, so
        # the provider's fallback pool supplies a random story image.
        self._update_background({}, bundle)

        self._show_start_page(start_page)

        # Open with the sidebar owning the keys (ring + banded current-page
        # node): a visible, predictable starting focus for the 6-button remote,
        # matching the main screen's tree-first model.
        self._set_focus_region(FocusRegion.SIDEBAR)

    def _show_start_page(self, start_page: Path | None) -> None:
        """Show the opening page, if any: the caller's choice, else the saved session's.

        A caller-chosen page wins; otherwise resume where the last session
        left off (page and scroll offset), when a state file says where.
        """
        start_scroll = 1.0
        if start_page is None and self._state_path is not None:
            saved = load_session_state(self._state_path, self.bundle)
            if saved is not None:
                start_page, start_scroll = saved.page, saved.scroll_y
        if start_page is not None:  # the tree syncs itself
            self._show(start_page, push=True, scroll_y=start_scroll)

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
        with left.canvas.before:  # ty: ignore[unresolved-attribute]
            Color(rgba=SIDEBAR_SCRIM)
            sidebar_scrim = Rectangle(pos=left.pos, size=left.size)
        left.bind(
            pos=lambda _inst, pos: setattr(sidebar_scrim, "pos", pos),
            size=lambda _inst, size: setattr(sidebar_scrim, "size", size),
        )
        self.search_field = TextInput(
            hint_text="Search pages…",
            multiline=False,
            write_tab=False,
            background_color=SEARCH_FIELD_BG,
            foreground_color=(1, 1, 1, 1),
            hint_text_color=self._theme.secondary_text,
            cursor_color=(1, 1, 1, 1),
            padding=(dp(8), dp(6)),
        )
        self.search_field.bind(
            text=self._on_search_text,
            on_text_validate=self._on_search_enter,
            focus=self._on_search_focus,
        )
        # The field shares a fixed-height row with a "clear" button that shows
        # only while there is text — a one-tap return to the tree when done searching.
        search_row = BoxLayout(
            size_hint_y=None,
            height=dp(SEARCH_FIELD_HEIGHT),
            spacing=dp(SEARCH_FIELD_ROW_GAP),
        )
        search_row.add_widget(self.search_field)
        self.search_clear_btn = _FlatButton(
            text="×",  # noqa: RUF001 — the multiplication sign renders in every font (unlike ✕)
            font_size=dp(SEARCH_CLEAR_GLYPH_SIZE),
            bold=True,
            color=SEARCH_CLEAR_GLYPH_COLOR,
            size_hint=(None, 1),
            width=dp(SEARCH_CLEAR_BTN_WIDTH),
            opacity=0,
            disabled=True,
        )
        # A dark backing matching the field, under the transparent-background glyph.
        with self.search_clear_btn.canvas.before:  # ty: ignore[unresolved-attribute]
            Color(rgba=SEARCH_FIELD_BG)
            clear_bg = Rectangle()
        self.search_clear_btn.bind(
            pos=lambda w, _v: setattr(clear_bg, "pos", w.pos),
            size=lambda w, _v: setattr(clear_bg, "size", w.size),
        )
        self.search_clear_btn.bind(on_release=lambda *_: self._clear_search())
        search_row.add_widget(self.search_clear_btn)
        left.add_widget(search_row)
        self._left_body = BoxLayout(size_hint=(1, 1))
        self._left_body.add_widget(self.tree_scroll)
        left.add_widget(self._left_body)
        return left

    def _build_top_bar(self, spec: TopBarSpec) -> BoxLayout:
        """Build the action-bar strip: app icon, markup heading, right-edge buttons.

        A Python rendition of the Barks Reader's kv action-bar idiom. Creates
        ``back_btn``, ``contrast_btn`` and the page-action slot as it goes.
        """
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=round(dp(spec.height)),
            padding=(dp(2), 0, dp(5), 0),
            spacing=dp(5),
        )
        with bar.canvas.before:  # ty: ignore[unresolved-attribute]
            Color(rgba=spec.bg_color)
            bar_bg = Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(
            pos=lambda _inst, pos: setattr(bar_bg, "pos", pos),
            size=lambda _inst, size: setattr(bar_bg, "size", size),
        )

        if spec.icon_path is not None:
            bar.add_widget(self._build_bar_icon(spec.icon_path, spec.icon_width))

        # The heading takes all the stretch space, pinning the buttons right.
        # Kept as an attribute: it doubles as the window-drag region when the
        # app replaces the OS titlebar with this bar (see OKFApp.on_start) —
        # the Barks Reader's draggable_title_bar arrangement, where only the
        # title area drags and the icon/buttons stay clickable.
        self.bar_drag_region = Label(
            text=spec.title_markup,
            color=spec.title_color,
            markup=True,
            halign="left",
            valign="middle",
        )
        self.bar_drag_region.bind(size=lambda inst, size: inst.setter("text_size")(inst, size))
        bar.add_widget(self.bar_drag_region)

        bar.add_widget(_bar_separator(spec.separator_color))

        if spec.back_icon_path is not None:
            # ActionButton is the Barks bars' BarButton base: standalone it
            # renders as a dp(48) icon button on a flat action-item background.
            self.back_btn = ActionButton(icon=str(spec.back_icon_path), mipmap=True, disabled=True)
            _tint_bar_icon(self.back_btn, self._theme.icon_tint)
        else:
            self.back_btn = Button(text="< Back", size_hint_x=None, width=dp(90), disabled=True)
        self.back_btn.bind(on_release=lambda *_: self.go_back())
        bar.add_widget(self.back_btn)

        # Dials the section bands from their subtle default up to near-opaque
        # (BLOCK_BG_CONTRAST_ALPHA) when the background image fights the text.
        if spec.contrast_on_icon_path is None:
            self.contrast_btn = ToggleButton(text="Contrast", size_hint_x=None, width=dp(90))
        else:
            assert spec.contrast_off_icon_path is not None
            self.contrast_btn = _IconToggleButton(
                str(spec.contrast_on_icon_path), str(spec.contrast_off_icon_path)
            )
            _tint_bar_icon(self.contrast_btn, self._theme.icon_tint)
        self.contrast_btn.bind(state=lambda *_: self._apply_band_alpha())
        bar.add_widget(self.contrast_btn)

        # The page's contextual action (see PageActionProvider): an empty
        # fixed-width slot until a page offers one — _set_page_action fills it
        # with a text or icon button (the two render too differently to
        # restyle one persistent widget).
        self.action_btn: Button | None = None
        self._action_slot = AnchorLayout(size_hint_x=None, width=0)
        bar.add_widget(self._action_slot)

        # The exit control sits alone in the window corner (with the OS titlebar
        # replaced by this bar, it is the window's only close control), fenced
        # off by a separator so an overshoot on the working buttons can't kill
        # the app.
        bar.add_widget(_bar_separator(spec.separator_color, spec.quit_fence_width))
        if spec.close_icon_path is not None:
            quit_btn = ActionButton(icon=str(spec.close_icon_path), mipmap=True)
            _tint_bar_icon(quit_btn, self._theme.icon_tint)
        else:
            quit_btn = Button(text="Quit", size_hint_x=None, width=dp(70))

        # The embedding app's leave-this-screen action, else stop the app (the
        # standalone case, where this bar carries the window's only close control).
        on_close = spec.on_close or (lambda: App.get_running_app().stop())
        quit_btn.bind(on_release=lambda *_: on_close())
        bar.add_widget(quit_btn)
        return bar

    def _build_bar_icon(self, icon_path: Path, icon_width: int) -> RelativeLayout:
        """Build the bar's left-edge app icon: an image under a transparent hitbox.

        The main-screen pattern — pressing dims the image, releasing shows the
        bundle's home page.
        """
        icon_box = RelativeLayout(size_hint=(None, 1), width=dp(icon_width))
        icon = Image(
            source=str(icon_path),
            size_hint=(None, None),
            fit_mode="contain",
            mipmap=True,
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        # Slightly smaller than its container, for padding (the kv idiom).
        icon_box.bind(
            size=lambda _inst, size: setattr(icon, "size", (size[0] - dp(8), size[1] - dp(8)))
        )
        hitbox = Button(background_color=(0, 0, 0, 0), size_hint=(1, 1))
        hitbox.bind(
            state=lambda _inst, state: setattr(icon, "opacity", 0.5 if state == "down" else 1.0)
        )
        hitbox.bind(on_release=lambda *_: self._show(self.bundle / "index.md", push=True))
        icon_box.add_widget(icon)
        icon_box.add_widget(hitbox)
        return icon_box

    def _add_tree_nodes(self, nodes, parent) -> None:  # noqa: ANN001
        # Bind one level of the Kivy-free bundle model (okf_reader.core list_children)
        # to TreeView widgets; the frontmatter reads for this level already happened there.
        for node in nodes:
            if isinstance(node, BundleDir):
                tv = self.tree.add_node(
                    TreeViewLabel(
                        text=node.title or node.name,
                        bold=True,
                        color=self._theme.dir_text,
                        color_selected=self._theme.selection,
                        even_color=self._theme.row_stripe_even,
                        odd_color=self._theme.row_stripe_odd,
                    ),
                    parent,
                )
                # Disclosure triangle only when there is something to open (cheap
                # existence scan); the real children still load lazily on expand.
                tv.is_leaf = not has_children(node.path)
                tv.bundle_path = node.path
                tv.loaded = False
                tv.bind(is_open=self._on_dir_open)
            else:  # ConceptNode
                tv = TreeViewLabel(
                    text=node.title,
                    color=self._theme.title_text,
                    color_selected=self._theme.selection,
                    even_color=self._theme.row_stripe_even,
                    odd_color=self._theme.row_stripe_odd,
                )
                tv.file_path = node.path
                self.tree.add_node(tv, parent)

    def _on_dir_open(self, dir_node, is_open) -> None:  # noqa: ANN001
        # Fires on both open and close; populate a directory's children once, lazily.
        if not is_open:
            return
        if not dir_node.loaded:
            dir_node.loaded = True
            self._add_tree_nodes(list_children(dir_node.bundle_path), dir_node)
        self._close_other_branches(dir_node)

    def _close_other_branches(self, opened) -> None:  # noqa: ANN001
        """Close every open node outside ``opened``'s ancestor chain.

        The Barks Reader's accordion rule: one open path at a time. Other
        branches are closed depth-first (children before parents), so nothing
        keeps a stale expanded state to spring back on its next open. Each
        toggle re-fires _on_dir_open with is_open=False, which returns
        immediately.
        """
        keep = {opened}
        node = opened.parent_node
        while node is not None:
            keep.add(node)
            node = node.parent_node

        def close_subtree(node) -> None:  # noqa: ANN001
            for child in node.nodes:
                if child.is_open:
                    close_subtree(child)
                    self.tree.toggle_node(child)

        def walk(parent) -> None:  # noqa: ANN001
            for child in parent.nodes:
                if not child.is_open:
                    continue
                if child in keep:
                    walk(child)  # on the kept path: only prune its off-path branches
                else:
                    close_subtree(child)
                    self.tree.toggle_node(child)

        walk(self.tree.root)

    def _on_node(self, node) -> None:  # noqa: ANN001
        if self._syncing_tree:
            return  # programmatic selection mirroring the page already on display
        path = getattr(node, "file_path", None)
        if path:
            self._show(Path(path), push=True)
            return
        # A directory: show its reserved index.md listing when it has one. Its
        # relative links resolve against the directory (resolve_link gets the
        # index.md as the page path), so the listing is navigable.
        bundle_path = getattr(node, "bundle_path", None)
        if bundle_path is not None:
            index = Path(bundle_path) / "index.md"
            if index.is_file():
                self._show(index, push=True)

    def _on_search_focus(self, _field, focused: bool) -> None:  # noqa: ANN001
        """On the field's first focus, warm the search index off the UI thread.

        Building the index walks the whole bundle; starting it on focus (before
        the user has typed) keeps the field responsive and usually has results
        ready by the first keystroke. A provider without a ``warm`` method is
        assumed to manage its own readiness, so it is marked ready at once.
        """
        if not focused or self._search_warming:
            return
        self._search_warming = True
        warm = getattr(self._searcher, "warm", None)
        if warm is None:
            self._search_ready = True
            return
        threading.Thread(target=self._warm_search_index, args=(warm,), daemon=True).start()

    def _warm_search_index(self, warm: Callable[[], None]) -> None:
        """Worker thread: build the index, then flip readiness on the UI thread.

        A build failure still flips readiness (with the failed flag) so the field
        recovers to an error note rather than hanging on "Searching…" forever; the
        exception must not escape here or the daemon thread would die silently.
        """
        try:
            warm()
        except Exception:  # noqa: BLE001 — any build failure must surface, not hang
            Clock.schedule_once(lambda _dt: self._mark_search_ready(failed=True), 0)
            return
        Clock.schedule_once(lambda _dt: self._mark_search_ready(failed=False), 0)

    def _mark_search_ready(self, *, failed: bool) -> None:
        """Mark the index ready (or failed) and refresh any query typed while warming."""
        self._search_ready = True
        self._search_failed = failed
        if self.search_field.text.strip():
            if failed:
                self._show_search_error()
            else:
                self._show_results(self._searcher.search(self.search_field.text))

    def _on_search_text(self, _field, text: str) -> None:  # noqa: ANN001
        """Swap the left column between the tree, a wait note, the results, or an error."""
        has_text = bool(text)
        self.search_clear_btn.opacity = 1 if has_text else 0
        self.search_clear_btn.disabled = not has_text
        if not text.strip():
            self._show_tree_panel()
        elif not self._search_ready:
            self._show_searching()
        elif self._search_failed:
            self._show_search_error()
        else:
            self._show_results(self._searcher.search(text))

    def _clear_search(self) -> None:
        """Clear the search field, restoring the tree (the clear button / done searching)."""
        self.search_field.text = ""
        self.search_field.focus = False

    def _on_search_enter(self, _field) -> None:  # noqa: ANN001
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
                    lambda _dt: self._scroll_tree_node_into_view(self.tree.selected_node), 0
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

    def _show_results(self, hits: list[SearchHit]) -> None:
        """Put the results list in the left column's body slot, replacing the tree."""
        self._sidebar_index = None  # rows are rebuilt; any ringed row is discarded
        self._left_body.clear_widgets()
        self._left_body.add_widget(self._results_widget(hits))

    def _results_widget(self, hits: list[SearchHit]) -> ScrollView:
        """Build the scrollable results list — one row per hit, or a no-match note."""
        scroll = _scroll_view(size_hint=(1, 1), do_scroll_x=False)
        column = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(2), padding=(0, dp(2))
        )
        column.bind(minimum_height=column.setter("height"))
        self._result_rows = []
        if not hits:
            note = Label(
                text="No matches",
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
        """Build one result row: gold title over a dim breadcrumb, opening the page."""
        title = _markup_escape(hit.title)
        crumb = (
            f"\n[size=11][color={self._theme.crumb_hex}]"
            f"{_markup_escape(hit.breadcrumb)}[/color][/size]"
            if hit.breadcrumb
            else ""
        )
        btn = Button(
            text=f"[color={self._theme.title_hex}]{title}[/color]{crumb}",
            markup=True,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(SEARCH_RESULT_HEIGHT),
            background_color=SEARCH_RESULT_INACTIVE_COLOR,
            background_normal="",
        )
        btn.bind(width=lambda inst, w: inst.setter("text_size")(inst, (w - dp(12), None)))
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
        """Focus the search field. The hosting app routes Ctrl+F here."""
        self.search_field.focus = True

    def escape_search(self) -> bool:
        """Clear and unfocus the search field if active; report whether it consumed Escape.

        The hosting app calls this before its Back handling, so Escape backs out
        of an active search first and only navigates back once search is idle.
        """
        if self.search_field.text or self.search_field.focus:
            self.search_field.text = ""
            self.search_field.focus = False
            return True
        return False

    def _set_page_action(self, action: PageAction | None) -> None:
        """Show the contextual bar button for ``action``, or hide it for None."""
        self._page_action = action
        self._action_slot.clear_widgets()
        if action is None:
            self.action_btn = None
            self._action_slot.width = 0
            return
        if action.icon_path is not None:
            # The kv ActionButton style pins an icon button at dp(48) wide.
            self.action_btn = ActionButton(icon=str(action.icon_path), mipmap=True)
            _tint_bar_icon(self.action_btn, self._theme.icon_tint)
        else:
            self.action_btn = Button(text=action.label, size_hint_x=None, width=dp(120))
        self.action_btn.bind(on_release=lambda *_: self._run_page_action())
        self._action_slot.add_widget(self.action_btn)
        # Keep the slot tracking the button (the icon style computes its own width).
        self.action_btn.bind(width=self._action_slot.setter("width"))
        self._action_slot.width = self.action_btn.width

    def _run_page_action(self) -> None:
        if self._page_action is not None:
            self._page_action.run()

    def go_back(self) -> None:
        """Navigate to the previous page, or leave the reader at the history's root.

        Public: besides the bar's Back button, the hosting app routes its own
        back gestures here (mouse button 4; the standalone app also binds Escape
        and Alt+Left). At the root the ``on_exit`` seam fires when the hosting app
        supplied one (embedded: return to the host screen); otherwise it is a
        no-op (standalone: the reader is the whole app).
        """
        if len(self.history) > 1:
            self.history.pop()
            entry = self.history[-1]
            self._show(entry.path, push=False, scroll_y=entry.scroll_y)
        elif self._on_exit is not None:
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
        if path is None:
            if self.history:
                path, scroll_y = self.history[-1].path, self.body_scroll.scroll_y
            else:
                path = self.bundle / "index.md"
        self.history.clear()
        self._show(path, push=True, scroll_y=scroll_y)
        # Re-entry starts over with the sidebar focused, like a fresh open.
        self._set_focus_region(FocusRegion.SIDEBAR)

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

    def on_touch_down(self, touch) -> bool:  # noqa: ANN001
        """Route the mouse's back button (button 4) to Back, wherever it lands."""
        if getattr(touch, "button", "") == "mouse4":
            self.go_back()
            return True
        return bool(super().on_touch_down(touch))

    # ------------------------------------------------------------------
    # Keyboard navigation (see okf_reader.ui.keynav for the pure logic)
    # ------------------------------------------------------------------

    def _init_keyboard_nav(self) -> None:
        """Initialize keyboard-navigation state (see `handle_key`).

        Link focus indexes into ``_page_links``; sidebar focus is the tree's own
        selection band in tree mode and ``_sidebar_index`` over the result rows
        in results mode.
        """
        self._focus_region = FocusRegion.PAGE
        self._page_links: list[tuple[Label, str, int]] = []  # (label, ref, occurrence-in-label)
        self._focused_link: int | None = None
        self._sidebar_index: int | None = None
        self._results_scroll: ScrollView | None = None
        self._footnote_popup: ModalView | None = None

    def handle_key(self, key: int, modifiers: Collection[str] = ()) -> bool:
        """Handle one navigation key press; return whether it was consumed.

        The hosting apps delegate here from their window keyboard handlers (the
        standalone ``OKFApp``, an embedding screen) after their own shortcut
        handling. Keys carrying command modifiers (Ctrl/Alt/Meta) and keys typed
        into the focused search field are refused, so host shortcuts (Ctrl+F,
        Alt+Left) and search typing are never stolen. Escape is consumed only
        when there is viewer-internal state to unwind (an open footnote popup, a
        focused link); otherwise it is left to the host's back handling.

        The map is built for a 6-button remote (Esc, Enter, and the arrows —
        the 10-foot TV case): Up/Down walk the page's links and scroll its
        link-free stretches; Left/Right move spatially between the sidebar and
        the page (Left goes leftward, Right drills rightward); Enter activates.
        Tab (region toggle) and PageUp/PageDown/Home/End (page scrolling) are
        desktop extras. Mouse interaction is deliberately not tracked: a click
        that navigates rebuilds the page, which resets the keyboard focus state
        anyway.

        Args:
            key: The SDL2 keycode from the window keyboard event.
            modifiers: The event's active modifier names (e.g. ``{"ctrl"}``).

        Returns:
            True when the key was consumed.

        """
        if self.search_focused:
            return False
        if {"ctrl", "alt", "meta"} & set(modifiers):
            return False
        if self._footnote_popup is not None:
            return self._handle_popup_key(key)
        if key == KEY_TAB:
            self._toggle_focus_region()
            return True
        if self._focus_region is FocusRegion.SIDEBAR:
            return self._handle_sidebar_key(key)
        return self._handle_page_key(key)

    def _handle_popup_key(self, key: int) -> bool:
        """Escape/Enter dismiss the footnote popup; nav keys are inert under it."""
        assert self._footnote_popup is not None
        if key in (KEY_ESCAPE, KEY_ENTER, KEY_NUMPAD_ENTER):
            self._footnote_popup.dismiss()
            return True
        # Nothing may scroll or refocus under the modal.
        return key in _NAV_NOOP_KEYS or key == KEY_TAB

    def _handle_page_key(self, key: int) -> bool:
        """Walk the page with Up/Down (hybrid link/scroll) and follow links with Enter.

        The 10-foot model: Up/Down is the only reading control a 6-button
        remote has, so it walks the links while they pass through the viewport
        and scrolls through the link-free stretches (see `hybrid_link_step`).
        Left moves leftward to the sidebar; PageUp/PageDown/Home/End are
        desktop extras. Escape is deliberately NOT handled here: back
        navigation must never need a second press to clear link focus first.
        """
        if key in (KEY_UP, KEY_DOWN):
            self._page_line_step(1 if key == KEY_DOWN else -1)
            return True
        if self._handle_page_scroll_key(key):
            return True
        if key == KEY_LEFT:
            self._set_focus_region(FocusRegion.SIDEBAR)
            return True
        if key == KEY_RIGHT:
            return True  # nothing further right; consumed so it cannot leak
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            return self._follow_focused_link()
        return False

    def _handle_page_scroll_key(self, key: int) -> bool:
        """Handle the desktop page-scrolling extras (PageUp/PageDown/Home/End)."""
        if key in (KEY_PAGE_UP, KEY_PAGE_DOWN):
            step = self.body_scroll.height - dp(PAGE_STEP_OVERLAP)
            self._scroll_page_by(step if key == KEY_PAGE_DOWN else -step)
        elif key == KEY_HOME:
            self.body_scroll.scroll_y = 1.0
        elif key == KEY_END:
            fits = self.body.height <= self.body_scroll.height
            self.body_scroll.scroll_y = 1.0 if fits else 0.0
        else:
            return False
        self._prune_offscreen_link_focus()
        return True

    def _page_line_step(self, delta: int) -> None:
        """One Up/Down press: focus the next/previous nearby link, else scroll a step."""
        step_px = dp(PAGE_LINE_STEP)
        action, idx = hybrid_link_step(
            self._link_label_geometry(),
            self._focused_link,
            self.body_scroll.height,
            step_px,
            delta,
        )
        if action == "focus":
            assert idx is not None
            self._set_link_focus(idx)
        else:
            self._scroll_page_by(step_px * delta)
            self._prune_offscreen_link_focus()

    def _link_label_geometry(self) -> list[tuple[float, float]]:
        """Each page link's label (top, bottom) in viewport-relative pixels.

        Viewport-relative: y grows downward from the viewport's top edge, so a
        label spanning the top of the view has top ~0 (see `hybrid_link_step`).
        Occurrences within one label share its geometry.
        """
        viewport_top = self.body_scroll.to_window(self.body_scroll.x, self.body_scroll.top)[1]
        geometry = []
        for lbl, _ref, _occurrence in self._page_links:
            label_top = viewport_top - lbl.to_window(lbl.x, lbl.top)[1]
            geometry.append((label_top, label_top + lbl.height))
        return geometry

    def _prune_offscreen_link_focus(self) -> None:
        """Drop link focus once its label has scrolled fully out of the viewport.

        This is what lets Up/Down re-acquire the first *visible* link after any
        scrolling — focus can never sit on (and Enter can never follow) a link
        the reader cannot see.
        """
        if self._focused_link is None:
            return
        lbl, _ref, _occurrence = self._page_links[self._focused_link]
        viewport_top = self.body_scroll.to_window(self.body_scroll.x, self.body_scroll.top)[1]
        label_top = viewport_top - lbl.to_window(lbl.x, lbl.top)[1]
        if label_top + lbl.height <= 0 or label_top >= self.body_scroll.height:
            self._clear_link_focus()

    def _scroll_page_by(self, delta_px: float) -> None:
        self.body_scroll.scroll_y = scroll_step(
            self.body_scroll.scroll_y, self.body_scroll.height, self.body.height, delta_px
        )

    def _build_page_links(self) -> list[tuple[Label, str, int]]:
        """Collect the page's links in document order: (label, ref, occurrence-in-label)."""
        return [
            (lbl, ref, i)
            for lbl in self._link_labels
            for i, ref in enumerate(enumerate_refs(lbl.text))
        ]

    def _set_link_focus(self, idx: int | None) -> None:
        """Move the gold link highlight to ``idx``, scrolling its label into view."""
        self._restore_focused_link_markup()
        self._focused_link = idx
        if idx is None:
            return
        lbl, _ref, occurrence = self._page_links[idx]
        lbl._orig_markup = lbl.text  # noqa: SLF001
        lbl.text = highlight_ref_occurrence(lbl.text, occurrence, LINK_COLOR, LINK_FOCUS_COLOR)
        if self.body.height > self.body_scroll.height:
            self.body_scroll.scroll_to(lbl, padding=dp(24))

    def _restore_focused_link_markup(self) -> None:
        """Put the focused link's label text back to its unhighlighted markup."""
        if self._focused_link is None:
            return
        lbl, _ref, _occurrence = self._page_links[self._focused_link]
        orig = getattr(lbl, "_orig_markup", None)
        if orig is not None:
            lbl.text = orig
            lbl._orig_markup = None  # noqa: SLF001

    def _clear_link_focus(self) -> None:
        self._restore_focused_link_markup()
        self._focused_link = None

    def _follow_focused_link(self) -> bool:
        """Activate the focused link exactly as a tap would; False with no focus."""
        if self._focused_link is None:
            return False
        lbl, ref, _occurrence = self._page_links[self._focused_link]
        self._on_ref(lbl, ref)
        return True

    def _handle_sidebar_key(self, key: int) -> bool:
        """Drive the contents tree, or the search-result rows while results show."""
        if self._result_rows:
            return self._handle_results_key(key)
        if self.tree_scroll.parent is self._left_body:
            return self._handle_tree_key(key)
        # "Searching…" / search-error / no-match states: nothing to navigate —
        # Right still crosses to the page panel, and the rest of the keys must
        # not leak to the host while the sidebar owns them.
        if key == KEY_RIGHT:
            self._set_focus_region(FocusRegion.PAGE)
            return True
        return key in _NAV_NOOP_KEYS or key in (KEY_ENTER, KEY_NUMPAD_ENTER)

    def _handle_tree_key(self, key: int) -> bool:
        """Walk the contents tree: the selection band is the keyboard focus."""
        nodes = list(self.tree.iterate_open_nodes())
        if not nodes:
            return key in _NAV_NOOP_KEYS
        focused = self.tree.selected_node
        idx = nodes.index(focused) if focused in nodes else None
        node = focused if idx is not None else None
        if key in (KEY_UP, KEY_DOWN):
            self._tree_move(nodes, idx, 1 if key == KEY_DOWN else -1)
        elif key == KEY_HOME:
            self._focus_tree_node(nodes[0])
        elif key == KEY_END:
            self._focus_tree_node(nodes[-1])
        elif key == KEY_RIGHT:
            self._tree_expand(node)
        elif key == KEY_LEFT:
            self._tree_collapse(node)
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._tree_activate(node)
        else:
            return False
        return True

    def _tree_move(self, nodes: list, idx: int | None, delta: int) -> None:
        """Move the focus band up or down the visible nodes (clamped, no wrap)."""
        if idx is None:
            new_idx = 0 if delta > 0 else len(nodes) - 1
        else:
            new_idx = step_index(idx, len(nodes), delta)
        self._focus_tree_node(nodes[new_idx])

    def _tree_expand(self, node) -> None:  # noqa: ANN001
        """Right in the tree: drill rightward — expand a directory, or cross to the page.

        The spatial continuum for a 6-button remote: Right keeps moving
        "rightward" — a closed directory expands, an open one steps into its
        first child, and a page leaf (nothing left to expand) opens its page
        exactly as Enter would and crosses over to the page panel to read it.
        """
        if node is None:
            self._set_focus_region(FocusRegion.PAGE)
            return
        if node.is_leaf:
            self._open_leaf_and_cross_to_page(node)
            return
        if not node.is_open:
            self.tree.toggle_node(node)  # lazy children load via _on_dir_open
            Clock.schedule_once(lambda _dt: self._scroll_tree_node_into_view(node), 0)
        elif node.nodes:
            self._focus_tree_node(node.nodes[0])

    def _tree_collapse(self, node) -> None:  # noqa: ANN001
        """Close the focused directory, or move the focus band to the parent."""
        if node is None:
            return
        if node.is_open and not node.is_leaf:
            self.tree.toggle_node(node)
        elif node.parent_node is not None and node.parent_node is not self.tree.root:
            self._focus_tree_node(node.parent_node)

    def _tree_activate(self, node) -> None:  # noqa: ANN001
        """Open the focused leaf's page, or toggle a directory open/closed.

        Enter on a page leaf behaves exactly like Right: it opens the page and
        crosses over to the page panel to read it. Enter on an open section
        closes it (the main Barks tree's convention), so a reader scrolled up
        to the section heading can put the list away; on a closed one it
        expands and shows the section's index listing.
        """
        if node is None:
            return
        if node.is_leaf:
            self._open_leaf_and_cross_to_page(node)
            return
        was_open = node.is_open
        self.tree.toggle_node(node)
        if not was_open:
            self._on_node(node)

    def _open_leaf_and_cross_to_page(self, node) -> None:  # noqa: ANN001
        """Open a page leaf's page and hand the keys to the page panel."""
        self._on_node(node)
        self._set_focus_region(FocusRegion.PAGE)

    def _focus_tree_node(self, node) -> None:  # noqa: ANN001
        """Move the tree's selection band to ``node`` without navigating."""
        self._syncing_tree = True
        try:
            self.tree.select_node(node)
        finally:
            self._syncing_tree = False
        self._scroll_tree_node_into_view(node)

    def _handle_results_key(self, key: int) -> bool:
        """Walk the search-result rows with a drawn focus ring."""
        count = len(self._result_rows)
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
            scroll.scroll_to(btn, padding=dp(8))

    def _clear_result_focus(self) -> None:
        if self._sidebar_index is not None and self._sidebar_index < len(self._result_rows):
            clear_focus_ring(self._result_rows[self._sidebar_index][1])
        self._sidebar_index = None

    def _toggle_focus_region(self) -> None:
        self._set_focus_region(
            FocusRegion.SIDEBAR if self._focus_region is FocusRegion.PAGE else FocusRegion.PAGE
        )

    def _set_focus_region(self, region: FocusRegion) -> None:
        """Hand the navigation keys to ``region``, updating the visible indicators.

        Entering the sidebar rings it in blue and seeds a focus (the active
        result row, or the tree's selected node scrolled into view). Returning
        to the page clears the rings and re-syncs the tree's selection band to
        the page on display, so a focus band wandered by Up/Down snaps back to
        reality.
        """
        self._focus_region = region
        if region is FocusRegion.SIDEBAR:
            self._clear_link_focus()
            draw_focus_ring(self._left_body, group=SIDEBAR_RING_GROUP, color=self._theme.focus_ring)
            if self._result_rows:
                self._set_result_focus(self._initial_result_index())
            elif self.tree_scroll.parent is self._left_body and self.tree.selected_node is not None:
                self._reveal_tree_node_when_settled(self.tree.selected_node)
        else:
            clear_focus_ring(self._left_body, group=SIDEBAR_RING_GROUP)
            self._clear_result_focus()
            if self.history:
                self._sync_tree_to(self.history[-1].path)

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

    def _sync_tree_to(self, path: Path) -> None:
        """Select and reveal the tree node for ``path``, expanding ancestors as needed.

        Keeps the tree in step with pages reached through links or Back. Walks the
        node's ancestor directories, lazily populating and opening each (the same
        loading path as a manual expand), then selects the node — a directory node
        when ``path`` is an ``index.md``, the concept leaf otherwise.
        """
        try:
            rel = path.resolve().relative_to(self.bundle.resolve())
        except ValueError:
            return
        dir_node = None  # the directory node walked to so far (None == tree root)
        children = self.tree.root.nodes
        for part in rel.parts[:-1]:
            dir_node = next(
                (n for n in children if Path(getattr(n, "bundle_path", "")).name == part),
                None,
            )
            if dir_node is None:
                return  # not represented in the tree (e.g. hidden dir) — nothing to sync
            if not dir_node.loaded:  # populate before opening, as a manual expand would
                dir_node.loaded = True
                self._add_tree_nodes(list_children(dir_node.bundle_path), dir_node)
            if not dir_node.is_open:
                self.tree.toggle_node(dir_node)
            children = dir_node.nodes
        if rel.name == "index.md":  # a directory's own page selects the directory node
            target = dir_node  # None for the bundle root's index — no visible node
        else:
            resolved = path.resolve()
            target = next(
                (
                    n
                    for n in children
                    if getattr(n, "file_path", None) and Path(n.file_path).resolve() == resolved
                ),
                None,
            )
        if target is None or self.tree.selected_node is target:
            return
        self._syncing_tree = True
        try:
            self.tree.select_node(target)
        finally:
            self._syncing_tree = False
        # Scroll once the freshly-expanded tree has actually been laid out — a
        # single-frame deferral is not enough after a large expansion.
        self._reveal_tree_node_when_settled(target)

    def _reveal_tree_node_when_settled(self, node) -> None:  # noqa: ANN001
        """Scroll ``node`` into view once the tree's geometry has stopped moving.

        Right after a page sync or a fresh open, a large lazy expansion (e.g.
        the one-pagers section) and the host's deferred viewer sizing keep
        relaying the tree out for several frames; scrolling immediately would
        compute against node positions the layout has not yet placed and land
        the panel at the bottom. Poll once per frame and scroll only when two consecutive
        frames agree on the geometry (with a frame-count backstop so a
        perpetually-animating layout cannot stall the reveal forever).
        """
        state: dict[str, tuple[float, float, float] | int | None] = {"last": None, "frames": 0}

        def check(_dt: float) -> None:
            geometry = (node.top, self.tree.height, self.tree_scroll.height)
            frames = state["frames"]
            assert isinstance(frames, int)
            if geometry == state["last"] or frames >= _TREE_REVEAL_MAX_FRAMES:
                self._scroll_tree_node_into_view(node)
                return
            state["last"] = geometry
            state["frames"] = frames + 1
            Clock.schedule_once(check, 0)

        Clock.schedule_once(check, 0)

    def _scroll_tree_node_into_view(self, node) -> None:  # noqa: ANN001
        """Scroll the tree panel so ``node`` sits about a quarter of the way down.

        ScrollView.scroll_to would stop as soon as the node is visible, typically
        leaving it hugging the bottom edge; positioning it near the top keeps the
        following siblings (what you usually scan next) on screen.
        """
        viewport_h = self.tree_scroll.height
        content_h = self.tree.height
        if content_h <= viewport_h:
            return  # everything already visible
        node_top = node.top - self.tree.y  # node top, measured from the tree's bottom
        offset = 0.25 * viewport_h
        scroll = (node_top - viewport_h + offset) / (content_h - viewport_h)
        self.tree_scroll.scroll_y = max(0.0, min(1.0, scroll))

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
        self._sync_tree_to(path)
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
        self._set_page_action(
            self._action_provider.action_for(page.frontmatter, path)
            if self._action_provider is not None
            else None
        )
        self.body.clear_widgets()
        self._band_colors.clear()  # their sections were just discarded
        self._link_labels.clear()  # ditto their link labels
        self._focused_link = None  # its label was just discarded — nothing to restore
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
        self._page_links = self._build_page_links()
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
        Clock.schedule_once(lambda _dt: self._refresh_cursor(), 0)

    def _new_section(self) -> BoxLayout:
        """Append and return a fresh banded section box for the next run of blocks."""
        box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=SECTION_BLOCK_SPACING,
            padding=SECTION_PADDING,
        )
        box.bind(minimum_height=box.setter("height"))
        self._band_colors.append(_add_text_backing(box, self._band_alpha()))
        self.body.add_widget(box)
        return box

    def _body_label(self, blk: Block, path: Path) -> Label:
        """Build one body block's self-sizing, ref-navigable Label."""
        lbl = Label(
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
        lbl._page_path = path  # noqa: SLF001
        lbl.bind(on_ref_press=self._on_ref)
        if "[ref=" in blk.markup:
            self._link_labels.append(lbl)
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

        def sync_height(_lbl, height: float) -> None:  # noqa: ANN001
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

    def _add_reading_pane_scrim(self) -> None:
        """Draw the continuous scrim behind the reading column (see READING_PANE_SCRIM).

        Spans the whole body column under the per-section bands, so the
        inter-section gaps and the column padding keep a legibility floor over a
        vivid background panel. Its Color is kept so the Contrast toggle can dial
        it up alongside the bands (see _apply_band_alpha).
        """
        with self.body.canvas.before:
            self._pane_scrim_color = Color(rgba=(*READING_PANE_SCRIM[:3], self._pane_scrim_alpha()))
            rect = Rectangle(pos=self.body.pos, size=self.body.size)
        self.body.bind(
            pos=lambda _inst, pos: setattr(rect, "pos", pos),
            size=lambda _inst, size: setattr(rect, "size", size),
        )

    def _apply_band_alpha(self) -> None:
        """Retune the current page's section bands and the reading-pane scrim to the toggle."""
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
        """
        stack = BoxLayout(orientation="vertical", size_hint=(None, None))
        stack.bind(
            minimum_height=stack.setter("height"),
            minimum_width=stack.setter("width"),
        )
        for row in blk.rows:
            lbl = Label(
                text=row,
                markup=True,
                font_name=TABLE_FONT_NAME,
                font_size=blk.font_size,
                size_hint=(None, None),
            )
            lbl.bind(texture_size=lbl.setter("size"))
            lbl._page_path = path  # noqa: SLF001
            lbl.bind(on_ref_press=self._on_ref)
            if "[ref=" in row:
                self._link_labels.append(lbl)
            stack.add_widget(lbl)
        scroller = _scroll_view(size_hint=(1, None), do_scroll_y=False, height=0)

        def fit_height(*_args: object) -> None:
            # Kivy draws the horizontal bar inside the ScrollView's bounds, so when
            # the table overflows, reserve room below the rows — otherwise the bar
            # covers the last row. (The bar is only drawn when the table overflows,
            # so fitting tables get no dead strip.)
            overflows = stack.width > scroller.width
            scroller.height = stack.height + (
                scroller.bar_width + TABLE_BAR_GAP if overflows else 0
            )

        stack.bind(height=fit_height, width=fit_height)
        scroller.bind(width=fit_height)
        scroller.add_widget(stack)
        return scroller

    def _on_ref(self, label, ref: str) -> None:  # noqa: ANN001
        if ref.startswith("fn:"):
            markup = self._anchors.get(ref)  # tapped [id] → its definition, in a popup
            if markup is not None:
                self._show_footnote_popup(markup, label._page_path)  # noqa: SLF001
            return
        target = resolve_link(label._page_path, ref, self.bundle)  # noqa: SLF001
        if target:
            self._show(target, push=True)

    def _init_link_hover(self) -> None:
        """Set up link hover: the hand cursor whenever the mouse is over a page link.

        ``_link_labels`` holds the current page's link-bearing labels — the hit-test
        candidates (see ``_ref_under``); ``_show`` rebuilds it with the page.
        """
        self._link_labels: list[Label] = []
        self._popup_link_label: Label | None = None  # an open footnote popup's label
        self._hand_cursor = False
        from kivy.core.window import Window  # noqa: PLC0415 — needs the realized window

        Window.bind(mouse_pos=self._on_mouse_pos)

    def _on_mouse_pos(self, _window: Any, pos: tuple[float, float]) -> None:  # noqa: ANN401
        self._set_hand_cursor(self._over_link(pos))

    def _over_link(self, pos: tuple[float, float]) -> bool:
        """Return whether the window point ``pos`` is over a page link."""
        if self.get_root_window() is None:  # viewer not on screen (e.g. wiki closed)
            return False
        if self._popup_link_label is not None:  # a modal popup: only its label counts
            return _ref_under(self._popup_link_label, *pos) is not None
        # Fast reject: outside the page pane's viewport nothing can be a link —
        # this also blocks labels scrolled out of view, whose content-space boxes
        # would otherwise still collide. collide_point wants parent-space coords;
        # the scroll view's own to_widget would apply the scroll transform.
        if not self.body_scroll.collide_point(*self.body_scroll.parent.to_widget(*pos)):
            return False
        return any(_ref_under(lbl, *pos) is not None for lbl in self._link_labels)

    def _set_hand_cursor(self, over: bool) -> None:
        """Flip the system cursor between hand and arrow, only on a state change.

        Change-only so this never fights other cursor owners (e.g. the Barks
        Reader's busy cursor) while the mouse just moves about.
        """
        if over == self._hand_cursor:
            return
        self._hand_cursor = over
        from kivy.core.window import Window  # noqa: PLC0415 — needs the realized window

        Window.set_system_cursor("hand" if over else "arrow")

    def _refresh_cursor(self) -> None:
        """Re-evaluate the cursor against the current mouse position (no move needed)."""
        from kivy.core.window import Window  # noqa: PLC0415 — needs the realized window

        self._set_hand_cursor(self._over_link(Window.mouse_pos))

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
        self._popup_link_label = lbl
        self._footnote_popup = popup

        def _release_hover(_popup: ModalView) -> None:
            self._popup_link_label = None
            self._footnote_popup = None
            self._refresh_cursor()

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
        **kwargs,  # noqa: ANN003
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

    def _on_keyboard(self, _window, key, _scancode, _codepoint, modifiers) -> bool:  # noqa: ANN001
        """Ctrl+F focuses search; Escape and Alt+Left navigate back, like a browser.

        Everything else defers to the viewer's own keyboard navigation
        (``OKFViewer.handle_key``): page scrolling, link traversal, and the
        sidebar — so the standalone reader navigates exactly like the embedded
        one. Escape is always consumed: kivy's default would close the window,
        and an accidental Escape must not kill the reader (the same overshoot
        hazard the Quit button was moved to the corner for). While a search is
        active Escape backs out of it first; at the start of the history both
        back keys are a harmless no-op. Alt+Left is not stolen while the search
        field owns the keyboard, so it can move the cursor within a typed query.
        """
        assert self._viewer is not None
        if key == KEY_F and "ctrl" in modifiers:
            self._viewer.focus_search()
            return True
        if self._viewer.handle_key(key, set(modifiers)):
            return True
        return self._handle_back_key(key, modifiers)

    def _handle_back_key(self, key, modifiers) -> bool:  # noqa: ANN001
        """Handle the browser-style back keys the viewer's handle_key refused."""
        assert self._viewer is not None
        if key == KEY_ESCAPE:
            if not self._viewer.escape_search():
                self._viewer.go_back()
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
