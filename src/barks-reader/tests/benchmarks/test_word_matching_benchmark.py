# ruff: noqa: INP001
"""How long the word search box takes to match a keystroke against the index's words.

The box re-matches on every keystroke, and from three letters it also looks inside
every word, so this is paid once per key. The plan (docs/plans/advanced-search.md)
budgets it at under 10 ms over the ~23,000 words of the real index. A synthetic
word list of that size keeps the benchmark free of the data pack, so it runs on any
machine; it is shaped like the real one - lower-case words, some capitalized names,
some several words long.
"""

from __future__ import annotations

import random
import string
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.search_terms import TermLexicon

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

WORD_COUNT = 23_000
BUDGET_SECS = 0.010


def _synthetic_words(count: int) -> list[str]:
    rng = random.Random(1947)  # fixed: the same list every run
    letters = string.ascii_lowercase
    words = set()
    while len(words) < count:
        word = "".join(rng.choice(letters) for _ in range(rng.randint(3, 11)))
        roll = rng.random()
        if roll < 0.06:  # noqa: PLR2004
            word = word.capitalize()
        elif roll < 0.07:  # noqa: PLR2004
            word = f"{word.capitalize()} {word[::-1].capitalize()}"
        words.add(word)
    return sorted(words)


@pytest.fixture(scope="module")
def lexicon() -> TermLexicon:
    return TermLexicon(_synthetic_words(WORD_COUNT))


# One of the costliest keystrokes: a three-letter text is the first to be looked for
# inside every word, and a common one ("ing" is inside 1,788 real words) sorts the most.
@pytest.mark.parametrize("text", ["ing", "tha", "e"])
def test_matching_a_keystroke_benchmark(
    benchmark: BenchmarkFixture, lexicon: TermLexicon, text: str
) -> None:
    result = benchmark(lexicon.matching, text)
    assert result.total > 0
    assert benchmark.stats is not None
    assert benchmark.stats["median"] < BUDGET_SECS, "over the plan's 10 ms a keystroke"
