"""Unit tests for bundle search (``okf_reader.core.search``).

These pin the index build (curated order, breadcrumbs, heading extraction,
tolerance) and the query ranking (exact > prefix > words-in-title > heading,
AND semantics, empty query, limit).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from okf_reader.core.search import (
    BundleSearcher,
    build_search_index,
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
        index = build_search_index(_make_bundle(tmp_path), include_headings=False)
        assert search_index(index, "payment") == []

    def test_fenced_code_hash_not_a_heading(self, tmp_path: Path) -> None:
        """A ``#`` comment inside a fenced code block is not indexed as a heading."""
        bundle = tmp_path / "b"
        bundle.mkdir()
        (bundle / "index.md").write_text("# B\n", encoding="utf-8")
        (bundle / "a.md").write_text(
            _page("Recipe", "# Recipe\n\n```\n# not a heading\n```\n"), encoding="utf-8"
        )
        assert search_index(build_search_index(bundle), "not a heading") == []

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

    def test_limit_respected(self, tmp_path: Path) -> None:
        """No more than ``limit`` hits come back."""
        bundle = tmp_path / "b"
        bundle.mkdir()
        (bundle / "index.md").write_text("# B\n", encoding="utf-8")
        for i in range(5):
            (bundle / f"p{i}.md").write_text(_page(f"Duck {i}"), encoding="utf-8")
        limit = 3
        assert len(search_index(build_search_index(bundle), "duck", limit=limit)) == limit


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
