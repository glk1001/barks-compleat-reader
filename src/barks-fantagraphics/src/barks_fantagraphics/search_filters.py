"""Which stories a word search may find: by tag, by submitted year, by Fantagraphics volume.

A typed query's ``tag:``, ``year:`` and ``vol:`` qualifiers (``search_query``), and the
filters the search screen sets (an era, "only in tagged stories"), become story
filters here. The query evaluator (``search_evaluate``) keeps the stories a filter
allows, drops the ones a negated filter allows, and - when a filter can say which
stories it allows - searches only those. Kivy-free and Whoosh-free.

Stories are named as the index names them (``ENUM_TO_STR_TITLE``); one the title
tables do not know has no year and no tags, so a year or tag filter never allows it.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Protocol

from .barks_tags import BARKS_TAG_ALIASES, BARKS_TAG_GROUPS_ALIASES
from .barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM
from .comic_book_info import BARKS_TITLE_INFO
from .title_search import BarksTitleSearch

if TYPE_CHECKING:
    from .search_results import TitleDict

# The most tags a notice names for a tag that does not exist.
MAX_CLOSEST_TAGS = 3


class StoryFilter(Protocol):
    """Which stories a search may find."""

    @property
    def candidates(self) -> frozenset[str] | None:
        """Every story the filter can allow (perhaps more), or None when it cannot say."""
        ...

    def allows(self, title: str, fanta_vol: int) -> bool:
        """Return whether the story `title`, in volume `fanta_vol`, may be found."""
        ...


@dataclass(frozen=True, slots=True)
class SearchFilter:
    """Stories in a range of submitted years, a range of volumes and a set of stories.

    Each part left as None allows every story; the parts given must all allow it.

    Attributes:
        years: The first and last submitted year, both included.
        volumes: The first and last Fantagraphics volume, both included.
        tag_titles: The stories allowed (those a tag selection tags).

    """

    years: tuple[int, int] | None = None
    volumes: tuple[int, int] | None = None
    tag_titles: frozenset[str] | None = None

    @property
    def is_empty(self) -> bool:
        """Whether the filter allows every story."""
        return self.years is None and self.volumes is None and self.tag_titles is None

    @property
    def candidates(self) -> frozenset[str] | None:
        """The stories the years and tags allow, or None when neither is set."""
        year_titles = None if self.years is None else titles_in_years(*self.years)
        return _intersect_known([year_titles, self.tag_titles])

    def allows(self, title: str, fanta_vol: int) -> bool:
        """Return whether the story `title`, in volume `fanta_vol`, may be found."""
        if self.tag_titles is not None and title not in self.tag_titles:
            return False
        if self.volumes is not None and not self.volumes[0] <= fanta_vol <= self.volumes[1]:
            return False
        if self.years is None:
            return True
        year = submitted_year(title)
        return year is not None and self.years[0] <= year <= self.years[1]


@dataclass(frozen=True, slots=True)
class NotFilter:
    """The stories `part` does not allow."""

    part: StoryFilter

    @property
    def candidates(self) -> frozenset[str] | None:
        """None: the complement of a story set is not a set this module can list."""
        return None

    def allows(self, title: str, fanta_vol: int) -> bool:
        """Return whether `part` refuses the story."""
        return not self.part.allows(title, fanta_vol)


@dataclass(frozen=True, slots=True)
class AllFilters:
    """The stories every part allows."""

    parts: tuple[StoryFilter, ...]

    @property
    def candidates(self) -> frozenset[str] | None:
        """The stories every part that can list its stories lists."""
        return _intersect_known([p.candidates for p in self.parts])

    def allows(self, title: str, fanta_vol: int) -> bool:
        """Return whether every part allows the story."""
        return all(p.allows(title, fanta_vol) for p in self.parts)


@dataclass(frozen=True, slots=True)
class AnyFilter:
    """The stories any part allows."""

    parts: tuple[StoryFilter, ...]

    @property
    def candidates(self) -> frozenset[str] | None:
        """Every part's stories, or None when any part cannot list its own."""
        listed = [p.candidates for p in self.parts]
        if any(c is None for c in listed):
            return None
        return frozenset[str]().union(*(c for c in listed if c is not None))

    def allows(self, title: str, fanta_vol: int) -> bool:
        """Return whether any part allows the story."""
        return any(p.allows(title, fanta_vol) for p in self.parts)


def _intersect_known(sets: list[frozenset[str] | None]) -> frozenset[str] | None:
    known = [s for s in sets if s is not None]
    return known[0].intersection(*known[1:]) if known else None


def apply_filter(story_filter: StoryFilter, title_dict: TitleDict) -> TitleDict:
    """Return the stories of `title_dict` the filter allows, in the same order.

    Args:
        story_filter: Which stories to keep.
        title_dict: A search result.

    Returns:
        A new result holding the allowed stories.

    """
    return {t: info for t, info in title_dict.items() if story_filter.allows(t, info.fanta_vol)}


def submitted_year(title: str) -> int | None:
    """Return the year the story `title` was submitted, or None for a story not listed."""
    enum = STR_TITLE_TO_ENUM.get(title)
    return None if enum is None else BARKS_TITLE_INFO[enum].submitted_year


@cache
def titles_in_years(first: int, last: int) -> frozenset[str]:
    """Return every story submitted from `first` to `last`, both included."""
    return frozenset(
        ENUM_TO_STR_TITLE[info.title]
        for info in BARKS_TITLE_INFO
        if first <= info.submitted_year <= last
    )


def tag_titles(name: str) -> frozenset[str] | None:
    """Return the stories a tag or tag group tags, or None when no tag has that name.

    Args:
        name: One of the tag's or group's aliases, in any case.

    Returns:
        The stories, as the index names them; a group's, every story its members tag.

    """
    item, titles = BarksTitleSearch.get_titles_from_alias_tag(name.strip().lower())
    return None if item is None else frozenset(ENUM_TO_STR_TITLE[t] for t in titles)


def closest_tags(name: str, limit: int = MAX_CLOSEST_TAGS) -> list[str]:
    """Return the names of the tags nearest to one that does not exist, best first.

    The tags whose names hold the text first (as the tag search box finds them),
    then close spellings.

    Args:
        name: The name typed.
        limit: The most names to return.

    Returns:
        Tag and tag group aliases.

    """
    lower = name.strip().lower()
    found = [m.label for m in BarksTitleSearch.get_tags_matching(lower)]
    aliases = [*BARKS_TAG_ALIASES, *BARKS_TAG_GROUPS_ALIASES]
    found += difflib.get_close_matches(lower, aliases, n=limit)
    return list(dict.fromkeys(found))[:limit]


def unknown_tag_notice(name: str) -> str:
    """Return what to tell the user of a tag name that is no tag's: the closest ones.

    Args:
        name: The name typed.

    Returns:
        ``No tag is called "x".``, and the closest tags, if any.

    """
    closest = closest_tags(name)
    notice = f'No tag is called "{name}".'
    if closest:
        notice += " Closest: " + ", ".join(closest) + "."
    return notice
