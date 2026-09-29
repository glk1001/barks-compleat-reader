"""In-memory test adapter for ``FullTextSearchPort``.

Use ``InMemoryFullTextSearch`` in tests to avoid any Whoosh or disk dependency.
Construct it with canned data for the methods your test exercises::

    fake = InMemoryFullTextSearch(
        find_words_results={"duck": {
            "The Golden Helmet": TitleInfo(fanta_vol=7),
        }}
    )

For typed word queries, give it a small corpus instead and ``find_bubbles`` searches
it as the index would::

    fake = InMemoryFullTextSearch(bubbles=[FakeBubble("Pirate Gold", "gold in the mine")])

The default tokenizer lower-cases and splits on non-word characters, keeping a word's
own hyphens and apostrophes; pass the index's analyzer as ``tokenize`` (it also drops
stop words, which NEAR distances do not count) to match the real engine exactly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from barks_fantagraphics.search_ports import CorpusTextTotals
from barks_fantagraphics.search_query import AnyTerm, Near, Phrase
from barks_fantagraphics.search_results import (
    PageInfo,
    SpeechInfo,
    TitleInfo,
    merge_title_dicts,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_fantagraphics.search_ports import AlphaSplitTerms
    from barks_fantagraphics.search_query import SearchLeaf
    from barks_fantagraphics.whoosh_search_engine import TitleDict

_WORD_RE = re.compile(r"\w+(?:['\-.]\w+)*'?")


def _default_tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


@dataclass(frozen=True)
class FakeBubble:
    """One speech group in the fake's corpus."""

    title: str
    text: str
    fanta_vol: int = 1
    fanta_page: str = "001"
    comic_page: str = "1"
    group_id: str = "1"
    panel_num: int = 1
    speaker: str | None = None


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
    corpus_text_totals: CorpusTextTotals = field(
        default_factory=lambda: CorpusTextTotals(0, 0, 0, 0, 0)
    )
    speakers: dict[str, int] = field(default_factory=dict)
    bubbles: list[FakeBubble] = field(default_factory=list)
    tokenize: Callable[[str], list[str]] = _default_tokenize
    # Every find_bubbles call, for tests that check what the evaluator asked for.
    bubble_calls: list[tuple[SearchLeaf, str | None, frozenset[str] | None]] = field(
        default_factory=list
    )

    def find_bubbles(
        self,
        leaf: SearchLeaf,
        speaker: str | None = None,
        titles: frozenset[str] | None = None,
    ) -> TitleDict:
        """Search the corpus for one query leaf, as the real engine searches the index."""
        self.bubble_calls.append((leaf, speaker, titles))
        if isinstance(leaf, Phrase):  # its words go through the analyzer too, as in Whoosh
            leaf = Phrase(tuple(self.tokenize(" ".join(leaf.words))))
        found: list[TitleDict] = []
        for bubble in self.bubbles:
            if titles is not None and bubble.title not in titles:
                continue
            if speaker and bubble.speaker != speaker:
                continue
            if _leaf_matches(leaf, self.tokenize(bubble.text)):
                speech = SpeechInfo(
                    group_id=bubble.group_id,
                    panel_num=bubble.panel_num,
                    speech_text=bubble.text,
                    speech_text_markup=bubble.text,
                    speaker=bubble.speaker,
                )
                page = PageInfo(bubble.comic_page, [speech])
                found.append({bubble.title: TitleInfo(bubble.fanta_vol, {bubble.fanta_page: page})})
        return merge_title_dicts(*found)

    def find_words(self, search_words: str, speaker: str | None = None) -> TitleDict:
        """Return canned results for the given query, or empty dict.

        With ``speaker``, the canned result is narrowed to the speech infos
        carrying that speaker, and pages and titles left empty by that are
        dropped -- the same shape the real engine's filtered query returns.
        """
        found = self.find_words_results.get(search_words, {})
        if not speaker:
            return found
        return _filter_by_speaker(found, speaker)

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

    def get_corpus_text_totals(self) -> CorpusTextTotals:
        """Return the configured corpus totals."""
        return self.corpus_text_totals

    def get_speakers(self) -> dict[str, int]:
        """Return the configured speaker counts."""
        return self.speakers


def _leaf_matches(leaf: SearchLeaf, tokens: list[str]) -> bool:
    match leaf:
        case AnyTerm(terms):
            return any(t in terms for t in tokens)
        case Phrase(words):
            n = len(words)
            return any(tuple(tokens[i : i + n]) == words for i in range(len(tokens) - n + 1))
        case Near(left, right, distance):
            lefts = [i for i, t in enumerate(tokens) if t in left.terms]
            rights = [i for i, t in enumerate(tokens) if t in right.terms]
            return any(i != j and abs(i - j) <= distance for i in lefts for j in rights)


def _filter_by_speaker(found: TitleDict, speaker: str) -> TitleDict:
    # `replace` rather than the constructors, so this stays free of the Whoosh
    # module the real classes live in.
    narrowed: TitleDict = {}
    for title, title_info in found.items():
        pages = {}
        for fanta_page, page_info in title_info.fanta_pages.items():
            kept = [s for s in page_info.speech_info_list if s.speaker == speaker]
            if kept:
                pages[fanta_page] = replace(page_info, speech_info_list=kept)
        if pages:
            narrowed[title] = replace(title_info, fanta_pages=pages)
    return narrowed
