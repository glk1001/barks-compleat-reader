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

import textwrap
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import TYPE_CHECKING

from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO
from barks_fantagraphics.search_filters import SearchFilter
from barks_fantagraphics.search_query import Combine
from barks_fantagraphics.speech_speakers import CHARACTER_SPEAKER_OPTIONS, NARRATOR
from barks_fantagraphics.tag_query import TagSelection, range_text

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable, Sequence

    from barks_fantagraphics.barks_titles import Titles

# The ALL/ANY chip's value in a picked row: never a word or a tag.
BASKET_MODE_VALUE = ""


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
        self.combine = self.combine.flipped()
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

    def chip_options(self) -> list[tuple[str, str]]:
        """Return the picked-words row's chips: ALL/ANY, then each word with its x."""
        options = [(w, f"{w}  \u00d7") for w in self.words]
        if options:
            options.insert(0, (BASKET_MODE_VALUE, self.combine.upper()))
        return options


# The picked-tags row's chips for a typed years or volumes range: never a tag's name.
YEARS_KEY, VOLUMES_KEY = "year:", "vol:"


class TagState(StrEnum):
    """Whether a picked tag's stories are listed or left out."""

    INCLUDED = auto()
    EXCLUDED = auto()


@dataclass
class TagBasket:
    """The tags picked, in the order picked, each included or left out, and ALL or ANY.

    A typed selection may also bring a range of submitted years and of Fantagraphics
    volumes (``year:1950-55``, ``vol:7``), each a chip of its own in the picked row.
    """

    tags: dict[str, TagState] = field(default_factory=dict)
    combine: Combine = Combine.ALL
    years: tuple[int, int] | None = None
    volumes: tuple[int, int] | None = None

    def __contains__(self, tag: object) -> bool:
        """Return whether `tag` is picked, either way."""
        return tag in self.tags

    def __len__(self) -> int:
        """Return how many chips are picked: the tags, and a years or volumes range."""
        return len(self.tags) + (self.years is not None) + (self.volumes is not None)

    def drop_range(self, key: str) -> None:
        """Take the years (``"year:"``) or volumes (``"vol:"``) range out."""
        if key == YEARS_KEY:
            self.years = None
        elif key == VOLUMES_KEY:
            self.volumes = None

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
        self.combine = self.combine.flipped()
        return self.combine

    def clear(self) -> None:
        """Put every tag back; the next tag picked starts an ALL basket."""
        self.tags.clear()
        self.combine = Combine.ALL
        self.years = self.volumes = None

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
        self.years, self.volumes = selection.years, selection.volumes

    def selection(self) -> TagSelection:
        """Return the basket as a selection of tag names."""
        return TagSelection(
            included=tuple(t for t, s in self.tags.items() if s is TagState.INCLUDED),
            excluded=tuple(t for t, s in self.tags.items() if s is TagState.EXCLUDED),
            combine=self.combine,
            years=self.years,
            volumes=self.volumes,
        )

    def chip_options(self) -> list[tuple[str, str]]:
        """Return the picked-tags row's chips: ALL/ANY, each tag ("not" one left out), a range."""
        options = [
            (tag, tag if state is TagState.INCLUDED else f"not {tag}")
            for tag, state in self.tags.items()
        ]
        if self.years is not None:
            options.append((YEARS_KEY, f"years {range_text(self.years, years=True)}"))
        if self.volumes is not None:
            vols = range_text(self.volumes, years=False)
            options.append((VOLUMES_KEY, f"vol {vols}" if "-" not in vols else f"vols {vols}"))
        if options:
            options.insert(0, (BASKET_MODE_VALUE, self.combine.upper()))
        return options


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
        """Return a range's chip label, as it would be typed: ``"1951-54"``."""
        return range_text(years, years=True)

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

    def in_era(self, titles: Iterable[Titles]) -> list[Titles]:
        """Return the stories of `titles` submitted in the era, in the same order."""
        return [t for t in titles if self.allows(BARKS_TITLE_INFO[t].submitted_year)]

    def search_filter(self) -> SearchFilter | None:
        """Return the word search's story filter for the era, or None for all years."""
        return None if self.years is None else SearchFilter(years=self.years)


# The speaker value for anyone: no filter.
ALL_SPEAKERS = ""


def offered_speakers(indexed: Collection[str]) -> list[str]:
    """Return the speakers the filter offers: the roster's that the index has, in roster order.

    The roster's named characters and the narrator; ``other:`` speakers are a long tail
    and are not offered. An index without speakers offers none.
    """
    return [s for s in (*CHARACTER_SPEAKER_OPTIONS, NARRATOR) if s in indexed]


def speaker_story_counts(
    count_for: Callable[[str | None], int], offered: Sequence[str], picked: str
) -> list[tuple[str, int]]:
    """Return anyone's stories, then each speaker's who says what was searched, most first.

    Args:
        count_for: Counts the stories the search finds under a speaker (None: anyone).
        offered: The speakers offered, in roster order, which ties keep.
        picked: The speaker picked now, listed even at none so the filter can be lifted.

    Returns:
        ``(speaker, count)`` pairs: `ALL_SPEAKERS` first, then the rest by count.

    """
    total = count_for(None)
    counts = [(s, count_for(s)) for s in offered]
    listed = [(s, n) for s, n in counts if n or s == picked]
    listed.sort(key=lambda speaker_count: -speaker_count[1])  # stable: roster order on ties
    return [(ALL_SPEAKERS, total), *listed]


# The tag scope row's chips: the word search everywhere, or only in the tags' stories.
EVERYWHERE, ONLY_IN_TAGS = "", "tags"
MAX_SCOPE_LABEL = 40


@dataclass
class TagScope:
    """The tags the tag search has selected, which the word search may list only within.

    Attributes:
        tags: The selection as typed or described, named on the chip; "" for none.
        titles: The selected tags' stories.

    """

    tags: str = ""
    titles: frozenset[str] = frozenset()

    def clear(self) -> None:
        """Forget the selection: no scope to offer."""
        self.tags, self.titles = "", frozenset()

    def count_in(self, titles: Iterable[str]) -> int:
        """Return how many of `titles` the scope holds."""
        return sum(1 for title in titles if title in self.titles)

    @staticmethod
    def narrows(in_tags: int, everywhere: int) -> bool:
        """Return whether the scope would narrow a list: it holds some of it, not all."""
        return 0 < in_tags < everywhere

    def label(self) -> str:
        """Return the scope chip's text, "Only in: <tags>", cut to fit its row."""
        return textwrap.shorten(f"Only in: {self.tags}", MAX_SCOPE_LABEL, placeholder="\u2026")

    def options(self) -> list[tuple[str, str]]:
        """Return the scope row's two chips: everywhere, and only in the tags' stories."""
        return [(EVERYWHERE, "Everywhere"), (ONLY_IN_TAGS, self.label())]

    def search_filter(self, era: EraChoice, *, in_force: bool) -> SearchFilter | None:
        """Return the word search's story filter: the era's years, and the scope's stories in force.

        Returns:
            The filter, or None when neither narrows the search.

        """
        tag_titles = self.titles if in_force else None
        if era.years is None and tag_titles is None:
            return None
        return SearchFilter(years=era.years, tag_titles=tag_titles)
