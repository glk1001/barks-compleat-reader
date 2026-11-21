"""Where the keyboard is on the search screen.

Kivy-free. The screen's key handlers, and the classes that take over a part of the
screen (the speaker filter, in time a pane each for the tags and the words), read and
move one `SearchFocus` between them, in place of a handful of fields on the screen.

The areas, and the parts of a row, are `StrEnum`s whose values are the words the
screen has always used for them, so a log line that names one reads as it did.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, auto


class FocusArea(StrEnum):
    """A part of the search screen the keyboard can be on."""

    INPUT = auto()  # the search box
    CLEAR = auto()  # the x beside the box
    TAGS = auto()  # the tag list, or the word list (both are lists of chips or rows)
    BASKET = auto()  # the row of picked words or tags, under the box
    SPEAKERS = auto()  # the word results' Said by chip
    SAID_BY_LIST = auto()  # the list that chip opens
    SCOPE = auto()  # the word results' tag scope row
    ERA = auto()  # the results' era row
    RESULTS = auto()  # the stories listed


class ListPart(StrEnum):
    """The part of a word or tag row the keyboard is on."""

    ITEM = "word"  # the word or the tag itself
    PLUS = auto()  # its + button


class RowPart(StrEnum):
    """The part of a word search's story row the keyboard is on."""

    TITLE = auto()  # the story, which opens it
    SPEECH = auto()  # its speech-bubble button


@dataclass
class SearchFocus:
    """Where the keyboard is: whether it is on the screen at all, and on what.

    Attributes:
        active: Whether the screen has the keys (the remote's focus is on it).
        area: The part of the screen they are on.
        chip_index: The chip or row focused in the tag or word list.
        result_index: The story focused in the results.
        list_part: The part of that chip's row.
        row_part: The part of that story's row (a word search's rows have two).

    """

    active: bool = False
    area: FocusArea = FocusArea.INPUT
    chip_index: int = 0
    result_index: int = 0
    list_part: ListPart = ListPart.ITEM
    row_part: RowPart = RowPart.TITLE
