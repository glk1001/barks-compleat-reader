"""Tests for the wiki story-order diagnostic.

Both cases here are mistakes the script made before they were caught: apostrophes
turned into separators (which silently dropped pages from the comparison) and an
off-by-one in counting inversions.
"""

# ruff: noqa: PLR2004  (small literal counts are the point of these tests)

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import check_wiki_story_order
from check_wiki_story_order import Entry, inversions, linked_entries, report, slugify

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class TestSlugify:
    def test_apostrophes_vanish_rather_than_separate(self) -> None:
        """The bundle writes "That's No Fable!" as thats-no-fable, not that-s-no-fable."""
        assert slugify("That's No Fable!") == "thats-no-fable"
        assert slugify("The Old Castle's Secret") == "the-old-castles-secret"

    def test_curly_apostrophes_too(self) -> None:
        assert slugify("That\u2019s No Fable!") == "thats-no-fable"

    def test_punctuation_and_ampersands(self) -> None:
        assert slugify("Lost in the Andes!") == "lost-in-the-andes"
        assert slugify("Trick & Treat") == "trick-and-treat"
        assert slugify("Micro-Ducks from Outer Space") == "micro-ducks-from-outer-space"


class TestInversions:
    @staticmethod
    def _entries(*ranks: int) -> list[Entry]:
        return [Entry(f"s{r}", f"T{r}", r) for r in ranks]

    def test_sorted_has_none(self) -> None:
        assert inversions(self._entries(1, 2, 3, 4)) == []

    def test_counts_each_out_of_order_pair_once(self) -> None:
        # One story out of place makes exactly one inverted adjacent pair.
        found = inversions(self._entries(1, 3, 2, 4))
        assert [(a.rank, b.rank) for a, b in found] == [(3, 2)]

    def test_fully_reversed(self) -> None:
        assert len(inversions(self._entries(4, 3, 2, 1))) == 3

    def test_too_short_to_invert(self) -> None:
        assert inversions(self._entries(9)) == []
        assert inversions([]) == []


class TestLinkedEntries:
    def test_reads_links_in_order_and_reports_unknowns(self, tmp_path: Path) -> None:
        index = tmp_path / "index.md"
        index.write_text(
            "[up](../../index.md)\n"  # a path, not a same-directory slug
            "- [B](beta.md)\n"
            "- [A](alpha.md)\n"
            "- [?](mystery.md)\n",
            encoding="utf-8",
        )
        ranks = {
            "alpha": Entry("alpha", "Alpha", 1),
            "beta": Entry("beta", "Beta", 2),
        }

        found, unknown = linked_entries(index, ranks)

        assert [e.slug for e in found] == ["beta", "alpha"]  # listed order, not sorted
        assert unknown == ["mystery"]


class TestReport:
    """The exit codes full-lint.sh leans on."""

    @staticmethod
    def _bundle(tmp_path: Path, *slugs: str) -> Path:
        index = tmp_path / "concept" / "stories" / "donald-duck-adventures" / "index.md"
        index.parent.mkdir(parents=True)
        index.write_text(
            "".join(f"- [{s}]({s}.md)\n" for s in slugs),
            encoding="utf-8",
        )
        return tmp_path

    def test_absent_bundle_is_not_a_failure(self, tmp_path: Path) -> None:
        """Most checkouts have no sibling wiki repo, and CI never does."""
        assert report(tmp_path / "nowhere", quiet=True) == 0

    def test_bundle_present_but_empty_is_suspicious(self, tmp_path: Path) -> None:
        assert report(tmp_path, quiet=True) == 2

    def test_out_of_order_fails(self, tmp_path: Path) -> None:
        # The real case: The Golden Christmas Tree was submitted before Lost in
        # the Andes, so listing it second is the wrong way round.
        bundle = self._bundle(tmp_path, "lost-in-the-andes", "the-golden-christmas-tree")
        assert report(bundle, quiet=True) == 1

    def test_in_order_passes(self, tmp_path: Path) -> None:
        bundle = self._bundle(tmp_path, "the-golden-christmas-tree", "lost-in-the-andes")
        assert report(bundle, quiet=True) == 0

    def test_the_report_names_each_pair_the_wrong_way_round(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bundle = self._bundle(tmp_path, "lost-in-the-andes", "the-golden-christmas-tree", "nope")

        assert report(bundle, show_order=True) == 1

        out = capsys.readouterr().out
        assert "donald-duck-adventures  (2 story links, 1 unrecognised)" in out
        assert "Lost in the Andes!\n" in out
        assert "The Golden Christmas Tree   <- listed after, belongs before" in out
        # The corrected order, as file names to paste back into the index.
        corrected = out[out.index("corrected order:") :].splitlines()[1:3]
        assert corrected == ["    the-golden-christmas-tree.md", "    lost-in-the-andes.md"]
        assert "1 out-of-order pairs across 1 story indexes" in out

    def test_an_index_in_order_is_said_to_be_unless_quiet(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bundle = self._bundle(tmp_path, "the-golden-christmas-tree", "lost-in-the-andes")

        assert report(bundle) == 0
        assert "  in chronological order" in capsys.readouterr().out

        assert report(bundle, quiet=True) == 0
        assert capsys.readouterr().out.strip() == "0 out-of-order pairs across 1 story indexes"


class TestMain:
    def test_the_flags_reach_the_report(self, tmp_path: Path) -> None:
        with patch.object(check_wiki_story_order, "report", return_value=1) as run:
            status = check_wiki_story_order.main(
                ["--bundle", str(tmp_path), "--show-order", "--quiet"]
            )

        assert status == 1
        run.assert_called_once_with(tmp_path, show_order=True, quiet=True)

    def test_with_no_flags_it_reports_on_the_sibling_wiki_in_full(self) -> None:
        with patch.object(check_wiki_story_order, "report", return_value=0) as run:
            assert check_wiki_story_order.main([]) == 0

        run.assert_called_once_with(
            check_wiki_story_order.DEFAULT_BUNDLE, show_order=False, quiet=False
        )
