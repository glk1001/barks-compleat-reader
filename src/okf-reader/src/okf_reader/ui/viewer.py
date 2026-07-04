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
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.treeview import TreeView, TreeViewLabel

from okf_reader.core.render import BundleDir, list_children, render_page, resolve_link

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
