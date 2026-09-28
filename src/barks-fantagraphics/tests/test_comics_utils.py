# ruff: noqa: PLR2004

from __future__ import annotations

import os
import re
import zipfile
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, cast
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.comics_consts import BARKS_ROOT_DIR
from barks_fantagraphics.comics_utils import (
    delete_all_files_in_directory,
    dest_file_is_older_than_srce,
    file_is_older_than_timestamp,
    get_abbrev_path,
    get_abspath_from_relpath,
    get_backup_file,
    get_clean_path,
    get_dest_comic_dirname,
    get_dest_comic_zip_file_stem,
    get_formatted_day,
    get_formatted_submitted_date,
    get_long_formatted_submitted_date,
    get_max_timestamp,
    get_ocr_json_suffix,
    get_ocr_type,
    get_relpath,
    get_short_formatted_submitted_date,
    get_short_submitted_day_and_month,
    get_submitted_date,
    get_timestamp,
    get_timestamp_as_str,
    get_titles_and_info_chronologically_sorted,
    get_titles_and_info_sorted_by_submission_date,
    get_titles_sorted_by_submission_date,
    get_work_dir,
)

if TYPE_CHECKING:
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo


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

    # noinspection GrazieInspection,GrazieInspectionRunner
    def test_day_21_bug(self) -> None:
        # noinspection GrazieInspectionRunner
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

    def test_short_formatted_submitted_date_unknown(self) -> None:
        """A wholly unrecorded submitted date (e.g. some covers) formats as Unknown."""
        info = self._make_comic_info(submitted_day=-1, submitted_month=-1, submitted_year=-1)
        assert get_short_formatted_submitted_date(info) == "Unknown"

    def test_long_formatted_submitted_date_unknown(self) -> None:
        info = self._make_comic_info(submitted_day=-1, submitted_month=-1, submitted_year=-1)
        assert get_long_formatted_submitted_date(info) == "Unknown"

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


# ---------------------------------------------------------------------------
# File times: what the build pipeline's rebuild decisions rest on
# ---------------------------------------------------------------------------


def _file(path: Path, mtime: float) -> Path:
    path.write_text("x")
    os.utime(path, (mtime, mtime))
    return path


class TestFileTimes:
    @pytest.mark.skipif(
        os.utime not in os.supports_follow_symlinks,
        reason="this platform cannot set a symlink's own time (Windows)",
    )
    def test_a_symlink_has_its_own_time_not_its_targets(self, tmp_path: Path) -> None:
        target = _file(tmp_path / "target", 2_000)
        link = tmp_path / "link"
        link.symlink_to(target)
        os.utime(link, (1_000, 1_000), follow_symlinks=False)
        assert get_timestamp(link) == 1_000
        assert get_timestamp(target) == 2_000

    def test_the_newest_of_several(self, tmp_path: Path) -> None:
        files = [_file(tmp_path / f"f{n}", t) for n, t in enumerate((3_000, 5_000, 4_000))]
        assert get_max_timestamp(files) == 5_000
        assert get_max_timestamp([]) == -1.0

    @pytest.mark.parametrize(
        ("srce", "dest", "older"),
        [(2_000, 1_000, True), (1_000, 2_000, False), (1_000, 1_000, False)],
    )
    def test_a_dest_older_than_its_srce_needs_rebuilding(
        self, tmp_path: Path, srce: float, dest: float, older: bool
    ) -> None:
        assert (
            dest_file_is_older_than_srce(_file(tmp_path / "s", srce), _file(tmp_path / "d", dest))
            is older
        )

    def test_a_missing_dest_needs_building_unless_told_otherwise(self, tmp_path: Path) -> None:
        srce = _file(tmp_path / "s", 1_000)
        assert dest_file_is_older_than_srce(srce, tmp_path / "missing") is True
        with pytest.raises(FileNotFoundError):
            dest_file_is_older_than_srce(srce, tmp_path / "missing", include_missing_dest=False)

    def test_older_than_a_timestamp(self, tmp_path: Path) -> None:
        file = _file(tmp_path / "f", 1_000)
        assert file_is_older_than_timestamp(file, 1_001) is True
        assert file_is_older_than_timestamp(file, 1_000) is False

    def test_a_backup_is_named_by_the_files_time(self, tmp_path: Path) -> None:
        file = _file(tmp_path / "page.png", 0)
        assert get_backup_file(file) == tmp_path / "page_1970_01_01-00_00_00.00.png"


class TestDirsAndPaths:
    def test_every_file_in_a_dir_is_deleted_but_not_its_subdirs(self, tmp_path: Path) -> None:
        _file(tmp_path / "a", 1)
        _file(tmp_path / "b", 1)
        (tmp_path / "sub").mkdir()
        delete_all_files_in_directory(tmp_path)
        assert [p.name for p in tmp_path.iterdir()] == ["sub"]

    def test_a_work_dir_is_a_new_timestamped_dir_under_its_root(self, tmp_path: Path) -> None:
        work = Path(get_work_dir(str(tmp_path / "work")))
        assert work.is_dir()
        assert work.parent == tmp_path / "work"
        assert re.fullmatch(r"\d{4}_\d\d_\d\d-\d\d_\d\d_\d\d\.\d{6}", work.name)

    def test_a_path_under_the_barks_root_is_relative_to_it(self) -> None:
        assert get_relpath(BARKS_ROOT_DIR / "Fanta" / "x.jpg") == "Fanta/x.jpg"

    def test_the_abbreviated_path_drops_the_volume_titles_decoration(self) -> None:
        file = (
            BARKS_ROOT_DIR
            / "Carl Barks Vol. 5 - Donald Duck - Christmas on Bear Mountain (Digital)"
        )
        assert (
            get_abbrev_path(str(file / "001.jpg"))
            == "**Vol. 5 - Christmas on Bear Mountain/001.jpg"
        )


# ---------------------------------------------------------------------------
# Titles by chronology and by submission date
# ---------------------------------------------------------------------------


def _info(chrono: int, year: int, month: int, day: int) -> FantaComicBookInfo:
    info = MagicMock()
    info.fanta_chronological_number = chrono
    info.comic_book_info.submitted_year = year
    info.comic_book_info.submitted_month = month
    info.comic_book_info.submitted_day = day
    return cast("FantaComicBookInfo", info)


class TestTitleOrders:
    TITLES: ClassVar[list[tuple[str, FantaComicBookInfo]]] = [
        ("Late", _info(3, 1950, 5, -1)),
        ("Early", _info(1, 1946, 2, 10)),
        ("Middle", _info(2, 1950, 4, 30)),
    ]

    def test_chronological_order(self) -> None:
        assert [t for t, _ in get_titles_and_info_chronologically_sorted(self.TITLES)] == [
            "Early",
            "Middle",
            "Late",
        ]

    def test_submission_order_with_an_unknown_day_as_the_first(self) -> None:
        assert get_titles_sorted_by_submission_date(self.TITLES) == ["Early", "Middle", "Late"]
        assert [t for t, _ in get_titles_and_info_sorted_by_submission_date(self.TITLES)] == [
            "Early",
            "Middle",
            "Late",
        ]
        assert get_submitted_date(self.TITLES[0]) == date(1950, 5, 1)

    @pytest.mark.parametrize(
        ("info", "field"), [(_info(1, 1950, -1, 1), "month"), (_info(1, -1, 5, 1), "year")]
    )
    def test_an_unknown_month_or_year_cannot_be_ordered(
        self, info: FantaComicBookInfo, field: str
    ) -> None:
        with pytest.raises(ValueError, match=f'Invalid submitted {field} -1, for title "T"'):
            get_submitted_date(("T", info))
