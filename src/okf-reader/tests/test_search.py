"""Unit tests for bundle search (``okf_reader.core.search``).

These pin the index build (curated order, breadcrumbs, heading and text
extraction, tolerance) and the query ranking (exact > prefix > words-in-title >
heading > text, AND semantics, phrases, empty query, limit), and the snippets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from okf_reader.core.search import (
    _ELLIPSIS,
    BundleSearcher,
    build_search_index,
    page_text,
    parse_query,
    search_index,
)

if TYPE_CHECKING:
    from pathlib import Path


def _page(frontmatter_title: str, body: str = "") -> str:
    return f"---\ntitle: {frontmatter_title}\n---\n{body}"


def _make_bundle(tmp_path: Path) -> Path:
    """Build a small bundle: a curated stories dir plus a loose article.

    stories/index.md lists dither before guess, so the curated walk must return
    them in that order regardless of filename sort.
    """
    bundle = tmp_path / "bundle"
    stories = bundle / "stories"
    stories.mkdir(parents=True)
    (bundle / "index.md").write_text("# Home\n\n- [Stories](stories/index.md)\n", encoding="utf-8")
    (stories / "index.md").write_text(
        "# Stories\n\n- [Dither](dither.md)\n- [Guess](guess.md)\n", encoding="utf-8"
    )
    (stories / "guess.md").write_text(
        _page("You Can't Guess!", "# You Can't Guess!\n\n## The Bomb\n\nText.\n"),
        encoding="utf-8",
    )
    (stories / "dither.md").write_text(
        _page("Ten-Dollar Dither", "# Ten-Dollar Dither\n\n## Payment Dispute\n"),
        encoding="utf-8",
    )
    return bundle


class TestBuildIndex:
    def test_entries_follow_curated_order(self, tmp_path: Path) -> None:
        """Pages come back in the index.md listing order, not filename order."""
        index = build_search_index(_make_bundle(tmp_path))
        titles = [e.title for e in index.entries]
        assert titles == ["Ten-Dollar Dither", "You Can't Guess!"]

    def test_breadcrumb_is_ancestor_dir_titles(self, tmp_path: Path) -> None:
        """Each entry carries its parent-dir chain for display."""
        index = build_search_index(_make_bundle(tmp_path))
        assert all(e.breadcrumb == "Stories" for e in index.entries)

    def test_headings_indexed(self, tmp_path: Path) -> None:
        """Body headings are searchable, not just the title."""
        hits = search_index(build_search_index(_make_bundle(tmp_path)), "payment")
        assert [h.title for h in hits] == ["Ten-Dollar Dither"]
        assert hits[0].matched_on == "heading"

    def test_headings_skipped_when_disabled(self, tmp_path: Path) -> None:
        """Titles-only build does no heading matching."""
        index = build_search_index(
            _make_bundle(tmp_path), include_headings=False, include_text=False
        )
        assert search_index(index, "payment") == []

    def test_fenced_code_hash_not_a_heading(self, tmp_path: Path) -> None:
        """A ``#`` comment inside a fenced code block is not indexed as a heading."""
        bundle = tmp_path / "b"
        bundle.mkdir()
        (bundle / "index.md").write_text("# B\n", encoding="utf-8")
        (bundle / "a.md").write_text(
            _page("Recipe", "# Recipe\n\n```\n# not a heading\n```\n"), encoding="utf-8"
        )
        index = build_search_index(bundle)
        assert index.entries[0].headings_lower == ("recipe",)
        assert [h.matched_on for h in search_index(index, "not a heading")] == ["text"]

    def test_reserved_files_excluded(self, tmp_path: Path) -> None:
        """index.md/log.md are not concept pages and never appear as hits."""
        index = build_search_index(_make_bundle(tmp_path))
        assert all(e.path.name not in ("index.md", "log.md") for e in index.entries)

    def test_page_without_headings_indexes_title(self, tmp_path: Path) -> None:
        """A page with no body headings still indexes, with an empty heading set."""
        bundle = tmp_path / "b"
        bundle.mkdir()
        (bundle / "index.md").write_text("# B\n", encoding="utf-8")
        (bundle / "plain.md").write_text(_page("Plain", "Just prose, no headings.\n"), "utf-8")
        index = build_search_index(bundle)
        plain = next(e for e in index.entries if e.path.name == "plain.md")
        assert plain.headings_lower == ()


class TestRanking:
    def test_exact_beats_prefix_beats_substring(self, tmp_path: Path) -> None:
        """A query that exactly matches one title ranks it above partial matches."""
        bundle = tmp_path / "b"
        bundle.mkdir()
        (bundle / "index.md").write_text("# B\n", encoding="utf-8")
        (bundle / "duck.md").write_text(_page("Duck"), encoding="utf-8")
        (bundle / "duckling.md").write_text(_page("Duckling"), encoding="utf-8")
        (bundle / "lucky.md").write_text(_page("A Lucky Duck Tale"), encoding="utf-8")
        hits = search_index(build_search_index(bundle), "duck")
        assert [h.title for h in hits] == ["Duck", "Duckling", "A Lucky Duck Tale"]

    def test_title_match_beats_heading_match(self, tmp_path: Path) -> None:
        """A word in the title outranks the same word only in a heading."""
        bundle = tmp_path / "b"
        bundle.mkdir()
        (bundle / "index.md").write_text("# B\n", encoding="utf-8")
        (bundle / "a.md").write_text(_page("Gold Story", "# Gold Story\n"), encoding="utf-8")
        (bundle / "z.md").write_text(_page("Other", "# Other\n\n## Gold Rush\n"), encoding="utf-8")
        hits = search_index(build_search_index(bundle), "gold")
        assert [h.title for h in hits] == ["Gold Story", "Other"]
        assert hits[0].matched_on == "title"
        assert hits[1].matched_on == "heading"

    def test_and_semantics(self, tmp_path: Path) -> None:
        """Every query word must be present; a page missing one is excluded."""
        index = build_search_index(_make_bundle(tmp_path))
        assert [h.title for h in search_index(index, "ten dither")] == ["Ten-Dollar Dither"]
        assert search_index(index, "ten guess") == []

    def test_case_insensitive(self, tmp_path: Path) -> None:
        """Matching ignores case on both sides."""
        index = build_search_index(_make_bundle(tmp_path))
        assert [h.title for h in search_index(index, "TEN-DOLLAR")] == ["Ten-Dollar Dither"]

    def test_empty_query_returns_nothing(self, tmp_path: Path) -> None:
        """A blank or whitespace-only query is not a match-everything."""
        index = build_search_index(_make_bundle(tmp_path))
        assert search_index(index, "") == []
        assert search_index(index, "   ") == []

    def test_quoted_phrase_matches_its_words_in_order(self, tmp_path: Path) -> None:
        """The words inside quotes match together, in order, not as separate words."""
        bundle = tmp_path / "b"
        bundle.mkdir()
        (bundle / "index.md").write_text("# B\n", encoding="utf-8")
        (bundle / "a.md").write_text(_page("Letter to Glen Brown"), encoding="utf-8")
        (bundle / "z.md").write_text(_page("Brown Glen Walk"), encoding="utf-8")
        index = build_search_index(bundle)
        assert [h.title for h in search_index(index, '"glen brown"')] == ["Letter to Glen Brown"]
        assert len(search_index(index, "glen brown")) == 2  # noqa: PLR2004 — unquoted: both

    def test_quoted_exact_title_ranks_as_exact(self, tmp_path: Path) -> None:
        """Quotes round a whole title still give the exact-title tier."""
        index = build_search_index(_make_bundle(tmp_path))
        hits = search_index(index, '"ten-dollar dither"')
        assert [h.title for h in hits] == ["Ten-Dollar Dither"]
        assert hits[0].score == search_index(index, "ten-dollar dither")[0].score

    def test_quotes_alone_find_nothing(self, tmp_path: Path) -> None:
        """A lone quote, or an empty pair, is no query: it does not match every page."""
        index = build_search_index(_make_bundle(tmp_path))
        assert search_index(index, '"') == []
        assert search_index(index, '""') == []

    def test_apostrophes_match_straight_or_curly(self, tmp_path: Path) -> None:
        """A typed straight apostrophe finds a curly one, and the other way round."""
        bundle = tmp_path / "b"
        bundle.mkdir()
        (bundle / "index.md").write_text("# B\n", encoding="utf-8")
        (bundle / "a.md").write_text(_page("Scrooge’s Quest"), encoding="utf-8")  # noqa: RUF001
        index = build_search_index(bundle)
        assert [h.title for h in search_index(index, "scrooge's")] == ["Scrooge’s Quest"]  # noqa: RUF001
        assert [h.title for h in search_index(index, "scrooge’s")] == ["Scrooge’s Quest"]  # noqa: RUF001

    def test_limit_respected(self, tmp_path: Path) -> None:
        """No more than ``limit`` hits come back."""
        bundle = tmp_path / "b"
        bundle.mkdir()
        (bundle / "index.md").write_text("# B\n", encoding="utf-8")
        for i in range(5):
            (bundle / f"p{i}.md").write_text(_page(f"Duck {i}"), encoding="utf-8")
        limit = 3
        assert len(search_index(build_search_index(bundle), "duck", limit=limit)) == limit


_OPEN, _CLOSE = "\u201c", "\u201d"  # curly double quotes


def _text_bundle(tmp_path: Path, pages: dict[str, tuple[str, str]]) -> Path:
    """Build a flat bundle of ``{filename: (title, body)}`` pages."""
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "index.md").write_text("# B\n", encoding="utf-8")
    for name, (title, body) in pages.items():
        (bundle / name).write_text(_page(title, body), encoding="utf-8")
    return bundle


class TestPageText:
    @pytest.mark.parametrize(
        ("body", "text"),
        [
            ("# Title\n\nSome *bold* and `code`.", "Title Some bold and code."),
            ("See [the letter](../web/letter.md) here.", "See the letter here."),
            (
                "![a cover](cover.jpg) and [ref words][1]\n\n[1]: http://x.y",
                "a cover and ref words",
            ),
            ("| A | B |\n|---|:-:|\n| 1 | 2 |", "A B 1 2"),
            ("> quoted\n> on\n\n<!-- note -->ok <br> done", "quoted on ok done"),
            ("```python\nx = 1\n```", "x = 1"),
        ],
    )
    def test_markdown_marks_go(self, body: str, text: str) -> None:
        assert page_text(body) == text


class TestTextSearch:
    def test_words_in_the_text_find_the_page(self, tmp_path: Path) -> None:
        """A page whose title and headings lack the words is found by its text."""
        bundle = _text_bundle(
            tmp_path, {"a.md": ("Carl Barks", "He wrote to\nGlen Brown in 1974.")}
        )
        hits = search_index(build_search_index(bundle), '"glen brown"')
        assert [(h.title, h.matched_on) for h in hits] == [("Carl Barks", "text")]

    def test_a_url_is_not_text(self, tmp_path: Path) -> None:
        """A link's target is not what the reader sees, so it does not match."""
        bundle = _text_bundle(tmp_path, {"a.md": ("A", "[the letter](glen-brown-1974.md)")})
        index = build_search_index(bundle)
        assert search_index(index, "glen-brown") == []
        assert len(search_index(index, "the letter")) == 1

    def test_title_and_heading_hits_rank_above_text_hits(self, tmp_path: Path) -> None:
        bundle = _text_bundle(
            tmp_path,
            {
                "a.md": ("Other", "gold gold gold gold"),
                "b.md": ("Mine", "# Mine\n\n## Gold Rush\n"),
                "c.md": ("Gold", ""),
            },
        )
        hits = search_index(build_search_index(bundle), "gold")
        assert [(h.title, h.matched_on) for h in hits] == [
            ("Gold", "title"),
            ("Mine", "heading"),
            ("Other", "text"),
        ]

    def test_more_mentions_rank_first(self, tmp_path: Path) -> None:
        """Among text hits, the page naming the words more often comes first."""
        bundle = _text_bundle(
            tmp_path,
            {"a.md": ("Once", "a grotto."), "b.md": ("Thrice", "grotto, grotto and grotto.")},
        )
        hits = search_index(build_search_index(bundle), "grotto")
        assert [h.title for h in hits] == ["Thrice", "Once"]

    def test_terms_may_split_between_title_and_text(self, tmp_path: Path) -> None:
        bundle = _text_bundle(tmp_path, {"a.md": ("Carl Barks", "A letter to a fan.")})
        assert [h.matched_on for h in search_index(build_search_index(bundle), "barks fan")] == [
            "text"
        ]

    def test_text_skipped_when_disabled(self, tmp_path: Path) -> None:
        bundle = _text_bundle(tmp_path, {"a.md": ("A", "hidden words")})
        assert search_index(build_search_index(bundle, include_text=False), "hidden") == []


class TestSnippet:
    def test_a_title_hit_has_no_snippet(self, tmp_path: Path) -> None:
        hits = search_index(build_search_index(_make_bundle(tmp_path)), "dither")
        assert (hits[0].snippet, hits[0].snippet_match) == ("", (0, 0))

    def test_the_match_is_marked_in_the_text_case(self, tmp_path: Path) -> None:
        bundle = _text_bundle(tmp_path, {"a.md": ("A", "He wrote to Glen Brown in 1974.")})
        hit = search_index(build_search_index(bundle), '"glen brown"')[0]
        start, end = hit.snippet_match
        assert hit.snippet == "He wrote to Glen Brown in 1974."
        assert hit.snippet[start:end] == "Glen Brown"

    def test_a_long_text_is_cut_at_words_with_ellipses(self, tmp_path: Path) -> None:
        words = " ".join(f"w{i}" for i in range(100))
        bundle = _text_bundle(tmp_path, {"a.md": ("A", f"{words} needle {words}")})
        hit = search_index(build_search_index(bundle), "needle")[0]
        start, end = hit.snippet_match
        assert hit.snippet[start:end] == "needle"
        assert hit.snippet.startswith(_ELLIPSIS + "w")
        assert hit.snippet.endswith(_ELLIPSIS)
        assert all(
            word.startswith(("w", "needle")) for word in hit.snippet.strip(_ELLIPSIS).split()
        )
        assert start <= 32  # noqa: PLR2004 — the match stays near the row's start

    def test_the_rarest_term_is_shown(self, tmp_path: Path) -> None:
        bundle = _text_bundle(tmp_path, {"a.md": ("A", "duck duck duck duck goose")})
        hit = search_index(build_search_index(bundle), "duck goose")[0]
        start, end = hit.snippet_match
        assert hit.snippet[start:end] == "goose"

    def test_a_curly_apostrophe_keeps_the_offsets(self, tmp_path: Path) -> None:
        bundle = _text_bundle(tmp_path, {"a.md": ("A", "In Scrooge\u2019s bin.")})
        hit = search_index(build_search_index(bundle), "scrooge's")[0]
        start, end = hit.snippet_match
        assert hit.snippet[start:end] == "Scrooge\u2019s"


class TestParseQuery:
    @pytest.mark.parametrize(
        ("query", "terms"),
        [
            ("gold  rush", ["gold", "rush"]),
            ('"glen brown"', ["glen brown"]),
            ('letter "glen brown" 1974', ["letter", "glen brown", "1974"]),
            ('"glen bro', ["glen bro"]),  # an open quote: the rest is the phrase
            (f"{_OPEN}glen   brown{_CLOSE}", ["glen brown"]),  # curly quotes, spaces folded
            ('"" "', []),
            ("Scrooge’s", ["scrooge's"]),  # noqa: RUF001
        ],
    )
    def test_terms(self, query: str, terms: list[str]) -> None:
        assert parse_query(query) == terms


class TestBundleSearcher:
    def test_builds_once_and_queries(self, tmp_path: Path) -> None:
        """The lazy searcher answers a query and caches the built index."""
        searcher = BundleSearcher(_make_bundle(tmp_path))
        assert [h.title for h in searcher.search("guess")] == ["You Can't Guess!"]
        # Second call reuses the cached index (same answer, no rebuild needed).
        assert [h.title for h in searcher.search("guess")] == ["You Can't Guess!"]

    def test_blank_query_short_circuits(self, tmp_path: Path) -> None:
        """A blank query returns nothing without forcing an index build."""
        searcher = BundleSearcher(_make_bundle(tmp_path))
        assert searcher.search("  ") == []
        assert searcher.is_ready is False

    def test_warm_builds_index_ahead_of_search(self, tmp_path: Path) -> None:
        """warm() makes the searcher ready so a later search does not build inline."""
        searcher = BundleSearcher(_make_bundle(tmp_path))
        assert searcher.is_ready is False
        searcher.warm()
        assert searcher.is_ready is True
        searcher.warm()  # idempotent — a second call is a no-op
        assert [h.title for h in searcher.search("guess")] == ["You Can't Guess!"]

    def test_search_marks_ready(self, tmp_path: Path) -> None:
        """A non-blank search builds the index and leaves the searcher ready."""
        searcher = BundleSearcher(_make_bundle(tmp_path))
        searcher.search("guess")
        assert searcher.is_ready is True
