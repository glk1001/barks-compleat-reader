import unittest

from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.title_search import BarksTitleSearch


class TestBarksTitleSearch(unittest.TestCase):
    def setUp(self) -> None:
        """Set up a new BarksTitleSearch instance for each test."""
        self.search = BarksTitleSearch()

    def test_get_titles_matching_prefix_empty(self) -> None:
        """Test that an empty prefix returns an empty list."""
        assert self.search.get_titles_matching_prefix("") == []

    def test_get_titles_matching_prefix_one_char(self) -> None:
        """Test searching with a single character prefix."""
        # Assuming there are titles starting with 'C'
        results = self.search.get_titles_matching_prefix("C")
        assert len(results) > 0
        # Check if a known title is in the results
        assert Titles.CHRISTMAS_IN_DUCKBURG in results

    def test_get_titles_matching_prefix_two_chars(self) -> None:
        """Test searching with a two-character prefix."""
        results = self.search.get_titles_matching_prefix("in")
        assert Titles.IN_OLD_CALIFORNIA in results
        assert Titles.IN_ANCIENT_PERSIA in results

    def test_get_titles_matching_prefix_long_prefix(self) -> None:
        """Test searching with a prefix longer than two characters."""
        results = self.search.get_titles_matching_prefix("the golden")
        assert Titles.GOLDEN_HELMET_THE in results
        assert Titles.GHOST_OF_THE_GROTTO_THE not in results

    def test_get_titles_matching_prefix_case_insensitivity(self) -> None:
        """Test that prefix matching is case-insensitive."""
        results_lower = self.search.get_titles_matching_prefix("va")
        results_upper = self.search.get_titles_matching_prefix("VA")
        assert results_lower == results_upper
        assert Titles.VACATION_TIME in results_lower

    def test_get_titles_matching_prefix_no_match(self) -> None:
        """Test a prefix that should not match any titles."""
        assert self.search.get_titles_matching_prefix("xyz") == []

    def test_get_titles_containing_word(self) -> None:
        """Test searching for titles containing a specific word."""
        results = self.search.get_titles_containing("christmas")
        assert Titles.CHRISTMAS_IN_DUCKBURG in results
        assert Titles.BLACK_PEARLS_OF_TABU_YAMA_THE not in results
        assert Titles.GOLDEN_HELMET_THE not in results

    def test_get_titles_containing_word_no_match(self) -> None:
        """Test searching for a word that is not in any title."""
        assert self.search.get_titles_containing("establish") == []

    def test_get_titles_containing_word_too_short(self) -> None:
        """Test that searching for a word that is too short returns nothing."""
        assert self.search.get_titles_containing("a") == []

    def test_get_tags_matching_prefix(self) -> None:
        """Test searching for tags by prefix."""
        results = self.search.get_tags_matching_prefix("gy")
        assert Tags.GYRO_GEARLOOSE in results

    def test_get_tags_matching_prefix_group(self) -> None:
        """Test that a prefix can match a tag group."""
        results = self.search.get_tags_matching_prefix("pig v")
        assert TagGroups.PIG_VILLAINS in results

    def test_get_tags_matching_prefix_no_match(self) -> None:
        """Test a prefix that should not match any tags."""
        assert self.search.get_tags_matching_prefix("xyz") == []

    def test_get_titles_from_alias_tag_single_tag(self) -> None:
        """Test getting titles from a single tag alias."""
        tag, titles = BarksTitleSearch.get_titles_from_alias_tag("gyro")
        assert tag == Tags.GYRO_GEARLOOSE
        assert Titles.CAT_BOX_THE in titles
        assert Titles.INVENTOR_OF_ANYTHING in titles

    def test_get_titles_from_alias_tag_group_tag(self) -> None:
        """Test getting titles from a tag group alias."""
        tag_group, titles = BarksTitleSearch.get_titles_from_alias_tag("pig villains")
        assert tag_group == TagGroups.PIG_VILLAINS
        # Check for a title from one villain
        assert Titles.FORBIDDEN_VALLEY in titles
        # Check for a title from another villain
        assert Titles.NORTH_OF_THE_YUKON in titles  # From Beagle Boys

    def test_get_titles_from_alias_tag_no_match(self) -> None:
        """Test an alias that does not exist."""
        tag, titles = BarksTitleSearch.get_titles_from_alias_tag("NonExistentTag")
        assert tag is None
        assert titles == []

    def test_get_titles_as_strings(self) -> None:
        """Test the static method for converting enums to strings."""
        titles_enum = [Titles.GOLDEN_HELMET_THE, Titles.VACATION_TIME]
        titles_str = BarksTitleSearch.get_titles_as_strings(titles_enum)
        assert len(titles_str) == 2  # noqa: PLR2004
        assert "The Golden Helmet" in titles_str
        assert "Vacation Time" in titles_str

    def test_get_titles_from_issue_nums(self) -> None:
        titles = BarksTitleSearch.get_titles_from_issue_num("CS 106")
        assert titles == [Titles.PLENTY_OF_PETS]

        titles = BarksTitleSearch.get_titles_from_issue_num("US 3")
        assert titles == [Titles.HORSERADISH_STORY_THE, Titles.ROUND_MONEY_BIN_THE]

        titles = BarksTitleSearch.get_titles_from_issue_num("FC 495")
        assert titles == [Titles.HORSERADISH_STORY_THE, Titles.ROUND_MONEY_BIN_THE]

        titles = BarksTitleSearch.get_titles_from_issue_num("FC 238")
        assert titles == [Titles.VOODOO_HOODOO]

        titles = BarksTitleSearch.get_titles_from_issue_num("US 10")
        assert titles == [Titles.FABULOUS_PHILOSOPHERS_STONE_THE, Titles.HEIRLOOM_WATCH]


if __name__ == "__main__":
    unittest.main()
