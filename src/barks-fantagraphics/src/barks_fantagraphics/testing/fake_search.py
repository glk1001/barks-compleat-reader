"""In-memory test adapter for ``FullTextSearchPort``.

Use ``InMemoryFullTextSearch`` in tests to avoid any Whoosh or disk dependency.
Construct it with canned data for the methods your test exercises::

    fake = InMemoryFullTextSearch(
        find_words_results={"duck": {
            "The Golden Helmet": TitleInfo(fanta_vol=7),
        }}
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from barks_fantagraphics.search_ports import AlphaSplitTerms
    from barks_fantagraphics.whoosh_search_engine import TitleDict


@dataclass
class InMemoryFullTextSearch:
    """Fake ``FullTextSearchPort`` backed by plain dicts. No Whoosh, no disk."""

    find_words_results: dict[str, TitleDict] = field(default_factory=dict)
    find_entities_results: dict[tuple[str, str], TitleDict] = field(default_factory=dict)
    all_titles: set[str] = field(default_factory=set)
    cleaned_terms: list[str] = field(default_factory=list)
    cleaned_alpha_split_terms: AlphaSplitTerms = field(default_factory=dict)
    entity_terms: dict[str, list[str]] = field(default_factory=dict)
    alpha_split_entity_terms: dict[str, AlphaSplitTerms] = field(default_factory=dict)

    def find_words(self, search_words: str) -> TitleDict:
        """Return canned results for the given query, or empty dict."""
        return self.find_words_results.get(search_words, {})

    def find_entities(self, entity_type: str, entity_name: str) -> TitleDict:
        """Return canned results for the given entity lookup, or empty dict."""
        return self.find_entities_results.get((entity_type, entity_name), {})

    def get_all_titles(self) -> set[str]:
        """Return the configured title set."""
        return self.all_titles

    def get_cleaned_terms(self) -> list[str]:
        """Return the configured cleaned term list."""
        return self.cleaned_terms

    def get_cleaned_alpha_split_terms(self) -> AlphaSplitTerms:
        """Return the configured alpha-split terms."""
        return self.cleaned_alpha_split_terms

    def get_entity_terms(self, entity_type: str) -> list[str]:
        """Return the configured entity terms for the given type."""
        return self.entity_terms.get(entity_type, [])

    def get_alpha_split_entity_terms(self, entity_type: str) -> AlphaSplitTerms:
        """Return the configured alpha-split entity terms for the given type."""
        return self.alpha_split_entity_terms.get(entity_type, {})
