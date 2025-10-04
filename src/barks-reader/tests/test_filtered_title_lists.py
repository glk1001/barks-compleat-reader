import unittest
from unittest.mock import MagicMock, patch

from barks_fantagraphics.barks_tags import TagCategories
from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo
from barks_reader.filtered_title_lists import FilteredTitleLists


class TestFilteredTitleLists(unittest.TestCase):
    def setUp(self) -> None:
        """Set up a new FilteredTitleLists instance for each test."""
        self.filtered_lists = FilteredTitleLists()

    def test_get_cs_year_str(self) -> None:
        """Test creating a CS-prefixed year string from an int."""
        assert self.filtered_lists.get_cs_year_str(1947) == "CS-1947"

    def test_get_us_range_str(self) -> None:
        """Test creating a US-prefixed year string from an int."""
        assert self.filtered_lists.get_us_year_str(1955) == "US-1955"

    @patch("barks_reader.filtered_title_lists.get_filtered_title_lists")
    def test_get_title_lists_creates_correct_filters(
        self, mock_get_filtered_title_lists: dict[str, list[FantaComicBookInfo]]
    ) -> None:
        """Verify that 'get_filtered_title_lists' constructs the correct filter dictionary.

        and passes it to the external function.
        """
        # Call the method
        self.filtered_lists.get_title_lists()

        # Check that the external function was called exactly once
        # noinspection PyUnresolvedReferences
        assert mock_get_filtered_title_lists.call_count == 1

        # Get the arguments passed to the mocked function
        # noinspection PyUnresolvedReferences
        args, _kwargs = mock_get_filtered_title_lists.call_args
        filters = args[0]

        # --- Verify the keys in the filters dictionary ---
        # Check for chronological ranges
        assert "1942" in filters
        assert "1958" in filters

        # Check for series names
        assert "CS-1942" in filters
        assert "US-1951" in filters

        # Check for CS and US specific ranges
        assert "CS-1947" in filters
        assert "US-1955" in filters

        # Check for categories
        assert TagCategories.CHARACTERS.value in filters
        assert TagCategories.FAVOURITES.value in filters

        # --- Verify the behavior of a sample filter lambda ---
        # Create a mock comic info object to test the filter functions
        mock_info = MagicMock()
        mock_info.comic_book_info = MagicMock()

        # Test a chronological filter
        chrono_filter = filters["1951"]
        mock_info.comic_book_info = MagicMock()
        mock_info.comic_book_info.submitted_year = 1951
        assert chrono_filter(mock_info)
        mock_info.comic_book_info = MagicMock()
        mock_info.comic_book_info.submitted_year = 1960
        assert not chrono_filter(mock_info)

        # Test a series filter
        series_filter = filters["Donald Duck Adventures"]
        mock_info.comic_book_info = MagicMock()
        mock_info.series_name = "Donald Duck Adventures"
        assert series_filter(mock_info)
        mock_info.series_name = "CS"
        assert not series_filter(mock_info)


if __name__ == "__main__":
    unittest.main()
