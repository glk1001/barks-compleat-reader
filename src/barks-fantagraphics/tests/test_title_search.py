import pytest
from barks_fantagraphics.barks_tags import (
    BARKS_TAG_ALIASES,
    BARKS_TAG_GROUPS_ALIASES,
    TagGroups,
    Tags,
)
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO
from barks_fantagraphics.comic_issues import Issues
from barks_fantagraphics.title_search import BarksTitleSearch


class TestBarksTitleSearch:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Set up a new BarksTitleSearch instance for each test."""
        self.search = BarksTitleSearch()

    def test_get_titles_matching_prefix_empty(self) -> None:
        """Test that an empty prefix returns an empty list."""
        assert self.search.get_titles_matching_prefix("") == []

    def test_every_title_is_found_by_its_canonical_title(self) -> None:
        """Typing a whole title finds it, for every title the search indexes.

        Extras are not indexed. The query is the plain canonical title, not the
        parenthesised display form. Membership, not position: a title that is a
        prefix of another still matches both.
        """
        not_found = [
            info.get_title_str()
            for info in BARKS_TITLE_INFO
            if info.issue_name != Issues.EXTRAS
            and info.title not in self.search.get_titles_matching_prefix(info.get_title_str())
        ]
        assert not_found == []

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

    def _tags(self, text: str) -> list[Tags | TagGroups]:
        return [match.item for match in self.search.get_tags_matching(text)]

    def test_a_tag_is_found_by_the_start_of_an_alias(self) -> None:
        assert Tags.GYRO_GEARLOOSE in self._tags("gy")

    def test_a_tag_group_is_found_too(self) -> None:
        assert TagGroups.PIG_VILLAINS in self._tags("pig v")

    def test_no_match(self) -> None:
        assert self.search.get_tags_matching("xyz") == []
        assert self.search.get_tags_matching("") == []

    def test_a_one_letter_text_is_searched_not_recursed_on(self) -> None:
        """It once called itself for ever; the screen's two-letter minimum hid it."""
        aliased = {**BARKS_TAG_ALIASES, **BARKS_TAG_GROUPS_ALIASES}
        assert set(self._tags("g")) == {t for a, t in aliased.items() if a.startswith("g")}

    def test_whole_alias_then_start_then_inside(self) -> None:
        """Africa is typed whole; Central and South Africa have it inside their names."""
        matches = self.search.get_tags_matching("africa")
        assert [m.label for m in matches] == ["Africa", "Central Africa", "South Africa"]
        assert [m.exact for m in matches] == [True, False, False]

    def test_inside_a_name_only_from_three_letters(self) -> None:
        assert TagGroups.AFRICA not in self._tags("fr")
        assert self._tags("frica")[:1] == [TagGroups.AFRICA]  # cspell:disable-line

    @pytest.mark.parametrize("text", ["g", "sou", "pig", "gy", "duck"])
    def test_each_tag_once_and_each_rank_in_display_name_order(self, text: str) -> None:
        """Not the order of a set, which Python's per-process hash seed shuffles."""
        matches = self.search.get_tags_matching(text)
        assert matches, f"no tags for {text!r}"
        items = [m.item for m in matches]
        assert len(items) == len(set(items)), "each tag once"
        starts = [m for m in matches if not m.exact and m.label.lower().startswith(text)]
        assert [m.label for m in starts] == sorted(m.label for m in starts)

    def test_any_case(self) -> None:
        assert self.search.get_tags_matching("SOU") == self.search.get_tags_matching("sou")

    def test_the_count_is_the_stories_the_tag_lists(self) -> None:
        """A group's count is every story its members tag, as picking it lists them."""
        for match in self.search.get_tags_matching("africa"):
            _, titles = BarksTitleSearch.get_titles_from_alias_tag(match.label.lower())
            assert match.title_count == len(titles), match.label
            assert match.title_count > 0

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
