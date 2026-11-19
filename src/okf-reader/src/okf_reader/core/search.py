"""Kivy-free search over an OKF bundle's titles, headings and text — the core of wiki search.

No Kivy, no GUI. Walks a bundle into an in-memory `SearchIndex` (one entry per
navigable concept page — its title, ancestor breadcrumb, heading texts and its
text as a reader sees it) and answers substring queries against it, so the UI
only owns the search box and the results list. Pure and deterministic — same
bundle + query in, same hits out — so it is unit-testable in isolation.

A title or heading match ranks above a match in the text alone, and a text hit
carries a snippet of the text round the match. It reuses the bundle walk
(`bundle.load_bundle_tree`), reads headings with a cheap ATX line scan and the
text with a few regexes (no markdown-it parse), and follows the
tolerant-consumption spirit (SPEC §9) — an unreadable page is skipped, never
fatal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from okf_reader.core.bundle import BundleDir, load_bundle_tree
from okf_reader.core.render import parse_frontmatter

if TYPE_CHECKING:
    from pathlib import Path

BREADCRUMB_SEP = " › "  # noqa: RUF001 — display glyph, not a greater-than

# An ATX heading line ("## Title", up to three leading spaces, optional trailing
# #s). A cheap scan beats a full markdown-it parse per page — indexing the whole
# bundle for headings must stay fast enough to run without freezing the UI.
_ATX_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")

# A query's phrase marks: straight double quotes and the curly pair a phone or a
# word processor's paste gives. They are operators, so a quote is never matched.
_QUOTE_MARKS = re.compile('["\u201c\u201d]')
# The wiki writes apostrophes curly and a keyboard types them straight: both sides
# fold the curly ones to "'" so "scrooge's" finds the wiki's curly spelling.
_CURLY_APOSTROPHES = ("\u2018", "\u2019")
_WHITESPACE_RUN = re.compile(r"\s+")

# The markdown a reader never sees, stripped from a page's text before it is
# indexed, so a search matches what the page shows (a link's words, not its URL)
# and a snippet reads as prose. Applied in order; cheap regexes, not a parse.
_MARKDOWN_TO_TEXT: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"<!--.*?-->", re.DOTALL), " "),  # HTML comments
    (re.compile(r"^ {0,3}(```|~~~).*$", re.MULTILINE), " "),  # code fence lines
    (re.compile(r"!?\[([^\]\n]*)\]\([^)\n]*\)"), r"\1"),  # [words](url), ![alt](src)
    (re.compile(r"\[([^\]\n]*)\]\[[^\]\n]*\]"), r"\1"),  # [words][ref]
    (re.compile(r"^ {0,3}\[[^\]\n]+\]:.*$", re.MULTILINE), " "),  # [ref]: url
    (re.compile(r"<[^<>\n]+>"), " "),  # HTML tags and <url> links
    (re.compile(r"^ {0,3}#{1,6}[ \t]+", re.MULTILINE), ""),  # heading marks
    (re.compile(r"^ {0,3}(> ?)+", re.MULTILINE), ""),  # blockquote marks
    (re.compile(r"^[ \t]*\|?[ \t:|-]*-[ \t:|-]*$", re.MULTILINE), " "),  # table rules
    (re.compile(r"[*`]|~~"), ""),  # emphasis, code spans, strikes
    (re.compile(r"\|"), " "),  # table cells
)

# A text hit's snippet: up to this many characters before the match and after
# it, cut back to whole words. The lead is short so the match stays on the
# results row's visible line.
_SNIPPET_LEAD = 30
_SNIPPET_TAIL = 90
_ELLIPSIS = "\u2026"

# Score tiers, best first. The gaps leave room to interpolate later without
# reshuffling; ranking is otherwise stable on the curated walk order.
_SCORE_EXACT_TITLE = 400
_SCORE_PREFIX_TITLE = 300
_SCORE_WORDS_IN_TITLE = 200
_SCORE_WORDS_IN_HEADING = 100
_SCORE_WORDS_IN_TEXT = 50  # among these, the page with more mentions ranks first


@dataclass(frozen=True)
class SearchHit:
    """One matched page, ready for the results list."""

    path: Path  # absolute .md page to open (feeds OKFViewer.show_page)
    title: str  # display title
    breadcrumb: str  # ancestor-dir chain joined by BREADCRUMB_SEP
    matched_on: str  # "title" | "heading" | "text"
    score: int  # higher = better
    # A "text" hit's words round the match, and the match's [start, end) in it;
    # empty for a title or heading hit.
    snippet: str = ""
    snippet_match: tuple[int, int] = (0, 0)


@dataclass(frozen=True)
class _Entry:
    """One indexed page: display fields plus lowercased haystacks for matching."""

    path: Path
    title: str
    breadcrumb: str
    order: int  # position in the curated walk — the stable tie-break
    title_lower: str
    headings_lower: tuple[str, ...]
    text: str = ""  # the page's text as shown (see `page_text`), for snippets
    text_lower: str = ""  # the same, folded for matching (see `_fold`)


@dataclass(frozen=True)
class SearchIndex:
    """An immutable, in-memory index of a bundle's navigable pages."""

    entries: tuple[_Entry, ...]


class SearchProvider(Protocol):
    """A pluggable search backend — the viewer's optional override seam.

    okf_reader's built-in title, heading and text search (see `BundleSearcher`)
    needs no app knowledge, so the viewer uses it by default. An embedding app
    may inject its own (e.g. a unified backend) instead.
    """

    def search(self, query: str) -> list[SearchHit]:
        """Return the pages matching ``query``, best first."""
        ...


def _fold_chars(text: str) -> str:
    """Return ``text`` lowercased with its apostrophes straight; it keeps its length, nearly always.

    Two ``replace`` calls, not ``str.translate``: on a bundle's worth of text the
    translate table is ten times slower.
    """
    folded = text.lower()
    for apostrophe in _CURLY_APOSTROPHES:
        folded = folded.replace(apostrophe, "'")
    return folded


def _fold(text: str) -> str:
    """Return ``text`` as matching compares it: lowercased, apostrophes straight, spaces single."""
    return _WHITESPACE_RUN.sub(" ", _fold_chars(text)).strip()


def parse_query(query: str) -> list[str]:
    """Split a query into the terms every hit must contain, each folded (see `_fold`).

    Words outside quotes are terms one by one; the words inside a pair of double
    quotes are one term, matched as that phrase. A quote left open takes the rest
    of the query as its phrase, so a phrase being typed already narrows the
    results, and an empty pair (or a lone quote) adds nothing.

    Args:
        query: The user's search string.

    Returns:
        The terms, in query order; empty when the query holds no words.

    """
    terms: list[str] = []
    for i, part in enumerate(_QUOTE_MARKS.split(_fold(query))):
        if i % 2:  # inside quotes: the words between them are one phrase
            phrase = part.strip()
            if phrase:
                terms.append(phrase)
        else:
            terms.extend(part.split())
    return terms


def page_text(body: str) -> str:
    """Return a page body's text as a reader sees it: markdown marks gone, spaces single.

    A link keeps its words and loses its URL, a heading its ``#`` marks, a table
    its rules and pipes; HTML tags and comments go. Code is kept as text. A few
    regexes rather than a markdown-it parse, so the whole bundle indexes quickly.

    Args:
        body: The page's markdown, its frontmatter already removed.

    Returns:
        The text on one line, words separated by single spaces.

    """
    for pattern, replacement in _MARKDOWN_TO_TEXT:
        body = pattern.sub(replacement, body)
    return _WHITESPACE_RUN.sub(" ", body).strip()


def _extract_headings(body: str) -> list[str]:
    """Return the ATX heading texts of a page body, in document order (tolerant).

    A line scan (not a full markdown-it parse) for speed — the whole bundle is
    indexed at once. The caller strips the frontmatter first (a ``#`` there is a
    YAML comment), and fenced code blocks are skipped so a ``#`` comment inside
    one is not mistaken for a heading — the same guard `bundle.dir_title` uses.
    """
    headings: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _ATX_HEADING.match(line)
        if match and match.group(2):
            headings.append(match.group(2).strip())
    return headings


def build_search_index(
    bundle: Path, *, include_headings: bool = True, include_text: bool = True
) -> SearchIndex:
    """Walk ``bundle`` into a searchable index of its concept pages.

    Titles come from the bundle walk's frontmatter reads (no extra I/O); headings
    and text cost one read per page between them. Intended to be built once and
    cached — the whole bundle is walked, and its text is held in memory. An
    unreadable page contributes its title but no headings or text rather than
    failing the build (SPEC §9).

    Args:
        bundle: The OKF bundle root directory.
        include_headings: Also index each page's headings.
        include_text: Also index each page's text (see `page_text`). With
            neither, the build reads no page bodies.

    Returns:
        The immutable `SearchIndex`.

    """
    entries: list[_Entry] = []
    counter = 0

    def walk(node: BundleDir, crumbs: tuple[str, ...]) -> None:
        nonlocal counter
        for child in node.children:
            if isinstance(child, BundleDir):
                walk(child, (*crumbs, child.title or child.name))
            else:  # ConceptNode
                headings: tuple[str, ...] = ()
                text = ""
                if include_headings or include_text:
                    try:
                        source = child.path.read_text(encoding="utf-8")
                    except OSError:
                        source = ""
                    body = parse_frontmatter(source)[1]  # one YAML parse serves both
                    if include_headings:
                        headings = tuple(_extract_headings(body))
                    if include_text:
                        text = page_text(body)
                entries.append(
                    _Entry(
                        path=child.path,
                        title=child.title,
                        breadcrumb=BREADCRUMB_SEP.join(crumbs),
                        order=counter,
                        title_lower=_fold(child.title),
                        headings_lower=tuple(_fold(h) for h in headings),
                        text=text,
                        text_lower=_fold_chars(text),  # page_text made its spaces single
                    )
                )
                counter += 1

    walk(load_bundle_tree(bundle), ())
    return SearchIndex(tuple(entries))


def _score_entry(entry: _Entry, terms: list[str], query: str) -> tuple[int, str] | None:
    """Score ``entry`` against a query, or None if it does not match.

    AND semantics: every term must appear in the title, a heading or the text.
    The tier is decided by the strongest title relationship, falling through to a
    heading match and then to a match that needs the text.
    """
    if entry.title_lower == query:
        return _SCORE_EXACT_TITLE, "title"
    if entry.title_lower.startswith(query):
        return _SCORE_PREFIX_TITLE, "title"
    if all(term in entry.title_lower for term in terms):
        return _SCORE_WORDS_IN_TITLE, "title"
    haystacks = (entry.title_lower, *entry.headings_lower)
    if all(any(term in hay for hay in haystacks) for term in terms):
        return _SCORE_WORDS_IN_HEADING, "heading"
    if all(term in entry.title_lower or term in entry.text_lower for term in terms):
        return _SCORE_WORDS_IN_TEXT, "text"
    return None


def _snippet(entry: _Entry, terms: list[str]) -> tuple[str, tuple[int, int]]:
    """Return the words round a text hit's match, and the match's span in them.

    The match shown is the first mention of the query's rarest term in the page,
    the one that says most about why it matched. The window is cut back to whole
    words and marked with an ellipsis where it was cut. A term only in the title
    has no mention in the text: then the snippet is the text's opening words.
    """
    text, folded = entry.text, entry.text_lower
    if len(text) != len(folded):  # a lowercase that changed the length: offsets differ
        text = folded
    found = [t for t in terms if t in folded]
    term = min(found, key=folded.count) if found else ""
    at = folded.find(term) if term else 0
    start = max(0, at - _SNIPPET_LEAD)
    if start:
        space = text.find(" ", start, at)
        start = space + 1 if space >= 0 else start
    end = min(len(text), at + len(term) + _SNIPPET_TAIL)
    if end < len(text):
        space = text.rfind(" ", at + len(term), end)
        end = space if space >= 0 else end
    lead = _ELLIPSIS if start else ""
    tail = _ELLIPSIS if end < len(text) else ""
    match_at = len(lead) + at - start
    return f"{lead}{text[start:end]}{tail}", (match_at, match_at + len(term))


def search_index(index: SearchIndex, query: str, *, limit: int = 50) -> list[SearchHit]:
    """Return the pages matching ``query``, best first.

    Case-insensitive, whitespace-tokenized, AND semantics (all words must be
    present); a double-quoted phrase is one term (see `parse_query`), and curly
    apostrophes match straight ones. Ranking: exact title, then title prefix,
    then all-terms-in-title, then all terms across title+headings, then all terms
    across title+text, the page with the most mentions first; ties break on the
    curated walk order. A text hit carries a snippet round its match. A query
    with no words (blank, or only quotes) returns no hits.

    Args:
        index: The index to search.
        query: The user's search string.
        limit: Maximum number of hits to return.

    Returns:
        Up to ``limit`` `SearchHit`s, ordered best first.

    """
    terms = parse_query(query)
    if not terms:
        return []
    q = " ".join(terms)  # the query without its quotes, for the whole-title tiers
    scored: list[tuple[int, int, int, _Entry, str]] = []
    for entry in index.entries:
        result = _score_entry(entry, terms, q)
        if result is None:
            continue
        score, matched_on = result
        mentions = (
            sum(entry.text_lower.count(term) for term in terms) if matched_on == "text" else 0
        )
        scored.append((score, mentions, entry.order, entry, matched_on))
    # Best score first, then the most mentions; the curated walk order breaks ties.
    scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
    hits: list[SearchHit] = []
    for score, _mentions, _order, entry, matched_on in scored[:limit]:
        snippet, snippet_match = _snippet(entry, terms) if matched_on == "text" else ("", (0, 0))
        hits.append(
            SearchHit(
                path=entry.path,
                title=entry.title,
                breadcrumb=entry.breadcrumb,
                matched_on=matched_on,
                score=score,
                snippet=snippet,
                snippet_match=snippet_match,
            )
        )
    return hits


class BundleSearcher:
    """The built-in `SearchProvider`: lazily builds and caches a bundle's index.

    The index is built on the first `search` call (a whole-bundle walk) and
    reused thereafter, so constructing one is cheap — the viewer can make it up
    front and pay the cost only if the user actually searches.
    """

    def __init__(
        self,
        bundle: Path,
        *,
        include_headings: bool = True,
        include_text: bool = True,
        limit: int = 50,
    ) -> None:
        self._bundle = bundle
        self._include_headings = include_headings
        self._include_text = include_text
        self._limit = limit
        self._index: SearchIndex | None = None

    @property
    def is_ready(self) -> bool:
        """Whether the index is already built (a search will not block on I/O)."""
        return self._index is not None

    def warm(self) -> None:
        """Build and cache the index now, if not already built.

        Whole-bundle I/O; intended to be called from a worker thread so the first
        `search` returns without a UI-blocking build. Idempotent.
        """
        if self._index is None:
            self._index = build_search_index(
                self._bundle,
                include_headings=self._include_headings,
                include_text=self._include_text,
            )

    def search(self, query: str) -> list[SearchHit]:
        """Return the bundle pages matching ``query`` (building the index once)."""
        if not query.strip():
            return []
        self.warm()
        assert self._index is not None
        return search_index(self._index, query, limit=self._limit)
