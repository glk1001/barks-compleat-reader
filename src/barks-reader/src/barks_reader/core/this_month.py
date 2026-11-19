"""The stories tied to one calendar month, across all of Barks's working years.

A story has two dates: the day Barks submitted it and the month on its issue's cover.
'<Month> in Barks' lists the stories by each: what he was drawing at this time of
year, and what a reader was buying. Covers and articles are not stories and are left
out, as on 'By the Numbers'.
"""

from __future__ import annotations

import calendar
from enum import StrEnum
from typing import TYPE_CHECKING

from .corpus_stats import get_stories

if TYPE_CHECKING:
    from datetime import date

    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.comic_book_info import ComicBookInfo


class MonthDate(StrEnum):
    """Which of a story's two dates puts it in a month."""

    SUBMITTED = "submitted"
    ON_SALE = "on_sale"


def get_month_node_text(month: int) -> str:
    """Return the name of a month's node, e.g. 'November in Barks'.

    Args:
        month: The calendar month, 1 to 12.

    Returns:
        The node's text.

    """
    return f"{calendar.month_name[month]} in Barks"


def get_month_group_heading(dated_by: MonthDate, month: int) -> str:
    """Return the heading of one of a month node's two groups.

    Args:
        dated_by: Which date the group goes by.
        month: The calendar month, 1 to 12.

    Returns:
        'Submitted in November' or 'On sale in November'.

    """
    lead = "Submitted in" if dated_by is MonthDate.SUBMITTED else "On sale in"
    return f"{lead} {calendar.month_name[month]}"


def get_stories_in_month(dated_by: MonthDate, month: int) -> list[ComicBookInfo]:
    """Return the stories one of their dates puts in a month, the earliest year first.

    Args:
        dated_by: Which date to go by.
        month: The calendar month, 1 to 12.

    Returns:
        The stories submitted in that month in the order Barks submitted them, or
        those whose issue carries that month, by issue year and then as submitted.

    """
    stories = get_stories()  # in the order submitted
    if dated_by is MonthDate.SUBMITTED:
        return [info for info in stories if info.submitted_month == month]
    return sorted(
        (info for info in stories if info.issue_month == month), key=lambda info: info.issue_year
    )


def get_titles_in_month(month: int) -> list[Titles]:
    """Return every story either date puts in a month, each once, in the order submitted.

    Args:
        month: The calendar month, 1 to 12.

    Returns:
        The titles the month's top view draws its picture from.

    """
    return [
        info.title for info in get_stories() if month in (info.submitted_month, info.issue_month)
    ]


def get_submitted_on_this_day_text(info: ComicBookInfo, today: date) -> str:
    """Return the line saying a story was submitted on today's date, or nothing.

    Args:
        info: The story.
        today: Today's date.

    Returns:
        'Submitted 79 years ago today: Lost in the Andes!', or "" when the story was
        submitted on some other day of the year.

    """
    if (info.submitted_month, info.submitted_day) != (today.month, today.day):
        return ""
    years = today.year - info.submitted_year
    return f"Submitted {years} years ago today: {info.get_display_title()}"
