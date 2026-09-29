# cspell:ignore aeiou duckin makin runnin scroge
"""The word list behind the word search box: which of the index's words match what is typed.

`TermLexicon` holds the cleaned, display-ready terms of one full-text index (the
list `FullTextSearchPort.get_cleaned_terms` returns). The word search box shows
`matching(text)` as the user types: the words that are the text, then the words
that start with it, then - once the text is long enough to mean something - the
words that have it inside them. Kivy-free; one instance per index directory is
cached by the search facade.

For typed queries (the search plan's phase 5, docs/plans/advanced-search.md in the
reader) it also expands a wildcard to the index's words, finds a word's other forms
the index holds (duck: ducks, ducked, ducking, duckin'), and suggests close
spellings for a word it does not hold. Those work on single words, in the lower
case the index stores; a suggestion comes back as the word list shows it.
"""

from __future__ import annotations

import difflib
import re
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
# The most words one wildcard stands for; past it the query is too broad to run well.
MAX_WILDCARD_TERMS = 200
# How alike a word must be to be suggested for one the index does not hold (difflib).
SUGGESTION_CUTOFF = 0.75
MAX_SUGGESTIONS = 5
_VOWELS = frozenset("aeiou")
# A stem is at least this long ("bus" is not "bu" + "s"), and longer before -ing:
# "thing", "king" and "bring" are not forms of "th", "k" and "br".
_MIN_STEM = 2
_MIN_ING_STEM = 3


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
        self._all_lower = {lower for lower, _ in self._terms}
        # Single words only: forms, wildcards and suggestions are for one word.
        self._words = sorted({lower for lower in self._all_lower if " " not in lower})
        self._word_set = frozenset(self._words)
        self._display: dict[str, str] = {}
        for lower, term in self._terms:
            self._display.setdefault(lower, term)

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

    def contains(self, word: str) -> bool:
        """Return whether the index holds `word` (in any case; a several-word term too)."""
        return word.strip().lower() in self._all_lower

    @staticmethod
    def is_multi_word(term: str) -> bool:
        """Return whether `term` is several words: searched as a phrase, not one word."""
        return " " in term.strip()

    def expand_wildcard(self, pattern: str, limit: int = MAX_WILDCARD_TERMS) -> TermMatches:
        """Return the index's words a wildcard matches: ``*`` any letters, ``?`` one.

        Within one word: several-word terms are not matched. Any other character is
        taken as itself.

        Args:
            pattern: The wildcard, in any case.
            limit: The most words to return; `total` counts them all.

        Returns:
            The matching words in lower case, sorted, and how many matched in all.

        """
        regex = re.compile(
            "".join(
                ".*" if c == "*" else "." if c == "?" else re.escape(c)
                for c in pattern.strip().lower()
            )
        )
        words = [w for w in self._words if regex.fullmatch(w)]
        return TermMatches(words[:limit], len(words))

    def variants(self, word: str) -> tuple[str, ...]:
        """Return the forms of `word` the index holds, the word itself among them if held.

        Both ways: from a stem to its forms (duck: ducks, duck's, ducked, ducking and
        Barks's dropped g, duckin'), and from a form back to its stem and on to the
        stem's other forms (ducking: duck, ducked, ...). Also y to ies (city, cities),
        a dropped e (make: making, makin') and a doubled last letter (run: running,
        runnin'). Only forms the index holds come back, so a rule that makes a word
        the index lacks costs nothing.

        Args:
            word: A single word, in any case.

        Returns:
            The forms, in lower case, sorted.

        """
        lower = word.strip().lower()
        if not lower or " " in lower:
            return ()
        forms: set[str] = set()
        for stem in _stems_of(lower):
            forms |= _forms_of(stem)
        return tuple(sorted(f for f in forms if f in self._word_set))

    def suggest(self, word: str, limit: int = MAX_SUGGESTIONS) -> list[str]:
        """Return close spellings of `word` the index holds, closest first, as displayed.

        For a word the index does not hold (``scroge``: Scrooge, scrounge, ...).

        Args:
            word: The word typed, in any case.
            limit: The most suggestions to return.

        Returns:
            The suggestions, never the word itself.

        """
        lower = word.strip().lower()
        if not lower:
            return []
        close = difflib.get_close_matches(lower, self._words, n=limit + 1, cutoff=SUGGESTION_CUTOFF)
        return [self._display[w] for w in close if w != lower][:limit]


def _doubles_last_letter(stem: str) -> bool:
    """Whether a suffix doubles the stem's last letter: run, running; stop, stopped."""
    min_len = 3
    return (
        len(stem) >= min_len
        and stem[-1] not in _VOWELS
        and stem[-1] not in "wxy"
        and stem[-2] in _VOWELS
        and stem[-3] not in _VOWELS
    )


def _forms_of(stem: str) -> set[str]:
    """Return the forms a stem may take (the index keeps the ones it holds)."""
    forms = {stem, f"{stem}s", f"{stem}es", f"{stem}'s", f"{stem}ed", f"{stem}ing", f"{stem}in'"}
    if stem.endswith("e"):
        forms |= {f"{stem}d", f"{stem[:-1]}ing", f"{stem[:-1]}in'"}
    if len(stem) >= _MIN_STEM and stem.endswith("y") and stem[-2] not in _VOWELS:
        forms |= {f"{stem[:-1]}ies", f"{stem[:-1]}ied"}
    if _doubles_last_letter(stem):
        doubled = stem + stem[-1]
        forms |= {f"{doubled}ed", f"{doubled}ing", f"{doubled}in'"}
    return forms


def _stems_of(word: str) -> set[str]:
    """Return the word and every stem it may be a form of."""
    stems = {word}
    for suffix in ("'s", "es", "s", "d", "ed", "ing", "in'"):
        base = word.removesuffix(suffix)
        shortest = _MIN_ING_STEM if suffix in ("ing", "in'") else _MIN_STEM
        if base == word or len(base) < shortest:
            continue
        stems.add(base)
        if suffix in ("ed", "ing", "in'"):
            stems.add(f"{base}e")  # making, make
            if len(base) > _MIN_STEM and base[-1] == base[-2]:
                stems.add(base[:-1])  # running, run
    for suffix in ("ies", "ied"):
        base = word.removesuffix(suffix)
        if base != word and len(base) >= 1:
            stems.add(f"{base}y")  # cities, city
    return stems
