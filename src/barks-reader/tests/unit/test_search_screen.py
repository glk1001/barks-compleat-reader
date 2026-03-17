# ruff: noqa: SLF001

from __future__ import annotations

from typing import ClassVar
from unittest.mock import patch

from barks_reader.ui.search_screen import SearchScreen


def _make_screen(word_terms: dict) -> SearchScreen:
    """Create a SearchScreen with just enough state for prefix-matching tests."""
    with patch.object(SearchScreen, "__init__", lambda _self, *_a, **_kw: None):
        screen = SearchScreen.__new__(SearchScreen)
        screen._word_terms = word_terms
        return screen


class TestGetWordsMatchingPrefix:
    TERMS: ClassVar[dict] = {
        "d": {
            "do": ["don", "Don Gaspar", "Don Quixote", "done", "Donna Duck"],
            "da": ["dance", "Daniel Boone"],
        },
        "q": {"qu": ["quixote"]},
    }

    def _match(self, text: str) -> list[str]:
        screen = _make_screen(self.TERMS)
        return screen._get_words_matching_prefix(text)

    def test_single_word_prefix(self) -> None:
        assert self._match("do") == [
            "Don Gaspar",
            "Don Quixote",
            "Donna Duck",
            "don",
            "done",
        ]

    def test_multi_word_prefix_case_insensitive(self) -> None:
        """Regression: 'don qu' must match 'Don Quixote' (mixed-case term)."""
        assert self._match("don qu") == ["Don Quixote"]

    def test_exact_match(self) -> None:
        assert self._match("don quixote") == ["Don Quixote"]

    def test_no_match(self) -> None:
        assert self._match("doz") == []

    def test_single_char_returns_all_in_letter_group(self) -> None:
        results = self._match("d")
        assert "don" in results
        assert "Daniel Boone" in results

    def test_different_letter_group(self) -> None:
        assert self._match("qu") == ["quixote"]
