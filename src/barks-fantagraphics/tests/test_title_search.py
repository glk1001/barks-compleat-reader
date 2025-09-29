import unittest

from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.title_search import BarksTitleSearch


class TestBarksTitleSearch(unittest.TestCase):
    def setUp(self):
        """Set up a new BarksTitleSearch instance for each test."""
        self.search = BarksTitleSearch()

    def test_get_titles_matching_prefix_empty(self):
        """Test that an empty prefix returns an empty list."""
        self.assertEqual(self.search.get_titles_matching_prefix(""), [])

    def test_get_titles_matching_prefix_one_char(self):
        """Test searching with a single character prefix."""
        # Assuming there are titles starting with 'C'
        results = self.search.get_titles_matching_prefix("C")
        self.assertGreater(len(results), 0)
        # Check if a known title is in the results
        self.assertIn(Titles.CHRISTMAS_IN_DUCKBURG, results)

    def test_get_titles_matching_prefix_two_chars(self):
        """Test searching with a two-character prefix."""
        results = self.search.get_titles_matching_prefix("in")
        self.assertIn(Titles.IN_OLD_CALIFORNIA, results)
        self.assertIn(Titles.IN_ANCIENT_PERSIA, results)

    def test_get_titles_matching_prefix_long_prefix(self):
        """Test searching with a prefix longer than two characters."""
        results = self.search.get_titles_matching_prefix("the golden")
        self.assertIn(Titles.GOLDEN_HELMET_THE, results)
        self.assertNotIn(Titles.GHOST_OF_THE_GROTTO_THE, results)

    def test_get_titles_matching_prefix_case_insensitivity(self):
        """Test that prefix matching is case-insensitive."""
        results_lower = self.search.get_titles_matching_prefix("va")
        results_upper = self.search.get_titles_matching_prefix("VA")
        self.assertEqual(results_lower, results_upper)
        self.assertIn(Titles.VACATION_TIME, results_lower)

    def test_get_titles_matching_prefix_no_match(self):
        """Test a prefix that should not match any titles."""
        self.assertEqual(self.search.get_titles_matching_prefix("xyz"), [])

    def test_get_titles_containing_word(self):
        """Test searching for titles containing a specific word."""
        results = self.search.get_titles_containing("christmas")
        self.assertIn(Titles.CHRISTMAS_IN_DUCKBURG, results)
        self.assertNotIn(Titles.BLACK_PEARLS_OF_TABU_YAMA_THE, results)
        self.assertNotIn(Titles.GOLDEN_HELMET_THE, results)

    def test_get_titles_containing_word_no_match(self):
        """Test searching for a word that is not in any title."""
        self.assertEqual(self.search.get_titles_containing("establish"), [])

    def test_get_titles_containing_word_too_short(self):
        """Test that searching for a word that is too short returns nothing."""
        self.assertEqual(self.search.get_titles_containing("a"), [])

    def test_get_tags_matching_prefix(self):
        """Test searching for tags by prefix."""
        results = self.search.get_tags_matching_prefix("gy")
        self.assertIn(Tags.GYRO_GEARLOOSE, results)

    def test_get_tags_matching_prefix_group(self):
        """Test that a prefix can match a tag group."""
        results = self.search.get_tags_matching_prefix("pig v")
        self.assertIn(TagGroups.PIG_VILLAINS, results)

    def test_get_tags_matching_prefix_no_match(self):
        """Test a prefix that should not match any tags."""
        self.assertEqual(self.search.get_tags_matching_prefix("xyz"), [])

    def test_get_titles_from_alias_tag_single_tag(self):
        """Test getting titles from a single tag alias."""
        tag, titles = BarksTitleSearch.get_titles_from_alias_tag("gyro")
        self.assertEqual(tag, Tags.GYRO_GEARLOOSE)
        self.assertIn(Titles.CAT_BOX_THE, titles)
        self.assertIn(Titles.INVENTOR_OF_ANYTHING, titles)

    def test_get_titles_from_alias_tag_group_tag(self):
        """Test getting titles from a tag group alias."""
        tag_group, titles = BarksTitleSearch.get_titles_from_alias_tag("pig villains")
        self.assertEqual(tag_group, TagGroups.PIG_VILLAINS)
        # Check for a title from one villain
        self.assertIn(Titles.FORBIDDEN_VALLEY, titles)
        # Check for a title from another villain
        self.assertIn(Titles.NORTH_OF_THE_YUKON, titles)  # From Beagle Boys

    def test_get_titles_from_alias_tag_no_match(self):
        """Test an alias that does not exist."""
        tag, titles = BarksTitleSearch.get_titles_from_alias_tag("NonExistentTag")
        self.assertIsNone(tag)
        self.assertEqual(titles, [])

    def test_get_titles_as_strings(self):
        """Test the static method for converting enums to strings."""
        titles_enum = [Titles.GOLDEN_HELMET_THE, Titles.VACATION_TIME]
        titles_str = BarksTitleSearch.get_titles_as_strings(titles_enum)
        self.assertEqual(len(titles_str), 2)
        self.assertIn("The Golden Helmet", titles_str)
        self.assertIn("Vacation Time", titles_str)

    def test_get_titles_from_issue_nums(self):
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
