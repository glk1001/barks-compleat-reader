"""Kivy-free OKF page rendering — the core of the okf_reader package.

No Kivy import, no GUI. Turns an OKF page (markdown + YAML frontmatter) into
`Block`s of **Kivy markup** (plain strings — kivy-flavoured, but no kivy
dependency): markdown is tokenised with **markdown-it-py** (+ the `footnote`
plugin) and `render_page()` is pure — same text in, same `Page` out — so it is
unit-testable in isolation. Table layout goes through an embedding app's
`TableRewriter` first. The bundle's directory tree and its link resolution are
the sibling `okf_reader.core.bundle`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin

if TYPE_CHECKING:
    from collections.abc import Callable

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

# libyaml's loader, where PyYAML was built with it (the wheels are): the same safe
# subset as SafeLoader, but in C. Every page's front matter goes through it - twice
# per page when the search index is built, which took 2.9 s with the pure-Python
# loader and 0.8 s with this one (1,484 pages, 2026-10-15).
_YAML_LOADER: type[yaml.SafeLoader] = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


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


# --------------------------------------------------------------------------- render


# One parser for every page and index.md, on the UI thread and the search-warm thread
# (whose bundle walk reads each index.md): MarkdownIt keeps its per-parse state in the
# StateCore it creates on each ``parse`` call. Its one shared mutable state is each
# rule chain's cache, compiled lazily and without a lock on first use, so a parse
# racing the first could run with part of a chain. Compiled here, at import, the
# caches are only read after.
_MARKDOWN = MarkdownIt("commonmark").use(footnote_plugin).enable("table")
for _ruler in (
    _MARKDOWN.core.ruler,
    _MARKDOWN.block.ruler,
    _MARKDOWN.inline.ruler,
    _MARKDOWN.inline.ruler2,
):
    _ruler.getRules("")  # Compiles every chain of the ruler, not only this one.
del _ruler


def parse_markdown(body: str) -> list[Token]:
    """Tokenize markdown the OKF way: CommonMark plus the footnote and table extensions.

    Args:
        body: The markdown source, frontmatter already split off.

    Returns:
        markdown-it's block token stream; inline content sits in each ``inline``
        token's ``children``.

    """
    return _MARKDOWN.parse(body)


def escape_markup(text: str) -> str:
    """Escape the three characters that are special to Kivy markup.

    The same escaping as ``kivy.utils.escape_markup``, without the Kivy import. An
    embedding app that matches text against rendered cells (the Barks table
    rewriter does) must escape with this same function.

    Args:
        text: Plain text.

    Returns:
        The text with ``&``, ``[`` and ``]`` as Kivy markup entities.

    """
    return text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def _ref_quote(href: str) -> str:
    """Make an href safe to embed in a Kivy ``[ref=…]`` tag.

    A raw ``&``, ``[``, or ``]`` inside the tag corrupts the markup, but Kivy hands
    the ref value back verbatim on tap, so entity-escaping (`escape_markup`) would break
    navigation. Percent-encoding round-trips instead: `resolve_link` percent-decodes
    every href. markdown-it already encodes brackets in link destinations; ``&``
    it passes through raw. ``%`` is left alone to avoid double-encoding.
    """
    return href.replace("&", "%26").replace("[", "%5B").replace("]", "%5D")


# Inline tokens whose markup never varies: the two line breaks, emphasis on and off,
# and the end of a link. The rest (text, code, a link's start, a footnote marker, an
# image) carry content and are rendered in `_inline` itself.
_INLINE_FIXED_MARKUP = {
    "softbreak": " ",
    "hardbreak": "\n",
    "strong_open": "[b]",
    "strong_close": "[/b]",
    "em_open": "[i]",
    "em_close": "[/i]",
    "link_close": "[/u][/color][/ref]",
}


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
        if tp in _INLINE_FIXED_MARKUP:
            out.append(_INLINE_FIXED_MARKUP[tp])
        elif tp == "text":
            out.append(escape_markup(t.content))
        elif tp == "code_inline":
            out.append(f"[color={code_color}]{escape_markup(t.content)}[/color]")
        elif tp == "link_open":
            href = _ref_quote(str(t.attrGet("href") or ""))
            out.append(f"[ref={href}][color={link_color}][u]")
        elif tp == "footnote_ref":
            label = t.meta.get("label") or str(t.meta.get("id", ""))
            marker = escape_markup(f"[{label}]")
            out.append(
                f"[ref=fn:{label}][color={link_color}]"
                f"[sup][size={FOOTNOTE_REF_SIZE}]{marker}[/size][/sup][/color][/ref]"
            )
        elif tp == "image":
            alt = str(t.content or t.attrGet("src") or "image")
            out.append(f"[i]▨ image: {escape_markup(alt)}[/i]")
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
                    fm = yaml.load("\n".join(lines[1:i]), Loader=_YAML_LOADER) or {}  # noqa: S506
                except yaml.YAMLError:
                    fm = {}
                return (fm if isinstance(fm, dict) else {}), "\n".join(lines[i + 1 :]).strip()
    return {}, text


def _footnote_block(
    tokens: list[Token], start: int, link_color: str = LINK_COLOR
) -> tuple[Block, int]:
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
    markup = (
        f"[color={FOOTNOTE_TEXT_COLOR}][b][{escape_markup(label)}][/b] "
        + " ".join(parts)
        + "[/color]"
    )
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


def _markup_words(markup: str) -> list[tuple[str, int]]:
    """Split a Kivy-markup string at its visible spaces into (word markup, visible length).

    A markup tag or entity is one indivisible unit, and a tag adds nothing to the
    length; runs of spaces yield no empty words.
    """
    words: list[tuple[str, int]] = []
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
    return words


def _wrap_markup(markup: str, width: int) -> list[str]:
    """Greedy word-wrap of a Kivy-markup string at ``width`` visible characters.

    Breaks only at visible spaces — never inside a markup tag or entity, and a
    single word longer than ``width`` stays whole (its line overflows). Every
    returned line is markup-balanced: a tag pair the break would split is closed
    at the line's end and reopened on the next line, so a line never leaks its
    formatting into whatever the consumer appends after it (table rows append
    the row's remaining columns — see ``_table_block``).
    """
    lines: list[str] = []
    line, line_len = "", 0
    for word, word_len in _markup_words(markup):
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


def visible_len(markup: str) -> int:
    """Return the character count of what a Kivy-markup string displays.

    Args:
        markup: Kivy markup: tags count nothing, an escaped bracket or ampersand one.

    Returns:
        How many characters show.

    """
    return len(_visible_text(markup))


def _table_rows(tokens: list[Token], start: int) -> tuple[list[list[str]], int, int]:
    """Collect the table at ``tokens[start]`` (its ``table_open``) into rows of cell markup.

    Returns the rows, how many of them (leading) are header rows, and the index just
    past the table's ``table_close``.
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
    return rows, header_rows, j + 1


def _rewrite_table(
    rows: list[list[str]], header_rows: int, rewriter: TableRewriter | None
) -> tuple[list[list[str]], list[int | None]]:
    """Give the embedding app's rewriter its turn; return the rows and its wrap overrides.

    Markdown tables have exactly one header row, so the rewriter seam sees
    (header, body); it runs before wrapping/padding so its cells lay out normally.
    A table without that shape, or no rewriter, passes through with no overrides.
    """
    if rewriter is None or header_rows != 1 or not rows:
        return rows, []
    new_header, new_body = rewriter.rewrite(rows[0], rows[1:])
    return [new_header, *new_body], rewriter.wrap_widths(new_header)


def _column_wrap_widths(ncols: int, overrides: list[int | None]) -> list[int]:
    """Return each column's wrap width: the rewriter's override where given, else the default."""
    col_wrap: list[int] = []
    for c in range(ncols):
        override = overrides[c] if c < len(overrides) else None
        col_wrap.append(TABLE_COL_WRAP_WIDTH if override is None else override)
    return col_wrap


def _wrap_table_cells(rows: list[list[str]], col_wrap: list[int]) -> list[list[list[str]]]:
    """Wrap each cell at its column's width: rows -> cells -> the cell's lines."""
    return [
        [
            _wrap_markup(cell, col_wrap[c]) if visible_len(cell) > col_wrap[c] else [cell]
            for c, cell in enumerate(row)
        ]
        for row in rows
    ]


def _column_widths(wrapped: list[list[list[str]]], col_wrap: list[int]) -> list[int]:
    """Return each column's visible width: its widest line that fits the wrap width.

    An unbreakable word longer than the column's wrap width stays whole and overflows
    its own row only, so it does not widen the column for every other row.
    """
    widths = [0] * len(col_wrap)
    for row in wrapped:
        for c, cell in enumerate(row):
            for cell_line in cell:
                length = visible_len(cell_line)
                if length <= col_wrap[c]:
                    widths[c] = max(widths[c], length)
    return widths


def _numeric_columns(rows: list[list[str]], header_rows: int, ncols: int) -> list[bool]:
    """Return, per column, whether every non-empty body cell is a plain number."""
    numeric: list[bool] = []
    for c in range(ncols):
        body_texts = [_visible_text(row[c]).strip() for row in rows[header_rows:] if c < len(row)]
        non_empty = [text for text in body_texts if text]
        numeric.append(
            bool(non_empty) and all(_NUMERIC_CELL_RE.fullmatch(text) for text in non_empty)
        )
    return numeric


def _table_row_markup(row: list[list[str]], widths: list[int], numeric_cols: list[bool]) -> str:
    """Lay one wrapped row out: its lines newline-joined, cells padded to their column."""
    height = max((len(cell) for cell in row), default=0)
    row_lines = []
    for i in range(height):
        # A cell with fewer lines than the row contributes blank padding.
        segments = ((cell[i] if i < len(cell) else "") for cell in row)
        padded = (
            " " * max(widths[c] - visible_len(seg), 0) + seg
            if numeric_cols[c]
            else seg + " " * max(widths[c] - visible_len(seg), 0)
            for c, seg in enumerate(segments)
        )
        row_lines.append("  ".join(padded).rstrip())
    return "\n".join(row_lines)


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
    rows, header_rows, next_index = _table_rows(tokens, start)
    rows, overrides = _rewrite_table(rows, header_rows, rewriter)
    ncols = max((len(row) for row in rows), default=0)
    col_wrap = _column_wrap_widths(ncols, overrides)
    wrapped = _wrap_table_cells(rows, col_wrap)
    widths = _column_widths(wrapped, col_wrap)
    numeric_cols = _numeric_columns(rows, header_rows, ncols)
    entries: list[str] = []
    for r, row in enumerate(wrapped):
        entry = _table_row_markup(row, widths, numeric_cols)
        if r < header_rows:
            entry = f"[color={heading_color}]{entry}[/color]"
        entries.append(entry)
    return TableBlock(entries), next_index


class _PageBuilder:
    """Walks a page's block-level token stream, accumulating its rendered blocks.

    One handler per token type, dispatched from `_handlers`; each takes the index of
    the token it handles and returns the index of the next token to look at. Token
    types with no handler (``inline``, the ``*_close`` of a heading or paragraph, …)
    are passed over. The nesting state — the indent depth, the marker a list item
    holds for its first paragraph, and one counter per open list — lives here.
    """

    def __init__(
        self,
        tokens: list[Token],
        table_rewriter: TableRewriter | None,
        heading_color: str,
        link_color: str,
    ) -> None:
        self._tokens = tokens
        self._table_rewriter = table_rewriter
        self._heading_color = heading_color
        self._link_color = link_color
        self.blocks: list[Block | TableBlock] = []
        self._indent = 0
        self._pending_marker = ""
        self._list_counters: list[int | None] = []  # one entry per open list, innermost last
        self._handlers: dict[str, Callable[[int], int]] = {
            "heading_open": self._heading,
            "paragraph_open": self._paragraph,
            "footnote_open": self._footnote,
            "table_open": self._table,
            "bullet_list_open": self._open_container,
            "ordered_list_open": self._open_container,
            "blockquote_open": self._open_container,
            "bullet_list_close": self._close_container,
            "ordered_list_close": self._close_container,
            "blockquote_close": self._close_container,
            "list_item_open": self._list_item,
            "fence": self._code,
            "code_block": self._code,
            "html_block": self._html,
            "hr": self._rule,
            "footnote_block_open": self._footnotes_heading,
        }

    def build(self) -> list[Block | TableBlock]:
        """Run every token through its handler and return the blocks in page order."""
        i, n = 0, len(self._tokens)
        while i < n:
            handler = self._handlers.get(self._tokens[i].type)
            i = i + 1 if handler is None else handler(i)
        return self.blocks

    def _inline_at(self, i: int) -> str:
        """Render the inline token at ``i`` (a heading's or paragraph's content)."""
        return _inline(self._tokens[i].children or [], link_color=self._link_color)

    def _heading(self, i: int) -> int:
        tag = self._tokens[i].tag
        markup = f"[color={self._heading_color}][b]{self._inline_at(i + 1)}[/b][/color]"
        self.blocks.append(Block(markup, HEADING_SIZES.get(tag, 16), heading=True))
        return i + 3  # heading_open, inline, heading_close

    def _paragraph(self, i: int) -> int:
        marker, self._pending_marker = self._pending_marker, ""
        markup = self._inline_at(i + 1)
        if PROVENANCE_MARKER not in markup:  # drop editorial provenance notes
            self.blocks.append(Block(markup, indent=self._indent, marker=marker))
        return i + 3  # paragraph_open, inline, paragraph_close

    def _footnote(self, i: int) -> int:
        block, j = _footnote_block(self._tokens, i, link_color=self._link_color)
        self.blocks.append(block)
        return j

    def _table(self, i: int) -> int:
        block, j = _table_block(
            self._tokens, i, self._table_rewriter, heading_color=self._heading_color
        )
        self.blocks.append(block)
        return j

    def _open_container(self, i: int) -> int:
        """Open a list or blockquote: one indent level deeper, and a counter for a list."""
        t = self._tokens[i]
        self._indent += 1
        if t.type == "bullet_list_open":
            self._list_counters.append(None)  # None marks an unnumbered (bullet) list
        elif t.type == "ordered_list_open":
            self._list_counters.append(int(t.attrGet("start") or 1))
        return i + 1

    def _close_container(self, i: int) -> int:
        self._indent = max(self._indent - 1, 0)
        if self._tokens[i].type != "blockquote_close" and self._list_counters:
            self._list_counters.pop()
        return i + 1

    def _list_item(self, i: int) -> int:
        # Number the item from the innermost list's counter (CommonMark numbering:
        # sequential from the list's start, whatever the source says); bullet lists
        # carry None and keep the glyph.
        number = self._list_counters[-1] if self._list_counters else None
        if number is not None:
            self._list_counters[-1] = number + 1
        self._pending_marker = "•" if number is None else f"{number}."
        return i + 1

    def _code(self, i: int) -> int:
        content = self._tokens[i].content.rstrip()
        self.blocks.append(Block(f"[color={CODE_COLOR}]{escape_markup(content)}[/color]", 14))
        return i + 1

    def _html(self, i: int) -> int:
        # Raw HTML is not rendered, but its source must not vanish either
        # (SPEC §9 tolerance: show *something* rather than drop content) —
        # display it like a code block. Pure comments are the exception:
        # they are author metadata (e.g. the wiki's <!-- bib-notes-mined -->
        # markers), not content, and are skipped.
        content = self._tokens[i].content.strip()
        if not (content.startswith("<!--") and content.endswith("-->")):
            self.blocks.append(Block(f"[color={CODE_COLOR}]{escape_markup(content)}[/color]", 14))
        return i + 1

    def _rule(self, i: int) -> int:
        self.blocks.append(Block("─" * 40))
        return i + 1

    def _footnotes_heading(self, i: int) -> int:
        # The module's standalone heading colour, not the page's themed one.
        header = f"[color={HEADING_COLOR}][b]Footnotes[/b][/color]"
        self.blocks.append(Block(header, 18, heading=True))
        return i + 1


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
    blocks = _PageBuilder(parse_markdown(body), table_rewriter, heading_color, link_color).build()
    return Page(fm, blocks)
