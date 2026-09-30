"""What the search screen holds between keystrokes: words and tags picked, and an era.

Kivy-free (docs/plans/advanced-search.md, phases 9 to 11). The word search's basket
is the words picked from the word list, combined ALL (every one in the same story) or
ANY. It runs as a typed query whose words are quoted, so each is found exactly as
picked and a term of several words is a phrase: the same tree `query_from_words`
builds, through the same evaluator as anything typed.

The tag search's basket is the tags picked, each included or left out: its stories
are those every included tag tags (ALL) or any does (ANY), less the left-out tags'.

The era is one range of submitted years, or all of them, that both searches list
stories from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, auto

from barks_fantagraphics.search_filters import SearchFilter
from barks_fantagraphics.search_query import Combine
from barks_fantagraphics.tag_query import TagSelection


@dataclass
class WordBasket:
    """The words picked to search together, in the order picked, and how they combine."""

    words: list[str] = field(default_factory=list)
    combine: Combine = Combine.ALL

    def __contains__(self, word: object) -> bool:
        """Return whether `word` is picked."""
        return word in self.words

    def __len__(self) -> int:
        """Return how many words are picked."""
        return len(self.words)

    def toggle(self, word: str) -> bool:
        """Pick `word`, or put it back if it is picked already.

        Args:
            word: A word from the word list.

        Returns:
            Whether the word is picked now.

        """
        if word in self.words:
            self.words.remove(word)
            return False
        self.words.append(word)
        return True

    def remove(self, word: str) -> None:
        """Put `word` back, if it is picked."""
        if word in self.words:
            self.words.remove(word)

    def flip(self) -> Combine:
        """Switch between ALL and ANY, and return the new choice."""
        self.combine = Combine.ANY if self.combine is Combine.ALL else Combine.ALL
        return self.combine

    def clear(self) -> None:
        """Put every word back; the next word picked starts an ALL basket."""
        self.words.clear()
        self.combine = Combine.ALL

    def query_text(self) -> str:
        """Return the basket as a query: each word quoted, joined by a space (ALL) or ``|``.

        Returns:
            The query, or "" for an empty basket.

        """
        separator = " " if self.combine is Combine.ALL else " | "
        return separator.join(f'"{word}"' for word in self.words)


class TagState(StrEnum):
    """Whether a picked tag's stories are listed or left out."""

    INCLUDED = auto()
    EXCLUDED = auto()


@dataclass
class TagBasket:
    """The tags picked, in the order picked, each included or left out, and ALL or ANY."""

    tags: dict[str, TagState] = field(default_factory=dict)
    combine: Combine = Combine.ALL

    def __contains__(self, tag: object) -> bool:
        """Return whether `tag` is picked, either way."""
        return tag in self.tags

    def __len__(self) -> int:
        """Return how many tags are picked."""
        return len(self.tags)

    def toggle(self, tag: str) -> bool:
        """Pick `tag` to include, or put it back if it is picked either way.

        Returns:
            Whether the tag is picked now.

        """
        if tag in self.tags:
            del self.tags[tag]
            return False
        self.tags[tag] = TagState.INCLUDED
        return True

    def cycle(self, tag: str) -> TagState | None:
        """Step a picked tag on: included, then left out, then put back.

        Returns:
            The tag's state now, or None once it is put back (or was not picked).

        """
        match self.tags.get(tag):
            case TagState.INCLUDED:
                self.tags[tag] = TagState.EXCLUDED
                return TagState.EXCLUDED
            case TagState.EXCLUDED:
                del self.tags[tag]
        return None

    def flip(self) -> Combine:
        """Switch between ALL and ANY, and return the new choice."""
        self.combine = Combine.ANY if self.combine is Combine.ALL else Combine.ALL
        return self.combine

    def clear(self) -> None:
        """Put every tag back; the next tag picked starts an ALL basket."""
        self.tags.clear()
        self.combine = Combine.ALL

    def fill(self, selection: TagSelection, labels: dict[str, str] | None = None) -> None:
        """Replace the basket with a (typed) selection.

        Args:
            selection: The tags, included and left out, and how they combine.
            labels: The chip label to keep for a name, where it has one (the tag's
                display name for a lower-case alias typed).

        """
        names = labels or {}
        self.tags = {names.get(t, t): TagState.INCLUDED for t in selection.included}
        self.tags |= {names.get(t, t): TagState.EXCLUDED for t in selection.excluded}
        self.combine = selection.combine

    def selection(self) -> TagSelection:
        """Return the basket as a selection of tag names."""
        return TagSelection(
            included=tuple(t for t, s in self.tags.items() if s is TagState.INCLUDED),
            excluded=tuple(t for t, s in self.tags.items() if s is TagState.EXCLUDED),
            combine=self.combine,
        )


# The era chip that lifts the filter.
ALL_YEARS = ""


@dataclass
class EraChoice:
    """Which range of submitted years the searches list stories from; none picked, all.

    Attributes:
        ranges: The ranges offered, first and last year each, both included.
        years: The range picked, or None for all years.

    """

    ranges: tuple[tuple[int, int], ...]
    years: tuple[int, int] | None = None

    @staticmethod
    def value_of(years: tuple[int, int]) -> str:
        """Return a range's chip value: ``"1951-1954"``."""
        return f"{years[0]}-{years[1]}"

    @staticmethod
    def label_of(years: tuple[int, int]) -> str:
        """Return a range's chip label: ``"1951-54"``."""
        return f"{years[0]}-{years[1] % 100:02d}"

    @property
    def value(self) -> str:
        """The picked range's chip value, or `ALL_YEARS`."""
        return ALL_YEARS if self.years is None else self.value_of(self.years)

    @property
    def label(self) -> str:
        """The picked range's chip label, or "All years"."""
        return "All years" if self.years is None else self.label_of(self.years)

    def options(self) -> list[tuple[str, str]]:
        """Return the chips as ``(value, label)``: all years, then each range."""
        return [
            (ALL_YEARS, "All years"),
            *((self.value_of(r), self.label_of(r)) for r in self.ranges),
        ]

    def select(self, value: str) -> None:
        """Pick the range with chip value `value`; `ALL_YEARS`, or one not offered, lifts it."""
        self.years = next((r for r in self.ranges if self.value_of(r) == value), None)

    def allows(self, year: int) -> bool:
        """Return whether a story submitted in `year` is listed."""
        return self.years is None or self.years[0] <= year <= self.years[1]

    def search_filter(self) -> SearchFilter | None:
        """Return the word search's story filter for the era, or None for all years."""
        return None if self.years is None else SearchFilter(years=self.years)
