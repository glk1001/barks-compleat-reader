from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from unittest.mock import patch

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core import collection_page_groups as cpg_module
from barks_reader.core.collection_page_groups import (
    _assert_tiling,
    _group_ranges,
    get_collection_group_page_range,
    get_cover_collection_group_ranges,
    get_one_pager_collection_group_ranges,
    year_range_group,
    year_range_group_index,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

_RANGES = [(1948, 1952), (1953, 1955), (1956, 1959), (1960, 1965)]


@pytest.fixture(autouse=True)
def _clear_group_range_caches() -> Iterator[None]:
    """Drop the ``@cache`` on the collection group-range getters around every test.

    Without this the memoised result leaks between tests, so the bodies of
    ``_group_ranges``/``_assert_tiling`` run only once per process. Mutation testing
    then reports every mutant of those two functions as a false survivor (mutmut
    reuses one worker process across mutants — the second mutant onwards never
    executes the mutated code at all). Clearing keeps the data-driven tests below
    genuinely sensitive to changes in the code they claim to cover.
    """
    get_cover_collection_group_ranges.cache_clear()
    get_one_pager_collection_group_ranges.cache_clear()
    yield
    get_cover_collection_group_ranges.cache_clear()
    get_one_pager_collection_group_ranges.cache_clear()


class TestYearRangeGroup:
    def test_index_within_a_range(self) -> None:
        assert year_range_group_index(1954, _RANGES) == 1

    def test_index_at_range_start_is_inclusive(self) -> None:
        """The first year of a range belongs to that range, not the previous one."""
        assert year_range_group_index(1953, _RANGES) == 1
        assert year_range_group_index(1948, _RANGES) == 0

    def test_index_at_range_end_is_inclusive(self) -> None:
        """The last year of a range belongs to that range, not the next one."""
        assert year_range_group_index(1952, _RANGES) == 0
        assert year_range_group_index(1955, _RANGES) == 1

    def test_index_undated_folds_into_final_group(self) -> None:
        assert year_range_group_index(-1, _RANGES) == len(_RANGES) - 1

    def test_index_out_of_range_high_folds_into_final_group(self) -> None:
        assert year_range_group_index(2020, _RANGES) == len(_RANGES) - 1

    def test_group_returns_the_range_tuple(self) -> None:
        assert year_range_group(1954, _RANGES) == (1953, 1955)
        assert year_range_group(-1, _RANGES) == (1960, 1965)


class TestGroupRanges:
    def test_cover_group_ranges_tile_the_collection(self) -> None:
        ranges = get_cover_collection_group_ranges()
        assert ranges == [(1, 52), (53, 90), (91, 145), (146, 186)]

    def test_one_pager_group_ranges_tile_the_collection(self) -> None:
        ranges = get_one_pager_collection_group_ranges()
        assert ranges == [(1, 43), (44, 92), (93, 128)]


class TestGroupRangesOnSyntheticData:
    """``_group_ranges`` driven by a fake year lookup, so no real collection is needed.

    The real-data tests above only ever see one shape of input; these pin the mapping
    from a chronological located list to contiguous 1-based page runs.
    """

    _YEAR_RANGES: ClassVar = [(1948, 1949), (1950, 1951), (1952, 1953)]

    # Chronological, three per group: positions 1-3, 4-6, 7-9.
    _TITLES: ClassVar = [
        Titles.DONALD_DUCK_FINDS_PIRATE_GOLD,
        Titles.VICTORY_GARDEN_THE,
        Titles.RABBITS_FOOT_THE,
        Titles.LIFEGUARD_DAZE,
        Titles.GOOD_DEEDS,
        Titles.LIMBER_W_GUEST_RANCH_THE,
        Titles.MIGHTY_TRAPPER_THE,
        Titles.DONALD_DUCK_AND_THE_MUMMYS_RING,
        Titles.HARD_LOSER_THE,
    ]
    _YEARS: ClassVar = [1948, 1948, 1949, 1950, 1950, 1951, 1952, 1953, 1953]

    def _grouped(self, years: list[int]) -> list[tuple[int, int]]:
        located = self._TITLES[: len(years)]
        by_title = dict(zip(located, years, strict=True))
        with patch.object(cpg_module, "_submitted_year", by_title.__getitem__):
            return _group_ranges(located, self._YEAR_RANGES)

    def test_groups_become_contiguous_one_based_page_runs(self) -> None:
        assert self._grouped(self._YEARS) == [(1, 3), (4, 6), (7, 9)]

    def test_positions_are_one_based_not_zero_based(self) -> None:
        """The first page is 1: a 0-based enumerate would trip the tiling assert."""
        assert self._grouped(self._YEARS)[0][0] == 1

    def test_single_member_group_is_a_degenerate_range(self) -> None:
        assert self._grouped([1948, 1950, 1950, 1952]) == [(1, 1), (2, 3), (4, 4)]

    def test_undated_members_fold_into_the_final_group(self) -> None:
        """Undated (-1) entries sort last and extend the final group's run."""
        assert self._grouped([1948, 1950, 1952, -1, -1]) == [(1, 1), (2, 2), (3, 5)]

    def test_empty_group_is_skipped_not_emitted(self) -> None:
        """A year range with no members produces no range, keeping the runs contiguous."""
        assert self._grouped([1948, 1948, 1952, 1953]) == [(1, 2), (3, 4)]

    def test_non_chronological_order_trips_the_tiling_assert(self) -> None:
        """Interleaved groups can't be sliced contiguously, so the assert must fire."""
        with pytest.raises(AssertionError, match="not contiguous"):
            self._grouped([1948, 1950, 1948, 1950])


class TestAssertTiling:
    """``_assert_tiling`` is the guard that stops a bad grouping opening wrong pages."""

    def test_valid_tiling_passes(self) -> None:
        _assert_tiling([(1, 5), (6, 8), (9, 20)], 20)

    def test_single_group_covering_everything_passes(self) -> None:
        _assert_tiling([(1, 7)], 7)

    def test_empty_ranges_rejected(self) -> None:
        # Anchored: an unanchored `match` would also pass on a padded/reworded message.
        with pytest.raises(AssertionError, match=r"^no collection page groups$"):
            _assert_tiling([], 0)

    def test_not_starting_at_page_one_rejected(self) -> None:
        with pytest.raises(AssertionError, match="groups must start at page 1, got 2"):
            _assert_tiling([(2, 5), (6, 20)], 20)

    def test_not_ending_at_total_rejected(self) -> None:
        # Three groups, so the reported "got" value can only come from the *last* one.
        with pytest.raises(AssertionError, match="groups must end at page 20, got 12"):
            _assert_tiling([(1, 5), (6, 8), (9, 12)], 20)

    def test_gap_between_groups_rejected(self) -> None:
        with pytest.raises(AssertionError, match=r"not contiguous: 5 -> 7"):
            _assert_tiling([(1, 5), (7, 20)], 20)

    def test_overlapping_groups_rejected(self) -> None:
        with pytest.raises(AssertionError, match=r"not contiguous: 5 -> 5"):
            _assert_tiling([(1, 5), (5, 20)], 20)


class TestGetCollectionGroupPageRange:
    def test_cover_in_middle_group(self) -> None:
        # A cover in the 1953-1955 bucket (pages 53-90).
        assert get_collection_group_page_range(Titles.ALL_COVERS, 70) == (53, 90)

    def test_cover_first_group(self) -> None:
        assert get_collection_group_page_range(Titles.ALL_COVERS, 1) == (1, 52)

    def test_undated_cover_folds_into_final_group(self) -> None:
        # The 6 undated covers sort last (pages 181-186) and fold into the final group.
        assert get_collection_group_page_range(Titles.ALL_COVERS, 186) == (146, 186)

    def test_one_pager_group(self) -> None:
        assert get_collection_group_page_range(Titles.ALL_ONE_PAGERS, 100) == (93, 128)

    def test_unsupported_collection_raises(self) -> None:
        with pytest.raises(ValueError, match="Not a grouped collection"):
            get_collection_group_page_range(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD, 1)

    def test_page_outside_every_group_raises(self) -> None:
        with pytest.raises(ValueError, match="outside every group"):
            get_collection_group_page_range(Titles.ALL_COVERS, 999)
