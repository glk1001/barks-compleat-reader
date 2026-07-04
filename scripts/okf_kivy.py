#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["kivy>=2.3", "pyyaml>=6", "markdown-it-py>=3", "mdit-py-plugins>=0.4"]
# ///
# ruff: noqa: T201, PLR2004, C901, PLR0912, PLC0415
# (spike: T201 prints; branchy token dispatch; kivy imported lazily so --selftest needs no GUI deps)
# pyright: reportMissingImports=false
"""Rudimentary Kivy reader for the OKF bundle — a reference spike, not production code.

Demonstrates the in-app integration described in
`okf/concept/todo/integrate-wiki-into-reader-app.md`, updated for the bundle's move from
`[[wikilinks]]` to **relative markdown links**:

  * markdown is tokenised with **markdown-it-py** (+ the `footnote` plugin) and rendered to native
    Kivy widgets (no webview, no fragile regex) — `render_page()` is pure and `--selftest`-able;
  * a tapped **link** resolves by **path-join** — relative `[text](rel/path.md)` against the
    page's dir, absolute `[text](/concept/x.md)` against the bundle root (OKF SPEC §5) —
    bounds-checked under the bundle, then loaded (a small back-stack gives Back navigation);
  * **footnotes** `[^id]` render as a tappable superscript that scrolls to **and highlights**
    its definition block (collected once at the foot; the highlight clears on the next jump);
  * **image refs** (absolute Tier-1 paths, never embedded) render as a placeholder line.

Run the GUI:   uv run scripts/okf_kivy.py [bundle-dir]
Self-test:     uv run scripts/okf_kivy.py --selftest okf/concept/glossary/india.md
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin  # ty: ignore[unresolved-import]

LINK_COLOR = "4ea1ff"
CODE_COLOR = "c0a0ff"
HIGHLIGHT_COLOR = "ffe066"  # the footnote definition you just jumped to
HEADING_SIZES = {"h1": 30, "h2": 24, "h3": 20, "h4": 18, "h5": 16, "h6": 16}


# --------------------------------------------------------------------------- pure render layer


@dataclass
class Block:
    """One rendered block: a Kivy-markup string at a given font size."""

    markup: str
    font_size: int = 16
    anchor: str | None = None  # e.g. "fn:db" — a scroll target for a tapped footnote marker


@dataclass
class Page:
    """A rendered page: parsed frontmatter plus body and footnote blocks."""

    frontmatter: dict
    blocks: list[Block] = field(default_factory=list)


def _md() -> MarkdownIt:
    return MarkdownIt("commonmark").use(footnote_plugin).enable("table")


def _esc(text: str) -> str:
    """Escape the three characters that are special to Kivy markup."""
    return text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def _inline(tokens: list) -> str:
    """Render an inline token stream (a token's ``.children``) to Kivy markup."""
    out: list[str] = []
    for t in tokens:
        tp = t.type
        if tp == "text":
            out.append(_esc(t.content))
        elif tp == "softbreak":
            out.append(" ")
        elif tp == "hardbreak":
            out.append("\n")
        elif tp == "strong_open":
            out.append("[b]")
        elif tp == "strong_close":
            out.append("[/b]")
        elif tp == "em_open":
            out.append("[i]")
        elif tp == "em_close":
            out.append("[/i]")
        elif tp == "code_inline":
            out.append(f"[color={CODE_COLOR}]{_esc(t.content)}[/color]")
        elif tp == "link_open":
            href = t.attrGet("href") or ""
            out.append(f"[ref={href}][color={LINK_COLOR}][u]")
        elif tp == "link_close":
            out.append("[/u][/color][/ref]")
        elif tp == "footnote_ref":
            label = t.meta.get("label") or str(t.meta.get("id", ""))
            sup = _esc(f"[{label}]")
            out.append(f"[ref=fn:{label}][color={LINK_COLOR}][sup]{sup}[/sup][/color][/ref]")
        elif tp == "image":
            alt = t.content or t.attrGet("src") or "image"
            out.append(f"[i]▨ image: {_esc(alt)}[/i]")
    return "".join(out)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a page into (frontmatter dict, body markdown)."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                fm = {}
            return (fm if isinstance(fm, dict) else {}), parts[2].strip()
    return {}, text


def render_page(text: str) -> Page:
    """Parse a page's frontmatter and render its body + footnotes to Kivy-markup blocks."""
    fm, body = parse_frontmatter(text)
    tokens = _md().parse(body)
    blocks: list[Block] = []
    indent = 0
    pending_bullet = ""
    i, n = 0, len(tokens)
    while i < n:
        t = tokens[i]
        tp = t.type
        if tp == "heading_open":
            blocks.append(
                Block(
                    "[b]" + _inline(tokens[i + 1].children or []) + "[/b]",
                    HEADING_SIZES.get(t.tag, 16),
                )
            )
            i += 3
            continue
        if tp == "paragraph_open":
            base = pending_bullet or ("    " * indent if indent else "")
            prefix = "    " * max(indent - 1, 0) + base
            pending_bullet = ""
            blocks.append(Block(prefix + _inline(tokens[i + 1].children or [])))
            i += 3
            continue
        if tp == "footnote_open":
            # Render the whole footnote definition (up to its footnote_close) as one block,
            # tagged with an anchor so a tapped [^label] marker can scroll to it. Skipping to
            # footnote_close also stops the inner paragraph being re-rendered as a stray block.
            label = t.meta.get("label") or str(t.meta.get("id", ""))
            parts: list[str] = []
            j = i + 1
            while j < n and tokens[j].type != "footnote_close":
                if tokens[j].type == "inline":
                    parts.append(_inline(tokens[j].children or []))
                j += 1
            blocks.append(
                Block(f"[b][{_esc(label)}][/b] " + " ".join(parts), 13, anchor=f"fn:{label}")
            )
            i = j + 1
            continue
        if tp in ("bullet_list_open", "ordered_list_open", "blockquote_open"):
            indent += 1
        elif tp in ("bullet_list_close", "ordered_list_close", "blockquote_close"):
            indent = max(indent - 1, 0)
        elif tp == "list_item_open":
            pending_bullet = "    " * max(indent - 1, 0) + "•  "
        elif tp in ("fence", "code_block"):
            blocks.append(Block(f"[color={CODE_COLOR}]{_esc(t.content.rstrip())}[/color]", 14))
        elif tp == "hr":
            blocks.append(Block("─" * 40))
        elif tp == "footnote_block_open":
            blocks.append(Block("[b]Footnotes[/b]", 18))
        i += 1
    return Page(fm, blocks)


# --------------------------------------------------------------------------- link resolution


def resolve_link(page_path: Path, href: str, bundle: Path) -> Path | None:
    """Resolve a markdown href against the page, bounded to the bundle.

    Handles both OKF link forms (SPEC §5): an **absolute** bundle-relative href
    (``/concept/x.md``) resolves against the bundle root, a **relative** href
    against the page's directory. Returns the target file, or None for external
    links or anything outside the bundle.
    """
    href = href.split("#", 1)[0]  # drop any heading anchor
    if not href or "://" in href:
        return None
    base = bundle if href.startswith("/") else page_path.parent
    target = (base / href.lstrip("/")).resolve()
    try:
        target.relative_to(bundle.resolve())
    except ValueError:
        return None
    return target if target.is_file() else None


# --------------------------------------------------------------------------- Kivy UI


def _build_app(bundle: Path):  # noqa: ANN202  (kivy types are dynamic)
    from kivy.app import App
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.treeview import TreeView, TreeViewLabel

    class OKFViewer(BoxLayout):
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            super().__init__(orientation="horizontal", spacing=8, padding=8, **kwargs)
            self.bundle = bundle
            self.history: list[Path] = []
            self._anchors: dict[str, Any] = {}  # "fn:<label>" -> the definition's Label widget

            tree_scroll = ScrollView(size_hint=(0.32, 1))
            self.tree = TreeView(root_options={"text": "OKF concept/"}, hide_root=False)
            # bind passes (treeview, selected_node); we only want the node (2nd arg)
            self.tree.bind(selected_node=lambda *args: self._on_node(args[1]))
            tree_scroll.add_widget(self.tree)
            self.add_widget(tree_scroll)

            right = BoxLayout(orientation="vertical", size_hint=(0.68, 1), spacing=4)
            bar = BoxLayout(size_hint_y=None, height=32, spacing=6)
            self.back_btn = Button(text="< Back", size_hint_x=None, width=90, disabled=True)
            self.back_btn.bind(on_release=lambda *_: self._go_back())
            self.meta = Label(halign="left", valign="middle", markup=True)
            self.meta.bind(size=self.meta.setter("text_size"))
            bar.add_widget(self.back_btn)
            bar.add_widget(self.meta)
            right.add_widget(bar)

            self.body_scroll = ScrollView()
            self.body = BoxLayout(
                orientation="vertical", size_hint_y=None, spacing=8, padding=(4, 4)
            )
            self.body.bind(minimum_height=self.body.setter("height"))
            self.body_scroll.add_widget(self.body)
            right.add_widget(self.body_scroll)
            self.add_widget(right)

            self._populate(bundle / "concept", None)

        def _populate(self, path: Path, parent) -> None:  # noqa: ANN001
            if not path.is_dir():
                return
            for child in sorted(path.iterdir()):
                if child.is_dir():
                    node = self.tree.add_node(TreeViewLabel(text=f"[{child.name}]"), parent)
                    self._populate(child, node)
                elif child.suffix == ".md" and child.name not in ("index.md", "log.md"):
                    # index.md / log.md are reserved (SPEC §3.1) — not concepts.
                    fm, _ = parse_frontmatter(child.read_text(encoding="utf-8"))
                    node = TreeViewLabel(text=fm.get("title", child.stem))
                    node.file_path = child
                    self.tree.add_node(node, parent)

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
            fm = page.frontmatter
            self.meta.text = (
                f"[b]{fm.get('title', path.stem)}[/b]   [color=999999]"
                f"{fm.get('type', '?')} · {fm.get('description', '')}[/color]"
            )
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
        def build(self) -> OKFViewer:
            self.title = "OKF Wiki Reader (spike)"
            return OKFViewer()

    return OKFApp()


def _selftest(path: Path) -> int:
    page = render_page(path.read_text(encoding="utf-8"))
    print(f"frontmatter: {sorted(page.frontmatter)}")
    print(f"blocks: {len(page.blocks)}")
    refs = sum(blk.markup.count("[ref=") for blk in page.blocks)
    print(f"tappable refs (links + footnotes): {refs}")
    for blk in page.blocks[:6]:
        print(f"  ({blk.font_size:>2}) {blk.markup[:90]}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "--selftest":
        return _selftest(Path(argv[2]))
    bundle = Path(argv[1]) if len(argv) >= 2 else Path("okf")
    if not bundle.is_dir():
        print(f"error: bundle {bundle} not found", file=sys.stderr)
        return 2
    _build_app(bundle).run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
