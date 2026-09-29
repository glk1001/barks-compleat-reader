"""The word list behind the word search box: which of the index's words match what is typed.

`TermLexicon` holds the cleaned, display-ready terms of one full-text index (the
list `FullTextSearchPort.get_cleaned_terms` returns). The word search box shows
`matching(text)` as the user types: the words that are the text, then the words
that start with it, then - once the text is long enough to mean something - the
words that have it inside them. Kivy-free; one instance per index directory is
cached by the search facade.

Later phases of the search plan (docs/plans/advanced-search.md in the reader) add
wildcards, word forms and suggestions here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# Shorter than this, a typed text is matched at the start of a word only: two letters
# are inside a quarter of the index's words, and a list that long helps nobody.
SUBSTRING_MIN_CHARS = 3
# The most words the box lists; the rest are counted (a row says how many), not shown.
# A widget per row, rebuilt on every keystroke: "ing" alone is inside 1,788 words.
MAX_MATCHES_SHOWN = 300


@dataclass(frozen=True, slots=True)
class TermMatches:
    """The words matching a typed text, best first, and how many matched in all.

    Attributes:
        words: The matching words, at most the limit asked for.
        total: How many words matched, shown or not.

    """

    words: list[str]
    total: int

    @property
    def more(self) -> int:
        """How many matching words were left out of `words`."""
        return self.total - len(self.words)


class TermLexicon:
    """The index's words, for finding the ones a typed text matches."""

    def __init__(self, terms: Iterable[str]) -> None:
        """Hold `terms`, keeping each one's lower case alongside it.

        Args:
            terms: The index's cleaned terms, as displayed (some capitalized,
                some several words long).

        """
        self._terms = [(term.lower(), term) for term in terms]

    def __len__(self) -> int:
        """Return how many words the index holds."""
        return len(self._terms)

    def matching(self, text: str, limit: int | None = MAX_MATCHES_SHOWN) -> TermMatches:
        """Return the words `text` matches, in any case: itself, then prefixes, then inside.

        Each group keeps the order the box has always listed words in (a plain sort).
        Words containing the text are included only once it is `SUBSTRING_MIN_CHARS`
        long.

        Args:
            text: What was typed.
            limit: The most words to return, or None for all; `total` counts all.

        Returns:
            The matching words, best first, and their total.

        """
        query = text.strip().lower()
        if not query:
            return TermMatches([], 0)
        inside = len(query) >= SUBSTRING_MIN_CHARS
        exact: list[str] = []
        prefix: list[str] = []
        contained: list[str] = []
        for lower, term in self._terms:
            if lower == query:
                exact.append(term)
            elif lower.startswith(query):
                prefix.append(term)
            elif inside and query in lower:
                contained.append(term)
        words = sorted(exact) + sorted(prefix) + sorted(contained)
        return TermMatches(words if limit is None else words[:limit], len(words))
