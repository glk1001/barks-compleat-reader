import pytest
from barks_fantagraphics.barks_tags import (
    BARKS_TAG_ALIASES,
    BARKS_TAG_GROUPS_ALIASES,
    TagGroups,
    Tags,
)
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO, COVERS_SET
from barks_fantagraphics.comic_issues import Issues
from barks_fantagraphics.search_query import Combine
from barks_fantagraphics.tag_query import TagSelection
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


class TestTitlesForSelection:
    """The stories picked tags list together: ALL, ANY, and some left out."""

    @staticmethod
    def _titles(name: str) -> set[Titles]:
        return set(BarksTitleSearch.get_titles_from_alias_tag(name)[1])

    def test_all_is_the_stories_every_tag_tags(self) -> None:
        both = BarksTitleSearch.get_titles_for_selection(TagSelection(("the classics", "andes")))
        assert set(both) == self._titles("the classics") & self._titles("andes")
        assert both
        assert both == sorted(both)

    def test_any_is_the_stories_either_tags(self) -> None:
        either = BarksTitleSearch.get_titles_for_selection(
            TagSelection(("andes", "africa"), (), Combine.ANY)
        )
        assert set(either) == self._titles("andes") | self._titles("africa")

    def test_an_excluded_tag_leaves_its_stories_out(self) -> None:
        titles = BarksTitleSearch.get_titles_for_selection(
            TagSelection(("the classics",), ("andes",))
        )
        assert set(titles) == self._titles("the classics") - self._titles("andes")
        assert titles

    def test_names_are_matched_in_any_case(self) -> None:
        upper = BarksTitleSearch.get_titles_for_selection(TagSelection(("Andes",)))
        assert set(upper) == self._titles("andes")

    def test_nothing_is_listed_without_an_included_tag(self) -> None:
        assert BarksTitleSearch.get_titles_for_selection(TagSelection((), ("andes",))) == []

    def test_a_name_that_is_no_tag_tags_nothing(self) -> None:
        assert BarksTitleSearch.get_titles_for_selection(TagSelection(("no such tag",))) == []

    def test_years_and_volumes_narrow_the_stories(self) -> None:
        andes = self._titles("andes")
        in_1948 = BarksTitleSearch.get_titles_for_selection(
            TagSelection(("andes",), years=(1948, 1948))
        )
        assert set(in_1948) == {t for t in andes if BARKS_TITLE_INFO[t].submitted_year == 1948}  # noqa: PLR2004
        in_vol_7 = BarksTitleSearch.get_titles_for_selection(
            TagSelection(("andes",), volumes=(7, 7))
        )
        assert Titles.LOST_IN_THE_ANDES in in_vol_7
        assert (
            BarksTitleSearch.get_titles_for_selection(TagSelection(("andes",), volumes=(29, 29)))
            == []
        )


def test_a_prefix_finds_only_the_titles_it_starts() -> None:
    titles = BarksTitleSearch().get_titles_matching_prefix("vacation")
    assert titles
    assert all(BARKS_TITLE_INFO[t].get_title_str().lower().startswith("vacation") for t in titles)


def test_two_letters_are_enough_to_look_inside_titles() -> None:
    assert BarksTitleSearch().get_titles_containing("go")


def test_three_letters_find_tags_with_the_text_inside_their_names() -> None:
    labels = [m.label for m in BarksTitleSearch().get_tags_matching("fri")]
    assert labels == ["Africa", "Central Africa", "South Africa"]


def test_a_tag_named_by_several_aliases_keeps_its_best_rank() -> None:
    """Car 313 is "313" whole, and later also a name holding it: it stays the exact match."""
    matches = BarksTitleSearch().get_tags_matching("313")
    [car] = [m for m in matches if m.item is Tags.CAR_313]
    assert car.exact
    assert matches[0] is car


def test_one_letter_finds_only_the_titles_starting_with_it() -> None:
    titles = BarksTitleSearch().get_titles_matching_prefix("v")
    assert titles
    assert all(BARKS_TITLE_INFO[t].get_title_str().lower().startswith("v") for t in titles)


def test_a_volume_range_leaves_out_stories_in_no_volume() -> None:
    selection = TagSelection(("abduction stories",), volumes=(1, 30))
    titles = BarksTitleSearch().get_titles_for_selection(selection)
    assert Titles.CAPN_BLIGHTS_MYSTERY_SHIP not in titles  # in no Fantagraphics volume
    assert titles


def _find(query: str) -> list[Titles]:
    return BarksTitleSearch().find_titles(query)


def _starts_with(title: Titles, text: str) -> bool:
    lower = BARKS_TITLE_INFO[title].get_title_str().lower()
    return lower.startswith(text) or lower.removeprefix("the ").startswith(text)


def test_nothing_typed_finds_nothing() -> None:
    assert _find("") == []
    assert _find(" !? ") == []


def test_stories_found_are_in_chronological_order() -> None:
    """Titles starting with the text and titles with it later on are one list."""
    titles = _find("gold")
    assert titles == sorted(titles)
    assert Titles.GOLD_RUSH in titles
    assert Titles.GOLDEN_HELMET_THE in titles  # its "The" is passed over
    assert Titles.FROZEN_GOLD in titles  # "gold" starts its second word
    assert titles.index(Titles.DONALD_DUCK_FINDS_PIRATE_GOLD) == 0


def test_a_title_is_found_without_its_leading_article() -> None:
    assert _find("golden helmet") == [Titles.GOLDEN_HELMET_THE]


def test_typed_words_may_start_any_of_the_titles_words_in_any_order() -> None:
    assert _find("andes lost") == [Titles.LOST_IN_THE_ANDES]


def test_a_typed_word_may_be_another_form_of_a_titles_word() -> None:
    assert _find("gold fleece") == [Titles.GOLDEN_FLEECING_THE]
    assert _find("helmets") == [Titles.GOLDEN_HELMET_THE]


def test_case_apostrophes_and_punctuation_are_ignored() -> None:
    assert Titles.GOLD_FINDER_THE in _find("GOLD FINDER")
    assert _find("rabbits foot")[0] == Titles.RABBITS_FOOT_THE
    assert _find("rabbit\N{RIGHT SINGLE QUOTATION MARK}s foot")[0] == Titles.RABBITS_FOOT_THE
    assert _find("fun? what") == [Titles.FUN_WHATS_THAT]


def test_text_inside_a_word_is_found_in_its_chronological_place() -> None:
    titles = _find("old")
    assert Titles.ONLY_A_POOR_OLD_MAN in titles
    assert Titles.FROZEN_GOLD in titles
    assert titles == sorted(titles)


def test_two_letters_find_word_starts_and_three_look_inside_words() -> None:
    assert Titles.LOST_IN_THE_ANDES in _find("an")
    assert Titles.LOST_IN_THE_ANDES not in _find("os")
    assert Titles.LOST_IN_THE_ANDES in _find("ost")
    assert _find("ost andes") == [Titles.LOST_IN_THE_ANDES]


def test_one_letter_finds_only_titles_starting_with_it() -> None:
    titles = _find("v")
    assert Titles.VACATION_TIME in titles
    assert Titles.VICTORY_GARDEN_THE in titles
    assert all(_starts_with(t, "v") for t in titles)


def _in_issues(text: str) -> list[Titles] | None:
    return BarksTitleSearch.get_titles_in_issues(text)


@pytest.mark.parametrize(
    "text",
    [
        "CS 100",
        "cs100",
        "WDCS 100",
        "Comics and Stories 100",
        "Walt Disney's Comics and Stories #100",
    ],
)
def test_an_issue_is_named_by_its_code_or_its_names(text: str) -> None:
    assert _in_issues(text) == [Titles.TRUANT_OFFICER_DONALD]


def test_an_issue_lists_its_stories_one_pagers_and_cover() -> None:
    titles = _find("Four Color 223")
    assert titles[0] == Titles.LOST_IN_THE_ANDES
    assert Titles.TOO_FIT_TO_FIT in titles  # a one-pager
    assert titles[-1] == Titles.FOUR_COLOR_223_COVER
    assert len(titles) == len(set(titles))


def test_an_issue_number_is_matched_as_it_is_typed() -> None:
    """Typing CS 10 names CS 10 and CS 100 to 109: Truant Officer Donald is in CS 100."""
    titles = _find("CS 10")
    assert Titles.TRUANT_OFFICER_DONALD in titles
    assert all(BARKS_TITLE_INFO[t].issue_name == Issues.CS for t in titles)
    assert all(str(BARKS_TITLE_INFO[t].issue_number).startswith("10") for t in titles)
    stories = [t for t in titles if t not in COVERS_SET]
    assert stories == sorted(stories)


def test_a_text_naming_an_issue_finds_no_titles_by_their_words() -> None:
    """Typed "cs" is inside "Comics" and "10" inside "#310", but CS 310's cover is left out."""
    assert Titles.COMICS_AND_STORIES_310_COVER not in _find("CS 10")
    assert _find("US 999") == []


def test_uncle_scrooge_1_to_3_are_their_four_color_issues() -> None:
    assert Titles.ONLY_A_POOR_OLD_MAN in _find("us 1")
    assert Titles.BACK_TO_THE_KLONDIKE in _find("Uncle Scrooge 2")
    assert Titles.ONLY_A_POOR_OLD_MAN not in _find("us 4")
    assert Titles.MENEHUNE_MYSTERY_THE in _find("us4")


def test_a_text_naming_no_issue_is_told_apart_from_an_empty_issue() -> None:
    assert _in_issues("zz 4") is None
    assert _in_issues("US") is None
    assert _in_issues("gold") is None
    assert _in_issues("US 999") == []


def test_an_issues_titles_are_a_new_list_each_time() -> None:
    first = _in_issues("FC 29")
    assert first
    first.append(Titles.GOLD_RUSH)
    assert Titles.GOLD_RUSH not in (_in_issues("FC 29") or [])


def test_title_words_find_stories_not_covers() -> None:
    """A cover's title is its issue's name: "four" is in every "Four Color #n Cover"."""
    assert _find("four") == [Titles.TWENTY_FOUR_CARAT_MOON_THE]
    assert not set(_find("donald")) & COVERS_SET


def test_cover_alone_finds_every_cover_in_the_order_handed_in() -> None:
    covers = _find("covers")
    assert covers == _find("Cover")
    searchable = {i.title for i in BARKS_TITLE_INFO if i.issue_name != Issues.EXTRAS}
    assert set(covers) == COVERS_SET & searchable
    dated = [BARKS_TITLE_INFO[t] for t in covers if BARKS_TITLE_INFO[t].submitted_year > 0]
    handed_in = [(i.submitted_year, i.submitted_month, i.submitted_day) for i in dated]
    assert handed_in == sorted(handed_in)


def test_a_cover_with_no_date_goes_by_when_it_came_out() -> None:
    """Neither has a submission date; they came out in 1971 and 1974, after every other."""
    assert _find("covers")[-2:] == [
        Titles.HUEY_DEWEY_AND_LOUIE_JUNIOR_WOODCHUCKS_9_COVER,
        Titles.COMICS_AND_STORIES_405_COVER,
    ]


def test_an_issues_cover_is_among_its_stories_in_the_order_handed_in() -> None:
    assert _find("dd 26") == [
        Titles.TRICK_OR_TREAT,
        Titles.PRANK_ABOVE_A,
        Titles.FRIGHTFUL_FACE,
        Titles.DONALD_DUCK_26_COVER,
        Titles.HOBBLIN_GOBLINS,
    ]


def test_a_leading_zero_in_an_issue_number_is_passed_over() -> None:
    assert _in_issues("CS 0100") == [Titles.TRUANT_OFFICER_DONALD]
    assert _in_issues("CS 010") == _in_issues("CS 10")
    assert _in_issues("CS 0") == []
    assert _in_issues("CS 000") == []
