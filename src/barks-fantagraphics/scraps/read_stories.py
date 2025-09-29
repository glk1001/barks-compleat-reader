import os.path
import re
from dataclasses import dataclass
from typing import List, Tuple

from src.consts import THIS_DIR, PUBLICATION_INFO_SUBDIR

STORY_INDEX_FILE = os.path.join(THIS_DIR, PUBLICATION_INFO_SUBDIR, "wiki-story-index.txt")

LONG_MONTHS = {
    "<none>": "<none>",
    "Jan": "January",
    "Feb": "February",
    "Mar": "March",
    "March": "March",
    "April": "April",
    "May": "May",
    "June": "June",
    "July": "July",
    "Aug": "August",
    "Sept": "September",
    "Oct": "October",
    "Nov": "November",
    "Dec": "December",
}


def get_issue_month_year(issue_date: str) -> Tuple[str, int]:
    issue_month_year = issue_date.split(" ")
    assert 1 <= len(issue_month_year) <= 2

    if len(issue_month_year) == 1:
        issue_month = "<none>"
        issue_year = int(issue_month_year[0])
    else:
        issue_month = issue_month_year[0]
        issue_year = int(issue_month_year[1])

    return issue_month, issue_year


def replace_char(text: str, index: int, new_char: str):
    char_list = list(text)
    char_list[index] = new_char
    return "".join(char_list)


@dataclass
class StoryInfo:
    title: str
    issue_name: str
    issue_num: str
    issue_month: str
    issue_year: int


def get_all_stories() -> List[StoryInfo]:
    all_lines: List[str] = []
    with open(STORY_INDEX_FILE, "r") as f:
        while True:
            line = f.readline().strip()
            if not line:
                break

            index = line.find('"')
            assert index != -1
            title = '"' + line[:index].strip() + '"'

            line = title + " " + line[index:]

            index = line.find("#")
            assert index != -1
            next_blank_index = line[index + 1 :].find(" ")
            assert next_blank_index != -1
            next_blank_index += index
            line = (
                line[:index]
                + '"'
                + line[index + 1 : next_blank_index + 1]
                + '"'
                + line[next_blank_index:]
            )

            index = line.find("(")
            assert index != -1
            line = replace_char(line, index, '"')

            index = line.find(")")
            assert index != -1
            line = replace_char(line, index, '"')

            all_lines.append(line[: index + 1])

    titles = set()
    all_stories: List[StoryInfo] = []
    for line in all_lines:
        fields = re.findall('"([^"]*)"', line)

        title = fields[0]
        if title in titles:
            raise Exception(f'ERROR: Duplicate title in file "{STORY_INDEX_FILE}": "{title}".')
        titles.add(title)
        issue_name = fields[1]
        issue_number = fields[2]
        issue_date = fields[3]
        issue_month, issue_year = get_issue_month_year(issue_date)
        issue_month = LONG_MONTHS[issue_month]

        all_stories.append(StoryInfo(title, issue_name, issue_number, issue_month, issue_year))

    return all_stories
