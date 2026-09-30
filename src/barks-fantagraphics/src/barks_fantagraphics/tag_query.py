"""What the tag search box finds, and tags picked to combine: ALL or ANY, some left out.

Kivy-free. `TagMatch` is a tag or tag group a typed text matches, with its story
count. `TagSelection` is tags picked together (the search plan's phase 10,
docs/plans/advanced-search.md in the reader): the stories every included tag
tags (ALL) or any of them does (ANY), less those an excluded tag tags. The stories
are found by ``BarksTitleSearch.get_titles_for_selection``.

A selection can be typed too, `parse_tag_query`: tag names separated by ``+`` or
``,`` (ALL) or ``|`` (ANY), a name after a leading ``-`` left out::

    scrooge + gyro -christmas stories

A ``-`` is an exclusion only at a name's start, so ``indo-china`` stays one name.
Nothing here says whether a name is a tag; the search facade does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .search_query import Combine

if TYPE_CHECKING:
    from .barks_tags import TagGroups, Tags


@dataclass(frozen=True, slots=True)
class TagMatch:
    """A tag or tag group a typed text matched.

    Attributes:
        item: The tag or tag group.
        label: Its display name, the chip's text (and one of its aliases, lower-cased).
        title_count: How many stories it tags; a group's, every story its members tag.
        exact: Whether the text was one of its aliases, whole.

    """

    item: Tags | TagGroups
    label: str
    title_count: int
    exact: bool = False


@dataclass(frozen=True, slots=True)
class TagSelection:
    """Tags picked together, by name (a tag's or group's display name, or an alias).

    Attributes:
        included: The tags whose stories are listed: all of them (ALL) or any (ANY).
        excluded: The tags whose stories are left out, whatever `combine` is.
        combine: How the included tags combine.

    """

    included: tuple[str, ...] = ()
    excluded: tuple[str, ...] = ()
    combine: Combine = Combine.ALL

    def describe(self) -> str:
        """Return the selection as it would be typed: ``Scrooge + Gyro -Christmas``."""
        separator = " + " if self.combine is Combine.ALL else " | "
        parts = [separator.join(self.included), *(f"-{name}" for name in self.excluded)]
        return " ".join(part for part in parts if part)


@dataclass(frozen=True, slots=True)
class ParsedTagQuery:
    """A typed tag selection, or why it is not one."""

    selection: TagSelection | None = None
    error: str | None = None


_TAG_OPERATOR_RE = re.compile(r"\s*([+,|])\s*")
_EXCLUSION_RE = re.compile(r"(?:^|\s)-\s*\S")


def has_tag_syntax(text: str) -> bool:
    """Return whether `text` combines tags (``+ , |``, or a name after a leading ``-``)."""
    return bool(set(text) & {"+", ",", "|"}) or bool(_EXCLUSION_RE.search(text))


def parse_tag_query(text: str) -> ParsedTagQuery:
    """Read a typed tag selection. Never raises: bad text comes back as the `error`.

    Names are separated by ``+`` or ``,`` (every one: ALL) or ``|`` (any: ANY), not
    both kinds; within a part, a name after ``-`` is left out, and the part may name
    more after a space-separated ``-`` (``scrooge -gyro``).

    Args:
        text: What was typed.

    Returns:
        The selection, by the names typed (lower-cased, spaces tidied); or why not.

    """
    if not text.strip():
        return ParsedTagQuery(error="No tag is named.")
    pieces = _TAG_OPERATOR_RE.split(text.strip())
    names, operators = pieces[0::2], set(pieces[1::2])
    if {"|"} & operators and {"+", ","} & operators:
        return ParsedTagQuery(error="Use + or | between tags, not both.")
    included: list[str] = []
    excluded: list[str] = []
    for piece in names:
        head, *left_out = re.split(r"(?:^|\s)-", piece)
        if not head.strip() and not left_out:
            return ParsedTagQuery(error="A tag name is missing next to + , or |.")
        for name, into in ((head, included), *((n, excluded) for n in left_out)):
            tidy = " ".join(name.split()).lower()
            if tidy:
                into.append(tidy)
            elif into is excluded:
                return ParsedTagQuery(error="A tag name is missing after -.")
    combine = Combine.ANY if "|" in operators else Combine.ALL
    selection = TagSelection(
        tuple(dict.fromkeys(included)), tuple(dict.fromkeys(excluded)), combine
    )
    return ParsedTagQuery(selection=selection)
