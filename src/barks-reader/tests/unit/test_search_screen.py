# ruff: noqa: SLF001

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar, cast
from unittest.mock import MagicMock, patch

from barks_reader.ui import search_screen
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


class TestSearchInputEnter:
    """Enter in a search input focuses the first title-result row (any mode)."""

    @staticmethod
    def _enter_ready_screen(mode: str) -> SearchScreen:
        screen = _make_bare_screen()
        screen._active_mode = mode
        screen._nav_active = True
        screen.on_request_nav_focus = None
        screen._nav_focus_area = "input"
        screen._nav_focused_result_idx = 3
        screen._nav_word_sub_focus = "speech"
        return screen

    def test_enter_with_rows_focuses_first_row(self) -> None:
        screen = self._enter_ready_screen("Title")

        with (
            patch.object(SearchScreen, "_get_active_result_rows", return_value=[_fake_row(0)]),
            patch.object(SearchScreen, "_blur_all_inputs") as blur,
            patch.object(SearchScreen, "_draw_result_focus") as draw,
        ):
            screen.on_search_input_enter()

        assert screen._nav_focus_area == "results"
        assert screen._nav_focused_result_idx == 0
        assert screen._nav_word_sub_focus == "title"
        blur.assert_called_once()
        draw.assert_called_once()

    def test_enter_with_chips_auto_picks_first_chip_and_stays_on_chips(self) -> None:
        screen = self._enter_ready_screen("Tag")
        screen._selected_tag = ""
        screen._selected_member = ""
        screen._nav_focused_chip_idx = 5
        chip = MagicMock()
        chip.text = "Duckburg"
        chip.trigger_action.side_effect = (
            lambda duration: setattr(screen, "_selected_tag", "Duckburg")  # noqa: ARG005
        )

        with (
            patch.object(SearchScreen, "_get_active_chip_buttons", return_value=[chip]),
            patch.object(SearchScreen, "_blur_all_inputs") as blur,
            patch.object(SearchScreen, "_draw_chip_focus") as draw,
            patch.object(search_screen.Clock, "schedule_once", side_effect=lambda cb, *_a: cb(0)),
        ):
            screen.on_search_input_enter()

        chip.trigger_action.assert_called_once_with(duration=0)
        assert screen._nav_focus_area == "tags"
        assert screen._nav_focused_chip_idx == 0
        blur.assert_called_once()
        draw.assert_called_once()

    def test_enter_with_selected_chip_focuses_it_without_picking_again(self) -> None:
        screen = self._enter_ready_screen("Word")
        screen._selected_word = "squash"
        chips = [MagicMock(), MagicMock()]
        chips[0].text = "squab"
        chips[1].text = "squash"

        with (
            patch.object(SearchScreen, "_get_active_chip_buttons", return_value=chips),
            patch.object(SearchScreen, "_blur_all_inputs"),
            patch.object(SearchScreen, "_draw_chip_focus") as draw,
            patch.object(search_screen.Clock, "schedule_once", side_effect=lambda cb, *_a: cb(0)),
        ):
            screen.on_search_input_enter()

        for chip in chips:
            chip.trigger_action.assert_not_called()
        assert screen._nav_focus_area == "tags"
        assert screen._nav_focused_chip_idx == 1
        draw.assert_called_once()

    def test_enter_with_no_rows_and_no_chips_is_a_no_op(self) -> None:
        screen = self._enter_ready_screen("Word")

        with (
            patch.object(SearchScreen, "_get_active_result_rows", return_value=[]),
            patch.object(SearchScreen, "_get_active_chip_buttons", return_value=[]),
            patch.object(SearchScreen, "_blur_all_inputs") as blur,
            patch.object(SearchScreen, "_draw_result_focus") as draw,
        ):
            screen.on_search_input_enter()

        assert screen._nav_focus_area == "input"
        blur.assert_not_called()
        draw.assert_not_called()

    def test_enter_with_nav_inactive_requests_nav_focus(self) -> None:
        screen = self._enter_ready_screen("Title")
        screen._nav_active = False
        exit_cb = MagicMock()
        screen.on_request_nav_focus = MagicMock(side_effect=lambda: screen.adopt_nav_focus(exit_cb))

        with (
            patch.object(SearchScreen, "_get_active_result_rows", return_value=[_fake_row(0)]),
            patch.object(SearchScreen, "_blur_all_inputs"),
            patch.object(SearchScreen, "_draw_result_focus"),
        ):
            screen.on_search_input_enter()

        screen.on_request_nav_focus.assert_called_once_with()
        assert screen._nav_active is True
        assert screen._nav_on_exit_request is exit_cb
        assert screen._nav_focus_area == "results"


class TestAdoptNavFocus:
    """adopt_nav_focus activates nav without stomping the screen's focus state."""

    def test_sets_active_and_exit_request_only(self) -> None:
        screen = _make_bare_screen()
        screen._nav_active = False
        screen._nav_on_exit_request = None
        screen._nav_focus_area = "results"
        exit_cb = MagicMock()

        screen.adopt_nav_focus(exit_cb)

        assert screen._nav_active is True
        assert screen._nav_on_exit_request is exit_cb
        assert screen._nav_focus_area == "results"
