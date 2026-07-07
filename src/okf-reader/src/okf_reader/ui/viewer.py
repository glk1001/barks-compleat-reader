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
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.effects.scroll import ScrollEffect
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.actionbar import ActionButton
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.treeview import TreeView, TreeViewLabel
from kivy.uix.widget import Widget

from okf_reader.core.render import (
    BundleDir,
    TableBlock,
    TableRewriter,
    has_children,
    list_children,
    render_page,
    resolve_link,
)
from okf_reader.core.top_bar import TopBarSpec

if TYPE_CHECKING:
    from okf_reader.core.actions import PageAction, PageActionProvider
    from okf_reader.core.backgrounds import ImageProvider

BODY_LINE_HEIGHT = 1.25
# Tables come from the core space-padded to aligned columns (see TableBlock), which
# only lines up in a monospace face. RobotoMono ships with Kivy (regular only —
# another reason table headers are colored, not bold).
TABLE_FONT_NAME = "RobotoMono-Regular"
BODY_PADDING = (16, 8, 24, 16)  # left, top, right, bottom
BODY_BLOCK_SPACING = 12
POPUP_PADDING = 12
TREE_PANEL_WIDTH = 0.25  # fraction of the window; the page panel gets the rest
# Multiplied into the background image (Kivy Image.color) so white text stays
# readable over it — the same darkening mechanism the Barks Reader's kv files use.
WINDOW_BG_TINT = (0.30, 0.30, 0.30, 1)
# Translucent black drawn over the background image behind the tree panel only,
# softening it a touch further there than in the reading pane.
TREE_PANEL_SCRIM = (0, 0, 0, 0.25)
# Translucent rounded band drawn behind each page *section* (a heading plus
# everything under it, up to the next heading) so body text keeps its contrast
# over vivid background panels — the Barks Reader's BgColorLabel idiom
# (main_screen.kv <BackgroundColor@Widget>), in Python. The alpha is the
# delineation-strength knob.
BLOCK_BG_COLOR = (0.01, 0.01, 0.01, 0.30)
# Band alpha while the Contrast toggle is down: near-opaque, so the text reads
# as if on a plain dark page whatever the background image is doing.
BLOCK_BG_CONTRAST_ALPHA = 0.9
BLOCK_BG_RADIUS = 6  # dp
SECTION_PADDING = (10, 8)  # inset of a section's text from its band edge
SECTION_BLOCK_SPACING = 8  # between blocks inside one banded section
# The action-bar strip across the top, mirroring the Barks Reader's kv idiom
# (main_screen.kv / comic_book_reader.kv): a dark opaque band holding the app
# icon, the markup heading, and the right-aligned action buttons behind a thin
# separator. What fills it comes from the embedding app via TopBarSpec.
TOP_BAR_BG_COLOR = (0.12, 0.12, 0.12, 1)  # standard ActionBar background color
TOP_BAR_SEPARATOR_COLOR = (0.3, 0.3, 0.3, 1)
TOP_BAR_ICON_WIDTH = 70  # dp, the Barks bars' icon-container width
# Selection band: the link blue (render.LINK_COLOR, 4ea1ff) at low alpha — an
# accent already in the palette, translucent enough that the gold node label
# keeps its contrast. (The Barks Reader's magenta shouted over this page's
# muted grey/gold/blue scheme.)
TREE_SELECTED_COLOR = (0.306, 0.631, 1.0, 0.35)
# Barks Reader tree convention: group nodes bold white, titles yellow. Here:
# directories bold white; concept pages in the page-heading gold (ffd54a).
TREE_DIR_TEXT_COLOR = (1, 1, 1, 1)
TREE_CONCEPT_TEXT_COLOR = (1.0, 0.835, 0.29, 1.0)


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
        start_page: Path | None = None,
        action_provider: PageActionProvider | None = None,
        top_bar: TopBarSpec | None = None,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)
        self.bundle = bundle
        self.history: list[_HistoryEntry] = []
        self._anchors: dict[str, str] = {}  # "fn:<label>" -> the definition block's markup
        self._syncing_tree = False  # True while _sync_tree_to selects programmatically
        self._image_provider = image_provider
        self._table_rewriter = table_rewriter
        self._action_provider = action_provider
        self._page_action: PageAction | None = None
        self._band_colors: list[Color] = []  # the current page's section-band Colors

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

        self.tree_scroll = _scroll_view(size_hint=(TREE_PANEL_WIDTH, 1), do_scroll_x=False)
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

        self.body_scroll = _scroll_view(size_hint=(1 - TREE_PANEL_WIDTH, 1), do_scroll_x=False)
        self.body = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=BODY_BLOCK_SPACING,
            padding=BODY_PADDING,
        )
        self.body.bind(minimum_height=self.body.setter("height"))
        self.body_scroll.add_widget(self.body)
        content.add_widget(self.body_scroll)

        # Lazy: load only the bundle's top level (all tiers) now; each directory's
        # children are read on first expansion (see _on_dir_open). This keeps startup
        # cheap even though the full bundle is ~900 files across ~200 dirs.
        self._add_tree_nodes(list_children(bundle), None)

        # Startup, before any page is shown: empty frontmatter matches no title, so
        # the provider's fallback pool supplies a random story image.
        self._update_background({}, bundle)

        if start_page is not None:  # open on a caller-chosen page (tree syncs itself)
            self._show(start_page, push=True)

    def _build_top_bar(self, spec: TopBarSpec) -> BoxLayout:
        """Build the action-bar strip: app icon, markup heading, right-edge buttons.

        A Python rendition of the Barks Reader's kv action-bar idiom. Creates
        ``back_btn``, ``contrast_btn`` and ``action_btn`` as it goes.
        """
        bar = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=round(dp(spec.height)),
            padding=(dp(2), 0, dp(5), 0),
            spacing=dp(5),
        )
        with bar.canvas.before:  # ty: ignore[unresolved-attribute]
            Color(rgba=TOP_BAR_BG_COLOR)
            bar_bg = Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(
            pos=lambda _inst, pos: setattr(bar_bg, "pos", pos),
            size=lambda _inst, size: setattr(bar_bg, "size", size),
        )

        if spec.icon_path is not None:
            bar.add_widget(self._build_bar_icon(spec.icon_path))

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

        separator = Widget(size_hint_x=None, width=dp(1))
        with separator.canvas:  # ty: ignore[invalid-context-manager]
            Color(rgba=TOP_BAR_SEPARATOR_COLOR)
            separator_rect = Rectangle(pos=separator.pos, size=separator.size)
        separator.bind(
            pos=lambda _inst, pos: setattr(separator_rect, "pos", pos),
            size=lambda _inst, size: setattr(separator_rect, "size", size),
        )
        bar.add_widget(separator)

        # Quit leads the button group, as on the Barks main screen. With the OS
        # titlebar replaced by this bar, it is the window's only close control.
        if spec.close_icon_path is not None:
            quit_btn = ActionButton(icon=str(spec.close_icon_path), mipmap=True)
        else:
            quit_btn = Button(text="Quit", size_hint_x=None, width=dp(70))
        quit_btn.bind(on_release=lambda *_: App.get_running_app().stop())
        bar.add_widget(quit_btn)

        if spec.back_icon_path is not None:
            # ActionButton is the Barks bars' BarButton base: standalone it
            # renders as a dp(48) icon button on a flat action-item background.
            self.back_btn = ActionButton(icon=str(spec.back_icon_path), mipmap=True, disabled=True)
        else:
            self.back_btn = Button(text="< Back", size_hint_x=None, width=dp(90), disabled=True)
        self.back_btn.bind(on_release=lambda *_: self._go_back())
        bar.add_widget(self.back_btn)
        # Dials the section bands from their subtle default up to near-opaque
        # (BLOCK_BG_CONTRAST_ALPHA) when the background image fights the text.
        self.contrast_btn = ToggleButton(text="Contrast", size_hint_x=None, width=dp(90))
        self.contrast_btn.bind(state=lambda *_: self._apply_band_alpha())
        bar.add_widget(self.contrast_btn)
        # The page's contextual action (see PageActionProvider), hidden until a
        # page offers one.
        self.action_btn = Button(size_hint_x=None, width=0, opacity=0, disabled=True)
        self.action_btn.bind(on_release=lambda *_: self._run_page_action())
        bar.add_widget(self.action_btn)
        return bar

    def _build_bar_icon(self, icon_path: Path) -> RelativeLayout:
        """Build the bar's left-edge app icon: an image under a transparent hitbox.

        The main-screen pattern — pressing dims the image, releasing shows the
        bundle's home page.
        """
        icon_box = RelativeLayout(size_hint=(None, 1), width=dp(TOP_BAR_ICON_WIDTH))
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

    def _set_page_action(self, action: PageAction | None) -> None:
        """Show the contextual bar button for ``action``, or hide it for None."""
        self._page_action = action
        if action is None:
            self.action_btn.width = 0
            self.action_btn.opacity = 0
            self.action_btn.disabled = True
        else:
            self.action_btn.text = action.label
            self.action_btn.width = dp(120)
            self.action_btn.opacity = 1
            self.action_btn.disabled = False

    def _run_page_action(self) -> None:
        if self._page_action is not None:
            self._page_action.run()

    def _go_back(self) -> None:
        if len(self.history) > 1:
            self.history.pop()
            entry = self.history[-1]
            self._show(entry.path, push=False, scroll_y=entry.scroll_y)

    def _update_background(self, frontmatter: dict, path: Path) -> None:
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
        self._set_page_action(
            self._action_provider.action_for(page.frontmatter, path)
            if self._action_provider is not None
            else None
        )
        self.body.clear_widgets()
        self._band_colors.clear()  # their sections were just discarded
        self._anchors = {}
        # Blocks group into banded sections: each heading starts a new section
        # box holding it and everything up to the next heading (see BLOCK_BG_COLOR).
        section: BoxLayout | None = None
        for blk in page.blocks:
            if isinstance(blk, TableBlock):
                if section is None:
                    section = self._new_section()
                section.add_widget(self._table_widget(blk))
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
            if blk.anchor:
                self._anchors[blk.anchor] = blk.markup
            if section is None or blk.heading:
                section = self._new_section()
            section.add_widget(lbl)
        # Fresh pages open at the top; Back passes the offset the page was left at.
        self.body_scroll.scroll_y = scroll_y
        if scroll_y != 1:
            # The labels take their texture sizes over the next frame, shifting the
            # normalized offset; re-assert it once the layout has settled.
            Clock.schedule_once(lambda _dt: setattr(self.body_scroll, "scroll_y", scroll_y), 0)

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

    def _band_alpha(self) -> float:
        """Return the section-band alpha the Contrast toggle currently calls for."""
        if self.contrast_btn.state == "down":
            return BLOCK_BG_CONTRAST_ALPHA
        return BLOCK_BG_COLOR[3]

    def _apply_band_alpha(self) -> None:
        """Retune the current page's section bands to the toggle's alpha."""
        alpha = self._band_alpha()
        for color in self._band_colors:
            color.a = alpha

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
        start_page: Path | None = None,
        action_provider: PageActionProvider | None = None,
        top_bar: TopBarSpec | None = None,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)
        self._bundle = bundle
        self._image_provider = image_provider
        self._table_rewriter = table_rewriter
        self._start_page = start_page
        self._action_provider = action_provider
        self._top_bar = top_bar
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
        )
        return self._viewer

    def on_start(self) -> None:
        """Replace the OS window titlebar with the viewer's action bar.

        The Barks Reader convention (BarksReaderApp._set_custom_title_bar):
        only the bar's title area becomes the drag region, so the icon and
        buttons stay clickable. Kivy needs the realized window, hence on_start;
        where the system disallows it, the OS titlebar simply stays.
        """
        from kivy.core.window import Window  # noqa: PLC0415 — needs the realized window

        assert self._viewer is not None
        Window.custom_titlebar = True
        if not Window.set_custom_titlebar(self._viewer.bar_drag_region):
            print("warning: custom titlebar not allowed on this system")  # noqa: T201


def run(
    bundle: Path,
    image_provider: ImageProvider | None = None,
    table_rewriter: TableRewriter | None = None,
    start_page: Path | None = None,
    action_provider: PageActionProvider | None = None,
    top_bar: TopBarSpec | None = None,
) -> None:
    """Launch the standalone OKF reader on ``bundle`` (blocks until the window closes)."""
    OKFApp(
        bundle,
        image_provider=image_provider,
        table_rewriter=table_rewriter,
        start_page=start_page,
        action_provider=action_provider,
        top_bar=top_bar,
    ).run()
