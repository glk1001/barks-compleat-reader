# ruff: noqa: SLF001

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar, cast
from unittest.mock import patch

from barks_reader.ui.search_screen import SearchScreen, _SearchResultButton


def _make_screen(word_terms: dict) -> SearchScreen:
    """Create a SearchScreen with just enough state for prefix-matching tests."""
    with patch.object(SearchScreen, "__init__", lambda _self, *_a, **_kw: None):
        screen = SearchScreen.__new__(SearchScreen)
        screen._word_terms = word_terms
        return screen


def _make_bare_screen() -> SearchScreen:
    """Create a SearchScreen with no state, for exercising individual methods."""
    with patch.object(SearchScreen, "__init__", lambda _self, *_a, **_kw: None):
        return SearchScreen.__new__(SearchScreen)


def _fake_row(row_index: int) -> _SearchResultButton:
    """Return a stand-in result button with just the fields `_mark_result_selected` reads."""
    return cast("_SearchResultButton", SimpleNamespace(selected=False, row_index=row_index))


class TestMarkResultSelected:
    """The last-opened result row stays highlighted (mouse or keyboard) until superseded."""

    def test_marks_button_and_records_index(self) -> None:
        screen = _make_bare_screen()
        screen._selected_result_button = None
        row = _fake_row(2)

        screen._mark_result_selected(row)

        assert row.selected is True
        assert screen._selected_result_button is row
        assert screen._last_activated_result_idx == 2  # noqa: PLR2004
        assert screen._last_activated_word_sub_focus == "title"

    def test_selecting_another_row_clears_the_previous(self) -> None:
        screen = _make_bare_screen()
        screen._selected_result_button = None
        first, second = _fake_row(0), _fake_row(1)

        screen._mark_result_selected(first)
        screen._mark_result_selected(second)

        assert first.selected is False
        assert second.selected is True
        assert screen._selected_result_button is second
        assert screen._last_activated_result_idx == 1


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
