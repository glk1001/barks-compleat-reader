"""Kivy viewer for an OKF bundle — the UI layer of okf_reader.

Binds the Kivy-free core (okf_reader.core.render) to native widgets: a lazily
populated tree of the bundle's tiers on the left, the rendered page on the right.
Links resolve via the core's ``resolve_link``; tapping a footnote marker shows its
definition (keyed by the page `Block`'s anchor) in a dismiss-on-tap popup.
``run(bundle)`` launches the standalone app; the CLI entry point is
scripts/read_okf.py.
"""

from __future__ import annotations

from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.treeview import TreeView, TreeViewLabel

from okf_reader.core.render import (
    BundleDir,
    dir_title,
    list_children,
    render_page,
    resolve_link,
)

BODY_LINE_HEIGHT = 1.25
BODY_PADDING = (16, 8, 24, 16)  # left, top, right, bottom
BODY_BLOCK_SPACING = 12
POPUP_PADDING = 12


class OKFViewer(BoxLayout):
    def __init__(self, bundle: Path, **kwargs) -> None:  # noqa: ANN003
        super().__init__(orientation="horizontal", spacing=8, padding=8, **kwargs)
        self.bundle = bundle
        self.history: list[Path] = []
        self._anchors: dict[str, str] = {}  # "fn:<label>" -> the definition block's markup
        self._syncing_tree = False  # True while _sync_tree_to selects programmatically

        self.tree_scroll = ScrollView(size_hint=(0.32, 1))
        self.tree = TreeView(
            root_options={"text": dir_title(bundle)},
            hide_root=False,
            # Grow with the content instead of squeezing into the viewport — a
            # ScrollView only scrolls a child that is taller than itself.
            size_hint_y=None,
        )
        self.tree.bind(minimum_height=self.tree.setter("height"))
        # bind passes (treeview, selected_node); we only want the node (2nd arg)
        self.tree.bind(selected_node=lambda *args: self._on_node(args[1]))
        self.tree_scroll.add_widget(self.tree)
        self.add_widget(self.tree_scroll)

        right = BoxLayout(orientation="vertical", size_hint=(0.68, 1), spacing=4)
        bar = BoxLayout(size_hint_y=None, height=32, spacing=6)
        self.back_btn = Button(text="< Back", size_hint_x=None, width=90, disabled=True)
        self.back_btn.bind(on_release=lambda *_: self._go_back())
        bar.add_widget(self.back_btn)
        right.add_widget(bar)

        self.body_scroll = ScrollView()
        self.body = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=BODY_BLOCK_SPACING,
            padding=BODY_PADDING,
        )
        self.body.bind(minimum_height=self.body.setter("height"))
        self.body_scroll.add_widget(self.body)
        right.add_widget(self.body_scroll)
        self.add_widget(right)

        # Lazy: load only the bundle's top level (all tiers) now; each directory's
        # children are read on first expansion (see _on_dir_open). This keeps startup
        # cheap even though the full bundle is ~900 files across ~200 dirs.
        self._add_tree_nodes(list_children(bundle), None)

    def _add_tree_nodes(self, nodes, parent) -> None:  # noqa: ANN001
        # Bind one level of the Kivy-free bundle model (okf_reader.core list_children)
        # to TreeView widgets; the frontmatter reads for this level already happened there.
        for node in nodes:
            if isinstance(node, BundleDir):
                tv = self.tree.add_node(TreeViewLabel(text=node.title or node.name), parent)
                tv.is_leaf = False  # show a disclosure triangle; real children load on open
                tv.bundle_path = node.path
                tv.loaded = False
                tv.bind(is_open=self._on_dir_open)
            else:  # ConceptNode
                tv = TreeViewLabel(text=node.title)
                tv.file_path = node.path
                self.tree.add_node(tv, parent)

    def _on_dir_open(self, dir_node, is_open) -> None:  # noqa: ANN001
        # Fires on both open and close; populate a directory's children once, lazily.
        if is_open and not dir_node.loaded:
            dir_node.loaded = True
            self._add_tree_nodes(list_children(dir_node.bundle_path), dir_node)

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
            self._show(self.history[-1], push=False)

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

    def _show(self, path: Path, *, push: bool) -> None:
        if push:
            self.history.append(path)
        self.back_btn.disabled = len(self.history) <= 1
        self._sync_tree_to(path)
        page = render_page(path.read_text(encoding="utf-8"))
        self.body.clear_widgets()
        self._anchors = {}
        for blk in page.blocks:
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
            self.body.add_widget(lbl)
        self.body_scroll.scroll_y = 1

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
    def __init__(self, bundle: Path, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self._bundle = bundle

    def build(self) -> OKFViewer:
        self.title = f"OKF Reader — {self._bundle.name}"
        return OKFViewer(self._bundle)


def run(bundle: Path) -> None:
    """Launch the standalone OKF reader on ``bundle`` (blocks until the window closes)."""
    OKFApp(bundle).run()
