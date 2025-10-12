from __future__ import annotations

import re
import zipfile
from _pydatetime import UTC
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from comic_utils.comic_consts import MONTH_AS_LONG_STR, MONTH_AS_SHORT_STR
from loguru import logger

from .comic_issues import ISSUE_NAME, Issues
from .comics_consts import BARKS_ROOT_DIR

if TYPE_CHECKING:
    from .barks_titles import ComicBookInfo
    from .fanta_comics_info import FantaComicBookInfo


def delete_all_files_in_directory(directory_path: Path) -> None:
    logger.debug(f'Deleting all files in directory "{directory_path}".')

    for file in directory_path.iterdir():
        if file.is_file():
            file.unlink()


def get_dest_comic_dirname(title: str, chrono_num: int) -> str:
    return f"{chrono_num:03d} {title}"


def get_dest_comic_zip_file_stem(title: str, chrono_num: int, issue_name: str) -> str:
    return f"{get_dest_comic_dirname(title, chrono_num)} [{issue_name}]"


def get_titles_and_info_chronologically_sorted(
    titles_and_info: list[tuple[str, FantaComicBookInfo]],
) -> list[tuple[str, FantaComicBookInfo]]:
    return sorted(titles_and_info, key=lambda x: x[1].fanta_chronological_number)


def get_titles_sorted_by_submission_date(
    titles_and_info: list[tuple[str, FantaComicBookInfo]],
) -> list[str]:
    return [t[0] for t in sorted(titles_and_info, key=get_submitted_date)]


def get_titles_and_info_sorted_by_submission_date(
    titles_and_info: list[tuple[str, FantaComicBookInfo]],
) -> list[tuple[str, FantaComicBookInfo]]:
    return sorted(titles_and_info, key=get_submitted_date)


def get_submitted_date(title_and_info: tuple[str, FantaComicBookInfo]) -> date:
    fanta_info = title_and_info[1]
    submitted_day = (
        1
        if fanta_info.comic_book_info.submitted_day == -1
        else fanta_info.comic_book_info.submitted_day
    )
    return date(
        fanta_info.comic_book_info.submitted_year,
        fanta_info.comic_book_info.submitted_month,
        submitted_day,
    )


def get_work_dir(work_dir_root: str) -> str:
    work_dir_root_path = Path(work_dir_root)
    work_dir_root_path.mkdir(parents=True, exist_ok=True)
    if not work_dir_root_path.is_dir():
        msg = f'Could not find work root directory "{work_dir_root}".'
        raise FileNotFoundError(msg)

    work_dir = work_dir_root_path / datetime.now(UTC).strftime("%Y_%m_%d-%H_%M_%S.%f")
    work_dir.mkdir()

    return str(work_dir)


def get_abbrev_path(file: str | Path | zipfile.Path) -> str:
    if isinstance(file, str):
        file = Path(file)
    abbrev = get_relpath(file)

    abbrev = re.sub(r"Carl Barks ", "**", abbrev)
    abbrev = re.sub(r" -.*- ", " - ", abbrev)
    abbrev = re.sub(r" \(.*\)", "", abbrev)

    return abbrev  # noqa: RET504


def get_relpath(file: Path | zipfile.Path) -> str:
    """Get a relative path string from either a filesystem Path or a zipfile.Path."""
    if isinstance(file, zipfile.Path):
        # For zipfile.Path, the .at attribute gives the path inside the zip.
        # noinspection PyUnresolvedReferences
        return file.at.replace("\\", "/")

    if file.is_relative_to(BARKS_ROOT_DIR):
        return str(file.relative_to(BARKS_ROOT_DIR))

    return str(Path(*file.parts[-2:]))


def get_abspath_from_relpath(relpath: Path, root_dir: Path = BARKS_ROOT_DIR) -> Path:
    if relpath.is_absolute():
        return relpath
    return root_dir / relpath


def get_clean_path(file: Path) -> Path:
    return Path(str(file).replace(str(Path.home()), "$HOME"))


def get_timestamp(file: Path) -> float:
    if file.is_symlink():
        return file.lstat().st_mtime

    return file.stat().st_mtime


def get_max_timestamp(files: list[Path]) -> float:
    max_timestamp = -1.0
    for file in files:
        timestamp = get_timestamp(file)
        max_timestamp = max(max_timestamp, timestamp)

    return max_timestamp


def get_timestamp_str(
    file: Path,
    date_sep: str = "_",
    date_time_sep: str = "-",
    hr_sep: str = "_",
) -> str:
    return get_timestamp_as_str(get_timestamp(file), date_sep, date_time_sep, hr_sep)


def get_timestamp_as_str(
    timestamp: float,
    date_sep: str = "_",
    date_time_sep: str = "-",
    hr_sep: str = "_",
) -> str:
    timestamp_as_date = datetime.fromtimestamp(timestamp, tz=ZoneInfo("UTC"))
    timestamp_as_date_as_str = timestamp_as_date.strftime(
        f"%Y{date_sep}%m{date_sep}%d{date_time_sep}%H{hr_sep}%M{hr_sep}%S.%f",
    )
    return timestamp_as_date_as_str[:-4]  # trim microseconds to two places


def dest_file_is_older_than_srce(
    srce_file: Path,
    dest_file: Path,
    include_missing_dest: bool = True,
) -> bool:
    if include_missing_dest and not Path(dest_file).exists():
        return True

    srce_timestamp = get_timestamp(srce_file)
    dest_timestamp = get_timestamp(dest_file)

    return srce_timestamp > dest_timestamp


def file_is_older_than_timestamp(file: Path, timestamp: float) -> bool:
    file_timestamp = get_timestamp(file)

    return file_timestamp < timestamp


def get_ocr_no_json_suffix(ocr_json_file: str) -> str:
    return Path(Path(ocr_json_file).stem).suffix


def get_ocr_json_suffix(ocr_json_file: str) -> str:
    return get_ocr_no_json_suffix(ocr_json_file) + ".json"


def get_formatted_day(day: int) -> str:
    if day in {1, 31}:
        day_str = str(day) + "st"
    elif day in {2, 22}:
        day_str = str(day) + "nd"
    elif day in {3, 23}:
        day_str = str(day) + "rd"
    else:
        day_str = str(day) + "th"

    return day_str


def get_short_formatted_first_published_str(comic_book_info: ComicBookInfo) -> str:
    issue = comic_book_info.get_short_issue_title()

    if comic_book_info.issue_month == -1:
        issue_date = comic_book_info.issue_year
    else:
        issue_date = (
            f"{MONTH_AS_SHORT_STR[comic_book_info.issue_month]} {comic_book_info.issue_year}"
        )

    return f"{issue}, {issue_date}"


def get_short_formatted_submitted_date(comic_book_info: ComicBookInfo) -> str:
    if comic_book_info.submitted_day == -1:
        return (
            f"{MONTH_AS_SHORT_STR[comic_book_info.submitted_month]}"
            f" {comic_book_info.submitted_year}"
        )

    return (
        f"{get_formatted_day(comic_book_info.submitted_day)}"
        f" {MONTH_AS_SHORT_STR[comic_book_info.submitted_month]}"
        f" {comic_book_info.submitted_year}"
    )


def get_long_formatted_submitted_date(comic_book_info: ComicBookInfo) -> str:
    if comic_book_info.submitted_day == -1:
        return (
            f"{MONTH_AS_LONG_STR[comic_book_info.submitted_month]} {comic_book_info.submitted_year}"
        )

    return (
        f"{get_formatted_day(comic_book_info.submitted_day)}"
        f" {MONTH_AS_LONG_STR[comic_book_info.submitted_month]}"
        f" {comic_book_info.submitted_year}"
    )


def get_formatted_first_published_str(
    comic_book_info: ComicBookInfo,
    issue_name_dict: dict[Issues, str] = ISSUE_NAME,
    max_len_before_shorten: int = 0,
) -> str:
    issue_name = issue_name_dict[comic_book_info.issue_name]
    issue = f"{issue_name} #{comic_book_info.issue_number}"

    if comic_book_info.issue_month == -1:
        issue_date = comic_book_info.issue_year
    else:
        issue_date = (
            f"{MONTH_AS_LONG_STR[comic_book_info.issue_month]} {comic_book_info.issue_year}"
        )

    first_published_str = f"{issue}, {issue_date}"
    if (
        (max_len_before_shorten > 0)
        and (len(first_published_str) > max_len_before_shorten)
        and (comic_book_info.issue_month != -1)
    ):
        issue_date = (
            f"{MONTH_AS_SHORT_STR[comic_book_info.issue_month]} {comic_book_info.issue_year}"
        )
        first_published_str = f"{issue}, {issue_date}"

    return first_published_str


def get_formatted_submitted_date(comic_book_info: ComicBookInfo) -> str:
    if comic_book_info.submitted_day == -1:
        return (
            f", {MONTH_AS_LONG_STR[comic_book_info.submitted_month]}"
            f" {comic_book_info.submitted_year}"
        )

    return (
        f" on {MONTH_AS_LONG_STR[comic_book_info.submitted_month]}"
        f" {get_formatted_day(comic_book_info.submitted_day)},"
        f" {comic_book_info.submitted_year}"
    )


def get_short_submitted_day_and_month(comic_book_info: ComicBookInfo) -> str:
    if comic_book_info.submitted_day == -1:
        return f"{MONTH_AS_SHORT_STR[comic_book_info.submitted_month]}"

    return (
        f"{get_formatted_day(comic_book_info.submitted_day)}"
        f" {MONTH_AS_SHORT_STR[comic_book_info.submitted_month]}"
    )
