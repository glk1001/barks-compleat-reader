# ruff: noqa: PLR2004, C901, PLR0912
# (branchy markdown token dispatch; small magic font sizes in render_page)
"""Kivy-free OKF render + bundle-model layer — the core of the okf_reader package.

No Kivy import, no GUI. Turns an OKF page (markdown + YAML frontmatter) into
`Block`s of **Kivy markup** (plain strings — kivy-flavoured, but no kivy
dependency), and walks a bundle directory into a `BundleDir`/`ConceptNode` tree:

  * markdown is tokenised with **markdown-it-py** (+ the `footnote` plugin);
    `render_page()` is pure — same text in, same `Page` out — so it is
    unit-testable in isolation;
  * `resolve_link()` resolves both OKF link forms (SPEC §5): relative links
    against the page's dir, absolute `/…` links against the bundle root, both
    percent-decoded, bounds-checked under the bundle, and restricted to ``.md``
    concept documents;
  * `list_children()` / `load_bundle_tree()` enumerate a bundle one level at a
    time (lazy) or fully (eager), skipping reserved and hidden entries.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin

if TYPE_CHECKING:
    from pathlib import Path

# Colors baked into the emitted Kivy markup (hex, no leading '#'). Interaction-
# time colors (e.g. footnote highlight) belong to the UI layer, not here.
LINK_COLOR = "4ea1ff"
CODE_COLOR = "c0a0ff"
HEADING_SIZES = {"h1": 30, "h2": 24, "h3": 20, "h4": 18, "h5": 16, "h6": 16}
# Kivy's [sup] halves the current font size; the inner [size=…] overrides the
# shrink so markers stay readable. Kivy pins superscript glyphs near the top of
# the line box, so the visible "raise" is line height minus marker height —
# this size is the only knob for both marker size and how raised it looks.
FOOTNOTE_REF_SIZE = 11

# Paragraphs containing this marker are editorial provenance notes, not content
# (the barks-wiki bundle opens most concepts with a blockquote along the lines of
# "_LLM-owned synthesis. Do not hand-edit ..._"), so render_page drops them.
PROVENANCE_MARKER = "LLM-owned"


# --------------------------------------------------------------------------- model


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


@dataclass(frozen=True)
class ConceptNode:
    """A leaf in the bundle tree: one concept document and its display title."""

    path: Path
    title: str


@dataclass(frozen=True)
class BundleDir:
    """A directory node: its child directories and concept documents, in listing order."""

    path: Path
    name: str
    children: tuple[BundleDir | ConceptNode, ...] = ()


# --------------------------------------------------------------------------- render


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
            marker = _esc(f"[{label}]")
            out.append(
                f"[ref=fn:{label}][color={LINK_COLOR}]"
                f"[sup][size={FOOTNOTE_REF_SIZE}]{marker}[/size][/sup][/color][/ref]"
            )
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
            markup = _inline(tokens[i + 1].children or [])
            if PROVENANCE_MARKER not in markup:  # drop editorial provenance notes
                blocks.append(Block(prefix + markup))
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
    """Resolve a markdown href to a navigable OKF concept, bounded to the bundle.

    Handles both OKF link forms (SPEC §5): an **absolute** bundle-relative href
    (``/concept/x.md``) resolves against the bundle root, a **relative** href
    against the page's directory. Link targets are URLs, so the path is **percent-decoded**
    (``%20`` → space, ``%23`` → ``#``); the heading fragment is split off the still-
    encoded href first, so an in-path ``#`` written ``%23`` survives while a real
    ``#anchor`` is dropped. Only ``.md`` concept documents are navigable — links to
    other assets (``.html``, images) or directories return None, as do external
    (scheme-bearing) links and anything outside the bundle.
    """
    if "://" in href:  # external link (carries a scheme)
        return None
    path_part = urllib.parse.unquote(href.split("#", 1)[0])  # fragment off, then decode
    if not path_part:
        return None
    base = bundle if path_part.startswith("/") else page_path.parent
    target = (base / path_part.lstrip("/")).resolve()
    if target.suffix != ".md":  # only OKF concept documents are rendered as pages
        # KNOWN LIMITATION (intentional): the bundle's source/web tier — notably the
        # inducks mirror — links to raw scraped .html assets, not OKF concepts, so
        # those links deliberately do not navigate. The sibling "<page>_files/index.md"
        # is only an auto-generated asset manifest, not readable content. Making inducks
        # useful is bundle curation (barks-wiki), not a reader fix. Revisit if/when we
        # add "open external/asset links in the system browser".
        return None
    try:
        target.relative_to(bundle.resolve())
    except ValueError:
        return None
    return target if target.is_file() else None


# --------------------------------------------------------------------------- bundle tree

RESERVED_FILES = ("index.md", "log.md")  # SPEC §3.1 — reserved, never concept documents


def concept_title(path: Path) -> str:
    """Display title for a concept file: its frontmatter ``title``, else the filename stem."""
    fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    title = fm.get("title")
    return title if isinstance(title, str) and title else path.stem


def list_children(directory: Path) -> list[BundleDir | ConceptNode]:
    """Immediate children of a bundle directory, in name order — one level only.

    Subdirectories come back as `BundleDir`s **unexpanded** (empty ``children``);
    call `list_children` again on a subdir's ``path`` to descend. Non-reserved
    ``.md`` files become `ConceptNode` leaves (``index.md``/``log.md`` are reserved
    — SPEC §3.1 — and skipped). Frontmatter is read only for the concepts directly
    in ``directory``, so a consumer can populate a tree lazily one level at a time.
    A ``directory`` that is not a directory yields an empty list (SPEC §9).
    """
    children: list[BundleDir | ConceptNode] = []
    if directory.is_dir():
        for child in sorted(directory.iterdir()):
            if child.name.startswith("."):
                continue  # skip hidden entries (e.g. .obsidian) — not OKF content
            if child.is_dir():
                children.append(BundleDir(child, child.name))
            elif child.suffix == ".md" and child.name not in RESERVED_FILES:
                children.append(ConceptNode(child, concept_title(child)))
    return children


def load_bundle_tree(root: Path) -> BundleDir:
    """Eagerly walk ``root`` into a fully-expanded Kivy-free tree.

    Like `list_children` but recursive: every subdirectory is descended and its
    `BundleDir.children` populated. A ``root`` that is not a directory yields an
    empty `BundleDir` (tolerant consumption, SPEC §9). Prefer `list_children` for
    interactive/lazy consumers; use this for a whole-bundle walk (e.g. search).
    """
    children = tuple(
        load_bundle_tree(child.path) if isinstance(child, BundleDir) else child
        for child in list_children(root)
    )
    return BundleDir(root, root.name, children)
