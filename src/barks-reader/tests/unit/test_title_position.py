"""Where a title sits in the reader tree (barks_reader.core.navigation.title_position)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import COVERS_SET, ONE_PAGERS
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_reader.core.navigation import YearRangeKind, title_year_range
from barks_reader.core.reader_consts_and_types import (
    CHRONO_YEAR_RANGES,
    COVER_YEAR_RANGES,
    ONE_PAGER_YEAR_RANGES,
)


def _info(submitted_year: int) -> MagicMock:
    info = MagicMock()
    info.comic_book_info.submitted_year = submitted_year
    info.comic_book_info.get_title_str.return_value = "A Title"
    return info


@pytest.mark.parametrize("year_range", CHRONO_YEAR_RANGES)
def test_a_story_sits_in_the_chronological_group_of_its_year(year_range: tuple[int, int]) -> None:
    for year in year_range:  # both ends are inside
        assert title_year_range(Titles.LOST_IN_THE_ANDES, _info(year)) == (
            YearRangeKind.CHRONO,
            year_range,
        )


def test_a_real_story_is_placed_by_its_own_submitted_year() -> None:
    info = ALL_FANTA_COMIC_BOOK_INFO[Titles.LOST_IN_THE_ANDES]
    assert title_year_range(Titles.LOST_IN_THE_ANDES, info) == (YearRangeKind.CHRONO, (1947, 1950))


@pytest.mark.parametrize("year", [1900, -1])
def test_a_story_in_no_chronological_group_is_an_error(year: int) -> None:
    with pytest.raises(RuntimeError, match="No year range found for A Title"):
        title_year_range(Titles.LOST_IN_THE_ANDES, _info(year))


@pytest.mark.parametrize("year_range", ONE_PAGER_YEAR_RANGES)
def test_a_one_pager_sits_in_the_one_pager_group_of_its_year(year_range: tuple[int, int]) -> None:
    one_pager = next(iter(ONE_PAGERS))
    assert title_year_range(one_pager, _info(year_range[0])) == (
        YearRangeKind.ONE_PAGER,
        year_range,
    )


@pytest.mark.parametrize("year_range", COVER_YEAR_RANGES)
def test_a_cover_sits_in_the_cover_group_of_its_year(year_range: tuple[int, int]) -> None:
    cover = next(iter(COVERS_SET))
    assert title_year_range(cover, _info(year_range[1])) == (YearRangeKind.COVER, year_range)


def test_an_undated_one_pager_or_cover_folds_into_the_last_group() -> None:
    assert title_year_range(next(iter(ONE_PAGERS)), _info(-1)) == (
        YearRangeKind.ONE_PAGER,
        ONE_PAGER_YEAR_RANGES[-1],
    )
    assert title_year_range(next(iter(COVERS_SET)), _info(-1)) == (
        YearRangeKind.COVER,
        COVER_YEAR_RANGES[-1],
    )
