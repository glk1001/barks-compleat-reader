"""The viewer's own widgets and the small helpers that draw them.

None of these knows the viewer: a table that builds only the rows in view, the top
bar's icon buttons and their tint, the contents tree's nodes, a page's label, and the
markup and hit-testing a results row and a link need.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from functools import cache
from itertools import accumulate
from typing import TYPE_CHECKING

from kivy.clock import Clock
from kivy.core.text.markup import MarkupLabel as CoreMarkupLabel
from kivy.effects.scroll import ScrollEffect
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.actionbar import ActionButton, ActionToggleButton
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.treeview import TreeViewLabel
from kivy.uix.widget import Widget

from okf_reader.core.render import visible_len
from okf_reader.ui import trace

if TYPE_CHECKING:
    from pathlib import Path

    from kivy.uix.boxlayout import BoxLayout

    from okf_reader.core.search import SearchHit
    from okf_reader.core.theme import ViewerThemeSpec

# Tables come from the core space-padded to aligned columns (see TableBlock), which
# only lines up in a monospace face. RobotoMono ships with Kivy (regular only —
# another reason table headers are colored, not bold).
TABLE_FONT_NAME = "RobotoMono-Regular"
# Rows a lazy table keeps built beyond each edge of the viewport, in viewport heights,
# so a scroll step finds its rows ready.
LAZY_TABLE_MARGIN = 0.5
# Translucent rounded band drawn behind each page *section* (a heading plus
# everything under it, up to the next heading) so body text keeps its contrast
# over vivid background panels — the Barks Reader's BgColorLabel idiom
# (main_screen.kv <BackgroundColor@Widget>), in Python. The alpha is the
# delineation-strength knob.
BLOCK_BG_COLOR = (0.01, 0.01, 0.01, 0.30)
BLOCK_BG_RADIUS = 6  # dp


class IconToggleButton(ActionToggleButton):
    """An icon bar button that holds its down state, swapping icons with it.

    The kv ActionButton style supplies the fixed dp(48) icon-button width and
    the pressed background (the same rendering as the bar's Back/Quit buttons);
    the icon pair shows what pressing will do — ``on_icon`` while up, ``off_icon``
    while down.
    """

    def __init__(self, on_icon: str, off_icon: str, **kwargs: object) -> None:
        self._on_icon = on_icon
        self._off_icon = off_icon
        super().__init__(icon=on_icon, mipmap=True, **kwargs)

    def on_state(self, _widget: Widget, value: str) -> None:
        self.icon = self._off_icon if value == "down" else self._on_icon


def tint_bar_icon(button: ActionButton, tint: tuple[float, float, float, float]) -> None:
    """Overlay a theme-tinted copy of an ActionButton's icon glyph.

    The kv ActionButton style renders ``icon`` as a plain white child Image with
    no color hook, so a light glyph cannot be recolored in place. We lay a
    tinted copy of the same glyph over it (matching the style's dp(4) inset and
    ``contain`` fit), tracking ``icon`` so an ``IconToggleButton``'s state swap
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

    def _sync(*_args: object) -> None:
        overlay.pos = (button.x + dp(4), button.y + dp(4))
        overlay.size = (button.width - dp(8), button.height - dp(8))

    button.bind(pos=_sync, size=_sync, icon=lambda _inst, value: setattr(overlay, "source", value))
    button.add_widget(overlay)
    _sync()


def add_text_backing(widget: BoxLayout, alpha: float) -> Color:
    """Draw the translucent rounded band behind ``widget`` (see BLOCK_BG_COLOR),
    kept glued through pos/size changes. Returns the band's Color instruction so
    the caller can retune its alpha later (the Contrast toggle).
    """  # noqa: D205
    # pyrefly: ignore[missing-attribute]  # Kivy sets `canvas` in Widget.__init__.
    with widget.canvas.before:  # ty: ignore[missing-union-attribute]
        color = Color(rgba=(*BLOCK_BG_COLOR[:3], alpha))
        rect = RoundedRectangle(radius=[dp(BLOCK_BG_RADIUS)])

    def sync(_widget: Widget, _value: object) -> None:
        rect.pos = widget.pos
        rect.size = widget.size

    widget.bind(pos=sync, size=sync)
    sync(widget, None)
    return color


def markup_escape(text: str) -> str:
    """Escape the characters special to Kivy markup, for text shown in a markup label."""
    return text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def result_markup(hit: SearchHit, title_hex: str, dim_hex: str) -> str:
    """Return a results row's markup: the title over a dim breadcrumb, or a text hit's snippet.

    A hit found in a page's text shows the words round the match in place of the
    breadcrumb, the match itself bold in the title's color, so the row says why
    the page matched.
    """
    title = f"[color={title_hex}]{markup_escape(hit.title)}[/color]"
    if hit.snippet:
        start, end = hit.snippet_match
        before, match, after = (
            markup_escape(part)
            for part in (hit.snippet[:start], hit.snippet[start:end], hit.snippet[end:])
        )
        second = f"{before}[b][color={title_hex}]{match}[/color][/b]{after}"
    elif hit.breadcrumb:
        second = markup_escape(hit.breadcrumb)
    else:
        return title
    return f"{title}\n[size=11][color={dim_hex}]{second}[/color][/size]"


def ref_under(lbl: Label, wx: float, wy: float) -> str | None:
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


class FlatButton(ButtonBehavior, Label):
    """A clickable glyph with no button chrome.

    A plain Kivy Button paints a fixed light-gray image that ignores
    ``background_color`` (swallowing a light glyph); a Label draws only its text
    over a transparent background, so the caller controls the backing entirely.
    """


def bar_separator(color: tuple[float, float, float, float], width_dp: float = 1) -> Widget:
    """Build a top-bar separator: a centered 1dp vertical line in a ``width_dp`` slot.

    At the default width the slot is the line (the Barks bars' 1dp separator
    idiom); a wider slot adds dead space either side of the line — used to fence
    the Quit button off from the working buttons.
    """
    separator = Widget(size_hint_x=None, width=dp(width_dp))
    # pyrefly: ignore[bad-context-manager]  # Kivy sets `canvas` in Widget.__init__.
    with separator.canvas:  # ty: ignore[invalid-context-manager]
        Color(rgba=color)
        line = Rectangle()

    def sync(_widget: Widget, _value: object) -> None:
        line.pos = (separator.center_x - dp(0.5), separator.y)
        line.size = (dp(1), separator.height)

    separator.bind(pos=sync, size=sync)
    sync(separator, None)
    return separator


def scroll_view(theme: ViewerThemeSpec, **kwargs: object) -> ScrollView:
    """Build a ScrollView with the Barks Reader's scroll behavior (barks_kivy_ui.scrolling).

    ScrollEffect instead of the default DampedScrollEffect: scrolling stops dead
    at the edges rather than rubber-banding, and ``always_overscroll=False`` stops
    content that already fits from bouncing at all. The bar is widened from the
    2dp default, made draggable (``scroll_type`` includes "bars"), and colored
    from the embedding app's theme spec.
    """
    return ScrollView(
        always_overscroll=False,
        effect_cls=ScrollEffect,
        scroll_type=["bars", "content"],
        bar_color=theme.scrollbar,
        bar_inactive_color=theme.scrollbar_inactive,
        bar_width=dp(12),
        **kwargs,
    )


def table_texture_size(markup: str, font_size: int) -> tuple[int, int]:
    """Return the texture size a table row Label gives `markup` (the viewer's `_table_widget`)."""
    core = CoreMarkupLabel(text=markup, font_name=TABLE_FONT_NAME, font_size=font_size)
    core.refresh()
    return core.texture.size


@cache
def table_line_heights(font_size: int) -> tuple[int, int]:
    """Return a table row's height for its first line, and for each line after it."""
    one = table_texture_size("0", font_size)[1]
    return one, table_texture_size("0\n0", font_size)[1] - one


class LazyTable(RelativeLayout):
    """A long, link-free table that keeps Labels only for the rows near the viewport.

    Its rows are monospace and padded to aligned columns, so each row's height is
    known from its line count, and the table's width from its widest row, without
    a Label per row: the table takes its full size at once (the page's height, the
    scroll positions Back restores, are as an eager table's), then builds Labels
    for the rows within the viewport and LAZY_TABLE_MARGIN beyond, reusing them as
    the page scrolls. With no links in it, the page's link machinery never needs
    a row it has not built.
    """

    def __init__(self, rows: list[str], font_size: int, viewport: ScrollView) -> None:
        """Size the table for `rows`; its Labels come once it is laid out in `viewport`.

        Args:
            rows: The rows' markup, as TableBlock holds them.
            font_size: The rows' font size.
            viewport: The page's scroll view, whose visible part decides the rows built.

        """
        super().__init__(size_hint=(None, None))
        self._rows = rows
        self._font_size = font_size
        self._viewport = viewport
        first, more = table_line_heights(font_size)
        heights = [first + more * row.count("\n") for row in rows]
        # The distance of each row's top below the table's top, and the table's height.
        self._tops = list(accumulate(heights, initial=0))
        widest = max(rows, key=lambda row: max(visible_len(line) for line in row.split("\n")))
        self.size = (table_texture_size(widest, font_size)[0], self._tops[-1])
        self._built: dict[int, Label] = {}
        self._spare: list[Label] = []
        self._height_mismatch_logged = False
        self._update_trigger = Clock.create_trigger(self._update, -1)
        # bind holds a bound method weakly (Kivy's faster variant holds it strongly), so
        # the page's scroll view, which outlives every page, does not keep a table
        # alive once its page is gone.
        viewport.bind(scroll_y=self._viewport_moved, height=self._viewport_moved)
        self.bind(pos=self._viewport_moved)

    @property
    def built_rows(self) -> list[int]:
        """The rows that have a Label now, in order."""
        return sorted(self._built)

    def _viewport_moved(self, *_args: object) -> None:
        self._update_trigger()

    def _update(self, *_args: object) -> None:
        """Build the rows near the viewport and give back the Labels of the rest."""
        viewport = self._viewport
        margin = viewport.height * LAZY_TABLE_MARGIN
        viewport_bottom = viewport.to_window(viewport.x, viewport.y)[1]
        table_top = self.to_window(self.x, self.y)[1] + self.height
        # The viewport's span, as distances below the table's top.
        near = table_top - (viewport_bottom + viewport.height) - margin
        far = table_top - viewport_bottom + margin
        first = max(bisect_right(self._tops, near) - 1, 0)
        last = min(bisect_left(self._tops, far), len(self._rows))
        wanted = range(first, last)
        for index in [i for i in self._built if i not in wanted]:
            label = self._built.pop(index)
            self.remove_widget(label)
            self._spare.append(label)
        for index in wanted:
            if index not in self._built:
                self._built[index] = self._build_row(index)

    def _build_row(self, index: int) -> Label:
        if self._spare:
            label = self._spare.pop()
            label.text = self._rows[index]
        else:
            label = Label(
                text=self._rows[index],
                markup=True,
                font_name=TABLE_FONT_NAME,
                font_size=self._font_size,
                size_hint=(None, None),
            )
            label.bind(texture_size=label.setter("size"))
        label.texture_update()
        reserved = self._tops[index + 1] - self._tops[index]
        if label.texture_size[1] != reserved and not self._height_mismatch_logged:
            # Markup that changes a line's height, or a font that renders taller on
            # one platform, would break the reckoning: say so, once per table.
            self._height_mismatch_logged = True
            trace.lazy_row_height_differs(index, label.texture_size[1], reserved)
        label.pos = (0, self.height - self._tops[index + 1])
        self.add_widget(label)
        return label


class DirNode(TreeViewLabel):
    """A folder in the contents tree: its children are loaded the first time it opens."""

    def __init__(self, bundle_path: Path, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.bundle_path = bundle_path
        self.loaded = False


class PageNode(TreeViewLabel):
    """A page in the contents tree."""

    def __init__(self, file_path: Path, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.file_path = file_path


class PageLabel(Label):
    """A label of a page's text: it knows its page, which its links are relative to."""

    def __init__(self, page_path: Path, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.page_path = page_path
        # The text as rendered, kept while one of its links wears the focus color.
        self.orig_markup: str | None = None
