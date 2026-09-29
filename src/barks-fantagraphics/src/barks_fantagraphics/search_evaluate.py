"""Run a typed word query: its tree, from ``search_query``, against the full-text index.

The reader's search plan (docs/plans/advanced-search.md), phase 6. The engine finds
bubbles one leaf at a time (``FullTextSearchPort.find_bubbles``: any of some terms, a
phrase, a NEAR pair); everything above a leaf is worked out here, by story:

- AND keeps the stories every part found, with each part's bubbles, so each word's
  matches can be shown. Phrases and NEAR pairs, the rarest, run first, and each part
  searches only the stories found so far; an empty set ends it early.
- OR keeps every story any part found. NOT drops the stories its part found, so it
  needs words beside it in an AND to drop them from.
- ``tag:``, ``year:`` and ``vol:`` are story filters (``search_filters``), not
  searches: beside words in an AND they keep, and under NOT drop, the stories they
  name. Only filters, or a filter in an OR with words, is an error.

A bare word finds its forms the index holds (``TermLexicon.variants``); a word the
index lacks is searched as typed anyway and, found nowhere, brings close spellings
as suggestions. A quoted word, or one picked from the word list, finds only itself;
a wildcard, the index's words it matches, up to a limit. A stop word is in no story
(the index drops them): in an AND it is left out, with a notice.

Text that does not parse is searched literally instead, as the word search always
has searched, with a notice saying why.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .search_filters import (
    AllFilters,
    AnyFilter,
    NotFilter,
    SearchFilter,
    StoryFilter,
    apply_filter,
    closest_tags,
    tag_titles,
)
from .search_query import (
    And,
    AnyTerm,
    Near,
    NearQuery,
    Not,
    Or,
    Phrase,
    QueryNode,
    TagQualifier,
    VolumeQualifier,
    Word,
    YearQualifier,
    parse_query,
)
from .search_results import hit_counts, intersect_titles, merge_title_dicts, subtract_titles

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .search_ports import FullTextSearchPort
    from .search_results import TitleDict
    from .search_terms import TermLexicon

_NEEDS_WORDS = "The query needs a word or phrase to search for, not only filters or NOTs."
_OR_WITH_FILTER = (
    "A filter (tag:, year:, vol:) cannot be joined to words with OR; join it with AND."
)
_NOT_IN_OR = "NOT needs words beside it, joined with AND, to take its stories away from."


@dataclass(frozen=True, slots=True)
class WordQueryResult:
    """What a typed word query found, and what the user should be told about it.

    Attributes:
        title_dict: The stories found, with their matching bubbles.
        hit_counts: How many bubbles matched in each story.
        highlight_terms: The index terms searched for (not those under NOT), to
            mark in the bubbles shown.
        notices: Things to tell the user: words left out, limits reached, tags
            not found.
        suggestions: Close spellings for words found nowhere, as displayed.
        used_literal_fallback: Whether the text did not parse and was searched as
            it stands.
        error: Why the query could not be run as a query, or None.
        error_position: Where in the text a syntax error was found, or None.

    """

    title_dict: TitleDict = field(default_factory=dict)
    hit_counts: dict[str, int] = field(default_factory=dict)
    highlight_terms: tuple[str, ...] = ()
    notices: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()
    used_literal_fallback: bool = False
    error: str | None = None
    error_position: int | None = None


class _QueryNeedsWordsError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def evaluate_query(
    node: QueryNode,
    port: FullTextSearchPort,
    lexicon: TermLexicon,
    *,
    speaker: str | None = None,
    search_filter: StoryFilter | None = None,
    stop_words: frozenset[str] = frozenset(),
) -> WordQueryResult:
    """Run a parsed query's tree against the index.

    Args:
        node: The query's tree.
        port: The full-text engine, which finds each leaf's bubbles.
        lexicon: The index's words, for word forms, wildcards and suggestions.
        speaker: A stored speaker value every bubble found must have, or None.
        search_filter: Which stories may be found (an era, a tag selection), or None.
        stop_words: The words the index leaves out, which no search can find.

    Returns:
        The stories found and what to tell the user; or, for a query that cannot be
        run (only filters, a filter in an OR), just the error.

    """
    evaluator = _Evaluator(port, lexicon, speaker, stop_words)
    try:
        found = evaluator.run(node, search_filter)
    except _QueryNeedsWordsError as exc:
        return WordQueryResult(error=exc.message, notices=tuple(evaluator.notices))
    return WordQueryResult(
        title_dict=found,
        hit_counts=hit_counts(found),
        highlight_terms=tuple(dict.fromkeys(evaluator.highlights)),
        notices=tuple(dict.fromkeys(evaluator.notices)),
        suggestions=tuple(dict.fromkeys(evaluator.suggestions)),
    )


def run_query_text(
    text: str,
    port: FullTextSearchPort,
    lexicon: TermLexicon,
    *,
    speaker: str | None = None,
    search_filter: StoryFilter | None = None,
    stop_words: frozenset[str] = frozenset(),
) -> WordQueryResult:
    """Parse typed text and run it; text that does not parse is searched literally.

    Args:
        text: What was typed.
        port: The full-text engine.
        lexicon: The index's words.
        speaker: A stored speaker value every bubble found must have, or None.
        search_filter: Which stories may be found, or None.
        stop_words: The words the index leaves out.

    Returns:
        What the query found. For text that does not parse: what the literal
        search found, with the syntax error and where it is.

    """
    parsed = parse_query(text)
    if parsed.error is not None:
        found = port.find_words(text, speaker=speaker)
        if search_filter is not None:
            found = apply_filter(search_filter, found)
        notice = f"{parsed.error.message}: searched for the text as it stands."
        return WordQueryResult(
            title_dict=found,
            hit_counts=hit_counts(found),
            notices=(notice,),
            used_literal_fallback=True,
            error=parsed.error.message,
            error_position=parsed.error.position,
        )
    if parsed.root is None:
        return WordQueryResult()
    return evaluate_query(
        parsed.root,
        port,
        lexicon,
        speaker=speaker,
        search_filter=search_filter,
        stop_words=stop_words,
    )


def _is_filter(node: QueryNode) -> bool:
    match node:
        case TagQualifier() | YearQualifier() | VolumeQualifier():
            return True
        case Not(part):
            return _is_filter(part)
        case And(parts) | Or(parts):
            return all(_is_filter(p) for p in parts)
        case _:
            return False


def _unwrap_double_not(node: QueryNode) -> QueryNode:
    while isinstance(node, Not) and isinstance(node.part, Not):
        node = node.part.part
    return node


def _search_order(node: QueryNode) -> int:
    """Rarest first: phrases and NEAR pairs, then words as typed, then the broader ones."""
    match node:
        case Phrase() | NearQuery():
            return 0
        case Word(exact=True):
            return 1
        case Word() if not node.is_wildcard:
            return 2
        case Word():
            return 3
        case _:
            return 4


class _Evaluator:
    def __init__(
        self,
        port: FullTextSearchPort,
        lexicon: TermLexicon,
        speaker: str | None,
        stop_words: frozenset[str],
    ) -> None:
        self._port = port
        self._lexicon = lexicon
        self._speaker = speaker
        self._stop_words = stop_words
        self._negated = 0  # inside a NOT: found words are not highlighted or suggested for
        self.notices: list[str] = []
        self.highlights: list[str] = []
        self.suggestions: list[str] = []

    def run(self, node: QueryNode, search_filter: StoryFilter | None) -> TitleDict:
        node = _unwrap_double_not(node)
        if _is_filter(node) or isinstance(node, Not):
            raise _QueryNeedsWordsError(_NEEDS_WORDS)
        within = None if search_filter is None else search_filter.candidates
        found = self._eval(node, within)
        return found if search_filter is None else apply_filter(search_filter, found)

    # ------------------------------------------------------------------ searches --

    def _eval(self, node: QueryNode, within: frozenset[str] | None) -> TitleDict:
        match node:
            case And(parts):
                return self._eval_and(parts, within)
            case Or(parts):
                return self._eval_or(parts, within)
            case Word():
                return self._eval_word(node, within)
            case Phrase(words):
                self._highlight(w.lower() for w in words if w.lower() not in self._stop_words)
                return self._find(Phrase(tuple(w.lower() for w in words)), within)
            case NearQuery(left, right, distance):
                return self._eval_near(left, right, distance, within)
            case Not() | TagQualifier() | YearQualifier() | VolumeQualifier():
                # Reached only through an OR or on its own; an AND handles both itself.
                raise _QueryNeedsWordsError(_NOT_IN_OR if isinstance(node, Not) else _NEEDS_WORDS)

    def _eval_or(self, parts: tuple[QueryNode, ...], within: frozenset[str] | None) -> TitleDict:
        if any(_is_filter(p) for p in parts):
            raise _QueryNeedsWordsError(_OR_WITH_FILTER)
        return merge_title_dicts(*(self._eval(p, within) for p in parts))

    def _eval_and(self, parts: tuple[QueryNode, ...], within: frozenset[str] | None) -> TitleDict:
        story_filter, removed, searched = self._split_and(parts)
        if story_filter is not None:
            within = _narrowed(within, story_filter.candidates)

        found: TitleDict | None = None
        for part in sorted(searched, key=_search_order):
            part_found = self._eval(part, within)
            if story_filter is not None:
                part_found = apply_filter(story_filter, part_found)
            found = part_found if found is None else intersect_titles(found, part_found)
            if not found:
                return {}
            within = frozenset(found)
        assert found is not None
        return self._take_away(found, removed)

    def _split_and(
        self, parts: tuple[QueryNode, ...]
    ) -> tuple[StoryFilter | None, list[QueryNode], list[QueryNode]]:
        """Sort an AND's parts: its filters (as one), what its NOTs remove, what it searches."""
        filters: list[StoryFilter] = []
        removed: list[QueryNode] = []
        searched: list[QueryNode] = []
        for raw in parts:
            part = _unwrap_double_not(raw)
            if _is_filter(part):
                filters.append(self._filter_of(part))
            elif isinstance(part, Not):
                removed.append(part.part)
            elif isinstance(part, Word) and self._is_stop_word(part):
                self.notices.append(f'"{part.text}" is too common to search for; left out.')
            else:
                searched.append(part)
        if not searched:
            raise _QueryNeedsWordsError(_NEEDS_WORDS)
        return (AllFilters(tuple(filters)) if filters else None), removed, searched

    def _take_away(self, found: TitleDict, removed: list[QueryNode]) -> TitleDict:
        """Drop the stories each NOT's part finds among those found."""
        self._negated += 1
        try:
            for part in removed:
                found = subtract_titles(found, self._eval_removed(part, frozenset(found)))
                if not found:
                    return {}
        finally:
            self._negated -= 1
        return found

    def _eval_removed(self, node: QueryNode, within: frozenset[str]) -> TitleDict:
        """Search what a NOT takes away; a lone stop word takes nothing away."""
        if isinstance(node, Word) and self._is_stop_word(node):
            self.notices.append(f'"{node.text}" is too common to search for; left out.')
            return {}
        return self._eval(node, within)

    def _eval_word(self, word: Word, within: frozenset[str] | None) -> TitleDict:
        if self._is_stop_word(word):
            self.notices.append(f'"{word.text}" is too common to search for.')
            return {}
        lower = word.text.strip().lower()
        if word.exact and self._lexicon.is_multi_word(lower):  # a term picked from the list
            return self._eval(Phrase(tuple(lower.split())), within)
        terms = self._terms_of(word)
        if not terms:
            return {}
        found = self._find(AnyTerm(terms), within)
        if not (found or word.exact or word.is_wildcard or self._negated) and (
            not self._lexicon.contains(lower)
        ):
            self._suggest_for(word.text)
        return found

    def _eval_near(
        self, left: Word, right: Word, distance: int, within: frozenset[str] | None
    ) -> TitleDict:
        for side in (left, right):
            if self._is_stop_word(side):
                self.notices.append(f'"{side.text}" is too common to search for.')
                return {}
        left_terms, right_terms = self._terms_of(left), self._terms_of(right)
        if not left_terms or not right_terms:
            return {}
        return self._find(Near(AnyTerm(left_terms), AnyTerm(right_terms), distance), within)

    def _find(self, leaf: AnyTerm | Phrase | Near, within: frozenset[str] | None) -> TitleDict:
        return self._port.find_bubbles(leaf, speaker=self._speaker, titles=within)

    # --------------------------------------------------------------------- words --

    def _is_stop_word(self, word: Word) -> bool:
        return word.text.strip().lower() in self._stop_words

    def _terms_of(self, word: Word) -> tuple[str, ...]:
        """Return the index terms a word stands for: itself, its forms, or a wildcard's."""
        lower = word.text.strip().lower()
        if word.is_wildcard:
            matches = self._lexicon.expand_wildcard(lower)
            if not matches.total:
                self.notices.append(f'No word matches "{word.text}".')
            elif matches.more:
                self.notices.append(
                    f'"{word.text}" matches {matches.total} words;'
                    f" searched for the first {len(matches.words)}."
                )
            terms = tuple(matches.words)
        elif word.exact:
            terms = (lower,)
        else:
            terms = self._lexicon.variants(lower) or (lower,)
        self._highlight(terms)
        return terms

    def _highlight(self, terms: Iterable[str]) -> None:
        if not self._negated:
            self.highlights.extend(terms)

    def _suggest_for(self, text: str) -> None:
        suggestions = self._lexicon.suggest(text)
        self.suggestions.extend(suggestions)
        self.notices.append(f'"{text}" is in no story.')

    # ------------------------------------------------------------------- filters --

    def _filter_of(self, node: QueryNode) -> StoryFilter:
        match node:
            case TagQualifier(name):
                titles = tag_titles(name)
                if titles is None:
                    self.notices.append(_unknown_tag_notice(name))
                    titles = frozenset()
                return SearchFilter(tag_titles=titles)
            case YearQualifier(first, last):
                return SearchFilter(years=(first, last))
            case VolumeQualifier(first, last):
                return SearchFilter(volumes=(first, last))
            case Not(part):
                return NotFilter(self._filter_of(part))
            case And(parts):
                return AllFilters(tuple(self._filter_of(p) for p in parts))
            case Or(parts):
                return AnyFilter(tuple(self._filter_of(p) for p in parts))
            case _:  # _is_filter holds for every node passed here
                msg = f"Not a filter: {node!r}."
                raise ValueError(msg)


def _narrowed(
    within: frozenset[str] | None, allowed: frozenset[str] | None
) -> frozenset[str] | None:
    if allowed is None:
        return within
    return allowed if within is None else within & allowed


def _unknown_tag_notice(name: str) -> str:
    closest = closest_tags(name)
    notice = f'No tag is called "{name}".'
    if closest:
        notice += " Closest: " + ", ".join(closest) + "."
    return notice
