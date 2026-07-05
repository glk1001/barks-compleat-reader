"""Kivy viewer for an OKF bundle — the UI layer of okf_reader.

Binds the Kivy-free core (okf_reader.core.render) to native widgets: a lazily
populated tree of the bundle's tiers on the left, the rendered page on the right.
Links resolve via the core's ``resolve_link``; tapping a footnote marker shows its
definition (keyed by the page `Block`'s anchor) in a dismiss-on-tap popup.
``run(bundle)`` launches the standalone app; the CLI entry point is
scripts/read_okf.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.effects.scroll import ScrollEffect
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.treeview import TreeView, TreeViewLabel

from okf_reader.core.backgrounds import ImageProvider, choose_image
from okf_reader.core.render import (
    BundleDir,
    TableBlock,
    TableRewriter,
    dir_title,
    has_children,
    list_children,
    render_page,
    resolve_link,
)

BODY_LINE_HEIGHT = 1.25
# Tables come from the core space-padded to aligned columns (see TableBlock), which
# only lines up in a monospace face. RobotoMono ships with Kivy (regular only —
# another reason table headers are colored, not bold).
TABLE_FONT_NAME = "RobotoMono-Regular"
BODY_PADDING = (16, 8, 24, 16)  # left, top, right, bottom
BODY_BLOCK_SPACING = 12
POPUP_PADDING = 12
TREE_PANEL_WIDTH = 0.28  # fraction of the window; the page panel gets the rest
# Multiplied into the background image (Kivy Image.color) so white text stays
# readable over it — the same darkening mechanism the Barks Reader's kv files use.
WINDOW_BG_TINT = (0.22, 0.22, 0.22, 1)
# Translucent black drawn over the background image behind the tree panel only,
# softening it a touch further there than in the reading pane.
TREE_PANEL_SCRIM = (0, 0, 0, 0.25)
# Translucent rounded band drawn behind each text block so body text keeps its
# contrast over vivid background panels — the Barks Reader's BgColorLabel idiom
# (main_screen.kv <BackgroundColor@Widget>), in Python. The alpha is the
# delineation-strength knob; the sizing factors make the band leak out a bit
# past the text, as the Barks labels do.
BLOCK_BG_COLOR = (0.01, 0.01, 0.01, 0.5)
BLOCK_BG_RADIUS = 6  # dp
BLOCK_BG_SIZING_X = 1.01
BLOCK_BG_SIZING_Y = 1.06
# Same magenta the Barks Reader uses for tree selection
# (barks_reader.ui.tree_view_nodes.TREE_VIEW_NODE_SELECTED_COLOR).
TREE_SELECTED_COLOR = (1, 0, 1, 0.8)
# Barks Reader tree convention: group nodes bold white, titles yellow. Here:
# directories bold white; concept pages in the page-heading gold (ffd54a).
TREE_DIR_TEXT_COLOR = (1, 1, 1, 1)
TREE_CONCEPT_TEXT_COLOR = (1.0, 0.835, 0.29, 1.0)


def _add_text_backing(widget) -> None:  # noqa: ANN001
    """Draw the translucent rounded band behind ``widget`` (see BLOCK_BG_COLOR).

    Same geometry as the Barks kv rule: the rectangle is the widget's size
    scaled by the sizing factors, shifted by half the overhang so the leak-out
    is centered, and kept glued through pos/size changes.
    """
    with widget.canvas.before:
        Color(rgba=BLOCK_BG_COLOR)
        rect = RoundedRectangle(radius=[dp(BLOCK_BG_RADIUS)])

    def sync(_widget, _value) -> None:  # noqa: ANN001
        width = BLOCK_BG_SIZING_X * widget.width
        height = BLOCK_BG_SIZING_Y * widget.height
        rect.size = (width, height)
        rect.pos = (
            widget.x - 0.5 * (width - widget.width),
            widget.y - 0.5 * (height - widget.height),
        )

    widget.bind(pos=sync, size=sync)
    sync(widget, None)


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
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)
        self.bundle = bundle
        self.history: list[_HistoryEntry] = []
        self._anchors: dict[str, str] = {}  # "fn:<label>" -> the definition block's markup
        self._syncing_tree = False  # True while _sync_tree_to selects programmatically
        self._image_provider = image_provider
        self._table_rewriter = table_rewriter
        self._last_bg: Path | None = None

        # The whole window layers over a context background image (RelativeLayout
        # children stack in add order): image below, both panels above.
        self.bg_image = Image(fit_mode="cover", color=WINDOW_BG_TINT, size_hint=(1, 1))
        self.add_widget(self.bg_image)
        content = BoxLayout(orientation="horizontal", spacing=8, padding=8, size_hint=(1, 1))
        self.add_widget(content)

        self.tree_scroll = _scroll_view(size_hint=(TREE_PANEL_WIDTH, 1), do_scroll_x=False)
        self.tree = TreeView(
            root_options={
                "text": dir_title(bundle),
                "bold": True,
                "color": TREE_DIR_TEXT_COLOR,
                "color_selected": TREE_SELECTED_COLOR,
            },
            hide_root=False,
            # Grow with the content instead of squeezing into the viewport — a
            # ScrollView only scrolls a child that is taller than itself.
            size_hint_y=None,
        )
        self.tree.bind(minimum_height=self.tree.setter("height"))
        # bind passes (treeview, selected_node); we only want the node (2nd arg)
        self.tree.bind(selected_node=lambda *args: self._on_node(args[1]))
        self.tree_scroll.add_widget(self.tree)
        # Scrim between the background image and the tree text (canvas.before
        # renders under the panel's widgets), kept glued to the panel's rectangle.
        with self.tree_scroll.canvas.before:  # ty: ignore[unresolved-attribute]
            Color(rgba=TREE_PANEL_SCRIM)
            self._tree_scrim = Rectangle(pos=self.tree_scroll.pos, size=self.tree_scroll.size)
        self.tree_scroll.bind(
            pos=lambda _inst, pos: setattr(self._tree_scrim, "pos", pos),
            size=lambda _inst, size: setattr(self._tree_scrim, "size", size),
        )
        content.add_widget(self.tree_scroll)

        right = BoxLayout(orientation="vertical", size_hint=(1 - TREE_PANEL_WIDTH, 1), spacing=4)
        bar = BoxLayout(size_hint_y=None, height=32, spacing=6)
        self.back_btn = Button(text="< Back", size_hint_x=None, width=90, disabled=True)
        self.back_btn.bind(on_release=lambda *_: self._go_back())
        bar.add_widget(self.back_btn)
        right.add_widget(bar)

        self.body_scroll = _scroll_view(do_scroll_x=False)
        self.body = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=BODY_BLOCK_SPACING,
            padding=BODY_PADDING,
        )
        self.body.bind(minimum_height=self.body.setter("height"))
        self.body_scroll.add_widget(self.body)
        right.add_widget(self.body_scroll)
        content.add_widget(right)

        # Lazy: load only the bundle's top level (all tiers) now; each directory's
        # children are read on first expansion (see _on_dir_open). This keeps startup
        # cheap even though the full bundle is ~900 files across ~200 dirs.
        self._add_tree_nodes(list_children(bundle), None)

        # Startup, before any page is shown: empty frontmatter matches no title, so
        # the provider's fallback pool supplies a random story image.
        self._update_background({}, bundle)

    def _add_tree_nodes(self, nodes, parent) -> None:  # noqa: ANN001
        # Bind one level of the Kivy-free bundle model (okf_reader.core list_children)
        # to TreeView widgets; the frontmatter reads for this level already happened there.
        for node in nodes:
            if isinstance(node, BundleDir):
                tv = self.tree.add_node(
                    TreeViewLabel(
                        text=node.title or node.name,
                        bold=True,
                        color=TREE_DIR_TEXT_COLOR,
                        color_selected=TREE_SELECTED_COLOR,
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
                    color=TREE_CONCEPT_TEXT_COLOR,
                    color_selected=TREE_SELECTED_COLOR,
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

    def _go_back(self) -> None:
        if len(self.history) > 1:
            self.history.pop()
            entry = self.history[-1]
            self._show(entry.path, push=False, scroll_y=entry.scroll_y)

    def _update_background(self, frontmatter: dict, path: Path) -> None:
        """Set the page panel's background to an image suiting the page, if any."""
        if self._image_provider is None:
            return
        candidates = self._image_provider.candidate_images(frontmatter, path)
        image = choose_image(candidates, self._last_bg)
        self._last_bg = image
        self.bg_image.source = str(image) if image is not None else ""

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
            target = dir_node if dir_node is not None else self.tree.root
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
        # Scroll on the next frame, once the freshly-expanded tree has been laid out.
        Clock.schedule_once(lambda _dt: self._scroll_tree_node_into_view(target), 0)

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

    def _show(self, path: Path, *, push: bool, scroll_y: float = 1.0) -> None:
        if push:
            if self.history:  # remember where the outgoing page was scrolled to
                self.history[-1].scroll_y = self.body_scroll.scroll_y
            self.history.append(_HistoryEntry(path))
        self.back_btn.disabled = len(self.history) <= 1
        self._sync_tree_to(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as err:
            # Tolerant consumption (SPEC §9): a page deleted or made unreadable
            # after the tree was populated (e.g. the wiki being regenerated)
            # degrades to an error page instead of crashing the event handler.
            text = f"# Page unavailable\n\n`{path.name}`: {err.strerror or err}\n"
        page = render_page(text, table_rewriter=self._table_rewriter)
        self._update_background(page.frontmatter, path)
        self.body.clear_widgets()
        self._anchors = {}
        for blk in page.blocks:
            if isinstance(blk, TableBlock):
                self.body.add_widget(self._table_widget(blk))
                continue
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
            _add_text_backing(lbl)
            if blk.anchor:
                self._anchors[blk.anchor] = blk.markup
            self.body.add_widget(lbl)
        # Fresh pages open at the top; Back passes the offset the page was left at.
        self.body_scroll.scroll_y = scroll_y
        if scroll_y != 1:
            # The labels take their texture sizes over the next frame, shifting the
            # normalized offset; re-assert it once the layout has settled.
            Clock.schedule_once(lambda _dt: setattr(self.body_scroll, "scroll_y", scroll_y), 0)

    def _table_widget(self, blk: TableBlock) -> ScrollView:
        """Build the widget for a table: monospace rows, tightly stacked, one per Label.

        One Label per row (not one for the whole table) keeps each texture small —
        a several-hundred-row table in a single Label would exceed the GPU texture
        size limit. Each label takes its natural (texture) size so the columns'
        space padding is preserved, and the stack sits in its own horizontal
        ScrollView so a wide table scrolls instead of clipping.
        """
        stack = BoxLayout(orientation="vertical", size_hint=(None, None))
        stack.bind(
            minimum_height=stack.setter("height"),
            minimum_width=stack.setter("width"),
        )
        _add_text_backing(stack)  # one band behind the whole table, not per row
        for row in blk.rows:
            lbl = Label(
                text=row,
                markup=True,
                font_name=TABLE_FONT_NAME,
                font_size=blk.font_size,
                size_hint=(None, None),
            )
            lbl.bind(texture_size=lbl.setter("size"))
            stack.add_widget(lbl)
        scroller = _scroll_view(size_hint=(1, None), do_scroll_y=False, height=0)
        stack.bind(height=scroller.setter("height"))
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
        popup.open()


class OKFApp(App):
    def __init__(
        self,
        bundle: Path,
        image_provider: ImageProvider | None = None,
        table_rewriter: TableRewriter | None = None,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)
        self._bundle = bundle
        self._image_provider = image_provider
        self._table_rewriter = table_rewriter

    def build(self) -> OKFViewer:
        self.title = f"OKF Reader — {self._bundle.name}"
        return OKFViewer(
            self._bundle,
            image_provider=self._image_provider,
            table_rewriter=self._table_rewriter,
        )


def run(
    bundle: Path,
    image_provider: ImageProvider | None = None,
    table_rewriter: TableRewriter | None = None,
) -> None:
    """Launch the standalone OKF reader on ``bundle`` (blocks until the window closes)."""
    OKFApp(bundle, image_provider=image_provider, table_rewriter=table_rewriter).run()
