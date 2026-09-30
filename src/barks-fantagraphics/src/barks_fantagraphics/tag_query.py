"""What the tag search box finds, and tags picked to combine: ALL or ANY, some left out.

Kivy-free. `TagMatch` is a tag or tag group a typed text matches, with its story
count. `TagSelection` is tags picked together (the search plan's phase 10,
docs/plans/advanced-search.md in the reader): the stories every included tag
tags (ALL) or any of them does (ANY), less those an excluded tag tags. The stories
are found by ``BarksTitleSearch.get_titles_for_selection``.

A selection can be typed too, `parse_tag_query`: tag names separated by ``+`` or
``,`` (ALL) or ``|`` (ANY), a name after a leading ``-`` left out, and anywhere a
``year:`` or ``vol:`` range the stories must be in::

    scrooge + gyro -christmas stories year:1950-55

A ``-`` is an exclusion only at a name's start, so ``indo-china`` stays one name.
Nothing here says whether a name is a tag; the search facade does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .search_query import Combine, read_range

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
    years: tuple[int, int] | None = None
    volumes: tuple[int, int] | None = None

    def describe(self) -> str:
        """Return the selection as it would be typed: ``Scrooge + Gyro -Christmas year:1950-55``."""
        separator = " + " if self.combine is Combine.ALL else " | "
        parts = [separator.join(self.included), *(f"-{name}" for name in self.excluded)]
        if self.years is not None:
            parts.append(f"year:{range_text(self.years, years=True)}")
        if self.volumes is not None:
            parts.append(f"vol:{range_text(self.volumes, years=False)}")
        return " ".join(part for part in parts if part)


def range_text(first_last: tuple[int, int], *, years: bool) -> str:
    """Return a range as typed: ``1951``, ``1950-55`` (years), ``7``, ``5-8`` (volumes)."""
    first, last = first_last
    if first == last:
        return str(first)
    same_century = years and first // 100 == last // 100
    return f"{first}-{last % 100:02d}" if same_century else f"{first}-{last}"


@dataclass(frozen=True, slots=True)
class ParsedTagQuery:
    """A typed tag selection, or why it is not one."""

    selection: TagSelection | None = None
    error: str | None = None


_TAG_OPERATOR_RE = re.compile(r"\s*([+,|])\s*")
_EXCLUSION_RE = re.compile(r"(?:^|\s)-\s*\S")
_QUALIFIER_RE = re.compile(r"(?:^|(?<=\s))(year|vol):(\S*)", re.IGNORECASE)


def has_tag_syntax(text: str) -> bool:
    """Return whether `text` combines tags: ``+ , |``, a leading ``-``, ``year:`` or ``vol:``."""
    return (
        bool(set(text) & {"+", ",", "|"})
        or bool(_EXCLUSION_RE.search(text))
        or bool(_QUALIFIER_RE.search(text))
    )


def _read_qualifiers(text: str) -> dict[str, tuple[int, int]] | str:
    """Return the ``year:`` and ``vol:`` ranges in `text`, by key; or why one is wrong."""
    ranges: dict[str, tuple[int, int]] = {}
    for match in _QUALIFIER_RE.finditer(text):
        key = match.group(1).lower()
        if key in ranges:
            return f"{key}: is given twice."
        try:
            ranges[key] = read_range(match.group(2), years=key == "year")
        except ValueError as exc:
            return f"{key}: {exc}."
    return ranges


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
    ranges = _read_qualifiers(text)
    if isinstance(ranges, str):
        return ParsedTagQuery(error=ranges)
    text = _QUALIFIER_RE.sub(" ", text)
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
        tuple(dict.fromkeys(included)),
        tuple(dict.fromkeys(excluded)),
        combine,
        years=ranges.get("year"),
        volumes=ranges.get("vol"),
    )
    return ParsedTagQuery(selection=selection)
