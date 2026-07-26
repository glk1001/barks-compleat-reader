from collections import defaultdict
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_tags import BARKS_TAG_CATEGORIES_TITLES, TagCategories
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import (
    SERIES_COVERS,
    SERIES_CS,
    SERIES_ONE_PAGERS,
    SERIES_USA,
)
from barks_reader.core import filtered_title_lists as ftl_module
from barks_reader.core.filtered_title_lists import FilteredTitleLists, get_filtered_title_lists


class TestFilteredTitleLists:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Set up a new FilteredTitleLists instance for each test."""
        self.filtered_lists = FilteredTitleLists()

    @pytest.mark.parametrize("include_one_pagers", [True, False])
    @patch.object(ftl_module, get_filtered_title_lists.__name__)
    def test_include_one_pagers_in_chrono_flag_is_honoured(
        self, mock_get_filtered_title_lists: MagicMock, *, include_one_pagers: bool
    ) -> None:
        """The constructor flag decides whether one-pagers interleave into the year lists.

        They stay reachable under the One Pagers series node either way; this only
        controls the chronological nodes.
        """
        mock_get_filtered_title_lists.return_value = defaultdict(list)
        FilteredTitleLists(include_one_pagers_in_chrono=include_one_pagers).get_title_lists()
        filters = mock_get_filtered_title_lists.call_args.args[0]

        mock_info = MagicMock()
        mock_info.comic_book_info = MagicMock()
        mock_info.comic_book_info.submitted_year = 1951
        mock_info.series_name = SERIES_ONE_PAGERS
        assert bool(filters["1951"](mock_info)) is include_one_pagers

    def test_year_spans_are_the_inclusive_union_of_their_ranges(self) -> None:
        """Each per-year span runs from the first range's start to the last range's end.

        The end is inclusive: a tree node exists for every year covered by the ranges,
        so an off-by-one here silently drops (or invents) a whole year node.
        """
        spans = {
            "chrono": (self.filtered_lists.chrono_years, ftl_module.CHRONO_YEAR_RANGES),
            "cs": (self.filtered_lists.cs_years, ftl_module.CS_YEAR_RANGES),
            "us": (self.filtered_lists.us_years, ftl_module.US_YEAR_RANGES),
            "one_pager": (self.filtered_lists.one_pager_years, ftl_module.ONE_PAGER_YEAR_RANGES),
            "cover": (self.filtered_lists.cover_years, ftl_module.COVER_YEAR_RANGES),
        }
        for name, (years, ranges) in spans.items():
            assert years[0] == ranges[0][0], f"{name} span starts late"
            assert years[-1] == ranges[-1][1], f"{name} span ends wrong"

    def test_static_key_generators(self) -> None:
        """Test the static helper methods for generating dictionary keys."""
        assert self.filtered_lists.get_range_str((1940, 1945)) == "1940-1945"
        assert self.filtered_lists.get_cs_year_key_from_year(1947) == "CS-1947"
        assert self.filtered_lists.get_cs_year_range_key_from_range("1940-1945") == "CS-1940-1945"
        assert self.filtered_lists.get_us_year_key_from_year(1955) == "US-1955"
        assert self.filtered_lists.get_us_year_range_key_from_range("1950-1955") == "US-1950-1955"
        assert self.filtered_lists.get_one_pager_year_key_from_year(1948) == "OP-1948"
        assert self.filtered_lists.get_cover_year_key_from_year(1953) == "CV-1953"

    @patch.object(ftl_module, get_filtered_title_lists.__name__)
    def test_get_title_lists_creates_correct_filters(
        self, mock_get_filtered_title_lists: MagicMock
    ) -> None:
        """Verify that 'get_filtered_title_lists' constructs the correct filter dictionary.

        and passes it to the external function.
        """
        # Setup mock return to avoid errors in add_year_ranges (which expects a dict)
        mock_get_filtered_title_lists.return_value = defaultdict(list)

        # Call the method
        self.filtered_lists.get_title_lists()

        # Check that the external function was called exactly once
        assert mock_get_filtered_title_lists.call_count == 1

        # Get the arguments passed to the mocked function
        args, _kwargs = mock_get_filtered_title_lists.call_args
        filters = args[0]

        # --- Verify the keys in the filters dictionary ---
        # Check for chronological ranges
        assert "1942" in filters

        # Check for series names
        assert SERIES_CS in filters
        assert SERIES_USA in filters

        # Check for CS and US specific ranges
        assert "CS-1947" in filters
        assert "US-1955" in filters

        # Check for one-pager and cover per-year keys
        assert "OP-1948" in filters
        assert "CV-1953" in filters

        # Check for categories
        assert TagCategories.CHARACTERS.value in filters

        # --- Verify the behavior of a sample filter lambda ---
        # Create a mock comic info object to test the filter functions
        mock_info = MagicMock()
        mock_info.comic_book_info = MagicMock()

        # 1. Test a chronological filter
        chrono_filter = filters["1951"]
        mock_info.comic_book_info = MagicMock()
        mock_info.comic_book_info.submitted_year = 1951
        assert chrono_filter(mock_info)
        mock_info.comic_book_info = MagicMock()
        mock_info.comic_book_info.submitted_year = 1960
        assert not chrono_filter(mock_info)

        # 2. Test a series filter
        series_filter = filters["Donald Duck Adventures"]
        mock_info.comic_book_info = MagicMock()
        mock_info.series_name = "Donald Duck Adventures"
        assert series_filter(mock_info)
        mock_info.series_name = "CS"
        assert not series_filter(mock_info)

        # 3. Test CS Year Filter
        cs_filter = filters["CS-1945"]
        mock_info.series_name = SERIES_CS
        mock_info.comic_book_info.submitted_year = 1945
        assert cs_filter(mock_info)

        mock_info.series_name = "Other"
        assert not cs_filter(mock_info)

        mock_info.series_name = SERIES_CS
        mock_info.comic_book_info.submitted_year = 1946
        assert not cs_filter(mock_info)

        # 4. Test US Year Filter
        us_filter = filters["US-1955"]
        mock_info.series_name = SERIES_USA
        mock_info.comic_book_info.submitted_year = 1955
        assert us_filter(mock_info)

        mock_info.series_name = "Other"
        assert not us_filter(mock_info)

    @patch.object(ftl_module, get_filtered_title_lists.__name__)
    def test_series_filters_exclude_the_synthetic_collections(
        self, mock_get_filtered_title_lists: MagicMock
    ) -> None:
        """The synthetic collections never appear as members of their own series.

        They are reached by selecting a one-pager/cover, so a series filter must reject
        them even when the series name matches.
        """
        mock_get_filtered_title_lists.return_value = defaultdict(list)
        self.filtered_lists.get_title_lists()
        filters = mock_get_filtered_title_lists.call_args.args[0]

        mock_info = MagicMock()
        mock_info.comic_book_info = MagicMock()

        one_pagers_filter = filters[SERIES_ONE_PAGERS]
        mock_info.series_name = SERIES_ONE_PAGERS
        mock_info.comic_book_info.title = Titles.ALL_ONE_PAGERS
        assert not one_pagers_filter(mock_info)
        mock_info.comic_book_info.title = Titles.GOOD_DEEDS
        assert one_pagers_filter(mock_info)

        covers_filter = filters[SERIES_COVERS]
        mock_info.series_name = SERIES_COVERS
        mock_info.comic_book_info.title = Titles.ALL_COVERS
        assert not covers_filter(mock_info)
        mock_info.comic_book_info.title = Titles.GOOD_DEEDS
        assert covers_filter(mock_info)

    @patch.object(ftl_module, get_filtered_title_lists.__name__)
    def test_category_filters_select_that_category_s_titles(
        self, mock_get_filtered_title_lists: MagicMock
    ) -> None:
        """A tag-category filter admits exactly the titles tagged into that category."""
        mock_get_filtered_title_lists.return_value = defaultdict(list)
        self.filtered_lists.get_title_lists()
        filters = mock_get_filtered_title_lists.call_args.args[0]

        characters_filter = filters[TagCategories.CHARACTERS.value]
        tagged = next(iter(BARKS_TAG_CATEGORIES_TITLES[TagCategories.CHARACTERS]))

        mock_info = MagicMock()
        mock_info.comic_book_info = MagicMock()
        mock_info.comic_book_info.title = tagged
        assert characters_filter(mock_info)
        mock_info.comic_book_info.title = Titles.ALL_COVERS
        assert not characters_filter(mock_info)

    @patch.object(ftl_module, get_filtered_title_lists.__name__)
    def test_one_pager_and_cover_year_filters(
        self, mock_get_filtered_title_lists: MagicMock
    ) -> None:
        """One-pager/cover per-year filters, incl. the undated-cover fold into the final year."""
        mock_get_filtered_title_lists.return_value = defaultdict(list)
        self.filtered_lists.get_title_lists()
        filters = mock_get_filtered_title_lists.call_args.args[0]

        mock_info = MagicMock()
        mock_info.comic_book_info = MagicMock()

        # One-pager year filter (non-final year) matches only that year.
        op_filter = filters["OP-1948"]
        mock_info.series_name = SERIES_ONE_PAGERS
        mock_info.comic_book_info.submitted_year = 1948
        assert op_filter(mock_info)
        mock_info.comic_book_info.submitted_year = 1949
        assert not op_filter(mock_info)
        mock_info.comic_book_info.submitted_year = -1
        assert not op_filter(mock_info)

        # The final one-pager year folds in out-of-range/undated one-pagers.
        op_final_filter = filters["OP-1962"]
        mock_info.series_name = SERIES_ONE_PAGERS
        mock_info.comic_book_info.submitted_year = 1962
        assert op_final_filter(mock_info)
        mock_info.comic_book_info.submitted_year = 1900
        assert op_final_filter(mock_info)
        mock_info.series_name = "Other"
        assert not op_final_filter(mock_info)

        # Cover year filter (non-final year) matches only that year, not undated covers.
        cv_filter = filters["CV-1953"]
        mock_info.series_name = SERIES_COVERS
        mock_info.comic_book_info.submitted_year = 1953
        assert cv_filter(mock_info)
        mock_info.comic_book_info.submitted_year = -1
        assert not cv_filter(mock_info)

        # The final cover year folds in undated/out-of-range covers.
        cv_final_filter = filters["CV-1965"]
        mock_info.series_name = SERIES_COVERS
        mock_info.comic_book_info.submitted_year = 1965
        assert cv_final_filter(mock_info)
        mock_info.comic_book_info.submitted_year = -1
        assert cv_final_filter(mock_info)
        mock_info.series_name = "Other"
        assert not cv_final_filter(mock_info)

    @patch.object(ftl_module, get_filtered_title_lists.__name__)
    def test_add_year_ranges_aggregation(self, mock_get_filtered_title_lists: MagicMock) -> None:
        """Verify that year ranges are correctly aggregated into the result dictionary."""
        # Set up a mock dictionary returned by the filter function
        # We use defaultdict(list) because the code iterates over ALL years in a range,
        # so accessing a year key that doesn't exist would normally raise KeyError.
        mock_data = {
            "1942": ["Book A"],
            "1943": ["Book B"],
            # CS data
            "CS-1942": ["CS Book A"],
            "CS-1943": ["CS Book B"],
            # US data (US starts 1951 in constants)
            "US-1951": ["US Book A"],
        }
        ret_dict = defaultdict(list)
        ret_dict.update(mock_data)
        mock_get_filtered_title_lists.return_value = ret_dict

        # Execute
        results = self.filtered_lists.get_title_lists()

        # Check Chrono Range (1942-1946 is the first range in CHRONO_YEAR_RANGES)
        # 1942 and 1943 should be aggregated.
        range_key = "1942-1946"
        assert range_key in results
        assert "Book A" in results[range_key]
        assert "Book B" in results[range_key]

        # Check CS Range
        cs_range_key = "CS-1942-1946"
        assert cs_range_key in results
        assert "CS Book A" in results[cs_range_key]
        assert "CS Book B" in results[cs_range_key]

        # Check US Range (1951-1954)
        us_range_key = "US-1951-1954"
        assert us_range_key in results
        assert "US Book A" in results[us_range_key]

        # Check the 'Choose for me' decade ranges aggregate the same chrono year lists.
        decade_key = "1942-1949"
        assert decade_key in results
        assert "Book A" in results[decade_key]
        assert "Book B" in results[decade_key]
        assert "1950-1959" in results
        assert "1960-1971" in results

    @patch.object(ftl_module, get_filtered_title_lists.__name__)
    def test_add_year_ranges_takes_exactly_its_own_years(
        self, mock_get_filtered_title_lists: MagicMock
    ) -> None:
        """A range aggregates its first..last year inclusive, and nothing outside it.

        The first chrono range is 1942-1946 and the second 1947-1950, so a title in
        1946 belongs only to the first and one in 1947 only to the second. Both ends
        are one year away from a neighbouring range, which is what makes the inclusive
        bound worth pinning.
        """
        ret_dict = defaultdict(list)
        ret_dict.update(
            {
                "1942": ["First Year"],
                "1946": ["Last Year Of Range One"],
                "1947": ["First Year Of Range Two"],
                "1950": ["Last Year Of Range Two"],
            }
        )
        mock_get_filtered_title_lists.return_value = ret_dict

        results = self.filtered_lists.get_title_lists()

        assert results["1942-1946"] == ["First Year", "Last Year Of Range One"]
        assert results["1947-1950"] == ["First Year Of Range Two", "Last Year Of Range Two"]
