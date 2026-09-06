"""Protocol definitions for the search subsystem.

These ports isolate callers from the concrete search implementation (currently
Whoosh). Production adapters are ``SearchEngine`` and ``SearchEngineCreator``;
test code can use ``InMemoryFullTextSearch`` or any other implementation that
satisfies the protocol.

No Whoosh imports in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable

    from .whoosh_search_engine import TitleDict

type AlphaSplitTerms = dict[str, dict[str, list[str]]]


class SearchIndexUnavailableError(Exception):
    """No usable full-text index at the given location.

    Raised instead of the underlying engine's own error so that callers can
    degrade gracefully without importing Whoosh.
    """


@dataclass(frozen=True, slots=True)
class CorpusTextTotals:
    """Corpus-wide totals from a single pass over the indexed speech.

    Attributes:
        num_text_entities: Indexed speech groups - balloons, captions, sound effects.
        num_words: Whitespace-delimited words across all indexed speech text.
        num_titles: Distinct story titles present in the index.
        num_pages: Distinct ``(volume, page)`` pairs that carry indexed text.
        num_panels: Distinct ``(volume, page, panel)`` triples that carry indexed text.

    """

    num_text_entities: int
    num_words: int
    num_titles: int
    num_pages: int
    num_panels: int


@runtime_checkable
class FullTextSearchPort(Protocol):
    """Read-only query port for full-text search over indexed speech and entities."""

    def find_words(self, search_words: str) -> TitleDict:
        """Full-text search across all indexed speech bubble text."""
        ...

    def find_entities(self, entity_type: str, entity_name: str) -> TitleDict:
        """Search for a named entity of the given type."""
        ...

    def get_all_titles(self) -> set[str]:
        """Return all comic title strings present in the index."""
        ...

    def get_cleaned_terms(self) -> list[str]:
        """Return the cleaned, display-ready word list."""
        ...

    def get_cleaned_alpha_split_terms(self) -> AlphaSplitTerms:
        """Return cleaned terms grouped by first letter then by prefix."""
        ...

    def get_entity_terms(self, entity_type: str) -> list[str]:
        """Return sorted entity names for the given entity type."""
        ...

    def get_alpha_split_entity_terms(self, entity_type: str) -> AlphaSplitTerms:
        """Return entity terms grouped alphabetically."""
        ...

    def get_corpus_text_totals(self) -> CorpusTextTotals:
        """Aggregate corpus-wide totals in one pass over the whole index."""
        ...


@runtime_checkable
class IndexBuilderPort(Protocol):
    """Write port for offline index construction (used by barks-ocr)."""

    def index_volumes(
        self,
        volumes: list[int],
        entity_tagger: Callable[[str], dict[str, set[str]]] | None = None,
        entity_provider: Callable[[str, str, str], dict[str, set[str]]] | None = None,
    ) -> None:
        """Build or rebuild the search index for the given volumes."""
        ...

    def get_search_engine(self) -> FullTextSearchPort:
        """Return a read-only search port backed by the index just built."""
        ...
