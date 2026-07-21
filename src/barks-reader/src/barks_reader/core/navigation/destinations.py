"""Destination descriptors — the Kivy-free navigation domain.

A `Destination` identifies a navigable item in the reader. Tree-view nodes hold a
destination; the `NavigationModel` consumes them to answer policy questions
(view state, auto-select, tag context) without knowing about widgets.

Subclasses fall into two groups:

1. Payload-bearing destinations (`TitleDestination`, `YearRangeDestination`,
   `TagDestination`, ...): frozen dataclasses carrying the minimum domain data
   needed to reconstruct navigation decisions.
2. No-payload singletons (`IntroDestination`, `StoriesDestination`, ...): one
   class per kind so pattern matching in `NavigationModel.view_state_for` reads
   cleanly without enum tag dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from barks_fantagraphics.barks_tags import TagGroups, Tags
    from barks_fantagraphics.barks_titles import Titles
    from barks_fantagraphics.fanta_comics_info import FantaComicBookInfo

    from .view_states import ViewStates


@dataclass(frozen=True, slots=True)
class Destination:
    """Base class for every navigable item. Subclasses are the concrete kinds."""


# --- Root / container destinations (no payload) -------------------------


@dataclass(frozen=True, slots=True)
class IntroDestination(Destination):
    """The 'Introduction' parent node at the tree root."""


@dataclass(frozen=True, slots=True)
class IntroDocDestination(Destination):
    """The 'The Compleat Barks Reader' intro document (opens the document reader)."""


@dataclass(frozen=True, slots=True)
class StoriesDestination(Destination):
    """The 'The Stories' parent node."""


@dataclass(frozen=True, slots=True)
class ChronologicalDestination(Destination):
    """The 'Chronological' container under Stories."""


@dataclass(frozen=True, slots=True)
class AllSeriesDestination(Destination):
    """The 'Series' container under Stories (parent of every individual series)."""


@dataclass(frozen=True, slots=True)
class CategoriesDestination(Destination):
    """The 'Categories' container under Stories."""


@dataclass(frozen=True, slots=True)
class SearchDestination(Destination):
    """The 'Search' parent node."""


@dataclass(frozen=True, slots=True)
class TitleSearchDestination(Destination):
    """The 'Title Search' child of Search."""


@dataclass(frozen=True, slots=True)
class TagSearchDestination(Destination):
    """The 'Tag Search' child of Search."""


@dataclass(frozen=True, slots=True)
class WordSearchDestination(Destination):
    """The 'Word Search' child of Search."""


@dataclass(frozen=True, slots=True)
class ReadingDestination(Destination):
    """The 'Reading' parent node (History + Choose for me)."""


@dataclass(frozen=True, slots=True)
class HistoryDestination(Destination):
    """The 'History' node under Reading."""


@dataclass(frozen=True, slots=True)
class ChooseForMeDestination(Destination):
    """The 'Choose for me' container under Reading."""


@dataclass(frozen=True, slots=True)
class AppendixDestination(Destination):
    """The 'Appendix' parent node."""


@dataclass(frozen=True, slots=True)
class StatisticsDestination(Destination):
    """The 'Statistics' appendix entry."""


@dataclass(frozen=True, slots=True)
class CensorshipFixesDocDestination(Destination):
    """The 'Censorship Fixes' appendix entry (opens the document reader)."""


@dataclass(frozen=True, slots=True)
class IndexDestination(Destination):
    """The 'Index' parent node."""


@dataclass(frozen=True, slots=True)
class MainIndexDestination(Destination):
    """The 'Main' index child."""


@dataclass(frozen=True, slots=True)
class SpeechIndexDestination(Destination):
    """The 'Speech' index child."""


@dataclass(frozen=True, slots=True)
class SpeechWordsDestination(Destination):
    """The 'Words' child under Speech index."""


@dataclass(frozen=True, slots=True)
class NamesIndexDestination(Destination):
    """The 'Names' index child."""


@dataclass(frozen=True, slots=True)
class LocationsIndexDestination(Destination):
    """The 'Locations' index child."""


@dataclass(frozen=True, slots=True)
class WikiIndexDestination(Destination):
    """The 'Carl Barks Wiki' index child (opens the wiki reader screen)."""


# --- Payload-bearing destinations ----------------------------------------


class YearRangeKind(StrEnum):
    """Which tree section the year range lives under."""

    CHRONO = "chrono"
    CS = "cs"
    US = "us"


@dataclass(frozen=True, slots=True)
class YearRangeDestination(Destination):
    """A year-range container node under Chronological, CS, or US."""

    start: int
    end: int
    kind: YearRangeKind = YearRangeKind.CHRONO


@dataclass(frozen=True, slots=True)
class SeriesDestination(Destination):
    """A top-level series container (CS, DDA, USA, DDS, USS, GG, MISC)."""

    series_name: str


@dataclass(frozen=True, slots=True)
class CategoryDestination(Destination):
    """A tag-category container (e.g., 'Characters', 'Places')."""

    category: str


@dataclass(frozen=True, slots=True)
class TagGroupDestination(Destination):
    """A TagGroup container (e.g., TagGroups.AFRICA)."""

    tag_group: TagGroups


@dataclass(frozen=True, slots=True)
class TagDestination(Destination):
    """A single Tag container (e.g., Tags.AIRPLANES)."""

    tag: Tags


@dataclass(frozen=True, slots=True)
class RandomTitlesDestination(Destination):
    """A 'Choose for me' filter node showing a fresh random title sample.

    `year_range` is the inclusive submitted-year range, or None for all
    titles ('Surprise me').
    """

    year_range: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class TitleDestination(Destination):
    """A leaf: a specific comic title."""

    fanta_info: FantaComicBookInfo


@dataclass(frozen=True, slots=True)
class ArticleDestination(Destination):
    """A non-comic article opened via the comic reader (Rich Tommaso, Don Ault, etc.)."""

    view_state: ViewStates
    article_title: Titles
