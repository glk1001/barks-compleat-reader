"""Kivy-free title/heading search over an OKF bundle — the core of wiki search.

No Kivy, no GUI. Walks a bundle into an in-memory `SearchIndex` (one entry per
navigable concept page — its title, ancestor breadcrumb, and heading texts) and
answers substring queries against it, so the UI only owns the search box and the
results list. Pure and deterministic — same bundle + query in, same hits out —
so it is unit-testable in isolation.

Scope is deliberately tier 1: titles and headings, not body prose. It reuses the
bundle walk (`render.load_bundle_tree`) and extracts headings with a cheap ATX
line scan, and follows the tolerant-consumption spirit (SPEC §9) — an unreadable
page is skipped, never fatal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from okf_reader.core.render import (
    BundleDir,
    load_bundle_tree,
    parse_frontmatter,
)

if TYPE_CHECKING:
    from pathlib import Path

BREADCRUMB_SEP = " › "  # noqa: RUF001 — display glyph, not a greater-than

# An ATX heading line ("## Title", up to three leading spaces, optional trailing
# #s). A cheap scan beats a full markdown-it parse per page — indexing the whole
# bundle for headings must stay fast enough to run without freezing the UI.
_ATX_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")

# Score tiers, best first. The gaps leave room to interpolate later without
# reshuffling; ranking is otherwise stable on the curated walk order.
_SCORE_EXACT_TITLE = 400
_SCORE_PREFIX_TITLE = 300
_SCORE_WORDS_IN_TITLE = 200
_SCORE_WORDS_IN_HEADING = 100


@dataclass(frozen=True)
class SearchHit:
    """One matched page, ready for the results list."""

    path: Path  # absolute .md page to open (feeds OKFViewer.show_page)
    title: str  # display title
    breadcrumb: str  # ancestor-dir chain joined by BREADCRUMB_SEP
    matched_on: str  # "title" | "heading"
    score: int  # higher = better


@dataclass(frozen=True)
class _Entry:
    """One indexed page: display fields plus lowercased haystacks for matching."""

    path: Path
    title: str
    breadcrumb: str
    order: int  # position in the curated walk — the stable tie-break
    title_lower: str
    headings_lower: tuple[str, ...]


@dataclass(frozen=True)
class SearchIndex:
    """An immutable, in-memory index of a bundle's navigable pages."""

    entries: tuple[_Entry, ...]


class SearchProvider(Protocol):
    """A pluggable search backend — the viewer's optional override seam.

    okf_reader's built-in title/heading search (see `BundleSearcher`) needs no
    app knowledge, so the viewer uses it by default. An embedding app may inject
    its own (e.g. a full-text or unified backend) instead.
    """

    def search(self, query: str) -> list[SearchHit]:
        """Return the pages matching ``query``, best first."""
        ...


def _extract_headings(text: str) -> list[str]:
    """Return the ATX heading texts of a page body, in document order (tolerant).

    A line scan (not a full markdown-it parse) for speed — the whole bundle is
    indexed at once. Frontmatter is stripped first (a ``#`` there is a YAML
    comment), and fenced code blocks are skipped so a ``#`` comment inside one is
    not mistaken for a heading — the same guard `render.dir_title` uses.
    """
    _, body = parse_frontmatter(text)
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


def build_search_index(bundle: Path, *, include_headings: bool = True) -> SearchIndex:
    """Walk ``bundle`` into a searchable index of its concept pages.

    Titles come from the bundle walk's frontmatter reads (no extra I/O); heading
    texts, when ``include_headings`` is set, cost one read per page. Intended to
    be built once and cached — the whole bundle is walked. An unreadable page
    contributes its title but no headings rather than failing the build (SPEC §9).

    Args:
        bundle: The OKF bundle root directory.
        include_headings: Also index each page's headings (one read per page).
            Titles-only skips all body reads.

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
                if include_headings:
                    try:
                        text = child.path.read_text(encoding="utf-8")
                    except OSError:
                        text = ""
                    headings = tuple(_extract_headings(text))
                entries.append(
                    _Entry(
                        path=child.path,
                        title=child.title,
                        breadcrumb=BREADCRUMB_SEP.join(crumbs),
                        order=counter,
                        title_lower=child.title.lower(),
                        headings_lower=tuple(h.lower() for h in headings),
                    )
                )
                counter += 1

    walk(load_bundle_tree(bundle), ())
    return SearchIndex(tuple(entries))


def _score_entry(entry: _Entry, terms: list[str], query: str) -> tuple[int, str] | None:
    """Score ``entry`` against a query, or None if it does not match.

    AND semantics: every term must appear in the title or some heading. The tier
    is decided by the strongest title relationship, falling through to a
    heading-only match.
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
    return None


def search_index(index: SearchIndex, query: str, *, limit: int = 50) -> list[SearchHit]:
    """Return the pages matching ``query``, best first.

    Case-insensitive, whitespace-tokenized, AND semantics (all words must be
    present). Ranking: exact title, then title prefix, then all-words-in-title,
    then all-words across title+headings; ties break on the curated walk order.
    An empty (or whitespace-only) query returns no hits.

    Args:
        index: The index to search.
        query: The user's search string.
        limit: Maximum number of hits to return.

    Returns:
        Up to ``limit`` `SearchHit`s, ordered best first.

    """
    q = query.strip().lower()
    terms = q.split()
    if not terms:
        return []
    scored: list[tuple[int, int, SearchHit]] = []
    for entry in index.entries:
        result = _score_entry(entry, terms, q)
        if result is None:
            continue
        score, matched_on = result
        scored.append(
            (
                score,
                entry.order,
                SearchHit(
                    path=entry.path,
                    title=entry.title,
                    breadcrumb=entry.breadcrumb,
                    matched_on=matched_on,
                    score=score,
                ),
            )
        )
    # Best score first; the curated walk order breaks ties (ascending).
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [hit for _score, _order, hit in scored[:limit]]


class BundleSearcher:
    """The built-in `SearchProvider`: lazily builds and caches a bundle's index.

    The index is built on the first `search` call (a whole-bundle walk) and
    reused thereafter, so constructing one is cheap — the viewer can make it up
    front and pay the cost only if the user actually searches.
    """

    def __init__(self, bundle: Path, *, include_headings: bool = True, limit: int = 50) -> None:
        self._bundle = bundle
        self._include_headings = include_headings
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
            self._index = build_search_index(self._bundle, include_headings=self._include_headings)

    def search(self, query: str) -> list[SearchHit]:
        """Return the bundle pages matching ``query`` (building the index once)."""
        if not query.strip():
            return []
        self.warm()
        assert self._index is not None
        return search_index(self._index, query, limit=self._limit)
