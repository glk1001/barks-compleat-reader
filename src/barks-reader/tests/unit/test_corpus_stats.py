"""Tests for the corpus-wide statistics aggregator.

These are characterization tests: the expected figures are pinned against the
real ``barks_fantagraphics`` data, so a change to the corpus fails here and has
to be acknowledged rather than sliding through unnoticed.

No Kivy, no ``barks_reader.ui`` - this module is core and must stay that way.
"""
# ruff: noqa: PLR2004

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS
from barks_fantagraphics.comic_book_info import COVERS_SET, ONE_PAGERS
from barks_reader.core.corpus_stats import (
    CorpusStats,
    StatSection,
    _adjusted_payment_total,
    _paid_records,
    compute_static_stats,
    compute_text_stats,
    get_stories,
)

if TYPE_CHECKING:
    from pathlib import Path

_NUM_STORIES = 683


@pytest.fixture(scope="module")
def stats() -> CorpusStats:
    return compute_static_stats()


def _section(stats: CorpusStats, heading: str) -> StatSection:
    return next(s for s in stats.sections if s.heading == heading)


def _value(stats: CorpusStats, heading: str, label: str) -> str:
    return next(r.value for r in _section(stats, heading).rows if r.label == label)


class TestStorySelection:
    """The story set excludes covers, prose articles and collection entries."""

    def test_story_count(self) -> None:
        assert len(get_stories()) == _NUM_STORIES

    def test_covers_are_excluded(self) -> None:
        story_titles = {info.title for info in get_stories()}
        assert not (story_titles & COVERS_SET)

    def test_one_pagers_are_included(self) -> None:
        story_titles = {info.title for info in get_stories()}
        assert set(ONE_PAGERS) <= story_titles


class TestOpening:
    def test_headline_gives_the_count_and_the_span(self, stats: CorpusStats) -> None:
        assert stats.opening.headline == "683 stories, 1942\u20131973"

    def test_standfirst_gives_the_pages_and_the_rate(self, stats: CorpusStats) -> None:
        assert stats.opening.standfirst.startswith("6,591 pages,")
        assert stats.opening.standfirst.endswith("a page.")

    def test_standfirst_rate_matches_the_payment_row(self, stats: CorpusStats) -> None:
        # The opening hands the reader a rate to judge the rest of the page by,
        # so it has to be the same rate the Payment section reports.
        per_page = _value(stats, "Payment", "Per page, 2026 dollars")
        assert per_page in stats.opening.standfirst


class TestCorpusSection:
    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("Stories", "683"),
            ("One-pagers", "155"),
            ("Covers", "264"),
            ("Fantagraphics volumes", "30"),
            ("Submitted to Western", "1942–1973"),  # noqa: RUF001
        ],
    )
    def test_row(self, stats: CorpusStats, label: str, expected: str) -> None:
        assert _value(stats, "The corpus", label) == expected


class TestAttributionSection:
    """Attribution comes from Barrier's bibliography, never from is_barks_title."""

    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("Script and art", "561"),
            ("Art only", "80"),
            ("Script only", "27"),
            ("Art and rewritten script", "8"),
            ("Not in Barrier's bibliography", "7"),
        ],
    )
    def test_row(self, stats: CorpusStats, label: str, expected: str) -> None:
        assert _value(stats, "Barks's hand", label) == expected

    def test_rows_account_for_every_story(self, stats: CorpusStats) -> None:
        total = sum(int(row.value.replace(",", "")) for row in _section(stats, "Barks's hand").rows)
        assert total == _NUM_STORIES

    def test_is_barks_title_would_have_given_a_different_answer(self) -> None:
        # Guards the trap the module docstring warns about: is_barks_title means
        # "Barks titled it", not "Barks made it", and is nowhere near 561.
        assert sum(1 for info in get_stories() if info.is_barks_title) == 326


class TestLengthSection:
    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("One page", "161"),
            ("Short (2–15 pages)", "403"),  # noqa: RUF001
            ("Long (16+ pages)", "119"),
            ("Story pages", "6,591"),
            ("Mean pages per story", "9.7"),
            ("Longest story", "Donald Duck Finds Pirate Gold, 64 pages"),
        ],
    )
    def test_row(self, stats: CorpusStats, label: str, expected: str) -> None:
        assert _value(stats, "Length", label) == expected

    def test_bands_partition_the_stories(self, stats: CorpusStats) -> None:
        bands = ("One page", "Short (2–15 pages)", "Long (16+ pages)")  # noqa: RUF001
        total = sum(int(_value(stats, "Length", label).replace(",", "")) for label in bands)
        assert total == _NUM_STORIES


class TestPaymentSection:
    """The ledger's -1 sentinel must never be summed as a real amount."""

    def test_sentinel_records_are_excluded(self) -> None:
        assert len(_paid_records()) == 564
        assert len(_paid_records()) < len(BARKS_PAYMENTS)

    def test_every_kept_record_has_a_real_amount_and_year(self) -> None:
        assert all(p.payment > 0 and p.accepted_year > 0 for p in _paid_records())

    def test_nominal_total_exceeds_a_blind_sum(self, stats: CorpusStats) -> None:
        # Blindly summing the column subtracts a dollar for each of the 383
        # sentinel rows, so the correct total is the larger of the two.
        blind = sum(p.payment for p in BARKS_PAYMENTS.values())
        correct = sum(p.payment for p in _paid_records())
        assert correct > blind
        assert _value(stats, "Payment", "Total paid") == f"${correct:,.0f}"

    def test_inflation_adjustment_is_a_large_multiple(self) -> None:
        paid = _paid_records()
        nominal = sum(p.payment for p in paid)
        assert _adjusted_payment_total(paid) > nominal * 10

    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("Total paid", "$216,894"),
            ("Paid pages", "6,250"),
            ("Largest single payment", "$1,200"),
        ],
    )
    def test_row(self, stats: CorpusStats, label: str, expected: str) -> None:
        assert _value(stats, "Payment", label) == expected

    def test_footnote_states_the_coverage(self, stats: CorpusStats) -> None:
        footnote = _section(stats, "Payment").footnote
        assert footnote is not None
        assert "564 of 947" in footnote


class TestCastSection:
    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("Named characters", "49"),
            ("Places", "62"),
            ("Themes", "78"),
            ("Things", "43"),
            ("Most-tagged character", "Gyro Gearloose, 73 stories"),
        ],
    )
    def test_row(self, stats: CorpusStats, label: str, expected: str) -> None:
        assert _value(stats, "The cast", label) == expected


class TestTextStats:
    """The dialogue section needs the optional index and degrades to None."""

    def test_missing_directory(self, tmp_path: Path) -> None:
        assert compute_text_stats(tmp_path / "not-there") is None

    def test_empty_directory(self, tmp_path: Path) -> None:
        # A directory with no Whoosh index must not raise a Whoosh error out of
        # core - the page renders fine without this section.
        assert compute_text_stats(tmp_path) is None

    def test_directory_with_junk_in_it(self, tmp_path: Path) -> None:
        (tmp_path / "readme.txt").write_text("not an index")
        assert compute_text_stats(tmp_path) is None


class TestStructure:
    def test_five_always_available_sections(self, stats: CorpusStats) -> None:
        assert [s.heading for s in stats.sections] == [
            "The corpus",
            "Barks's hand",
            "Length",
            "Payment",
            "The cast",
        ]

    def test_shares_are_set_only_where_the_rows_partition_a_whole(self, stats: CorpusStats) -> None:
        # A bar is only readable against its siblings, so a share belongs on a
        # group whose rows are all slices of one total - and nowhere else.
        with_shares = {
            section.heading
            for section in stats.sections
            if any(row.share is not None for row in section.rows)
        }
        assert with_shares == {"Barks's hand", "Length"}

    def test_attribution_shares_cover_the_whole_corpus(self, stats: CorpusStats) -> None:
        rows = _section(stats, "Barks's hand").rows
        shares = [row.share for row in rows if row.share is not None]
        assert len(shares) == len(rows)
        assert sum(shares) == pytest.approx(1.0)

    def test_length_band_shares_cover_the_whole_corpus(self, stats: CorpusStats) -> None:
        banded = [row.share for row in _section(stats, "Length").rows if row.share is not None]
        assert len(banded) == 3
        assert sum(banded) == pytest.approx(1.0)

    def test_every_share_is_a_fraction(self, stats: CorpusStats) -> None:
        for section in stats.sections:
            for row in section.rows:
                if row.share is not None:
                    assert 0.0 <= row.share <= 1.0

    def test_named_values_are_marked_as_prose(self, stats: CorpusStats) -> None:
        # These two carry a story title and a character name; everything else on
        # the page is a figure that belongs in the right-hand column.
        prose = {
            (section.heading, row.label)
            for section in stats.sections
            for row in section.rows
            if row.prose
        }
        assert prose == {("Length", "Longest story"), ("The cast", "Most-tagged character")}

    def test_every_row_has_a_label_and_a_value(self, stats: CorpusStats) -> None:
        for section in stats.sections:
            assert section.rows
            for row in section.rows:
                assert row.label
                assert row.value
