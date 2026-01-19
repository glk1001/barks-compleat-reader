# ruff: noqa: BLE001, FBT003

import string

import pytest
from barks_fantagraphics.barks_titles import (
    BARKS_ISSUE_DICT,
    BARKS_TITLE_INFO,
    BARKS_TITLES,
    NUM_TITLES,
    # Import the raw data for some tests
    SHORT_ISSUE_NAME,
    ComicBookInfo,
    Issues,
    Titles,
    check_story_submitted_order,
)


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
        for title, title_str in enumerate(BARKS_TITLES):
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

    def test_issue_dict(self) -> None:
        assert "CS 106" in BARKS_ISSUE_DICT
        assert BARKS_ISSUE_DICT["CS 106"] == [Titles.PLENTY_OF_PETS]
        assert "FC 223" in BARKS_ISSUE_DICT
        assert BARKS_ISSUE_DICT["FC 223"] == [Titles.LOST_IN_THE_ANDES]
        assert "US 4" in BARKS_ISSUE_DICT
        assert BARKS_ISSUE_DICT["US 4"] == [Titles.MENEHUNE_MYSTERY_THE]
        assert "DD 68" in BARKS_ISSUE_DICT
        assert BARKS_ISSUE_DICT["DD 68"] == [Titles.MASTER_GLASSER_THE]

        # Two titles in one issue
        assert "DD 26" in BARKS_ISSUE_DICT
        assert BARKS_ISSUE_DICT["DD 26"] == [Titles.TRICK_OR_TREAT, Titles.HOBBLIN_GOBLINS]

        # Test Uncle Scrooge special cases
        assert "US 1" in BARKS_ISSUE_DICT
        assert BARKS_ISSUE_DICT["US 1"] == [Titles.ONLY_A_POOR_OLD_MAN]
        assert "US 2" in BARKS_ISSUE_DICT
        assert BARKS_ISSUE_DICT["US 2"] == [Titles.SOMETHIN_FISHY_HERE, Titles.BACK_TO_THE_KLONDIKE]
        assert "US 3" in BARKS_ISSUE_DICT
        assert BARKS_ISSUE_DICT["US 3"] == [
            Titles.HORSERADISH_STORY_THE,
            Titles.ROUND_MONEY_BIN_THE,
        ]

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
        assert len(BARKS_TITLES) == NUM_TITLES
        assert len(BARKS_TITLE_INFO) == NUM_TITLES
        assert BARKS_TITLE_INFO[0].chronological_number == 1
        assert BARKS_TITLE_INFO[-1].chronological_number == NUM_TITLES

    def test_story_submitted_order(self) -> None:
        try:
            check_story_submitted_order(BARKS_TITLE_INFO)
        except Exception as e:
            pytest.fail(f"get_all_comic_book_info raised an unexpected exception: {e}")


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
        try:
            check_story_submitted_order(valid_data)
        except Exception as e:
            pytest.fail(
                f"check_story_submitted_order raised an unexpected exception for valid data: {e}",
            )

    def test_invalid_month(self) -> None:
        """Tests detection of invalid submission month."""
        invalid_data: list[ComicBookInfo] = [
            ComicBookInfo(Titles(0), True, Issues.FC, 1, 1, 1940, 1, 1, 1940),
            ComicBookInfo(Titles(1), True, Issues.FC, 2, 2, 1940, 1, 13, 1940),  # Invalid month 13
        ]
        with pytest.raises(Exception, match="Invalid submission month: 13"):
            check_story_submitted_order(invalid_data)

        invalid_data_zero: list[ComicBookInfo] = [
            ComicBookInfo(Titles(0), True, Issues.FC, 1, 1, 1940, 1, 0, 1940),  # Invalid month 0
        ]
        with pytest.raises(Exception, match="Invalid submission month: 0"):
            check_story_submitted_order(invalid_data_zero)

    def test_out_of_order_submission_date(self) -> None:
        """Tests detection of out-of-order submission dates."""
        invalid_data: list[ComicBookInfo] = [
            ComicBookInfo(Titles(0), True, Issues.FC, 1, 1, 1940, 15, 2, 1940),
            # Submitted earlier than A
            ComicBookInfo(Titles(1), True, Issues.FC, 2, 2, 1940, 1, 2, 1940),
        ]
        with pytest.raises(Exception, match="Out of order submitted date"):
            check_story_submitted_order(invalid_data)

    def test_out_of_order_chronological_number(self) -> None:
        """Tests detection of out-of-order chronological numbers."""
        invalid_data: list[ComicBookInfo] = [
            ComicBookInfo(Titles(2), True, Issues.FC, 1, 1, 1940, 1, 1, 1940),
            # Chrono 1 (out of order)
            ComicBookInfo(Titles(1), True, Issues.FC, 2, 2, 1940, 1, 2, 1940),
        ]
        with pytest.raises(Exception, match="Out of order chronological number"):
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
        try:
            check_story_submitted_order(data)
        except Exception as e:
            pytest.fail(
                f"check_story_submitted_order raised an unexpected exception with day=-1: {e}",
            )

        # Check case where -1 makes dates equal (should pass)
        data_equal: list[ComicBookInfo] = [
            ComicBookInfo(Titles(0), True, Issues.FC, 1, 1, 1940, -1, 1, 1940),
            ComicBookInfo(Titles(1), True, Issues.FC, 2, 2, 1940, 1, 1, 1940),
        ]
        try:
            check_story_submitted_order(data_equal)
        except Exception as e:
            pytest.fail(
                f"check_story_submitted_order raised an unexpected exception"
                f" with day=-1 making dates equal: {e}",
            )
