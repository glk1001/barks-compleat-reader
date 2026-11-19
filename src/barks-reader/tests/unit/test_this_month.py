"""`this_month`: the stories a calendar month holds, by either of a story's two dates."""

from __future__ import annotations

from datetime import date

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.corpus_stats import get_stories
from barks_reader.core.this_month import (
    MonthDate,
    get_month_group_heading,
    get_month_node_text,
    get_stories_in_month,
    get_submitted_on_this_day_text,
    get_titles_in_month,
)

_MONTHS = range(1, 13)
# Submitted 21st October 1948.
_ANDES = next(info for info in get_stories() if info.title is Titles.LOST_IN_THE_ANDES)


class TestTexts:
    def test_the_node_is_named_for_its_month(self) -> None:
        assert get_month_node_text(11) == "November in Barks"
        assert get_month_node_text(1) == "January in Barks"

    def test_each_group_is_headed_by_its_date_and_month(self) -> None:
        assert get_month_group_heading(MonthDate.SUBMITTED, 11) == "Submitted in November"
        assert get_month_group_heading(MonthDate.ON_SALE, 12) == "On sale in December"


class TestStoriesInMonth:
    def test_every_story_is_submitted_in_exactly_one_month(self) -> None:
        by_month = [get_stories_in_month(MonthDate.SUBMITTED, month) for month in _MONTHS]

        assert sum(len(stories) for stories in by_month) == len(get_stories())
        for month, stories in zip(_MONTHS, by_month, strict=True):
            assert stories, f"no story submitted in month {month}"
            assert all(info.submitted_month == month for info in stories)

    def test_a_story_with_no_issue_month_is_on_sale_in_none(self) -> None:
        dated = [info for info in get_stories() if info.issue_month in _MONTHS]
        by_month = [get_stories_in_month(MonthDate.ON_SALE, month) for month in _MONTHS]

        assert 0 < len(get_stories()) - len(dated) < 10  # noqa: PLR2004
        assert sum(len(stories) for stories in by_month) == len(dated)
        for month, stories in zip(_MONTHS, by_month, strict=True):
            assert all(info.issue_month == month for info in stories)

    def test_the_submitted_run_in_the_order_barks_submitted_them(self) -> None:
        stories = get_stories_in_month(MonthDate.SUBMITTED, 11)

        dates = [(info.submitted_year, info.submitted_day) for info in stories]
        assert dates == sorted(dates)
        assert len({year for year, _day in dates}) > 1

    def test_the_on_sale_run_by_issue_year_then_as_submitted(self) -> None:
        stories = get_stories_in_month(MonthDate.ON_SALE, 12)

        keys = [(info.issue_year, info.chronological_number) for info in stories]
        assert keys == sorted(keys)

    def test_lost_in_the_andes_is_under_both_its_months(self) -> None:
        assert _ANDES in get_stories_in_month(MonthDate.SUBMITTED, _ANDES.submitted_month)
        assert _ANDES in get_stories_in_month(MonthDate.ON_SALE, _ANDES.issue_month)
        assert _ANDES not in get_stories_in_month(MonthDate.SUBMITTED, _ANDES.issue_month)


class TestTitlesInMonth:
    @pytest.mark.parametrize("month", _MONTHS)
    def test_it_is_both_groups_with_each_story_once(self, month: int) -> None:
        either = {
            info.title for dated_by in MonthDate for info in get_stories_in_month(dated_by, month)
        }

        titles = get_titles_in_month(month)

        assert set(titles) == either
        assert len(titles) == len(either)


class TestSubmittedOnThisDay:
    def test_a_story_submitted_on_today_s_date_says_how_long_ago(self) -> None:
        today = date(2027, _ANDES.submitted_month, _ANDES.submitted_day)

        assert get_submitted_on_this_day_text(_ANDES, today) == (
            f"Submitted {2027 - _ANDES.submitted_year} years ago today: Lost in the Andes!"
        )

    @pytest.mark.parametrize(
        "today",
        [
            date(2027, _ANDES.submitted_month, _ANDES.submitted_day + 1),
            date(2027, _ANDES.submitted_month + 1, _ANDES.submitted_day),
        ],
    )
    def test_any_other_day_says_nothing(self, today: date) -> None:
        assert get_submitted_on_this_day_text(_ANDES, today) == ""
