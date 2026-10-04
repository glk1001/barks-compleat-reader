"""The search screen's syntax help: a few things to type, each with what it does.

An empty results panel shows its box's help while the box is empty, and the first
keystroke hides it. The unit tests run every example through the search's own
parsers and title search, so the help cannot drift from what they do.
"""

from __future__ import annotations

from typing import Final

from barks_fantagraphics.search_query import NEAR_DEFAULT_DISTANCE

type HelpExamples = tuple[tuple[str, str], ...]

TITLE_HELP_HEADING: Final = "Type words from a title, or an issue:"
TITLE_HELP: Final[HelpExamples] = (
    ("golden helmet", "its start, The or not"),
    ("gold fleece", "words, any order"),
    ("CS 104", "an issue and cover"),
    ("CS 10", "CS 10 and 100-109"),
    ("Four Color 223", "an issue by name"),
    ("covers", "every cover"),
)

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
