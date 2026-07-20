# ruff: noqa: C901, PLR0912, PLR0915
# (branchy markdown token dispatch in render_page and _inline)
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
    time (lazy) or fully (eager), skipping reserved and hidden entries; children
    listed in a directory's reserved ``index.md`` keep that curated order.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from markdown_it.token import Token

# Colors baked into the emitted Kivy markup (hex, no leading '#'). Interaction-
# time colors (e.g. footnote highlight) belong to the UI layer, not here.
LINK_COLOR = "4ea1ff"
CODE_COLOR = "c0a0ff"
# Softened gold, one step warmer than the Barks Reader's pure title yellow
# (tree_view_nodes.TITLE_LABEL_COLOR) — comic caption feel without the glare,
# distinct from links (blue) and code (violet).
HEADING_COLOR = "ffd54a"
HEADING_SIZES = {"h1": 30, "h2": 24, "h3": 20, "h4": 18, "h5": 16, "h6": 16}
# Kivy's [sup] halves the current font size; the inner [size=…] overrides the
# shrink so markers stay readable. Kivy pins superscript glyphs near the top of
# the line box, so the visible "raise" is line height minus marker height —
# this size is the only knob for both marker size and how raised it looks.
FOOTNOTE_REF_SIZE = 11
# Footnote definitions are provenance metadata, not content, so they render
# dimmed: body text in a quiet grey, inline code (mostly file paths there) in a
# muted violet. Links keep LINK_COLOR — they are the section's working parts.
FOOTNOTE_TEXT_COLOR = "b0b0b0"
FOOTNOTE_CODE_COLOR = "9a8fc0"

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
    heading: bool = False  # headings begin a new visual section in consumers
    # List/blockquote nesting depth (0 = plain body text). A consumer renders an
    # indented block with a hanging indent: wrapped lines align under the text,
    # not the margin, with ``marker`` (the item's "•" / "3." glyph — empty for
    # continuation paragraphs and blockquotes) in its own column to the left.
    indent: int = 0
    marker: str = ""


@dataclass
class TableBlock:
    """One rendered table: rows of Kivy markup, space-padded to aligned columns.

    The padding is computed from each cell's *visible* length, so the columns
    line up only in a **monospace font** — the consumer must render the rows in
    one (and stack them with no extra spacing). A long cell wraps at
    `TABLE_COL_WRAP_WIDTH`, so a row may span several newline-joined lines; each
    row must be rendered as **one** label, both to keep those lines together and
    because a markup tag may legitimately span them. The header row (when
    present) is wrapped in the heading color rather than bold, because bold
    glyphs have different advances in a faked-bold monospace and would break
    the alignment.
    """

    rows: list[str]
    font_size: int = 13


class TableRewriter(Protocol):
    """Rewrites a parsed table before layout — the embedding app's presentation seam.

    Gets the header row and body rows as lists of cell Kivy-markup strings and
    returns replacements (e.g. an app folding a flag column into a decorated
    title column). okf_reader itself knows nothing about any particular table.
    """

    def rewrite(
        self, header: list[str], body: list[list[str]]
    ) -> tuple[list[str], list[list[str]]]:
        """Return the (header, body) to lay out in place of the parsed ones."""
        ...

    def wrap_widths(self, header: list[str]) -> list[int | None]:
        """Return per-column wrap-width overrides, aligned with ``header``.

        ``None`` (or a list shorter than the row) leaves that column on the
        default `TABLE_COL_WRAP_WIDTH`. Called with the *rewritten* header.
        """
        ...


@dataclass
class Page:
    """A rendered page: parsed frontmatter plus body and footnote blocks."""

    frontmatter: dict[str, Any]
    blocks: list[Block | TableBlock] = field(default_factory=list)


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
    # Human display title (see dir_title). Default "" keeps hand-built instances valid;
    # the model builders (list_children/load_bundle_tree) always fill it in.
    title: str = ""


# --------------------------------------------------------------------------- render


def _md() -> MarkdownIt:
    return MarkdownIt("commonmark").use(footnote_plugin).enable("table")


def _esc(text: str) -> str:
    """Escape the three characters that are special to Kivy markup."""
    return text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def _ref_quote(href: str) -> str:
    """Make an href safe to embed in a Kivy ``[ref=…]`` tag.

    A raw ``&``, ``[``, or ``]`` inside the tag corrupts the markup, but Kivy hands
    the ref value back verbatim on tap, so entity-escaping (``_esc``) would break
    navigation. Percent-encoding round-trips instead: `resolve_link` percent-decodes
    every href. markdown-it already encodes brackets in link destinations; ``&``
    it passes through raw. ``%`` is left alone to avoid double-encoding.
    """
    return href.replace("&", "%26").replace("[", "%5B").replace("]", "%5D")


def _inline(tokens: list[Token], code_color: str = CODE_COLOR, link_color: str = LINK_COLOR) -> str:
    """Render an inline token stream (a token's ``.children``) to Kivy markup.

    ``code_color`` recolors inline code spans only — footnote definitions pass
    their muted variant so code there stays quiet (see FOOTNOTE_CODE_COLOR).
    ``link_color`` recolors hyperlinks and footnote-reference markers, so an
    embedding app can theme them (default: the standalone LINK_COLOR).
    """
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
            out.append(f"[color={code_color}]{_esc(t.content)}[/color]")
        elif tp == "link_open":
            href = _ref_quote(str(t.attrGet("href") or ""))
            out.append(f"[ref={href}][color={link_color}][u]")
        elif tp == "link_close":
            out.append("[/u][/color][/ref]")
        elif tp == "footnote_ref":
            label = t.meta.get("label") or str(t.meta.get("id", ""))
            marker = _esc(f"[{label}]")
            out.append(
                f"[ref=fn:{label}][color={link_color}]"
                f"[sup][size={FOOTNOTE_REF_SIZE}]{marker}[/size][/sup][/color][/ref]"
            )
        elif tp == "image":
            alt = str(t.content or t.attrGet("src") or "image")
            out.append(f"[i]▨ image: {_esc(alt)}[/i]")
    return "".join(out)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a page into (frontmatter dict, body markdown).

    The delimiters must be whole ``---`` lines — a ``---`` inside a YAML value
    (or anywhere mid-line) is not a delimiter. Malformed or non-mapping YAML
    degrades to an empty dict (tolerant consumption, SPEC §9).
    """
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                try:
                    fm = yaml.safe_load("\n".join(lines[1:i])) or {}
                except yaml.YAMLError:
                    fm = {}
                return (fm if isinstance(fm, dict) else {}), "\n".join(lines[i + 1 :]).strip()
    return {}, text


def _footnote_block(tokens: list, start: int, link_color: str = LINK_COLOR) -> tuple[Block, int]:
    """Render the footnote definition at ``tokens[start]`` (its ``footnote_open``).

    The whole definition (up to its ``footnote_close``) becomes one block, tagged
    with an anchor so a tapped [^label] marker can show it. Consuming to
    ``footnote_close`` also stops the inner paragraph being re-rendered as a stray
    block; returns the block and the index just past ``footnote_close``.
    """
    t = tokens[start]
    label = t.meta.get("label") or str(t.meta.get("id", ""))
    parts: list[str] = []
    j = start + 1
    n = len(tokens)
    while j < n and tokens[j].type != "footnote_close":
        if tokens[j].type == "inline":
            parts.append(
                _inline(
                    tokens[j].children or [],
                    code_color=FOOTNOTE_CODE_COLOR,
                    link_color=link_color,
                )
            )
        j += 1
    # Dimmed as metadata (see FOOTNOTE_TEXT_COLOR); the inner link/code color
    # tags override the grey for their own spans.
    markup = f"[color={FOOTNOTE_TEXT_COLOR}][b][{_esc(label)}][/b] " + " ".join(parts) + "[/color]"
    block = Block(markup, 13, anchor=f"fn:{label}")
    return block, j + 1


_MARKUP_TAG_RE = re.compile(r"\[[^\[\]]*\]")  # a Kivy markup tag: [b], [/color], [ref=x] …
# One indivisible unit of a Kivy-markup string: a whole tag, a whole entity, or a
# single character — the pieces a wrap may never split.
_MARKUP_UNIT_RE = re.compile(r"\[[^\[\]]*\]|&amp;|&bl;|&br;|.")

# A cell longer than this wraps onto continuation lines within its column, so a
# handful of long titles (or a scraped mega-cell of flattened prose) don't pad
# every other row's column with dead space. 32 keeps the reference tables'
# title-plus-dates layouts within a comic-page-width window (the story-title
# columns' 90th percentile is ~25). A single unbreakable word longer than this
# stays whole and overflows its own row only.
TABLE_COL_WRAP_WIDTH = 32

# A column whose every non-empty body cell looks like a plain number — optional
# sign and currency mark, digits, thousands commas, an optional decimal part —
# is right-justified, the conventional alignment for figures.
_NUMERIC_CELL_RE = re.compile(r"-?\$?\d[\d,]*(?:\.\d+)?")


def _wrap_markup(markup: str, width: int) -> list[str]:
    """Greedy word-wrap of a Kivy-markup string at ``width`` visible characters.

    Breaks only at visible spaces — never inside a markup tag or entity, and a
    single word longer than ``width`` stays whole (its line overflows). Every
    returned line is markup-balanced: a tag pair the break would split is closed
    at the line's end and reopened on the next line, so a line never leaks its
    formatting into whatever the consumer appends after it (table rows append
    the row's remaining columns — see ``_table_block``).
    """
    words: list[tuple[str, int]] = []  # (markup, visible length)
    current, cur_len = "", 0
    for m in _MARKUP_UNIT_RE.finditer(markup):
        unit = m.group()
        if unit == " ":
            if current:
                words.append((current, cur_len))
                current, cur_len = "", 0
        else:
            current += unit
            cur_len += 0 if unit.startswith("[") else 1  # raw '[' only ever begins a tag
    if current:
        words.append((current, cur_len))
    lines: list[str] = []
    line, line_len = "", 0
    for word, word_len in words:
        if line and line_len + 1 + word_len > width:
            lines.append(line)
            line, line_len = word, word_len
        elif line:
            line, line_len = f"{line} {word}", line_len + 1 + word_len
        else:
            line, line_len = word, word_len
    if line:
        lines.append(line)
    return _balance_markup_lines(lines) if len(lines) > 1 else (lines or [""])


def _tag_name(tag: str) -> str:
    """Return a markup open-tag's name: ``[color=4ea1ff]`` → ``color``."""
    return tag[1:-1].split("=", 1)[0]


def _balance_markup_lines(lines: list[str]) -> list[str]:
    """Balance each line of a split Kivy-markup string so none leaks formatting.

    Tags still open at a line's end are closed there and reopened at the start
    of the next line. ``[anchor=…]`` is Kivy's only point tag (no closer); every
    other tag pairs with ``[/name]``.
    """
    open_tags: list[str] = []  # currently-open tags, outermost first
    balanced: list[str] = []
    for line in lines:
        prefix = "".join(open_tags)
        for match in _MARKUP_TAG_RE.finditer(line):
            tag = match.group()
            inner = tag[1:-1]
            if inner.startswith("/"):
                name = inner[1:]
                for k in range(len(open_tags) - 1, -1, -1):
                    if _tag_name(open_tags[k]) == name:
                        del open_tags[k]
                        break
            elif not inner.startswith("anchor="):
                open_tags.append(tag)
        suffix = "".join(f"[/{_tag_name(tag)}]" for tag in reversed(open_tags))
        balanced.append(prefix + line + suffix)
    return balanced


def _visible_text(markup: str) -> str:
    """Return what a Kivy-markup string displays: tags stripped, entities decoded."""
    text = _MARKUP_TAG_RE.sub("", markup)
    return text.replace("&amp;", "&").replace("&bl;", "[").replace("&br;", "]")


def _visible_len(markup: str) -> int:
    """Character count of what a Kivy-markup string displays."""
    return len(_visible_text(markup))


def _table_block(
    tokens: list[Token],
    start: int,
    rewriter: TableRewriter | None,
    heading_color: str = HEADING_COLOR,
) -> tuple[TableBlock, int]:
    """Render the table starting at ``tokens[start]`` (its ``table_open``) into a TableBlock.

    Each row becomes one markup entry with its cells space-padded to the column's
    widest visible content (see `TableBlock` for the monospace requirement this
    puts on the consumer); cells past `TABLE_COL_WRAP_WIDTH` wrap onto newline-joined
    continuation lines, all-number columns are right-justified, and header rows are
    wrapped in the heading color. Consumes
    up to ``table_close`` — like footnote definitions — so the cells' inline
    tokens are not re-rendered; returns the block and the index just past
    ``table_close``.
    """
    rows: list[list[str]] = []
    cells: list[str] = []
    header_rows = 0
    in_header = False
    j = start + 1
    n = len(tokens)
    while j < n and tokens[j].type != "table_close":
        tj = tokens[j].type
        if tj == "thead_open":
            in_header = True
        elif tj == "thead_close":
            in_header = False
        elif tj == "tr_open":
            cells = []
        elif tj == "inline":
            cells.append(_inline(tokens[j].children or []))
        elif tj == "tr_close":
            rows.append(cells)
            header_rows += in_header
        j += 1
    # Markdown tables have exactly one header row, so the rewriter seam sees
    # (header, body); it runs before wrapping/padding so its cells lay out normally.
    overrides: list[int | None] = []
    if rewriter is not None and header_rows == 1 and rows:
        new_header, new_body = rewriter.rewrite(rows[0], rows[1:])
        rows = [new_header, *new_body]
        overrides = rewriter.wrap_widths(new_header)
    ncols = max((len(row) for row in rows), default=0)
    col_wrap: list[int] = []
    for c in range(ncols):
        override = overrides[c] if c < len(overrides) else None
        col_wrap.append(TABLE_COL_WRAP_WIDTH if override is None else override)
    wrapped: list[list[list[str]]] = [  # rows -> cells -> the cell's wrapped lines
        [
            _wrap_markup(cell, col_wrap[c]) if _visible_len(cell) > col_wrap[c] else [cell]
            for c, cell in enumerate(row)
        ]
        for row in rows
    ]
    widths: list[int] = []
    for row in wrapped:
        for c, cell in enumerate(row):
            for cell_line in cell:
                length = _visible_len(cell_line)
                if length > col_wrap[c]:
                    length = 0  # unbreakable word: overflows its own row only
                if c == len(widths):
                    widths.append(length)
                else:
                    widths[c] = max(widths[c], length)
    numeric_cols: list[bool] = []
    for c in range(len(widths)):
        body_texts = [_visible_text(row[c]).strip() for row in rows[header_rows:] if c < len(row)]
        non_empty = [text for text in body_texts if text]
        numeric_cols.append(
            bool(non_empty) and all(_NUMERIC_CELL_RE.fullmatch(text) for text in non_empty)
        )
    entries: list[str] = []
    for r, row in enumerate(wrapped):
        height = max((len(cell) for cell in row), default=0)
        row_lines = []
        for i in range(height):
            # A cell with fewer lines than the row contributes blank padding.
            segments = ((cell[i] if i < len(cell) else "") for cell in row)
            padded = (
                " " * max(widths[c] - _visible_len(seg), 0) + seg
                if numeric_cols[c]
                else seg + " " * max(widths[c] - _visible_len(seg), 0)
                for c, seg in enumerate(segments)
            )
            row_lines.append("  ".join(padded).rstrip())
        entry = "\n".join(row_lines)
        if r < header_rows:
            entry = f"[color={heading_color}]{entry}[/color]"
        entries.append(entry)
    return TableBlock(entries), j + 1


def render_page(
    text: str,
    table_rewriter: TableRewriter | None = None,
    heading_color: str = HEADING_COLOR,
    link_color: str = LINK_COLOR,
) -> Page:
    """Parse a page's frontmatter and render its body + footnotes to Kivy-markup blocks.

    ``heading_color``/``link_color`` are the Kivy-markup hex colors (no leading
    '#') for headings/table headers and hyperlinks/footnote refs. They default
    to the module's standalone palette; an embedding app themes them via
    ``ViewerThemeSpec`` so the article text tracks its own palette.
    """
    fm, body = parse_frontmatter(text)
    tokens = _md().parse(body)
    blocks: list[Block | TableBlock] = []
    indent = 0
    pending_bullet = ""
    list_counters: list[int | None] = []  # one entry per open list, innermost last
    i, n = 0, len(tokens)
    while i < n:
        t = tokens[i]
        tp = t.type
        if tp == "heading_open":
            blocks.append(
                Block(
                    f"[color={heading_color}][b]"
                    + _inline(tokens[i + 1].children or [], link_color=link_color)
                    + "[/b][/color]",
                    HEADING_SIZES.get(t.tag, 16),
                    heading=True,
                )
            )
            i += 3
            continue
        if tp == "paragraph_open":
            marker = pending_bullet
            pending_bullet = ""
            markup = _inline(tokens[i + 1].children or [], link_color=link_color)
            if PROVENANCE_MARKER not in markup:  # drop editorial provenance notes
                blocks.append(Block(markup, indent=indent, marker=marker))
            i += 3
            continue
        if tp == "footnote_open":
            block, i = _footnote_block(tokens, i, link_color=link_color)
            blocks.append(block)
            continue
        if tp == "table_open":
            block, i = _table_block(tokens, i, table_rewriter, heading_color=heading_color)
            blocks.append(block)
            continue
        if tp in ("bullet_list_open", "ordered_list_open", "blockquote_open"):
            indent += 1
            if tp == "bullet_list_open":
                list_counters.append(None)  # None marks an unnumbered (bullet) list
            elif tp == "ordered_list_open":
                list_counters.append(int(t.attrGet("start") or 1))
        elif tp in ("bullet_list_close", "ordered_list_close", "blockquote_close"):
            indent = max(indent - 1, 0)
            if tp != "blockquote_close" and list_counters:
                list_counters.pop()
        elif tp == "list_item_open":
            # Number the item from the innermost list's counter (CommonMark numbering:
            # sequential from the list's start, whatever the source says); bullet lists
            # carry None and keep the glyph.
            number = list_counters[-1] if list_counters else None
            if number is not None:
                list_counters[-1] = number + 1
            pending_bullet = "•" if number is None else f"{number}."
        elif tp in ("fence", "code_block"):
            blocks.append(Block(f"[color={CODE_COLOR}]{_esc(t.content.rstrip())}[/color]", 14))
        elif tp == "html_block":
            # Raw HTML is not rendered, but its source must not vanish either
            # (SPEC §9 tolerance: show *something* rather than drop content) —
            # display it like a code block. Pure comments are the exception:
            # they are author metadata (e.g. the wiki's <!-- bib-notes-mined -->
            # markers), not content, and are skipped.
            content = t.content.strip()
            if not (content.startswith("<!--") and content.endswith("-->")):
                blocks.append(Block(f"[color={CODE_COLOR}]{_esc(content)}[/color]", 14))
        elif tp == "hr":
            blocks.append(Block("─" * 40))
        elif tp == "footnote_block_open":
            header = f"[color={HEADING_COLOR}][b]Footnotes[/b][/color]"
            blocks.append(Block(header, 18, heading=True))
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
    """Display title for a concept file: its frontmatter ``title``, else the filename stem.

    An unreadable file also falls back to the stem (tolerant consumption, SPEC §9).
    """
    try:
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    except OSError:
        return path.stem
    title = fm.get("title")
    return title if isinstance(title, str) and title else path.stem


def dir_title(path: Path) -> str:
    """Human title for a bundle directory.

    The reserved ``index.md`` (SPEC §3.1) is the directory's curated listing, and its
    first ``#`` heading names the directory — use that when present. The scan skips
    the frontmatter block (where a ``# …`` line is a YAML comment, not a heading) and
    fenced code blocks. Otherwise — no index.md, no heading, or an unreadable file —
    fall back to the directory name in Title Case ("comics-and-stories" → "Comics
    And Stories").
    """
    index = path / "index.md"
    if index.is_file():
        try:
            _, body = parse_frontmatter(index.read_text(encoding="utf-8"))
        except OSError:
            body = ""
        in_fence = False
        for line in body.splitlines():
            if line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
            elif not in_fence and line.startswith("# "):
                return line[2:].strip()
    return path.name.replace("-", " ").replace("_", " ").title()


def has_children(directory: Path) -> bool:
    """Whether a bundle directory has anything `list_children` would list.

    A cheap existence scan — no frontmatter reads — so a lazy consumer can decide
    whether a directory needs an expansion affordance without paying
    `list_children`'s per-concept file reads.
    """
    if not directory.is_dir():
        return False
    return any(
        not child.name.startswith(".")
        and (child.is_dir() or (child.suffix == ".md" and child.name not in RESERVED_FILES))
        for child in directory.iterdir()
    )


def _index_link_order(directory: Path) -> dict[str, int]:
    """Rank each immediate child by its first mention in the directory's ``index.md``.

    The reserved ``index.md`` (SPEC §3.1) is the directory's *curated* listing, so
    the order of its listed links is the author's intended child order. Only links
    inside list items count — a link in surrounding prose is a mention, not a
    listing entry. Each qualifying href is charged to the immediate child it enters:
    its first path segment (``stories/x/index.md`` → ``stories``; ``good-deeds.md``
    → itself). External (scheme-bearing), absolute ``/…`` (they name bundle-root
    children, not necessarily ours), and parent ``..`` links are ignored. A missing
    or unreadable index.md yields ``{}`` (tolerant consumption, SPEC §9).
    """
    index = directory / "index.md"
    if not index.is_file():
        return {}
    try:
        _, body = parse_frontmatter(index.read_text(encoding="utf-8"))
    except OSError:
        return {}
    order: dict[str, int] = {}
    list_depth = 0
    for token in _md().parse(body):
        if token.type in ("bullet_list_open", "ordered_list_open"):
            list_depth += 1
        elif token.type in ("bullet_list_close", "ordered_list_close"):
            list_depth -= 1
        elif token.type == "inline" and list_depth > 0:
            for child in token.children or []:
                if child.type != "link_open":
                    continue
                href = str(child.attrGet("href") or "")
                if "://" in href or href.startswith("/"):
                    continue
                path_part = urllib.parse.unquote(href.split("#", 1)[0])
                first_segment = path_part.split("/", 1)[0]
                if first_segment in ("", ".", ".."):
                    continue
                order.setdefault(first_segment, len(order))
    return order


def list_children(directory: Path) -> list[BundleDir | ConceptNode]:
    """Immediate children of a bundle directory, in curated order — one level only.

    Children linked from the directory's reserved ``index.md`` listing come first,
    in link order (`_index_link_order`); the rest follow in name order. A directory
    with no index.md (or one that lists nothing) is plain name order.

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
                children.append(BundleDir(child, child.name, title=dir_title(child)))
            elif child.suffix == ".md" and child.name not in RESERVED_FILES:
                children.append(ConceptNode(child, concept_title(child)))
        rank = _index_link_order(directory)
        # Stable sort over the name-ordered base: listed children first in listing
        # order, unlisted ones after, still alphabetical among themselves.
        children.sort(key=lambda child: rank.get(child.path.name, len(rank)))
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
    return BundleDir(root, root.name, children, title=dir_title(root))
