from __future__ import annotations

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.collection_page_groups import (
    get_collection_group_page_range,
    get_cover_collection_group_ranges,
    get_one_pager_collection_group_ranges,
    year_range_group,
    year_range_group_index,
)

_RANGES = [(1948, 1952), (1953, 1955), (1956, 1959), (1960, 1965)]


class TestYearRangeGroup:
    def test_index_within_a_range(self) -> None:
        assert year_range_group_index(1954, _RANGES) == 1

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
