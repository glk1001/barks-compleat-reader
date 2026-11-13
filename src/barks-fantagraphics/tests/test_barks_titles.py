# ruff: noqa: FBT003

import string
from pathlib import Path

import pytest
from barks_fantagraphics.barks_covers import (
    COVER_COLLECTION_PAGE_BASE,
    get_cover_collection_pages,
    get_located_covers,
)
from barks_fantagraphics.barks_titles import (
    ENUM_TO_STR_TITLE,
    NUM_TITLES,
    Titles,
    _title_name_from_enum,
)
from barks_fantagraphics.comic_book_info import (
    BARKS_TITLE_INFO,
    COVERS,
    FILENAME_TO_TITLE_SPECIAL_CASE_MAP,
    NON_COMIC_TITLES,
    ONE_PAGER_COLLECTION_PAGE_BASE,
    TITLE_TO_FILENAME_SPECIAL_CASE_MAP,
    ComicBookInfo,
    check_cover_submitted_order,
    check_story_submitted_order,
    get_filename_from_title_str,
    get_located_one_pagers,
    get_one_pager_collection_pages,
    get_title_str_from_filename,
    is_non_comic_title,
)
from barks_fantagraphics.comic_issues import (
    ISSUE_NAME,
    ISSUE_NAME_WRAPPED,
    SHORT_ISSUE_NAME,
    Issues,
)
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.page_classes import OriginalPage, get_collection_pages


class TestComicBookInfo:
    def test_get_issue_title(self) -> None:
        """Tests the formatting of the issue title."""
        info = ComicBookInfo(
            title=Titles(0),
            is_barks_title=True,
            issue_name=Issues.FC,
            issue_number=178,
            issue_month=12,
            issue_year=1947,
            submitted_day=22,
            submitted_month=7,
            submitted_year=1947,
        )
        expected_issue_title = f"{SHORT_ISSUE_NAME[Issues.FC]} 178"
        assert info.get_short_issue_title() == expected_issue_title

        info_us = ComicBookInfo(
            title=Titles(0),
            is_barks_title=False,
            issue_name=Issues.US,
            issue_number=31,
            issue_month=9,
            issue_year=1960,
            submitted_day=12,
            submitted_month=2,
            submitted_year=1960,
        )
        expected_title_us = f"{SHORT_ISSUE_NAME[Issues.US]} 31"
        assert info_us.get_short_issue_title() == expected_title_us

    def test_get_shortest_issue_title(self) -> None:
        """Comics and Stories is CS at its shortest; every other issue keeps its short name."""
        cs = BARKS_TITLE_INFO[Titles.VICTORY_GARDEN_THE]
        fc = BARKS_TITLE_INFO[Titles.GOLDEN_HELMET_THE]
        assert cs.get_short_issue_title() == "WDCS 31"
        assert cs.get_shortest_issue_title() == "CS 31"
        assert fc.get_shortest_issue_title() == "FC 408"

    def test_get_formatted_title_from_issue_name(self) -> None:
        """A long issue name is wrapped over lines its own way; any other goes above its number."""
        uncle_scrooge = BARKS_TITLE_INFO[Titles.MENEHUNE_MYSTERY_THE]
        four_color = BARKS_TITLE_INFO[Titles.GOLDEN_HELMET_THE]
        assert uncle_scrooge.get_formatted_title_from_issue_name() == "Uncle\nScrooge #4"
        assert four_color.get_formatted_title_from_issue_name() == "Four Color\n408"

    def test_every_display_title_gives_back_its_title(self) -> None:
        """Even one of Barks's own that ends in parentheses of its own."""
        not_given_back = [
            info.get_display_title()
            for info in BARKS_TITLE_INFO
            if ComicBookInfo.get_title_str_from_display_title(info.get_display_title())
            != info.get_title_str()
        ]
        assert not_given_back == []
        maple_sugar = "Maple Sugar Time (How Sweet It Is!)"
        assert ComicBookInfo.get_title_str_from_display_title(maple_sugar) == maple_sugar
        assert ComicBookInfo.get_title_str_from_display_title("(Gold Rush)") == "Gold Rush"

    def test_is_non_comic_title(self) -> None:
        article = next(iter(NON_COMIC_TITLES))
        assert is_non_comic_title(ENUM_TO_STR_TITLE[article])
        assert not is_non_comic_title(ENUM_TO_STR_TITLE[Titles.GOLDEN_HELMET_THE])


class TestBarksInfo:
    def test_sorted_by_chronological_number(self) -> None:
        """Tests if the titles list is sorted correctly."""
        for i in range(len(BARKS_TITLE_INFO) - 1):
            assert (
                BARKS_TITLE_INFO[i].chronological_number + 1
                == BARKS_TITLE_INFO[i + 1].chronological_number
            ), (
                f"Chronological order failed between  item {i} ("
                f"'{BARKS_TITLE_INFO[i].get_short_issue_title()}') and item {i + 1} ("
                f"'{BARKS_TITLE_INFO[i + 1].get_short_issue_title()}')"
            )

    def test_chronological_numbers_covered(self) -> None:
        for info in BARKS_TITLE_INFO:
            assert info.chronological_number == info.title + 1, (
                f"Chronological number not equal to title + 1; title: {info.title} ("
                f"'{info.get_short_issue_title()}')"
            )

    def test_correct_title_strings(self) -> None:
        for title, title_str in enumerate(ENUM_TO_STR_TITLE):
            expected_enum_var = self.get_title_var(title_str)
            actual_enum_var = Titles(title).name
            assert actual_enum_var == expected_enum_var, (
                f"Barks title does not match Titles enum name; title: {title_str};"
                f" actual_enum_var: {actual_enum_var}; expected_enum_var: {expected_enum_var} )"
            )

    def test_titles_match_title_info(self) -> None:
        for title in Titles:
            assert title == BARKS_TITLE_INFO[title].title, (
                f"Barks title info title does not match Titles enum title enum: {title};"
                f" title info title: {BARKS_TITLE_INFO[title].title} )"
            )

    @staticmethod
    def get_title_var(title: str) -> str:
        enum_var = title.upper()

        enum_var = enum_var.replace(" ", "_")
        enum_var = enum_var.replace("-", "_")

        str_punc = string.punctuation
        str_punc = str_punc.replace("_", "")
        str_punc = str_punc.replace("-", "")
        for punc in str_punc:
            enum_var = enum_var.replace(punc, "")

        if enum_var.startswith("THE_"):
            enum_var = enum_var[4:] + "_THE"
        elif enum_var.startswith("A_"):
            enum_var = enum_var[2:] + "_A"

        return enum_var

    def test_correct_number_of_titles(self) -> None:
        assert len(ENUM_TO_STR_TITLE) == NUM_TITLES
        assert len(BARKS_TITLE_INFO) == NUM_TITLES
        assert BARKS_TITLE_INFO[0].chronological_number == 1
        assert BARKS_TITLE_INFO[-1].chronological_number == NUM_TITLES

    def test_derivation_matches_barks_titles(self) -> None:
        """Validates that _title_name_from_enum produces the same string as ENUM_TO_STR_TITLE."""
        for title in Titles:
            derived = _title_name_from_enum(title)
            actual = ENUM_TO_STR_TITLE[title]
            assert derived == actual, (
                f"Derivation mismatch for {title.name}: derived={derived!r}, actual={actual!r}"
            )

    def test_story_submitted_order(self) -> None:
        check_story_submitted_order(BARKS_TITLE_INFO)  # no raise

    def test_cover_submitted_order(self) -> None:
        check_cover_submitted_order(BARKS_TITLE_INFO)  # no raise


class TestCheckStorySubmittedOrder:
    def test_valid_order(self) -> None:
        """Tests that correctly ordered data passes."""
        valid_data: list[ComicBookInfo] = [
            ComicBookInfo(Titles(0), True, Issues.FC, 1, 1, 1940, 1, 1, 1940),
            ComicBookInfo(Titles(1), True, Issues.FC, 2, 2, 1940, 1, 2, 1940),
            # Day -1 is ok
            ComicBookInfo(Titles(2), True, Issues.FC, 3, 3, 1940, -1, 2, 1940),
            ComicBookInfo(Titles(3), True, Issues.FC, 4, 4, 1940, 15, 2, 1940),
            ComicBookInfo(Titles(4), True, Issues.FC, 5, 5, 1941, 1, 1, 1941),
        ]
        check_story_submitted_order(valid_data)  # no raise

    def test_invalid_month(self) -> None:
        """Tests detection of invalid submission month."""
        invalid_data: list[ComicBookInfo] = [
            ComicBookInfo(Titles(0), True, Issues.FC, 1, 1, 1940, 1, 1, 1940),
            ComicBookInfo(Titles(1), True, Issues.FC, 2, 2, 1940, 1, 13, 1940),  # Invalid month 13
        ]
        with pytest.raises(RuntimeError, match="Invalid submission month: 13"):
            check_story_submitted_order(invalid_data)

        invalid_data_zero: list[ComicBookInfo] = [
            ComicBookInfo(Titles(0), True, Issues.FC, 1, 1, 1940, 1, 0, 1940),  # Invalid month 0
        ]
        with pytest.raises(RuntimeError, match="Invalid submission month: 0"):
            check_story_submitted_order(invalid_data_zero)

    def test_out_of_order_submission_date(self) -> None:
        """Tests detection of out-of-order submission dates."""
        invalid_data: list[ComicBookInfo] = [
            ComicBookInfo(Titles(0), True, Issues.FC, 1, 1, 1940, 15, 2, 1940),
            # Submitted earlier than A
            ComicBookInfo(Titles(1), True, Issues.FC, 2, 2, 1940, 1, 2, 1940),
        ]
        with pytest.raises(RuntimeError, match="Out of order submitted date"):
            check_story_submitted_order(invalid_data)

    def test_out_of_order_chronological_number(self) -> None:
        """Tests detection of out-of-order chronological numbers."""
        invalid_data: list[ComicBookInfo] = [
            ComicBookInfo(Titles(2), True, Issues.FC, 1, 1, 1940, 1, 1, 1940),
            # Chrono 1 (out of order)
            ComicBookInfo(Titles(1), True, Issues.FC, 2, 2, 1940, 1, 2, 1940),
        ]
        with pytest.raises(RuntimeError, match="Out of order chronological number"):
            check_story_submitted_order(invalid_data)

    def test_handles_day_minus_one(self) -> None:
        """Tests that submitted_day=-1 is handled correctly."""
        data: list[ComicBookInfo] = [
            ComicBookInfo(Titles(0), True, Issues.FC, 1, 1, 1940, -1, 1, 1940),
            # Same month, later day
            ComicBookInfo(Titles(1), True, Issues.FC, 2, 2, 1940, 1, 1, 1940),
            # Later month, day -1
            ComicBookInfo(Titles(2), True, Issues.FC, 3, 3, 1940, -1, 2, 1940),
        ]
        check_story_submitted_order(data)  # no raise

        # Check case where -1 makes dates equal (should pass)
        data_equal: list[ComicBookInfo] = [
            ComicBookInfo(Titles(0), True, Issues.FC, 1, 1, 1940, -1, 1, 1940),
            ComicBookInfo(Titles(1), True, Issues.FC, 2, 2, 1940, 1, 1, 1940),
        ]
        check_story_submitted_order(data_equal)  # no raise


class TestCheckCoverSubmittedOrder:
    """Unit tests for the cover-only submitted-order check.

    Only entries whose title is in COVERS_SET are validated, so synthetic rows
    use real cover titles (`COVERS[i]`) with fabricated submitted dates.
    """

    @staticmethod
    def _cover(i: int, day: int, month: int, year: int) -> ComicBookInfo:
        return ComicBookInfo(COVERS[i], False, Issues.FC, i + 1, 1, 1948, day, month, year)

    def test_valid_ascending(self) -> None:
        data = [
            self._cover(0, 1, 1, 1948),
            self._cover(1, -1, 2, 1948),  # day -1 ok
            self._cover(2, 15, 2, 1948),
            self._cover(3, 1, 1, 1949),
        ]
        check_cover_submitted_order(data)  # no raise

    def test_non_cover_entries_ignored(self) -> None:
        # A non-cover entry out of order is ignored (Titles(0) is a real story).
        data = [
            self._cover(0, 1, 1, 1948),
            ComicBookInfo(Titles(0), True, Issues.FC, 1, 1, 1930, 1, 1, 1930),
            self._cover(1, 1, 2, 1948),
        ]
        check_cover_submitted_order(data)  # no raise

    def test_invalid_month(self) -> None:
        with pytest.raises(RuntimeError, match="Invalid submission month: 13"):
            check_cover_submitted_order([self._cover(0, 1, 13, 1948)])

    def test_out_of_order_date_raises(self) -> None:
        data = [self._cover(0, 15, 2, 1948), self._cover(1, 1, 2, 1948)]
        with pytest.raises(RuntimeError, match="Out of order submitted date"):
            check_cover_submitted_order(data)

    def test_undated_after_dated_passes(self) -> None:
        data = [
            self._cover(0, 1, 1, 1948),
            self._cover(1, 1, 2, 1948),
            self._cover(2, -1, -1, -1),  # undated, at the end
            self._cover(3, -1, -1, -1),
        ]
        check_cover_submitted_order(data)  # no raise

    def test_dated_after_undated_raises(self) -> None:
        data = [
            self._cover(0, 1, 1, 1948),
            self._cover(1, -1, -1, -1),  # undated
            self._cover(2, 1, 2, 1948),  # dated cover after undated -> error
        ]
        with pytest.raises(RuntimeError, match="Dated cover appears after an undated cover"):
            check_cover_submitted_order(data)


class TestTitleStrFromFilename:
    @pytest.mark.parametrize(
        "title", ["Mr. Private Eye", "Operation St. Bernard", "The Limber W. Guest Ranch"]
    )
    def test_a_title_with_a_dot_is_kept_whole_without_asking_the_disk(self, title: str) -> None:
        # Bare names: nothing of the kind exists in the working directory.
        assert get_title_str_from_filename(title) == title
        assert get_title_str_from_filename(f"no-such-dir/{title}") == title
        assert get_title_str_from_filename(f"{title}.ini") == title

    def test_a_real_directory_and_a_missing_one_give_the_same_title(self, tmp_path: Path) -> None:
        (tmp_path / "Mr. Private Eye").mkdir()
        assert get_title_str_from_filename(tmp_path / "Mr. Private Eye") == "Mr. Private Eye"
        assert get_title_str_from_filename(tmp_path / "Mr. Private Eye.png") == "Mr. Private Eye"

    def test_a_name_that_is_only_an_extension_is_kept(self) -> None:
        assert get_title_str_from_filename(".ini") == ".ini"

    def test_every_title_comes_back_from_its_filename(self) -> None:
        # Guards the rule that tells an extension from the tail of a title.
        for title in ENUM_TO_STR_TITLE:
            assert get_title_str_from_filename(get_filename_from_title_str(title, "")) == title
            for ext in (".ini", ".png", ".jpg", ".json", ".cbz"):
                filename = get_filename_from_title_str(title, ext)
                assert get_title_str_from_filename(filename) == title, filename


class TestIssueNames:
    def test_every_issue_has_a_short_and_a_long_name_at_its_own_index(self) -> None:
        assert len(SHORT_ISSUE_NAME) == len(ISSUE_NAME) == len(Issues)
        assert len(set(SHORT_ISSUE_NAME)) == len(Issues)
        assert len(set(ISSUE_NAME)) == len(Issues)
        assert SHORT_ISSUE_NAME[Issues.ANDERS] == "ANDERS"
        assert SHORT_ISSUE_NAME[Issues.CS] == "WDCS"
        assert SHORT_ISSUE_NAME[Issues.EXTRAS] == "EX"
        assert ISSUE_NAME[Issues.ANDERS] == "Anders And & Co"
        assert ISSUE_NAME[Issues.US] == "Uncle Scrooge"
        assert ISSUE_NAME[Issues.EXTRAS] == "Extras (Non-Barks)"

    def test_a_wrapped_issue_name_is_for_a_known_issue(self) -> None:
        assert set(ISSUE_NAME_WRAPPED) <= set(Issues)


class TestFormattedTitleFromIssueName:
    """The title page of a comic with no title of its own. Both forms are meant.

    A name that wraps takes the number on its last line, after a "#". Any other name
    has the number alone on the next line: the Comics and Stories title page draws the
    name as a masthead and takes what follows it as the number, so a "#" there would be
    drawn in the masthead.
    """

    @staticmethod
    def _info(issue: Issues) -> ComicBookInfo:
        return next(info for info in BARKS_TITLE_INFO if info.issue_name == issue)

    def test_a_wrapped_name_has_a_hash_before_the_number(self) -> None:
        info = self._info(Issues.US)
        assert info.get_formatted_title_from_issue_name() == f"Uncle\nScrooge #{info.issue_number}"

    def test_an_unwrapped_name_has_the_number_alone_on_the_next_line(self) -> None:
        info = self._info(Issues.CS)
        assert (
            info.get_formatted_title_from_issue_name() == f"Comics and Stories\n{info.issue_number}"
        )
        info = self._info(Issues.DD)
        assert info.get_formatted_title_from_issue_name() == f"Donald Duck\n{info.issue_number}"

    def test_only_the_wrapped_names_have_a_hash(self) -> None:
        for info in BARKS_TITLE_INFO:
            formatted = info.get_formatted_title_from_issue_name()
            assert ("#" in formatted) == (info.issue_name in ISSUE_NAME_WRAPPED), info.title


class TestFilenameMaps:
    def test_the_two_titles_ending_in_a_question_mark_are_mapped(self) -> None:
        assert TITLE_TO_FILENAME_SPECIAL_CASE_MAP == {
            "Fun? What's That?": "Fun What's That",
            "Want to Buy an Island?": "Want to Buy an Island",
        }

    def test_the_inverse_map_is_the_forward_map_turned_round(self) -> None:
        assert {
            filename: title for title, filename in TITLE_TO_FILENAME_SPECIAL_CASE_MAP.items()
        } == FILENAME_TO_TITLE_SPECIAL_CASE_MAP

    def test_a_title_is_mapped_exactly_when_a_filename_cannot_hold_it(self) -> None:
        for title in ENUM_TO_STR_TITLE:
            cannot_hold = any(char in title for char in '<>:"/\\|?*')
            assert (title in TITLE_TO_FILENAME_SPECIAL_CASE_MAP) == cannot_hold, title


class TestCollectionPages:
    def test_pages_are_numbered_in_a_row_from_the_first(self) -> None:
        pages = get_collection_pages(500, 3, PageType.COVER)
        assert pages == [
            OriginalPage("500", PageType.COVER),
            OriginalPage("501", PageType.COVER),
            OriginalPage("502", PageType.COVER),
        ]

    def test_a_low_page_number_is_padded_to_three_digits(self) -> None:
        assert get_collection_pages(7, 1, PageType.BODY) == [OriginalPage("007", PageType.BODY)]

    def test_an_empty_collection_has_no_pages(self) -> None:
        assert get_collection_pages(500, 0, PageType.BODY) == []

    def test_the_one_pager_collection_has_a_body_page_for_each_located_one_pager(self) -> None:
        pages = get_one_pager_collection_pages()
        assert pages == get_collection_pages(
            ONE_PAGER_COLLECTION_PAGE_BASE, len(get_located_one_pagers()), PageType.BODY
        )
        assert pages

    def test_the_cover_collection_has_a_cover_page_for_each_located_cover(self) -> None:
        pages = get_cover_collection_pages()
        assert pages == get_collection_pages(
            COVER_COLLECTION_PAGE_BASE, len(get_located_covers()), PageType.COVER
        )
        assert pages
