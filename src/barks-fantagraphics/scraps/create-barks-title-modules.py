import collections
import csv
import os
import string
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from barks_fantagraphics.comic_issues import SHORT_ISSUE_NAME

ISSUE_NAME_VAR = {
    "Boys' and Girls' March of Comics": "MC",
    "Cheerios Giveaway": "CH",
    "Comics and Stories": "CS",
    "Christmas in Disneyland": "CID",
    "Christmas Parade": "CP",
    "Donald Duck": "DD",
    "Firestone Giveaway": "FG",
    "Four Color": "FC",
    "Kites Giveaway": "KI",
    "Mickey Mouse Almanac": "MMA",
    "Summer Fun": "SF",
    "Uncle Scrooge": "US",
    "Uncle Scrooge Goes to Disneyland": "USGTD",
    "Vacation Parade": "VP",
}


PUBLICATION_INFO_SUBDIR = "story-indexes"
SUBMISSION_DATES_SUBDIR = "story-indexes"
STORIES_INFO_FILENAME = "the-stories.csv"


@dataclass
class _ComicBookInfo:
    is_barks_title: bool
    issue_name: str
    issue_number: int
    issue_month: int
    issue_year: int
    submitted_day: int
    submitted_month: int
    submitted_year: int
    chronological_number: int

    def get_issue_title(self):
        short_issue_name = SHORT_ISSUE_NAME[self.issue_name]
        return f"{short_issue_name} {self.issue_number}"


_ComicBookInfoDict = OrderedDict[str, _ComicBookInfo]


def get_all_comic_book_info() -> _ComicBookInfoDict:
    story_info_dir = os.path.join(
        str(Path(__file__).parent.parent.absolute()), "barks-fantagraphics"
    )

    stories_filename = os.path.join(story_info_dir, PUBLICATION_INFO_SUBDIR, STORIES_INFO_FILENAME)

    all_info: _ComicBookInfoDict = collections.OrderedDict()

    chronological_number = 1
    with open(stories_filename, "r") as csv_file:
        reader = csv.reader(csv_file, delimiter=",", quotechar='"')
        for row in reader:
            ttl = row[0]

            cb_info = _ComicBookInfo(
                is_barks_title=row[1] == "T",
                issue_name=row[2],
                issue_number=int(row[3]),
                issue_year=int(row[4]),
                issue_month=int(row[5]),
                submitted_year=int(row[6]),
                submitted_month=int(row[7]),
                submitted_day=int(row[8]),
                chronological_number=chronological_number,
            )

            all_info[ttl] = cb_info

            chronological_number += 1

    check_story_submitted_order(all_info)

    return all_info


def check_story_submitted_order(all_ttls: _ComicBookInfoDict):
    prev_chronological_number = -1
    prev_title = ""
    prev_submitted_date = date(1940, 1, 1)
    for ttl in all_ttls:
        if not 1 <= all_ttls[ttl].submitted_month <= 12:
            raise Exception(f'"{ttl}": Invalid submission month: {all_ttls[ttl].submitted_month}.')
        submitted_day = 1 if all_ttls[ttl].submitted_day == -1 else all_ttls[ttl].submitted_day
        submitted_date = date(
            all_ttls[ttl].submitted_year,
            all_ttls[ttl].submitted_month,
            submitted_day,
        )
        if prev_submitted_date > submitted_date:
            raise Exception(
                f'"{ttl}": Out of order submitted date {submitted_date}.'
                f' Previous entry: "{prev_title}" - {prev_submitted_date}.'
            )
        chronological_number = all_ttls[ttl].chronological_number
        if prev_chronological_number > chronological_number:
            raise Exception(
                f'"{ttl}": Out of order chronological number {chronological_number}.'
                f' Previous entry: "{prev_title}" - {prev_chronological_number}.'
            )
        prev_title = ttl
        prev_submitted_date = submitted_date


def get_title_var(ttl: str) -> str:
    ttl_var = ttl.upper()

    ttl_var = ttl_var.replace(" ", "_")
    ttl_var = ttl_var.replace("-", "_")

    str_punc = string.punctuation
    str_punc = str_punc.replace("_", "")
    str_punc = str_punc.replace("-", "")
    for punc in str_punc:
        ttl_var = ttl_var.replace(punc, "")

    if ttl_var.startswith("THE_"):
        ttl_var = ttl_var[4:] + "_THE"
    elif ttl_var.startswith("A_"):
        ttl_var = ttl_var[2:] + "_A"

    return ttl_var


# noinspection SpellCheckingInspection
if __name__ == "__main__":
    comic_book_info = get_all_comic_book_info()

    all_titles = OrderedDict()
    for title in comic_book_info:
        title_var = get_title_var(title)
        assert title_var not in all_titles
        all_titles[title_var] = title

    all_titles = {key: all_titles[key] for key in sorted(all_titles.keys())}

    # all_title_vars = {all_titles[key]: key for key in all_titles}
    # with open("/tmp/barks_in.txt", "r") as f:
    #     all_lines = f.readlines()
    # with open("/tmp/barks_out.txt", "w") as f:
    #     for line in all_lines:
    #         print(f"|{line}|")
    #         title = line.split(":")[0].strip(' "')
    #         if not title.startswith("#") and not title.startswith("bt."):
    #             print(f"title: |{title}|")
    #             assert title in all_title_vars
    #             line = line.replace('"' + title + '"', "bt." + all_title_vars[title])
    #             print(f"line: |{line}|")
    #         f.write(line)
    # sys.exit(0)

    with open("/tmp/barks_titles.py", "w") as f:
        f.write(
            """from collections import OrderedDict
from dataclasses import dataclass
from datetime import date

from .comic_issues import (
    SHORT_ISSUE_NAME,
    CH,
    CID,
    CP,
    CS,
    DD,
    FC,
    FG,
    KI,
    MC,
    MMA,
    SF,
    US,
    USGTD,
    VP,
)


@dataclass
class ComicBookInfo:
    is_barks_title: bool
    issue_name: str
    issue_number: int
    issue_month: int
    issue_year: int
    submitted_day: int
    submitted_month: int
    submitted_year: int
    chronological_number: int

    def get_issue_title(self):
        short_issue_name = SHORT_ISSUE_NAME[self.issue_name]
        return f"{short_issue_name} {self.issue_number}"


ComicBookInfoDict = OrderedDict[str, ComicBookInfo]
"""
        )

        f.write(f"\n")
        f.write(f"\n")

        for title_var in all_titles:
            f.write(f'{title_var} = "{all_titles[title_var]}"\n')

        f.write(f"\n")
        f.write(f"# fmt: off\n")
        f.write(f"BARKS_TITLE_INFO: ComicBookInfoDict = OrderedDict([\n")

        for title_var in all_titles:
            title = all_titles[title_var]
            info = comic_book_info[title]

            f.write(
                f"    ({title_var}, ComicBookInfo("
                f" {info.is_barks_title},"
                f" {ISSUE_NAME_VAR[info.issue_name]},"
                f" {info.issue_number},"
                f" {info.issue_month},"
                f" {info.issue_year},"
                f" {info.submitted_day},"
                f" {info.submitted_month},"
                f" {info.submitted_year},"
                f" {info.chronological_number})),\n"
            )

        f.write(f"])\n")
        f.write(f"# fmt: on\n")

        f.write(f"\n")
        f.write(
            """
def get_all_comic_book_info() -> ComicBookInfoDict:
    sorted_info = OrderedDict(
        sorted(BARKS_TITLE_INFO.items(), key=lambda x: x[1].chronological_number)
    )

    check_story_submitted_order(sorted_info)

    return sorted_info


def check_story_submitted_order(all_titles: ComicBookInfoDict):
    prev_chronological_number = -1
    prev_title = ""
    prev_submitted_date = date(1940, 1, 1)
    for title in all_titles:
        if not 1 <= all_titles[title].submitted_month <= 12:
            raise Exception(
                f'"{title}": Invalid submission month: {all_titles[title].submitted_month}.'
            )
        submitted_day = (
            1 if all_titles[title].submitted_day == -1 else all_titles[title].submitted_day
        )
        submitted_date = date(
            all_titles[title].submitted_year,
            all_titles[title].submitted_month,
            submitted_day,
        )
        if prev_submitted_date > submitted_date:
            raise Exception(
                f'"{title}": Out of order submitted date {submitted_date}.'
                f' Previous entry: "{prev_title}" - {prev_submitted_date}.'
            )
        chronological_number = all_titles[title].chronological_number
        if prev_chronological_number > chronological_number:
            raise Exception(
                f'"{title}": Out of order chronological number {chronological_number}.'
                f' Previous entry: "{prev_title}" - {prev_chronological_number}.'
            )
        prev_title = title
        prev_submitted_date = submitted_date
"""
        )
