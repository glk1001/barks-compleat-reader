from __future__ import annotations

from unittest.mock import MagicMock

from barks_reader.core.comic_book_info import ComicTitleInfo, get_all_comic_titles


def _make_mock_comic(
    is_barks: bool,
    chrono_num: int,
    issue_title: str = "Issue #1",
    title_with_issue: str = "Title - Issue #1",
) -> MagicMock:
    comic = MagicMock()
    comic.is_barks_title.return_value = is_barks
    comic.chronological_number = chrono_num
    comic.get_comic_issue_title.return_value = issue_title
    comic.get_title_with_issue_num.return_value = title_with_issue
    return comic


class TestGetAllComicTitles:
    def test_barks_title_displayed_without_parens(self) -> None:
        db = MagicMock()
        db.get_comic_book.return_value = _make_mock_comic(is_barks=True, chrono_num=1)

        titles, _ = get_all_comic_titles(db, ["Christmas on Bear Mountain"])

        assert titles[0].title == "Christmas on Bear Mountain"

    def test_non_barks_title_displayed_with_parens(self) -> None:
        db = MagicMock()
        db.get_comic_book.return_value = _make_mock_comic(is_barks=False, chrono_num=2)

        titles, _ = get_all_comic_titles(db, ["Some Non-Barks Title"])

        assert titles[0].title == "(Some Non-Barks Title)"

    def test_longest_title_tracking(self) -> None:
        db = MagicMock()
        short_comic = _make_mock_comic(is_barks=True, chrono_num=1)
        long_comic = _make_mock_comic(is_barks=True, chrono_num=2)
        db.get_comic_book.side_effect = [short_comic, long_comic]

        _, longest = get_all_comic_titles(db, ["Short", "A Much Longer Title Here"])

        assert longest == "A Much Longer Title Here"

    def test_longest_title_accounts_for_parens(self) -> None:
        db = MagicMock()
        barks_comic = _make_mock_comic(is_barks=True, chrono_num=1)
        non_barks_comic = _make_mock_comic(is_barks=False, chrono_num=2)
        db.get_comic_book.side_effect = [barks_comic, non_barks_comic]

        # "ABCDE" (5 chars) vs "(ABCD)" (6 chars) -- parens make non-barks longer.
        _, longest = get_all_comic_titles(db, ["ABCDE", "ABCD"])

        assert longest == "(ABCD)"

    def test_empty_title_list(self) -> None:
        db = MagicMock()

        titles, longest = get_all_comic_titles(db, [])

        assert titles == []
        assert longest == ""

    def test_comic_title_info_fields(self) -> None:
        db = MagicMock()
        db.get_comic_book.return_value = _make_mock_comic(
            is_barks=True,
            chrono_num=42,
            issue_title="WDC #108",
            title_with_issue="Wintertime Wager - WDC #108",
        )

        titles, _ = get_all_comic_titles(db, ["Wintertime Wager"])

        info = titles[0]
        assert isinstance(info, ComicTitleInfo)
        assert info.chronological_number == 42  # noqa: PLR2004
        assert info.title == "Wintertime Wager"
        assert info.issue_title == "WDC #108"
        assert info.filename == "Wintertime Wager - WDC #108"
