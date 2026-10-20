"""The numbers behind the Appendix Statistics charts.

Three charts went wrong in one afternoon (2026-10-20) and each test here is one of
the ways they did: a year with no bar because the filter was ``is_barks_title``, a
"year -1" bar from the ledger's sentinel, and an axis squashed by it. The counts
pinned here are the corpus's as of that date, the way ``test_corpus_stats`` pins its
683 stories; a data change that moves them is meant to be seen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import barks_reader.core.statistics_series
import pytest
from barks_fantagraphics.barks_payments import BARKS_PAYMENTS
from barks_fantagraphics.barks_tags_enums import Tags
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO, COVERS_SET
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_reader.core.corpus_stats import (
    _adjusted_payment_total,
    _story_page_counts,
    get_paid_records,
    get_stories,
)
from barks_reader.core.statistics_series import (
    CHART_FILES,
    CHART_ITEMS,
    MOST_FREQUENT_FILE,
    MOST_FREQUENT_ITEM,
    TOP_N,
    WORDCLOUD_GLOB,
    Series,
    all_series,
    dump_series,
    load_series,
    pages_per_year,
    payment_rate,
    payments_per_year,
    stories_per_series,
    stories_per_year,
    stories_submitted_in,
    top_characters,
    top_locations,
    wordcloud_items,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

FIRST_YEAR = 1942
LAST_YEAR = 1973  # The last script Barks submitted (1973); 1982's entries are collections.
_NUM_STORIES = 683
_NUM_PAGES = 6591
_WORDCLOUD_ERAS = ((1943, 1946), (1947, 1950), (1951, 1955), (1956, 1959))


def _is_descending(series: Series) -> bool:
    return list(series.values) == sorted(series.values, reverse=True)


class TestPerYearCharts:
    """Every year on the axis is a real year of Barks's working life."""

    @pytest.mark.parametrize(
        "series", [stories_per_year(), pages_per_year(), payments_per_year(), payment_rate()]
    )
    def test_years_are_real(self, series: Series) -> None:
        # The ledger's -1 sentinel once put a "year -1" bar on the pages chart.
        assert all(FIRST_YEAR <= int(year) <= LAST_YEAR for year in series.labels)
        assert list(series.labels) == sorted(series.labels)

    @pytest.mark.parametrize("series", [stories_per_year(), pages_per_year()])
    def test_barks_submitted_something_every_year(self, series: Series) -> None:
        # The stories chart once had no 1953: the filter was is_barks_title.
        assert series.labels == tuple(range(FIRST_YEAR, LAST_YEAR + 1))
        assert all(value > 0 for value in series.values)


class TestStoriesPerYear:
    def test_counts_every_story(self) -> None:
        assert stories_per_year().total == len(get_stories()) == _NUM_STORIES

    def test_1953_is_a_full_year(self) -> None:
        series = stories_per_year()
        assert series.values[series.labels.index(1953)] == 30  # noqa: PLR2004

    def test_not_only_the_stories_barks_titled(self) -> None:
        self_titled = sum(1 for info in get_stories() if info.is_barks_title)
        assert stories_per_year().total > self_titled

    def test_covers_are_not_stories(self) -> None:
        assert not {info.title for info in get_stories()} & COVERS_SET
        assert stories_per_year().total < len(BARKS_TITLE_INFO) - len(COVERS_SET)


class TestPagesPerYear:
    def test_sums_to_the_by_the_numbers_page_total(self) -> None:
        assert pages_per_year().total == sum(_story_page_counts(get_stories()).values())
        assert pages_per_year().total == _NUM_PAGES

    def test_covers_pages_are_not_counted(self) -> None:
        every_record = sum(p.num_pages for p in BARKS_PAYMENTS.values())
        assert pages_per_year().total < every_record


class TestPaymentCharts:
    def test_payments_sum_to_the_by_the_numbers_total(self) -> None:
        adjusted = _adjusted_payment_total(get_paid_records())
        assert payments_per_year().total == pytest.approx(adjusted, abs=0.5)

    def test_payments_only_from_records_with_an_amount(self) -> None:
        years = {record.accepted_year for record in get_paid_records()}
        assert set(payments_per_year().labels) == years

    def test_rate_is_payment_over_pages_each_year(self) -> None:
        paid, rate = payments_per_year(), payment_rate()
        assert rate.labels == paid.labels
        pages_by_year: dict[int, int] = {}
        for record in get_paid_records():
            pages_by_year[record.accepted_year] = (
                pages_by_year.get(record.accepted_year, 0) + record.num_pages
            )
        for year, amount, per_page in zip(paid.labels, paid.values, rate.values, strict=True):
            assert per_page == pytest.approx(amount / pages_by_year[int(year)], abs=0.01)

    def test_money_is_rounded_to_cents(self) -> None:
        for series in (payments_per_year(), payment_rate()):
            assert all(round(value, 2) == value for value in series.values)


class TestRankedCharts:
    def test_series_counts_every_fantagraphics_entry(self) -> None:
        series = stories_per_series()
        assert series.total == len(ALL_FANTA_COMIC_BOOK_INFO)
        assert "Unknown" not in series.labels
        assert set(series.labels) == {i.series_name for i in ALL_FANTA_COMIC_BOOK_INFO.values()}
        assert _is_descending(series)

    # Called in the test, not at collection, so mutmut sees the test run them.
    @pytest.mark.parametrize("make_series", [top_characters, top_locations])
    def test_top_n_descending(self, make_series: Callable[[], Series]) -> None:
        series = make_series()
        assert len(series.labels) == TOP_N
        assert _is_descending(series)
        assert len(set(series.labels)) == TOP_N
        assert max(series.values) <= _NUM_STORIES

    def test_a_part_tag_is_not_a_character(self) -> None:
        # "Gyro not in GG series" holds part of Gyro's stories; it is not a third
        # character between him and Daisy.
        for tag in (Tags.GYRO_IN_GG, Tags.GYRO_NOT_IN_GG, Tags.SCROOGE_NOT_IN_US):
            assert tag.value not in top_characters().labels

    def test_equal_counts_rank_by_name(self) -> None:
        ranked = barks_reader.core.statistics_series._ranked(  # noqa: SLF001
            "ranked", {"b": 1, "c": 2, "a": 1}, 3
        )
        assert ranked == Series("ranked", ("c", "a", "b"), (2, 1, 1))


class TestWordcloudEras:
    def test_the_eras_cover_the_golden_years_once_each(self) -> None:
        first, last = _WORDCLOUD_ERAS[0][0], _WORDCLOUD_ERAS[-1][1]
        in_eras = [stories_submitted_in(a, b) for a, b in _WORDCLOUD_ERAS]
        assert sum(map(len, in_eras)) == len(stories_submitted_in(first, last))
        titles = [info.title for era in in_eras for info in era]
        assert len(titles) == len(set(titles))

    def test_1951_55_holds_every_story_not_twenty(self) -> None:
        # The eras once came from is_barks_title and this one had 20 stories.
        assert len(stories_submitted_in(1951, 1955)) == 155  # noqa: PLR2004


class TestSidecar:
    def test_every_chart_has_a_series_and_a_file(self) -> None:
        assert [series.name for series in all_series()] == list(CHART_FILES)

    def test_is_indented_json(self) -> None:
        # The sidecar's bytes are fingerprinted in scripts/data-manifest.json: a change of
        # layout is a change of the data pack every machine holds.
        assert dump_series([Series("s", (1942,), (2,))]) == (
            '[\n  {\n    "name": "s",\n    "labels": [\n      1942\n    ],\n'
            '    "values": [\n      2\n    ]\n  }\n]'
        )

    def test_round_trips_through_json(self) -> None:
        series = all_series()
        assert load_series(dump_series(series)) == series

    def test_is_deterministic(self) -> None:
        assert dump_series(all_series()) == dump_series(all_series())

    def test_a_changed_value_is_a_different_series(self) -> None:
        series = stories_per_year()
        changed = Series(series.name, series.labels, (*series.values[:-1], 0))
        assert changed != series


class TestWordcloudItems:
    def test_discovers_and_sorts_wordclouds(self, tmp_path: Path) -> None:
        """Test that wordcloud files are discovered with correct labels."""
        (tmp_path / "tfidf_wordcloud_1943-46.png").touch()
        (tmp_path / "tfidf_wordcloud_1947-50.png").touch()
        (tmp_path / "tfidf_wordcloud_1951-54.png").touch()
        # Non-matching file should be ignored
        (tmp_path / "other_image.png").touch()

        result = wordcloud_items(tmp_path)

        assert result == [
            ("Word Cloud 1943-46", "tfidf_wordcloud_1943-46.png"),
            ("Word Cloud 1947-50", "tfidf_wordcloud_1947-50.png"),
            ("Word Cloud 1951-54", "tfidf_wordcloud_1951-54.png"),
        ]

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Test that an empty directory returns no wordclouds."""
        assert wordcloud_items(tmp_path) == []

    def test_a_wordcloud_with_no_period_in_its_name_is_left_out(self, tmp_path: Path) -> None:
        """The glob matches an empty period, but there is nothing to label it with."""
        (tmp_path / "tfidf_wordcloud_.png").touch()
        (tmp_path / "tfidf_wordcloud_1943-46.png").touch()

        assert wordcloud_items(tmp_path) == [("Word Cloud 1943-46", "tfidf_wordcloud_1943-46.png")]

    def test_no_matching_files(self, tmp_path: Path) -> None:
        """Test that non-matching files are excluded."""
        (tmp_path / "stories_per_year.png").touch()
        (tmp_path / "most_frequent.png").touch()

        assert wordcloud_items(tmp_path) == []


class TestTheScreenAndTheGeneratorAgree:
    """The screen's menu and the generator's chart list are the same set of files."""

    def test_chart_files(self) -> None:
        assert [filename for _label, filename in CHART_ITEMS] == list(CHART_FILES.values())

    def test_most_frequent_and_wordcloud_files(self, tmp_path: Path) -> None:
        # The generator once wrote word_statistics.png while the menu showed
        # most_frequent.png, and the table on screen fell a year behind the index.
        assert MOST_FREQUENT_ITEM[1] == MOST_FREQUENT_FILE
        (tmp_path / "tfidf_wordcloud_1943-46.png").touch()
        assert [p.name for p in tmp_path.glob(WORDCLOUD_GLOB)] == ["tfidf_wordcloud_1943-46.png"]
        assert wordcloud_items(tmp_path)
