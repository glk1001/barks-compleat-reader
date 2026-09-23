"""Tests for the corpus-wide statistics aggregator.

These are characterization tests: the expected figures are pinned against the
real ``barks_fantagraphics`` data, so a change to the corpus fails here and has
to be acknowledged rather than sliding through unnoticed.

No Kivy, no ``barks_reader.ui`` - this module is core and must stay that way.
"""
# ruff: noqa: PLR2004

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal
from unittest.mock import patch

import pytest
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import COVERS_SET, ONE_PAGERS
from barks_fantagraphics.entity_types import EntityType
from barks_fantagraphics.search_ports import CorpusTextTotals
from barks_fantagraphics.testing.fake_search import InMemoryFullTextSearch
from barks_reader.core import corpus_stats as corpus_stats_module
from barks_reader.core.corpus_stats import (
    CorpusStats,
    StatSection,
    _adjusted_payment_total,
    _length_section,
    _paid_records,
    compute_static_stats,
    compute_text_stats,
    get_stories,
)
from comic_utils.cpi_calculator import get_adjusted_usd, get_latest_year

if TYPE_CHECKING:
    from pathlib import Path

_NUM_STORIES = 683


def _stats_scope(fixture_name: str, config: pytest.Config) -> Literal["module", "function"]:  # noqa: ARG001
    """Once per module normally; once per test under mutmut.

    mutmut credits everything a fixture computes to the first test that asked
    for it, then runs only that test against each mutant in the computation
    (docs/mutation-testing.md, trap 4). A module-scoped `stats` hid every row
    assertion below from it: 190 false survivors. The suite is not slowed: the
    whole computation takes a few milliseconds.
    """
    return "function" if os.environ.get("MUTANT_UNDER_TEST") else "module"


@pytest.fixture(scope=_stats_scope)
def stats(cpi_db: Path) -> CorpusStats:
    # Inflated with the conftest stand-in, not the shipped cpi.db: that is a
    # git-lfs object, and a bare checkout (CI's) only has the pointer file.
    return compute_static_stats(cpi_db)


def _section(stats: CorpusStats, heading: str) -> StatSection:
    return next(s for s in stats.sections if s.heading == heading)


def _payment_value_starting(stats: CorpusStats, prefix: str) -> str:
    """Return the Payment row whose label starts with `prefix`.

    The rate rows are labelled with the current CPI year, so matching on a prefix
    keeps these tests from needing an edit every time that year rolls over.
    """
    return next(r.value for r in _section(stats, "Payment").rows if r.label.startswith(prefix))


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
        per_page = _payment_value_starting(stats, "Per page")
        assert per_page in stats.opening.standfirst


class TestCorpusSection:
    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("Stories", "683"),
            ("One-pagers", "155"),
            ("Covers", "264"),
            ("Fantagraphics Volumes", "30"),
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
            ("Art, script rewritten", "8"),
            ("Not in the bibliography", "7"),
        ],
    )
    def test_row(self, stats: CorpusStats, label: str, expected: str) -> None:
        assert _value(stats, "Barks's hand", label) == expected

    def test_rows_account_for_every_story(self, stats: CorpusStats) -> None:
        total = sum(int(row.value.replace(",", "")) for row in _section(stats, "Barks's hand").rows)
        assert total == _NUM_STORIES

    def test_the_footnote_credits_the_bibliography(self, stats: CorpusStats) -> None:
        assert (
            _section(stats, "Barks's hand").footnote
            == "Attribution as stated in Michael Barrier's bibliography."
        )

    def test_is_barks_title_would_have_given_a_different_answer(self) -> None:
        # Guards the trap the module docstring warns about: is_barks_title means
        # "Barks titled it", not "Barks made it", and is nowhere near 561.
        assert sum(1 for info in get_stories() if info.is_barks_title) == 326


class TestLengthSection:
    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("One page", "161"),
            ("Short (2–12 pages)", "384"),  # noqa: RUF001
            ("Long (13+ pages)", "138"),
            ("Story pages", "6,591"),
            ("Mean pages", "9.7"),
            ("Longest (script and art)", "Vacation Time, 33 pages"),
        ],
    )
    def test_row(self, stats: CorpusStats, label: str, expected: str) -> None:
        assert _value(stats, "Length", label) == expected

    def test_bands_partition_the_stories(self, stats: CorpusStats) -> None:
        bands = ("One page", "Short (2–12 pages)", "Long (13+ pages)")  # noqa: RUF001
        total = sum(int(_value(stats, "Length", label).replace(",", "")) for label in bands)
        assert total == _NUM_STORIES

    def test_no_footnote_while_the_ledger_covers_every_story(self, stats: CorpusStats) -> None:
        assert _section(stats, "Length").footnote is None

    def test_a_shortfall_in_the_ledger_is_footnoted(self) -> None:
        """Built directly: the real ledger has no shortfall, so the branch needs one made."""
        pages = {Titles.LOST_IN_THE_ANDES: 32, Titles.VACATION_TIME: 33}
        section = _length_section(
            pages, total_pages=65, num_stories=3, script_and_art=frozenset({Titles.VACATION_TIME})
        )
        assert section.footnote == (
            "Page figures cover 2 of 3 stories; the rest are absent from the payment ledger."
        )
        assert _length_section(pages, 65, 2, frozenset({Titles.VACATION_TIME})).footnote is None
        longest = next(r.value for r in section.rows if r.label == "Longest (script and art)")
        assert longest == "Vacation Time, 33 pages"


class TestLongestScriptAndArtStory:
    def test_it_excludes_a_longer_story_barks_only_drew(self, stats: CorpusStats) -> None:
        # "Donald Duck Finds Pirate Gold" is 64 pages - nearly twice the winner -
        # but Barks drew it to someone else's script, so it must not appear here.
        value = _value(stats, "Length", "Longest (script and art)")
        assert "Pirate Gold" not in value
        assert value == "Vacation Time, 33 pages"

    def test_the_winner_really_is_unqualified_in_the_bibliography(self) -> None:
        from barks_fantagraphics.barks_bibliography import TITLE_TO_BIB_ENTRY  # noqa: PLC0415
        from barks_fantagraphics.barks_titles import Titles  # noqa: PLC0415

        assert TITLE_TO_BIB_ENTRY[Titles.VACATION_TIME].qualifier is None

    def test_no_longer_script_and_art_story_was_passed_over(self, stats: CorpusStats) -> None:
        from barks_fantagraphics.barks_bibliography import TITLE_TO_BIB_ENTRY  # noqa: PLC0415
        from barks_fantagraphics.barks_payments import BARKS_PAYMENTS  # noqa: PLC0415
        from barks_reader.core.corpus_stats import get_stories  # noqa: PLC0415

        longest = max(
            BARKS_PAYMENTS[info.title].num_pages
            for info in get_stories()
            if info.title in BARKS_PAYMENTS
            and (entry := TITLE_TO_BIB_ENTRY.get(info.title)) is not None
            and entry.qualifier is None
        )
        assert _value(stats, "Length", "Longest (script and art)").endswith(f"{longest} pages")


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

    def test_inflation_adjustment_is_a_large_multiple(self, cpi_db: Path) -> None:
        paid = _paid_records()
        nominal = sum(p.payment for p in paid)
        assert _adjusted_payment_total(paid, cpi_db) > nominal * 10

    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("Total paid", "$216,894"),
            ("Paid pages", "6,250"),
        ],
    )
    def test_row(self, stats: CorpusStats, label: str, expected: str) -> None:
        assert _value(stats, "Payment", label) == expected

    def test_per_year_averages_only_the_working_years(
        self, stats: CorpusStats, cpi_db: Path
    ) -> None:
        # Numerator and denominator have to cover the same span. Payments carry on
        # into 1971 (reprint and script work), and counting that money against
        # years that ended in 1966 would overstate the average.
        from barks_reader.core.corpus_stats import _RETIREMENT_YEAR  # noqa: PLC0415

        working = [p for p in _paid_records() if p.accepted_year <= _RETIREMENT_YEAR]
        first_year = min(p.accepted_year for p in working)
        expected = _adjusted_payment_total(working, cpi_db) / (_RETIREMENT_YEAR - first_year + 1)

        assert _payment_value_starting(stats, "Per year") == f"${expected:,.0f}"

    def test_per_year_is_lower_than_averaging_the_whole_ledger(
        self, stats: CorpusStats, cpi_db: Path
    ) -> None:
        # The guard for the mistake above: if the later payments crept back into
        # the numerator the figure would rise, so pin the direction.
        from barks_reader.core.corpus_stats import _RETIREMENT_YEAR  # noqa: PLC0415

        paid = _paid_records()
        first_year = min(p.accepted_year for p in paid)
        naive = _adjusted_payment_total(paid, cpi_db) / (_RETIREMENT_YEAR - first_year + 1)

        reported = float(_payment_value_starting(stats, "Per year").lstrip("$").replace(",", ""))
        assert reported < naive

    def test_the_rate_rows_are_labelled_with_the_tables_latest_year(
        self, stats: CorpusStats, cpi_db: Path
    ) -> None:
        latest = get_latest_year(cpi_db)
        labels = [r.label for r in _section(stats, "Payment").rows]
        assert f"In {latest} dollars" in labels
        assert f"Per page ({latest} dollars)" in labels
        assert f"Per year ({latest} dollars)" in labels

    def test_footnote_states_the_averaged_years(self, stats: CorpusStats) -> None:
        footnote = _section(stats, "Payment").footnote
        assert footnote is not None
        assert "1942-1966" in footnote

    def test_footnote_states_the_coverage(self, stats: CorpusStats) -> None:
        footnote = _section(stats, "Payment").footnote
        assert footnote is not None
        assert "564 of 947" in footnote


class TestAgainstTheShippedCpiTable:
    """The one check that needs the real cpi.db, so it skips where that is absent.

    Everything else runs on the conftest stand-in. This is the guard the stand-in
    cannot give: that the database the app actually ships covers every year the
    ledger asks it about - a payment accepted in a year the table lacks would
    crash the page, and only the real table can say whether one exists.
    """

    def test_every_paid_year_is_in_the_shipped_table(self) -> None:
        years = sorted({p.accepted_year for p in _paid_records()})
        try:
            for year in years:
                get_adjusted_usd(1.0, year)
        except FileNotFoundError as exc:
            # Absent, or a git-lfs pointer (`CpiDatabaseUnavailableError`, a subclass).
            pytest.skip(f"shipped cpi.db not present: {exc}")


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

    def test_the_rows_and_the_footnote_come_from_the_index(self, tmp_path: Path) -> None:
        """A table of literals deserves a table of assertions: every label and figure."""
        fake = InMemoryFullTextSearch(
            corpus_text_totals=CorpusTextTotals(
                num_text_entities=1234,
                num_words=56789,
                num_titles=600,
                num_pages=4321,
                num_panels=9876,
            ),
            cleaned_terms=["a", "b", "c"],
            entity_terms={EntityType.PERSON: ["Donald", "Scrooge"]},
        )
        with patch.object(corpus_stats_module, "ComicSearch", return_value=fake):
            section = compute_text_stats(tmp_path)
        assert section is not None
        assert section.heading == "The words"
        assert [(r.label, r.value) for r in section.rows] == [
            ("Balloons and captions", "1,234"),
            ("Words spoken", "56,789"),
            ("Distinct words", "3"),
            ("Panels with text", "9,876"),
            ("Pages with text", "4,321"),
            ("Person names", "2"),
        ]
        assert section.footnote == (
            "Balloons include captions and sound effects."
            f" Text figures cover 600 of {len(get_stories()):,} stories currently indexed."
        )

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
        assert prose == {
            ("Length", "Longest (script and art)"),
            ("The cast", "Most-tagged character"),
        }

    def test_every_row_has_a_label_and_a_value(self, stats: CorpusStats) -> None:
        for section in stats.sections:
            assert section.rows
            for row in section.rows:
                assert row.label
                assert row.value
