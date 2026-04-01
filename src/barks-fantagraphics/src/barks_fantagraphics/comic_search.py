"""Unified search facade for the Barks comic reader.

``ComicSearch`` is the single object that reader UI screens hold for all search
operations. It hides the two underlying subsystems (in-memory title/tag prefix
search and Whoosh full-text speech search) behind a simple interface.

Typical usage::

    search = ComicSearch(index_dir)
    result = search.search("Christmas", SearchMode.TITLE)
    result = search.search("money", SearchMode.WORD)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from .barks_tags import TagGroups, Tags
    from .barks_titles import Titles
    from .search_ports import AlphaSplitTerms, FullTextSearchPort
    from .title_search import BarksTitleSearch
    from .whoosh_search_engine import TitleDict


class SearchMode(StrEnum):
    """Which search domain to query."""

    TITLE = auto()
    TAG = auto()
    WORD = auto()


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Uniform result envelope returned by all search operations.

    Fields are populated based on the search mode. Unused fields remain at
    their defaults (empty lists / empty dicts / None).

    Attributes:
        mode: Which search mode produced this result.
        titles: Matching comic title enums (TITLE and TAG modes).
        title_strings: Display-ready title strings parallel to ``titles``.
        title_dict: Full-text match details with page/speech info (WORD and
            ENTITY modes).
        matched_tags: Tags or tag groups matching the query (TAG mode).
        matched_tag_or_group: The resolved tag or tag group (after
            ``resolve_tag``).

    """

    mode: SearchMode
    titles: list[Titles] = field(default_factory=list)
    title_strings: list[str] = field(default_factory=list)
    title_dict: TitleDict = field(default_factory=dict)
    matched_tags: list[Tags | TagGroups] = field(default_factory=list)
    matched_tag_or_group: Tags | TagGroups | None = None


class ComicSearch:
    """Unified search facade over title metadata and full-text speech indexes.

    Provides a single entry point for the reader UI's three search modes
    (title, tag, word) plus entity search and index browsing.

    The Whoosh full-text engine is initialized lazily on first use, so
    title-only callers pay no disk I/O cost.

    Args:
        index_dir: Path to the Whoosh index directory.

    """

    def __init__(self, index_dir: Path) -> None:
        self._index_dir = index_dir
        self._title_search: BarksTitleSearch | None = None
        self._full_text: FullTextSearchPort | None = None

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def search(self, query: str, mode: SearchMode) -> SearchResult:
        """Run a search and return a uniform result.

        Args:
            query: The user's input text.
            mode: Which search domain to query.

        Returns:
            A ``SearchResult`` with the appropriate fields populated.

        """
        if not query:
            return SearchResult(mode=mode)

        match mode:
            case SearchMode.TITLE:
                return self._search_titles(query)
            case SearchMode.TAG:
                return self._search_tags(query)
            case SearchMode.WORD:
                return self._search_words(query)

    def search_entity(self, entity_type: str, entity_name: str) -> SearchResult:
        """Search for comics containing a specific named entity.

        Args:
            entity_type: One of the ``EntityType`` values (e.g. ``"person"``).
            entity_name: The entity name to search for.

        Returns:
            A ``SearchResult`` with ``title_dict`` populated.

        """
        engine = self._get_full_text()
        return SearchResult(
            mode=SearchMode.WORD,
            title_dict=engine.find_entities(entity_type, entity_name),
        )

    # ------------------------------------------------------------------
    # Tag drill-down
    # ------------------------------------------------------------------

    def resolve_tag(self, tag_str: str) -> tuple[Tags | TagGroups | None, list[Titles]]:
        """Resolve a tag alias string to its tag/group and matching titles.

        Args:
            tag_str: The tag alias string (e.g. ``"junior woodchucks"``).

        Returns:
            A ``(tag_or_group, titles)`` tuple.

        """
        ts = self._get_title_search()
        return ts.get_titles_from_alias_tag(tag_str)

    def get_tag_group_members(self, tag_group: TagGroups) -> list[Tags | TagGroups]:
        """Return the direct members of a tag group.

        Args:
            tag_group: The tag group to expand.

        Returns:
            Direct child tags and subgroups.

        """
        ts = self._get_title_search()
        return ts.get_direct_group_members(tag_group)

    def get_title_display_strings(self, titles: list[Titles]) -> list[str]:
        """Convert title enums to display strings.

        Args:
            titles: List of ``Titles`` enum values.

        Returns:
            Parallel list of human-readable title strings.

        """
        ts = self._get_title_search()
        return ts.get_titles_as_strings(titles)

    # ------------------------------------------------------------------
    # Index browsing (SpeechIndexScreen / EntityIndexScreen)
    # ------------------------------------------------------------------

    def get_alpha_split_terms(self) -> AlphaSplitTerms:
        """Return the alphabetically-split word term index for A-Z browsing."""
        return self._get_full_text().get_cleaned_alpha_split_terms()

    def get_alpha_split_entity_terms(self, entity_type: str) -> AlphaSplitTerms:
        """Return alphabetically-split entity terms for the given type."""
        return self._get_full_text().get_alpha_split_entity_terms(entity_type)

    def get_entity_terms(self, entity_type: str) -> list[str]:
        """Return the flat entity term list for the given type."""
        return self._get_full_text().get_entity_terms(entity_type)

    def find_words(self, search_words: str) -> TitleDict:
        """Direct full-text search returning raw ``TitleDict``.

        Exposed for callers (e.g. ``SpeechIndexScreen``) that need the raw
        ``TitleDict`` structure rather than a ``SearchResult`` envelope.

        Args:
            search_words: The search query.

        Returns:
            Matching titles with page and speech-bubble detail.

        """
        return self._get_full_text().find_words(search_words)

    def find_entities(self, entity_type: str, entity_name: str) -> TitleDict:
        """Direct entity search returning raw ``TitleDict``.

        Args:
            entity_type: One of the ``EntityType`` values.
            entity_name: The entity name to search for.

        Returns:
            Matching titles with page and speech-bubble detail.

        """
        return self._get_full_text().find_entities(entity_type, entity_name)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_title_search(self) -> BarksTitleSearch:
        if self._title_search is None:
            from .title_search import BarksTitleSearch as _BarksTitleSearch  # noqa: PLC0415

            self._title_search = _BarksTitleSearch()
        assert self._title_search is not None
        return self._title_search

    def _get_full_text(self) -> FullTextSearchPort:
        if self._full_text is None:
            from .whoosh_search_engine import SearchEngine  # noqa: PLC0415

            self._full_text = SearchEngine(self._index_dir)
        assert self._full_text is not None
        return self._full_text

    def _search_titles(self, query: str) -> SearchResult:
        ts = self._get_title_search()
        titles = ts.get_titles_matching_prefix(query)
        min_chars = 2
        if len(query) > min_chars:
            if not titles:
                titles = ts.get_titles_from_issue_num(query)
            if not titles:
                seen = set(titles)
                titles.extend(t for t in ts.get_titles_containing(query) if t not in seen)
        return SearchResult(
            mode=SearchMode.TITLE,
            titles=titles,
            title_strings=ts.get_titles_as_strings(titles),
        )

    def _search_tags(self, query: str) -> SearchResult:
        ts = self._get_title_search()
        matched = ts.get_tags_matching_prefix(query)
        return SearchResult(
            mode=SearchMode.TAG,
            matched_tags=list(matched),
        )

    def _search_words(self, query: str) -> SearchResult:
        engine = self._get_full_text()
        return SearchResult(
            mode=SearchMode.WORD,
            title_dict=engine.find_words(query),
        )
