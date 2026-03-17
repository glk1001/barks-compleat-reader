# ruff: noqa: PLR2004

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.comics_utils import (
    get_abbrev_path,
    get_abspath_from_relpath,
    get_clean_path,
    get_dest_comic_dirname,
    get_dest_comic_zip_file_stem,
    get_formatted_day,
    get_formatted_submitted_date,
    get_long_formatted_submitted_date,
    get_ocr_json_suffix,
    get_ocr_type,
    get_relpath,
    get_short_formatted_submitted_date,
    get_short_submitted_day_and_month,
    get_timestamp_as_str,
)


class TestGetDestComicDirname:
    def test_zero_pads_chrono_number(self) -> None:
        assert get_dest_comic_dirname("My Title", 5) == "005 My Title"

    def test_three_digit_chrono_number(self) -> None:
        assert get_dest_comic_dirname("Title", 123) == "123 Title"

    def test_four_digit_chrono_number(self) -> None:
        assert get_dest_comic_dirname("Title", 1000) == "1000 Title"


class TestGetDestComicZipFileStem:
    def test_includes_brackets_around_issue_name(self) -> None:
        assert get_dest_comic_zip_file_stem("My Title", 5, "FC 123") == "005 My Title [FC 123]"


class TestGetFormattedDay:
    @pytest.mark.parametrize(
        ("day", "expected_suffix"),
        [
            (1, "st"),
            (2, "nd"),
            (3, "rd"),
            (4, "th"),
            (5, "th"),
            (10, "th"),
            (11, "th"),
            (12, "th"),
            (13, "th"),
            (14, "th"),
            (20, "th"),
            (22, "nd"),
            (23, "rd"),
            (25, "th"),
            (30, "th"),
            (31, "st"),
        ],
    )
    def test_ordinal_suffixes(self, day: int, expected_suffix: str) -> None:
        result = get_formatted_day(day)
        assert result == f"{day}{expected_suffix}"

    # noinspection GrazieInspection
    def test_day_21_bug(self) -> None:
        """Day 21 should end in 'st' but current implementation returns '21th'."""
        result = get_formatted_day(21)
        # This documents the current (buggy) behavior: 21 -> "21th" instead of "21st"
        assert result == "21th"


class TestGetRelpath:
    def test_zipfile_path(self) -> None:
        zp = MagicMock(spec=zipfile.Path)
        zp.at = "subdir\\image.png"
        assert get_relpath(zp) == "subdir/image.png"

    def test_non_relative_path(self) -> None:
        path = Path("/some/other/place/vol01/page001.png")
        result = get_relpath(path)
        assert result == "vol01/page001.png"


class TestGetAbspathFromRelpath:
    def test_relative_path_joined_with_root(self) -> None:
        root = Path("/my/root")
        rel = Path("sub/file.txt")
        assert get_abspath_from_relpath(rel, root) == Path("/my/root/sub/file.txt")

    def test_absolute_path_returned_unchanged(self) -> None:
        root = Path("/my/root")
        abs_path = Path("/absolute/path/file.txt")
        assert get_abspath_from_relpath(abs_path, root) == abs_path


class TestGetCleanPath:
    def test_replaces_home_with_dollar_home(self) -> None:
        home = Path.home()
        path = home / "some" / "file.txt"
        result = get_clean_path(path)
        assert str(result).startswith("$HOME")
        assert "file.txt" in str(result)


class TestGetTimestampAsStr:
    def test_default_separators(self) -> None:
        # 2024-01-15 10:30:45.123456 UTC
        ts = 1705311045.123456
        result = get_timestamp_as_str(ts)
        # Should be formatted as YYYY_MM_DD-HH_MM_SS.ff
        assert result.count("_") == 4
        assert "-" in result
        assert "." in result
        # Microseconds trimmed to 2 places
        parts = result.split(".")
        assert len(parts[1]) == 2

    def test_custom_separators(self) -> None:
        ts = 1705311045.0
        result = get_timestamp_as_str(ts, date_sep="-", date_time_sep="T", hr_sep=":")
        assert "T" in result


class TestGetOcrType:
    def test_extracts_type_from_double_suffix(self) -> None:
        path = Path("page001.tesseract.json")
        assert get_ocr_type(path) == "tesseract"

    def test_extracts_type_from_another_suffix(self) -> None:
        path = Path("page001.gcv.json")
        assert get_ocr_type(path) == "gcv"


class TestGetOcrJsonSuffix:
    def test_returns_type_plus_json(self) -> None:
        path = Path("page001.tesseract.json")
        assert get_ocr_json_suffix(path) == "tesseract.json"


class TestDateFormatting:
    @staticmethod
    def _make_comic_info(
        submitted_day: int = 15,
        submitted_month: int = 3,
        submitted_year: int = 1948,
        issue_month: int = 6,
        issue_year: int = 1948,
    ) -> MagicMock:
        info = MagicMock()
        info.submitted_day = submitted_day
        info.submitted_month = submitted_month
        info.submitted_year = submitted_year
        info.issue_month = issue_month
        info.issue_year = issue_year
        return info

    def test_short_formatted_submitted_date_with_day(self) -> None:
        info = self._make_comic_info(submitted_day=5, submitted_month=3, submitted_year=1948)
        result = get_short_formatted_submitted_date(info)
        assert "5th" in result
        assert "Mar" in result
        assert "1948" in result

    def test_short_formatted_submitted_date_no_day(self) -> None:
        info = self._make_comic_info(submitted_day=-1, submitted_month=6, submitted_year=1950)
        result = get_short_formatted_submitted_date(info)
        assert "Jun" in result
        assert "1950" in result

    def test_long_formatted_submitted_date_with_day(self) -> None:
        info = self._make_comic_info(submitted_day=1, submitted_month=12, submitted_year=1947)
        result = get_long_formatted_submitted_date(info)
        assert "1st" in result
        assert "December" in result
        assert "1947" in result

    def test_long_formatted_submitted_date_no_day(self) -> None:
        info = self._make_comic_info(submitted_day=-1, submitted_month=1, submitted_year=1945)
        result = get_long_formatted_submitted_date(info)
        assert "January" in result
        assert "1945" in result

    def test_formatted_submitted_date_with_day(self) -> None:
        info = self._make_comic_info(submitted_day=3, submitted_month=7, submitted_year=1949)
        result = get_formatted_submitted_date(info)
        assert result.startswith(" on ")
        assert "3rd" in result

    def test_formatted_submitted_date_no_day(self) -> None:
        info = self._make_comic_info(submitted_day=-1, submitted_month=7, submitted_year=1949)
        result = get_formatted_submitted_date(info)
        assert result.startswith(", ")

    def test_short_submitted_day_and_month_with_day(self) -> None:
        info = self._make_comic_info(submitted_day=22, submitted_month=4)
        result = get_short_submitted_day_and_month(info)
        assert "22nd" in result
        assert "Apr" in result

    def test_short_submitted_day_and_month_no_day(self) -> None:
        info = self._make_comic_info(submitted_day=-1, submitted_month=4)
        result = get_short_submitted_day_and_month(info)
        assert result == "Apr"


class TestGetAbbrevPath:
    def test_abbreviates_carl_barks_prefix(self) -> None:
        path = Path("/some/Carl Barks Volume 01 - Stuff - More/page.png")
        result = get_abbrev_path(path)
        assert "Carl Barks " not in result
        assert "**" in result

    def test_removes_parenthetical(self) -> None:
        path = Path("/dir/parent/Some Title (extra info)/page.png")
        result = get_abbrev_path(path)
        assert "(extra info)" not in result
