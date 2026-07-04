"""Kivy viewer for an OKF bundle — the UI layer of okf_reader.

Binds the Kivy-free core (okf_reader.core.render) to native widgets: a lazily
populated tree of the bundle's tiers on the left, the rendered page on the right.
Links and footnotes are handled via the core's ``resolve_link`` and each page
`Block`'s anchor. ``run(bundle)`` launches the standalone app; the CLI entry point
is scripts/read_okf.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.treeview import TreeView, TreeViewLabel

from okf_reader.core.render import BundleDir, list_children, render_page, resolve_link

HIGHLIGHT_COLOR = "ffe066"  # the footnote definition you just jumped to (applied at tap time)


class OKFViewer(BoxLayout):
    def __init__(self, bundle: Path, **kwargs) -> None:  # noqa: ANN003
        super().__init__(orientation="horizontal", spacing=8, padding=8, **kwargs)
        self.bundle = bundle
        self.history: list[Path] = []
        self._anchors: dict[str, Any] = {}  # "fn:<label>" -> the definition's Label widget

        tree_scroll = ScrollView(size_hint=(0.32, 1))
        self.tree = TreeView(root_options={"text": f"OKF: {bundle.name}"}, hide_root=False)
        # bind passes (treeview, selected_node); we only want the node (2nd arg)
        self.tree.bind(selected_node=lambda *args: self._on_node(args[1]))
        tree_scroll.add_widget(self.tree)
        self.add_widget(tree_scroll)

        right = BoxLayout(orientation="vertical", size_hint=(0.68, 1), spacing=4)
        bar = BoxLayout(size_hint_y=None, height=32, spacing=6)
        self.back_btn = Button(text="< Back", size_hint_x=None, width=90, disabled=True)
        self.back_btn.bind(on_release=lambda *_: self._go_back())
        bar.add_widget(self.back_btn)
        right.add_widget(bar)

        self.body_scroll = ScrollView()
        self.body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=8, padding=(4, 4))
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
                tv = self.tree.add_node(TreeViewLabel(text=f"[{node.name}]"), parent)
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
        path = getattr(node, "file_path", None)
        if path:
            self._show(Path(path), push=True)

    def _go_back(self) -> None:
        if len(self.history) > 1:
            self.history.pop()
            self._show(self.history[-1], push=False)

    def _show(self, path: Path, *, push: bool) -> None:
        if push:
            self.history.append(path)
        self.back_btn.disabled = len(self.history) <= 1
        page = render_page(path.read_text(encoding="utf-8"))
        self.body.clear_widgets()
        self._anchors = {}
        for blk in page.blocks:
            lbl = Label(
                text=blk.markup,
                markup=True,
                font_size=blk.font_size,
                halign="left",
                valign="top",
                size_hint_y=None,
            )
            lbl.bind(width=lambda inst, w: inst.setter("text_size")(inst, (w, None)))
            lbl.bind(texture_size=lambda inst, ts: inst.setter("height")(inst, ts[1]))
            lbl._page_path = path  # noqa: SLF001
            lbl.bind(on_ref_press=self._on_ref)
            if blk.anchor:
                lbl._orig_markup = blk.markup  # noqa: SLF001  (restore target after highlight)
                self._anchors[blk.anchor] = lbl
            self.body.add_widget(lbl)
        self.body_scroll.scroll_y = 1

    def _on_ref(self, label, ref: str) -> None:  # noqa: ANN001
        if ref.startswith("fn:"):
            widget = self._anchors.get(ref)  # tapped [^id] → scroll to + highlight its def
            if widget is not None:
                self.body_scroll.scroll_to(widget, padding=10)
                self._highlight(widget)
            return
        target = resolve_link(label._page_path, ref, self.bundle)  # noqa: SLF001
        if target:
            self._show(target, push=True)

    def _highlight(self, widget) -> None:  # noqa: ANN001
        """Tint the jumped-to footnote definition, clearing any previous one."""
        for w in self._anchors.values():
            orig = getattr(w, "_orig_markup", None)
            if orig is not None:
                w.text = orig  # restore all defs (idempotent if tapped twice)
        orig = getattr(widget, "_orig_markup", widget.text)
        widget.text = f"[color={HIGHLIGHT_COLOR}]{orig}[/color]"


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
