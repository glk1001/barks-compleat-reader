from dataclasses import dataclass
from typing import Dict, List, Tuple

LONG_MONTHS = {
    "<none>",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
}


@dataclass
class SubmittedInfo:
    title: str
    submitted_year: str
    submitted_month: str
    submitted_day: str


SubmittedInfoDict = Dict[Tuple[str, str], List[SubmittedInfo]]


def get_month_day(month_and_day: str) -> Tuple[str, str]:
    month_day = month_and_day.split(" ")
    if len(month_day) < 1 or len(month_day) > 2:
        raise Exception(f"Bad month_day '{month_day}'.")

    issue_month = month_day[0]
    if len(month_day) == 1:
        return issue_month, "<none>"

    issue_day = month_day[1]

    return issue_month, issue_day


def get_all_submitted_info(issue_filename: str, issue_name: str) -> SubmittedInfoDict:
    all_lines = []
    with open(issue_filename, "r") as f:
        while True:
            line1 = f.readline().strip()
            if not line1:
                break
            line2 = f.readline().strip()
            if not line2:
                break
            if not line1.startswith(issue_name):
                raise Exception(f"Wrong '{issue_name}' start: {line1}")
            if not line2.startswith("Submission:"):
                raise Exception(f"Wrong submission start: {line1}")

            all_lines.append((line1, line2))

    all_submitted_info: SubmittedInfoDict = {}

    def add_info(key: Tuple[str, str], info: SubmittedInfo):
        if key not in all_submitted_info:
            all_submitted_info[key] = [info]
        else:
            all_submitted_info[key].append(info)

    for line in all_lines:
        # print(line[1])

        issue_number = line[0][len(issue_name) + 1 :].split("-")[0].strip()
        title = line[0][len(issue_name) + 1 :].split("-")[1].strip()[2:].strip()

        sub_year = line[1][12:].split(",")[0].strip()
        sub_month_day = line[1][12:].split(",")[1].strip()

        if sub_month_day == "<none>":
            sub_month = "<none>"
            sub_day = "<none>"
        else:
            sub_month, sub_day = get_month_day(sub_month_day)

        if sub_month not in LONG_MONTHS:
            raise Exception(f"Bad month: '{line[1]}'.")

        add_info((issue_name, issue_number), SubmittedInfo(title, sub_year, sub_month, sub_day))

    return all_submitted_info
