"""The search screen's syntax help: a few things to type, each with what it does.

An empty results panel shows its box's help while the box is empty, and the first
keystroke hides it. The unit tests run every example through the search's own
parsers, so the help cannot drift from the syntax.
"""

from __future__ import annotations

from typing import Final

from barks_fantagraphics.search_query import NEAR_DEFAULT_DISTANCE

type HelpExamples = tuple[tuple[str, str], ...]

WORD_HELP_HEADING: Final = "Type a word, or combine them:"
WORD_HELP: Final[HelpExamples] = (
    ("gold mine", "both, in one story"),
    ("gold OR silver", "either"),
    ("gold -duck", "without duck"),
    ('"pirate gold"', "exact phrase"),
    ("gold NEAR mine", f"within {NEAR_DEFAULT_DISTANCE} words"),
    ("gold*", "any ending"),
    ("gold year:1950-55", "only 1950-55"),
    ("gold vol:7-9", "only volumes 7-9"),
    ("gold tag:gyro", "only its stories"),
)

TAG_HELP_HEADING: Final = "Type a tag, or combine them:"
TAG_HELP: Final[HelpExamples] = (
    ("scrooge + gyro", "both"),
    ("scrooge | gyro", "either"),
    ("scrooge -magica", "without magica"),
    ("gyro year:1950-55", "only 1950-55"),
    ("gyro vol:7-9", "only volumes 7-9"),
)
