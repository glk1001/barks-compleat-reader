from collections import defaultdict
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_tags import TagCategories
from barks_fantagraphics.fanta_comics_info import (
    SERIES_CS,
    SERIES_USA,
)
from barks_reader.core import filtered_title_lists as ftl_module
from barks_reader.core.filtered_title_lists import FilteredTitleLists, get_filtered_title_lists


class TestFilteredTitleLists:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Set up a new FilteredTitleLists instance for each test."""
        self.filtered_lists = FilteredTitleLists()

    def test_static_key_generators(self) -> None:
        """Test the static helper methods for generating dictionary keys."""
        assert self.filtered_lists.get_range_str((1940, 1945)) == "1940-1945"
        assert self.filtered_lists.get_cs_year_key_from_year(1947) == "CS-1947"
        assert self.filtered_lists.get_cs_year_range_key_from_range("1940-1945") == "CS-1940-1945"
        assert self.filtered_lists.get_us_year_key_from_year(1955) == "US-1955"
        assert self.filtered_lists.get_us_year_range_key_from_range("1950-1955") == "US-1950-1955"

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
