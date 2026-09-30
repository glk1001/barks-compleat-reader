# ruff: noqa: SLF001
# cspell:ignore scroge

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_tags import Tags
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.search_evaluate import Suggestion, WordQueryResult
from barks_fantagraphics.search_filters import SearchFilter
from barks_fantagraphics.search_results import PageInfo, SpeechInfo, TitleInfo
from barks_fantagraphics.search_terms import TermMatches
from barks_fantagraphics.tag_query import ParsedTagQuery, TagMatch, TagSelection
from barks_reader.core import log_markers
from barks_reader.core.search_state import EraChoice, TagBasket, WordBasket
from barks_reader.ui import search_screen
from barks_reader.ui.reader_keyboard_nav import KEY_ESCAPE
from barks_reader.ui.search_chip_row import ChipRow
from barks_reader.ui.search_screen import (
    SearchScreen,
    _NoticeLabel,
    _PlusButton,
    _QueryRowButton,
    _SearchResultButton,
    _SuggestionButton,
    _TagQueryChip,
    _TagRow,
    _WordRow,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


def _make_bare_screen() -> SearchScreen:
    """Create a SearchScreen with no state, for exercising individual methods."""
    with patch.object(SearchScreen, "__init__", lambda _self, *_a, **_kw: None):
        screen = SearchScreen.__new__(SearchScreen)
    # The word search's typed-query state, which every word path reads: none yet.
    screen._word_query = ""
    screen._word_query_result = None
    screen._box_query = ""
    # The speaker row over a stand-in layout, its chips stand-ins too (`_speaker_chip`).
    screen._speaker_row = ChipRow(MagicMock(), _speaker_chip, screen._on_speaker_chip_selected)
    # The picked words: none, and their row, likewise over stand-ins.
    screen._word_basket = WordBasket()
    screen._basket_row = ChipRow(MagicMock(), _live_chip, screen._on_basket_chip_picked)
    screen._basket_results = False
    screen._nav_list_sub = "word"
    # The picked tags: none, likewise.
    screen._tag_basket = TagBasket()
    screen._tag_basket_row = ChipRow(MagicMock(), _live_chip, screen._on_tag_basket_chip_picked)
    screen._tag_basket_results = False
    screen._tag_box_query = ""
    # The era: all years, a row in each results panel, over stand-ins.
    screen._listed_tag = ""
    screen._era = EraChoice(ERA_RANGES)
    screen._era_rows = {
        mode: ChipRow(MagicMock(), _live_chip, screen._on_era_selected) for mode in ("Tag", "Word")
    }
    for row in screen._era_rows.values():
        row.set_options(screen._era.options())
    return screen


ERA_RANGES = ((1942, 1946), (1951, 1954))
PIRATE_GOLD = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD  # submitted 1942
HELMET = Titles.GOLDEN_HELMET_THE  # submitted 1951


def _speaker_chip(value: str, label: str) -> MagicMock:
    chip = MagicMock()
    chip.value = value
    chip.text = label
    return chip


def _live_chip(value: str, label: str) -> MagicMock:
    """Return a stand-in chip whose trigger_action releases it, as a Kivy button's does."""
    chip = _speaker_chip(value, label)
    chip.trigger_action.side_effect = lambda duration=0: _press(chip)  # noqa: ARG005
    return chip


def _press(chip: MagicMock) -> None:
    """Release a stand-in chip as a click does: run the handler the row bound to it."""
    chip.bind.call_args.kwargs["on_release"](chip)


def _offer_speakers(screen: SearchScreen, selected: str = "") -> list[MagicMock]:
    """Give the screen's speaker row All, Donald and Scrooge, with `selected` picked."""
    screen._speaker_row.set_options([("", "All"), ("Donald", "Donald"), ("Scrooge", "Scrooge")])
    screen._speaker_row.set_selected(selected)
    return cast("list[MagicMock]", screen._speaker_row.chips)


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


class TestWordList:
    """The word box lists what the search facade matches (the rules: test_search_terms.py)."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._search = MagicMock()
            bare._speaker_chips_built = True
            yield bare

    @staticmethod
    def _rows(screen: SearchScreen) -> list[Any]:
        return [c.args[0] for c in screen.ids.word_chips_layout.add_widget.call_args_list]

    def test_the_facade_s_words_are_the_rows(self, screen: SearchScreen) -> None:
        screen._search.get_words_matching.return_value = TermMatches(["don", "abandon"], 2)
        with patch.object(screen, "_on_word_chip_selected") as picked:
            screen.on_word_search_text("don")
        screen._search.get_words_matching.assert_called_once_with("don")
        assert [r.word_button.text for r in self._rows(screen)] == ["don", "abandon"]
        assert [r.plus_button.text for r in self._rows(screen)] == ["+", "+"]
        picked.assert_not_called()

    def test_a_lone_match_is_picked(self, screen: SearchScreen) -> None:
        screen._search.get_words_matching.return_value = TermMatches(["airline"], 1)
        with patch.object(screen, "_on_word_chip_selected") as picked:
            screen.on_word_search_text("airline")
        picked.assert_called_once_with("airline")

    def test_a_capped_list_ends_with_a_disabled_count_row(self, screen: SearchScreen) -> None:
        screen._search.get_words_matching.return_value = TermMatches(["gold", "golden"], 40)
        screen.on_word_search_text("gol")
        rows = self._rows(screen)
        assert [r.disabled for r in rows] == [False, False, True]
        assert rows[-1].text.startswith("... 38 more")

    def test_the_keyboard_walk_skips_the_count_row(self, screen: SearchScreen) -> None:
        words = [_SearchResultButton(text=w) for w in ("gold", "golden")]
        more = _SearchResultButton(text="... 38 more", disabled=True)
        screen.ids.word_chips_layout.children = [more, *reversed(words)]  # Kivy: last first
        assert screen._get_word_chip_buttons() == words


def _found(*titles: str) -> dict[str, TitleInfo]:
    speech = SpeechInfo("1", 1, "GOLD!", "GOLD!")
    return {t: TitleInfo(1, {"001": PageInfo("3", [speech])}) for t in titles}


class TestTypedQuery:
    """Query syntax, or text no word matches, runs as a query from the word box."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Word"
            bare._search = MagicMock()
            bare._speaker_chips_built = True
            bare._selected_word = ""
            bare._word_search_results = []
            bare._selected_result_button = None
            bare._nav_active = True
            bare.on_request_nav_focus = None
            bare._nav_focus_area = "input"
            yield bare

    @staticmethod
    def _rows(screen: SearchScreen) -> list[Any]:
        return [c.args[0] for c in screen.ids.word_chips_layout.add_widget.call_args_list]

    def _run(self, screen: SearchScreen, query: str, result: WordQueryResult) -> list[Any]:
        screen._search.run_word_query.return_value = result
        screen._run_word_query(query)
        return self._rows(screen)

    @pytest.mark.parametrize(
        ("text", "matches"),
        [("gold -mine", TermMatches([], 0)), ("gold mine", TermMatches([], 0))],
    )
    def test_a_query_is_offered_as_the_first_row(
        self, screen: SearchScreen, text: str, matches: TermMatches
    ) -> None:
        screen._search.get_words_matching.return_value = matches
        screen.on_word_search_text(text)
        (row,) = self._rows(screen)
        assert isinstance(row, _QueryRowButton)
        assert row.text == f"Search for:  {text}"
        assert screen._box_query == text

    def test_query_syntax_is_offered_above_the_words_it_matches_and_none_is_picked(
        self, screen: SearchScreen
    ) -> None:
        screen._search.get_words_matching.return_value = TermMatches(["g.i."], 1)
        with patch.object(screen, "_on_word_chip_selected") as picked:
            screen.on_word_search_text("g*")
        assert [type(r) for r in self._rows(screen)] == [_QueryRowButton, _WordRow]
        picked.assert_not_called()

    def test_plain_words_that_match_are_not_a_query(self, screen: SearchScreen) -> None:
        screen._search.get_words_matching.return_value = TermMatches(["gold", "golden"], 2)
        screen.on_word_search_text("gold")
        assert not any(isinstance(r, _QueryRowButton) for r in self._rows(screen))
        assert screen._box_query == ""

    def test_return_in_the_box_runs_the_query_and_hands_on_the_keyboard(
        self, screen: SearchScreen
    ) -> None:
        screen._box_query = "gold -mine"
        with (
            patch.object(screen, "_run_word_query") as run,
            patch.object(screen, "_focus_after_query") as focus,
        ):
            screen.on_search_input_enter()
        run.assert_called_once_with("gold -mine")
        focus.assert_called_once_with()

    def test_a_query_lists_its_stories_with_counts_notices_and_suggestions(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        result = WordQueryResult(
            title_dict=_found("Story A"),
            hit_counts={"Story A": 2},
            notices=('"the" is too common to search for; left out.',),
            suggestions=(Suggestion("scroge", "Scrooge"), Suggestion("scroge", "scrounge")),
        )
        rows = self._run(screen, "the gold scroge", result)

        screen._search.run_word_query.assert_called_once_with(
            "the gold scroge", speaker=None, search_filter=None
        )
        assert [type(r) for r in rows] == [
            _QueryRowButton,
            _NoticeLabel,
            _NoticeLabel,
            _SuggestionButton,
            _SuggestionButton,
        ]
        assert rows[0].selected
        assert rows[1].text == '"the" is too common to search for; left out.'
        assert rows[2].text == 'Did you mean, for "scroge":'
        assert [r.suggestion.spelling for r in rows[3:]] == ["Scrooge", "scrounge"]
        assert screen._word_search_results[0][2] == "Story A, 3 (2)"
        assert loguru_sink[-4:] == [
            log_markers.WORD_QUERY_NOTICE.format(
                notice='"the" is too common to search for; left out.'
            ),
            log_markers.WORD_SUGGESTIONS.format(word="scroge", spellings="Scrooge, scrounge"),
            log_markers.SEARCH_WORD_RESULTS.format(count=1),
            log_markers.WORD_QUERY_RUN.format(text="the gold scroge", count=1),
        ]

    def test_text_that_does_not_parse_says_so_and_lists_the_literal_search(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        notice = "a bracket is not closed: searched for the text as it stands."
        result = WordQueryResult(
            title_dict=_found("Story A"),
            notices=(notice,),
            used_literal_fallback=True,
            error="a bracket is not closed",
            error_position=0,
        )
        rows = self._run(screen, "(gold", result)
        assert [r.text for r in rows[1:]] == [notice]
        assert (
            log_markers.WORD_QUERY_FALLBACK.format(text="(gold", error="a bracket is not closed")
            in loguru_sink
        )

    def test_a_query_that_cannot_run_shows_why(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        rows = self._run(screen, "tag:andes", WordQueryResult(error="needs a word"))
        assert [r.text for r in rows[1:]] == ["needs a word"]
        assert log_markers.WORD_QUERY_NOTICE.format(notice="needs a word") in loguru_sink
        assert loguru_sink[-1] == log_markers.WORD_QUERY_RUN.format(text="tag:andes", count=0)

    def test_a_picked_suggestion_replaces_its_word_and_runs_again(
        self, screen: SearchScreen
    ) -> None:
        screen._word_query = "scroge -gold"
        with patch.object(screen, "_run_word_query") as run:
            screen._on_suggestion_picked(Suggestion("scroge", "Scrooge"))
        assert screen.ids.word_search_input.text == "Scrooge -gold"
        run.assert_called_once_with("Scrooge -gold")

    def test_the_speaker_filter_reruns_the_query(self, screen: SearchScreen) -> None:
        chips = _offer_speakers(screen)
        screen._word_query = "gold -mine"
        with patch.object(screen, "_run_word_query") as run:
            _press(chips[2])
        run.assert_called_once_with("gold -mine", list_words=True)

    def test_the_bubbles_popup_highlights_the_query_terms(self, screen: SearchScreen) -> None:
        screen._word_query = "gold -mine"
        screen._word_query_result = WordQueryResult(highlight_terms=("gold", "gold's"))
        screen._speech_bubble_popup = MagicMock()
        screen._font_manager = MagicMock()
        with patch.object(search_screen, "show_speech_bubbles_popup") as show:
            screen._show_word_speech_bubbles("A Title", MagicMock())
        assert show.call_args.args[2] == "gold -mine"
        assert show.call_args.kwargs["highlight_terms"] == ("gold", "gold's")

    def test_a_literal_fallback_highlights_its_text_as_a_picked_word_does(
        self, screen: SearchScreen
    ) -> None:
        screen._word_query = "(gold"
        screen._word_query_result = WordQueryResult(used_literal_fallback=True)
        screen._speech_bubble_popup = MagicMock()
        screen._font_manager = MagicMock()
        with patch.object(search_screen, "show_speech_bubbles_popup") as show:
            screen._show_word_speech_bubbles("A Title", MagicMock())
        assert show.call_args.kwargs["highlight_terms"] is None

    def test_after_a_query_the_keyboard_goes_to_its_first_story(self, screen: SearchScreen) -> None:
        screen._word_search_results = [("Story A", "3", "Story A, 3 (2)", MagicMock())]
        with (
            patch.object(screen, "_blur_all_inputs"),
            patch.object(screen, "_draw_result_focus") as draw,
            patch.object(search_screen.Clock, "schedule_once", side_effect=lambda cb, *_a: cb(0)),
        ):
            screen._focus_after_query()
        assert screen._nav_focus_area == "results"
        draw.assert_called_once_with()

    def test_with_no_story_it_goes_to_the_first_suggestion(self, screen: SearchScreen) -> None:
        query_row = _QueryRowButton(text="Search for:  scroge")
        suggestion = _SuggestionButton(Suggestion("scroge", "Scrooge"), text="Scrooge")
        with (
            patch.object(screen, "_get_word_chip_buttons", return_value=[query_row, suggestion]),
            patch.object(screen, "_blur_all_inputs"),
            patch.object(screen, "_draw_chip_focus") as draw,
            patch.object(search_screen.Clock, "schedule_once", side_effect=lambda cb, *_a: cb(0)),
        ):
            screen._focus_after_query()
        assert (screen._nav_focus_area, screen._nav_focused_chip_idx) == ("tags", 1)
        draw.assert_called_once_with()

    def test_with_neither_it_goes_back_to_the_box(self, screen: SearchScreen) -> None:
        with (
            patch.object(screen, "_get_word_chip_buttons", return_value=[]),
            patch.object(screen, "_blur_all_inputs"),
            patch.object(screen, "_focus_active_input") as focus_box,
        ):
            screen._focus_after_query()
        assert screen._nav_focus_area == "input"
        focus_box.assert_called_once_with()

    def test_return_on_the_query_row_or_a_suggestion_runs_it_and_hands_on(
        self, screen: SearchScreen
    ) -> None:
        row = MagicMock(spec=_QueryRowButton)
        screen._nav_focused_chip_idx = 0
        with (
            patch.object(screen, "_clear_chip_focus"),
            patch.object(screen, "_focus_after_query") as focus,
        ):
            screen._handle_tags_enter([row])
        row.trigger_action.assert_called_once_with(duration=0)
        focus.assert_called_once_with()

    def test_left_from_the_results_lands_on_the_query_row(self, screen: SearchScreen) -> None:
        screen._word_query = "gold -mine"
        rows = [_QueryRowButton(text="Search for:  gold -mine"), _SearchResultButton(text="x")]
        with (
            patch.object(screen, "_get_word_chip_buttons", return_value=rows),
            patch.object(screen, "_draw_chip_focus"),
        ):
            screen._nav_back_to_word_chips()
        assert screen._nav_focused_chip_idx == 0

    def test_clear_forgets_the_query(self, screen: SearchScreen) -> None:
        screen._word_query, screen._box_query = "gold -mine", "gold -mine"
        screen.on_word_clear()
        assert (screen._word_query, screen._box_query, screen._word_query_result) == ("", "", None)


def _word_row(word: str, row_index: int = 0) -> _WordRow:
    return _WordRow(_SearchResultButton(text=word, row_index=row_index), _PlusButton(text="+"))


class TestWordBasket:
    """A word's + picks it to search with the others, ALL or ANY, from a row under the box."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Word"
            bare._search = MagicMock()
            bare._search.run_word_query.return_value = WordQueryResult(
                title_dict=_found("Story A"), hit_counts={"Story A": 1}
            )
            bare._speaker_chips_built = True
            bare._selected_word = ""
            bare._word_search_results = []
            bare._selected_result_button = None
            bare._nav_active = True
            bare.on_request_nav_focus = None
            bare._nav_on_exit_request = None
            bare._nav_focus_area = "tags"
            bare._nav_focused_chip_idx = 0
            bare._nav_focused_result_idx = 0
            bare._nav_word_sub_focus = "title"
            bare.rows = [_word_row("gold", 0), _word_row("golden", 1)]
            bare.ids.word_chips_layout.children = list(reversed(bare.rows))  # Kivy: last first
            yield bare

    @staticmethod
    def _basket_chips(screen: SearchScreen) -> list[MagicMock]:
        return cast("list[MagicMock]", screen._basket_row.chips)

    def test_a_words_plus_picks_it_and_runs_the_basket_beside_the_list(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        with patch.object(screen, "_list_query_words") as relist:
            screen._toggle_basket_word("gold")

        assert screen._word_basket.words == ["gold"]
        assert [(c.value, c.text) for c in self._basket_chips(screen)] == [
            ("", "ALL"),
            ("gold", "gold  \u00d7"),
        ]
        screen._search.run_word_query.assert_called_once_with(
            '"gold"', speaker=None, search_filter=None
        )
        relist.assert_not_called()  # the word list stays, to pick more from
        assert screen._basket_results
        assert screen.rows[0].plus_button.text == "\u2013"
        assert log_markers.WORD_BASKET_CHANGED.format(count=1, mode="ALL", words="gold") in (
            loguru_sink
        )
        assert loguru_sink[-1] == log_markers.WORD_QUERY_RUN.format(text='"gold"', count=1)

    def test_the_mode_chip_flips_all_and_any(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._toggle_basket_word("gold")
        screen._toggle_basket_word("golden")
        _press(self._basket_chips(screen)[0])

        assert self._basket_chips(screen)[0].text == "ANY"
        assert log_markers.WORD_BASKET_MODE.format(mode="ANY") in loguru_sink
        assert screen._search.run_word_query.call_args.args[0] == '"gold" | "golden"'

    def test_a_words_chip_takes_it_out_and_an_empty_basket_empties_the_results(
        self, screen: SearchScreen
    ) -> None:
        screen._toggle_basket_word("gold")
        _press(self._basket_chips(screen)[1])

        assert screen._word_basket.words == []
        assert screen._basket_row.chips == []
        assert (screen._basket_results, screen._word_query) == (False, "")
        assert screen.rows[0].plus_button.text == "+"

    def test_the_plus_of_a_picked_word_puts_it_back(self, screen: SearchScreen) -> None:
        screen._toggle_basket_word("gold")
        screen._toggle_basket_word("gold")
        assert screen._word_basket.words == []

    def test_typing_keeps_the_baskets_results(self, screen: SearchScreen) -> None:
        screen._toggle_basket_word("gold")
        screen.ids.word_results_layout.clear_widgets.reset_mock()
        screen._search.get_words_matching.return_value = TermMatches(["mine"], 1)
        with patch.object(screen, "_on_word_chip_selected"):
            screen.on_word_search_text("min")
        screen.ids.word_results_layout.clear_widgets.assert_not_called()
        assert screen._word_query == '"gold"'

    def test_picking_a_word_alone_ends_the_baskets_results(self, screen: SearchScreen) -> None:
        screen._toggle_basket_word("gold")
        screen._search.find_words.return_value = {}
        screen._on_word_chip_selected("golden")
        assert (screen._basket_results, screen._word_query) == (False, "")
        screen._search.find_words.assert_called_once_with("golden", speaker=None)
        assert screen._word_basket.words == ["gold"]  # still picked, for the next +

    def test_the_speaker_filter_reruns_the_basket_beside_the_list(
        self, screen: SearchScreen
    ) -> None:
        screen._toggle_basket_word("gold")
        chips = _offer_speakers(screen)
        with patch.object(screen, "_run_word_query") as run:
            _press(chips[1])
        run.assert_called_once_with('"gold"', list_words=False)

    def test_clear_empties_the_basket(self, screen: SearchScreen) -> None:
        screen._toggle_basket_word("gold")
        screen.on_word_clear()
        assert (screen._word_basket.words, screen._basket_row.chips) == ([], [])

    # --- keys ---

    def test_right_moves_to_the_plus_enter_picks_left_goes_back(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_list_sub == "plus"
        assert 'Nav focus on _PlusButton "+".' in loguru_sink

        assert screen.handle_key(search_screen.KEY_ENTER) is True
        assert screen._word_basket.words == ["gold"]
        assert screen._nav_list_sub == "plus"  # stays, to put it back or move on

        assert screen.handle_key(search_screen.KEY_LEFT) is True
        assert screen._nav_list_sub == "word"

    def test_down_keeps_to_the_plus_column(self, screen: SearchScreen) -> None:
        screen.handle_key(search_screen.KEY_RIGHT)
        screen.handle_key(search_screen.KEY_DOWN)
        assert (screen._nav_focused_chip_idx, screen._nav_list_sub) == (1, "plus")
        screen.handle_key(search_screen.KEY_ENTER)
        assert screen._word_basket.words == ["golden"]

    def test_right_from_the_plus_goes_on_to_the_speakers_or_the_era_row(
        self, screen: SearchScreen
    ) -> None:
        screen.handle_key(search_screen.KEY_RIGHT)
        assert screen.handle_key(search_screen.KEY_RIGHT) is True  # no speakers here
        assert (screen._nav_focus_area, screen._nav_list_sub) == ("era", "word")

    def test_up_from_the_first_word_is_the_basket_row_when_words_are_picked(
        self, screen: SearchScreen
    ) -> None:
        screen._toggle_basket_word("golden")
        assert screen.handle_key(search_screen.KEY_UP) is True
        assert (screen._nav_focus_area, screen._basket_row.focused) == ("basket", 0)

    def test_up_from_the_first_word_is_the_box_with_none_picked(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_focus_active_input"):
            assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "input"

    def test_down_from_the_box_is_the_basket_row_when_words_are_picked(
        self, screen: SearchScreen
    ) -> None:
        screen._toggle_basket_word("gold")
        screen._nav_focus_area = "input"
        with patch.object(screen, "_blur_all_inputs"):
            assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert (screen._nav_focus_area, screen._basket_row.focused) == ("basket", 0)

    def test_the_basket_rows_keys(self, screen: SearchScreen) -> None:
        screen._toggle_basket_word("gold")
        screen._toggle_basket_word("golden")
        screen._nav_enter_basket()

        assert screen.handle_key(search_screen.KEY_ENTER) is True  # ALL -> ANY, and stays
        assert (screen._nav_focus_area, screen._basket_row.focused) == ("basket", 0)
        assert screen._word_basket.combine.upper() == "ANY"

        screen.handle_key(search_screen.KEY_RIGHT)
        screen.handle_key(search_screen.KEY_RIGHT)
        assert screen.handle_key(search_screen.KEY_ENTER) is True  # golden comes out
        assert screen._word_basket.words == ["gold"]
        assert (screen._nav_focus_area, screen._basket_row.focused) == ("basket", 1)

        assert screen.handle_key(search_screen.KEY_DOWN) is True  # to the word list
        assert (screen._nav_focus_area, screen._nav_focused_chip_idx) == ("tags", 0)

        screen._nav_enter_basket()
        with patch.object(screen, "_focus_active_input"):
            assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "input"

    def test_taking_the_last_word_out_moves_the_keyboard_to_the_word_list(
        self, screen: SearchScreen
    ) -> None:
        screen._toggle_basket_word("gold")
        screen._nav_enter_basket()
        screen.handle_key(search_screen.KEY_RIGHT)
        screen.handle_key(search_screen.KEY_ENTER)
        assert screen._word_basket.words == []
        assert (screen._nav_focus_area, screen._nav_focused_chip_idx) == ("tags", 0)


def _tag(label: str, count: int = 3, *, exact: bool = False) -> TagMatch:
    return TagMatch(Tags.GYRO_GEARLOOSE, label, count, exact=exact)


class TestTagChips:
    """The chips keep the search's order, show each tag's count, and pick a whole name."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._search = MagicMock()
            bare._selected_tag = ""
            bare._current_tag = None
            yield bare

    def test_the_search_s_order_is_kept_not_resorted(self, screen: SearchScreen) -> None:
        screen._search.get_tags_matching.return_value = [_tag("Zebra"), _tag("Apple")]
        with patch.object(screen, "_rebuild_tag_chips"):
            screen.on_tag_search_text("ze")
        assert screen._tag_chip_strings == ["Zebra", "Apple"]

    @pytest.mark.parametrize(
        ("matches", "picked"),
        [
            ([_tag("Africa", exact=True), _tag("Central Africa")], "Africa"),  # whole name
            ([_tag("Duckburg")], "Duckburg"),  # the only one
            ([_tag("Daisy Duck"), _tag("Duckburg")], None),  # several, none whole
        ],
        ids=["exact", "alone", "neither"],
    )
    def test_a_whole_name_or_a_lone_tag_is_picked_as_typed(
        self, screen: SearchScreen, matches: list[TagMatch], picked: str | None
    ) -> None:
        screen._search.get_tags_matching.return_value = matches
        with (
            patch.object(screen, "_rebuild_tag_chips"),
            patch.object(screen, "_on_tag_result_selected") as select,
        ):
            screen.on_tag_search_text("text")
        if picked is None:
            select.assert_not_called()
        else:
            select.assert_called_once_with(picked)

    def test_each_chip_shows_its_count_and_keeps_its_name(self, screen: SearchScreen) -> None:
        screen._tag_chip_counts = {"Africa": 17}
        stack = screen._make_main_chip_stack(["Africa"], selected="")
        [row] = stack.children
        assert isinstance(row, _TagRow)
        assert row.chip.text == "Africa"  # picked and logged by name
        assert row.chip.count_text == "17"
        assert row.plus_button.text == "+"

    def test_listing_a_tag_s_stories_is_logged_with_their_count(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._search.resolve_tag.return_value = (Tags.GYRO_GEARLOOSE, [PIRATE_GOLD, HELMET])
        screen._search.get_title_display_strings.return_value = ["T1", "T2"]
        with (
            patch.object(screen, "_populate_title_results"),
            patch.object(screen, "_update_background_from_results"),
        ):
            screen._show_tag_titles("Gyro Gearloose")
        assert 'Tag search: "Gyro Gearloose" lists 2 stories.' in loguru_sink


def _tag_stack(*labels: str) -> MagicMock:
    """Return a stand-in tag list stack of a real row per label, as a main chip stack holds."""
    stack = MagicMock()
    rows = [
        _TagRow(search_screen._TagChipButton(text=label), _PlusButton(text="+")) for label in labels
    ]
    stack.children = list(reversed(rows))  # Kivy: last first
    stack.is_member_layout = False
    return stack


class TestTagBasket:
    """A tag's + picks it; the picked-tags row flips ALL/ANY and steps a tag to left out."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Tag"
            bare._search = MagicMock()
            bare._search.titles_for_tag_selection.return_value = [PIRATE_GOLD, HELMET]
            bare._search.get_title_display_strings.return_value = ["Story 1", "Story 2"]
            bare._search.resolve_tag.side_effect = lambda name: (
                SimpleNamespace(value=name.title()),
                [],
            )
            bare._tag_titles = []
            bare.on_search_results_title_changed = None
            bare._selected_tag = ""
            bare._selected_member = ""
            bare._current_tag = None
            bare._tag_chip_strings = []
            bare._tag_chip_counts = {}
            bare._selected_result_button = None
            bare._nav_active = True
            bare.on_request_nav_focus = None
            bare._nav_on_exit_request = None
            bare._nav_focus_area = "tags"
            bare._nav_focused_chip_idx = 0
            bare._nav_focused_result_idx = 0
            bare._nav_word_sub_focus = "title"
            bare.stack = _tag_stack("Scrooge", "Gyro")
            bare.ids.tag_chips_layout.children = [bare.stack]
            yield bare

    @staticmethod
    def _basket_chips(screen: SearchScreen) -> list[MagicMock]:
        return cast("list[MagicMock]", screen._tag_basket_row.chips)

    def test_a_tags_plus_picks_it_and_lists_the_combined_stories(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        with patch.object(screen, "_populate_title_results") as populate:
            screen._toggle_tag_basket("Scrooge")

        assert [(c.value, c.text) for c in self._basket_chips(screen)] == [
            ("", "ALL"),
            ("Scrooge", "Scrooge"),
        ]
        screen._search.titles_for_tag_selection.assert_called_once_with(TagSelection(("Scrooge",)))
        assert populate.call_args.args[1] == ["Story 1", "Story 2"]
        assert screen._tag_basket_results
        assert log_markers.TAG_BASKET_CHANGED.format(count=1, mode="ALL", tags="Scrooge") in (
            loguru_sink
        )
        assert loguru_sink[-1] == log_markers.TAG_COMBINED_RESULTS.format(tags="Scrooge", count=2)

    def test_a_picked_tags_chip_steps_it_to_left_out_then_back(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_populate_title_results"):
            screen._toggle_tag_basket("Scrooge")
            screen._toggle_tag_basket("Gyro")
            _press(self._basket_chips(screen)[2])  # Gyro: left out
            assert self._basket_chips(screen)[2].text == "not Gyro"
            selection = screen._search.titles_for_tag_selection.call_args.args[0]
            assert selection == TagSelection(("Scrooge",), ("Gyro",))
            _press(self._basket_chips(screen)[2])  # and put back
        assert [c.value for c in self._basket_chips(screen)] == ["", "Scrooge"]

    def test_the_mode_chip_flips_all_and_any(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        with patch.object(screen, "_populate_title_results"):
            screen._toggle_tag_basket("Scrooge")
            screen._toggle_tag_basket("Gyro")
            _press(self._basket_chips(screen)[0])
        assert self._basket_chips(screen)[0].text == "ANY"
        assert log_markers.TAG_BASKET_MODE.format(mode="ANY") in loguru_sink
        assert screen._search.titles_for_tag_selection.call_args.args[0].combine.upper() == "ANY"

    def test_only_left_out_tags_list_nothing_and_say_why(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_populate_title_results"):
            screen._toggle_tag_basket("Gyro")
            _press(self._basket_chips(screen)[1])
        added = [c.args[0] for c in screen.ids.tag_title_results_layout.add_widget.call_args_list]
        assert added[-1].text == "Include a tag to list stories"

    def test_the_plus_shows_what_is_picked(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_populate_title_results"):
            screen._toggle_tag_basket("Gyro")
        rows = list(reversed(screen.stack.children))
        assert [r.plus_button.text for r in rows] == ["+", "\u2013"]

    def test_emptying_the_basket_empties_the_results(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_populate_title_results"):
            screen._toggle_tag_basket("Gyro")
            screen._toggle_tag_basket("Gyro")
        assert (screen._tag_basket_results, screen._tag_titles) == (False, [])

    def test_typing_keeps_the_combined_stories(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_populate_title_results"):
            screen._toggle_tag_basket("Gyro")
        screen.ids.tag_title_results_layout.clear_widgets.reset_mock()
        screen._search.get_tags_matching.return_value = []
        screen.on_tag_search_text("sc")
        screen.ids.tag_title_results_layout.clear_widgets.assert_not_called()

    def test_picking_one_tag_alone_ends_the_combined_stories(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_populate_title_results"):
            screen._toggle_tag_basket("Gyro")
        with patch.object(screen, "_rebuild_tag_chips"), patch.object(screen, "_show_tag_titles"):
            screen._on_tag_result_selected("Scrooge")
        assert not screen._tag_basket_results

    def test_clear_empties_the_picked_tags(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_populate_title_results"):
            screen._toggle_tag_basket("Gyro")
        screen.on_tag_clear()
        assert (screen._tag_basket.tags, screen._tag_basket_row.chips) == ({}, [])

    # --- typed tags ---

    def test_typed_tags_are_offered_as_one_chip_and_logged_per_keystroke(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen.on_tag_search_text("scrooge + gy")
        assert screen._tag_box_query == "scrooge + gy"
        assert log_markers.SEARCH_TAG_RESULTS.format(count=0, text="scrooge + gy") in loguru_sink
        (stack,) = [c.args[0] for c in screen.ids.tag_chips_layout.add_widget.call_args_list]
        (chip,) = stack.children
        assert isinstance(chip, _TagQueryChip)
        assert chip.text == "Combine:  scrooge + gy"
        screen._search.get_tags_matching.assert_not_called()

    def test_return_combines_the_typed_tags_in_place_of_the_picked(
        self, screen: SearchScreen
    ) -> None:
        screen._search.parse_tag_query.return_value = ParsedTagQuery(
            TagSelection(("scrooge",), ("gyro",))
        )
        with patch.object(screen, "_populate_title_results"):
            screen._toggle_tag_basket("Donald")
            screen._tag_box_query = "scrooge -gyro"
            with patch.object(screen, "_focus_after_query") as focus:
                screen.on_search_input_enter()
        assert [(c.value, c.text) for c in self._basket_chips(screen)] == [
            ("", "ALL"),
            ("Scrooge", "Scrooge"),
            ("Gyro", "not Gyro"),
        ]
        focus.assert_called_once_with()

    def test_typed_tags_that_cannot_combine_say_why_under_their_chip(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._search.parse_tag_query.return_value = ParsedTagQuery(error="Use + or |")
        assert screen._run_tag_query("a + b | c") is False
        assert log_markers.TAG_QUERY_NOTICE.format(notice="Use + or |") in loguru_sink
        (stack,) = [c.args[0] for c in screen.ids.tag_chips_layout.add_widget.call_args_list]
        chip, notice = reversed(stack.children)
        assert (type(chip), notice.text) == (_TagQueryChip, "Use + or |")
        assert not screen._tag_basket

    # --- keys ---

    def test_right_moves_to_the_tags_plus_enter_picks_left_goes_back(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_list_sub == "plus"
        assert 'Nav focus on _PlusButton "+".' in loguru_sink
        with patch.object(screen, "_populate_title_results"):
            assert screen.handle_key(search_screen.KEY_ENTER) is True
        assert list(screen._tag_basket.tags) == ["Scrooge"]
        assert screen.handle_key(search_screen.KEY_LEFT) is True
        assert screen._nav_list_sub == "word"
        assert 'Nav focus on _TagChipButton "Scrooge".' in loguru_sink

    def test_up_from_the_first_tag_is_the_picked_tags_row(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_populate_title_results"):
            screen._toggle_tag_basket("Gyro")
        assert screen.handle_key(search_screen.KEY_UP) is True
        assert (screen._nav_focus_area, screen._tag_basket_row.focused) == ("basket", 0)
        with patch.object(screen, "_populate_title_results"):
            assert screen.handle_key(search_screen.KEY_ENTER) is True  # ALL -> ANY, stays
        assert (screen._nav_focus_area, screen._tag_basket_row.focused) == ("basket", 0)
        assert screen.handle_key(search_screen.KEY_DOWN) is True  # back to the tag list
        assert screen._nav_focus_area == "tags"


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


class TestSearchMarkers:
    """Result counts and clears are logged, so a no-match search is observable."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        """Return a bare screen with its Kivy ids and image-change timer stubbed at class level.

        A screen made without __init__ has no property storage, so `ids` cannot
        be assigned on the instance; shadowing the descriptor on the class does.
        """
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            yield _make_bare_screen()

    def test_title_results_are_counted(self, screen: SearchScreen, loguru_sink: list[str]) -> None:
        screen._search = MagicMock()
        screen._search.search.return_value = SimpleNamespace(
            titles=[], title_strings=["Vacation Time", "Vacation Misery"]
        )
        with (
            patch.object(screen, "_populate_title_results"),
            patch.object(screen, "_update_background_from_results"),
        ):
            screen.on_title_search_text("vac")
        assert "Search results: 2 titles for 'vac'." in loguru_sink

    def test_word_results_are_counted(self, screen: SearchScreen, loguru_sink: list[str]) -> None:
        screen._word_search_results = []
        screen._populate_word_results_layout(MagicMock())
        assert "Search results: 0 word rows." in loguru_sink

    def test_tag_results_are_counted_per_keystroke(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._search = MagicMock()
        screen._search.get_tags_matching.return_value = [
            TagMatch(Tags.SCROOGE_NOT_IN_US, "Scrooge", 5),
            TagMatch(Tags.GYRO_GEARLOOSE, "Scrooge's", 2),
        ]
        with (
            patch.object(screen, "_clear_tag_title_results"),
            patch.object(screen, "_rebuild_tag_chips"),
        ):
            screen.on_tag_search_text("sc")
        assert "Search results: 2 tags for 'sc'." in loguru_sink

    def test_a_single_character_tag_query_logs_nothing(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        with patch.object(screen, "_clear_tag_title_results"):
            screen.on_tag_search_text("s")
        assert not [line for line in loguru_sink if line.startswith("Search results")]

    def test_word_matches_are_counted_per_keystroke(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._speaker_chips_built = True
        screen._search = MagicMock()
        screen._search.get_words_matching.return_value = TermMatches([], 0)
        screen.on_word_search_text("air")
        assert 'Word search: "air" matched 0 words.' in loguru_sink

    def test_each_clear_button_logs(self, screen: SearchScreen, loguru_sink: list[str]) -> None:
        screen._tag_chip_strings = ["x"]
        screen._selected_member = "y"
        screen._clear_tag_title_results = MagicMock()
        screen.on_title_clear()
        screen.on_tag_clear()
        screen.on_word_clear()
        for kind in ("title", "tag", "word"):
            assert f"Search cleared: {kind}." in loguru_sink


class TestNavFocusMarkers:
    """Focus shown by colour rather than a drawn ring still logs, as does the search box."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Title"
            bare._selected_tag = ""
            bare._selected_member = ""
            yield bare

    def test_the_search_box_logs_taking_and_losing_focus(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen.on_search_input_focus(MagicMock(), focused=True)
        screen.on_search_input_focus(MagicMock(), focused=False)
        assert "SearchScreen: Title search box focused." in loguru_sink
        assert "SearchScreen: Title search box unfocused." in loguru_sink

    def test_the_clear_button_logs_its_focus(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        clear_button = MagicMock()
        clear_button.text = "x"
        with patch.object(screen, "_get_active_clear_button", return_value=clear_button):
            screen._draw_clear_focus()
        assert 'Nav focus on MagicMock "x".' in loguru_sink

    def test_a_focused_tag_chip_logs(self, screen: SearchScreen, loguru_sink: list[str]) -> None:
        chips = [MagicMock(), MagicMock()]
        chips[1].text = "Scrooge"
        with patch.object(screen, "_get_main_tag_chip_buttons", return_value=chips):
            screen._update_tag_chip_colors(cast("list", chips), focused_idx=1)
        assert 'Nav focus on MagicMock "Scrooge".' in loguru_sink

    def test_redrawing_chips_without_a_focus_logs_nothing(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        chips = [MagicMock()]
        with patch.object(screen, "_get_main_tag_chip_buttons", return_value=chips):
            screen._update_tag_chip_colors(cast("list", chips))
        assert not [line for line in loguru_sink if line.startswith("Nav focus on")]


class TestSpeakerFilter:
    """The word search offers a who-said-it row, built from what the index knows."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Word"
            bare._search = MagicMock()
            bare._selected_word = ""
            bare._speaker_chips_built = False
            yield bare

    def test_chips_are_the_roster_speakers_the_index_has_plus_all(
        self, screen: SearchScreen
    ) -> None:
        screen._search.get_speakers.return_value = {
            "none": 900,
            "Scrooge": 50,
            "Donald": 300,
            "narrator": 40,
            "other:Witch Hazel": 12,
            "unknown": 3,
        }
        screen._build_speaker_chips()

        chips = cast("list[MagicMock]", screen._speaker_row.chips)
        # Roster order, sentinels other than the narrator left out, `other:` not offered.
        assert [(c.text, c.value) for c in chips] == [
            ("All", ""),
            ("Donald", "Donald"),
            ("Scrooge", "Scrooge"),
            ("Narrator", "narrator"),
        ]
        assert screen._speaker_chips_built is True

    def test_the_chips_are_speaker_chips(self) -> None:
        """Their class is in the focus line the app logs, which the GUI tests match."""
        chip = search_screen._make_speaker_chip("Scrooge", "Scrooge")
        assert type(chip).__name__ == "_SpeakerChipButton"
        assert (chip.value, chip.text) == ("Scrooge", "Scrooge")

    def test_index_without_speakers_offers_no_row(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._search.get_speakers.return_value = {}

        screen._build_speaker_chips()

        assert screen._speaker_row.chips == []
        assert not screen._has_speaker_row()
        assert "Word search: index has no speakers; no speaker filter." in loguru_sink

    def test_chips_are_built_once_on_the_first_word_typed(self, screen: SearchScreen) -> None:
        screen._search.get_words_matching.return_value = TermMatches([], 0)
        with patch.object(screen, "_build_speaker_chips") as build:
            screen.on_word_search_text("d")
            screen._speaker_chips_built = True
            screen.on_word_search_text("do")
        build.assert_called_once()

    def test_picking_a_speaker_reruns_the_search_filtered(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        chips = _offer_speakers(screen)
        screen._selected_word = "money"
        screen._search.find_words.return_value = {"A Title": MagicMock()}
        with (
            patch.object(screen, "_build_word_results", return_value=[]),
            patch.object(screen, "_populate_word_results_layout"),
        ):
            _press(chips[2])

        screen._search.find_words.assert_called_once_with("money", speaker="Scrooge")
        assert screen._speaker_row.selected == "Scrooge"
        assert log_markers.SPEAKER_FILTER_SET.format(speaker="Scrooge") in loguru_sink
        assert 'Word search: speaker filter "Scrooge".' in loguru_sink  # the line is unchanged

    def test_all_lifts_the_filter(self, screen: SearchScreen, loguru_sink: list[str]) -> None:
        chips = _offer_speakers(screen, selected="Scrooge")
        screen._selected_word = "money"
        screen._search.find_words.return_value = {"A Title": MagicMock()}
        with (
            patch.object(screen, "_build_word_results", return_value=[]),
            patch.object(screen, "_populate_word_results_layout"),
        ):
            _press(chips[0])

        screen._search.find_words.assert_called_once_with("money", speaker=None)
        assert log_markers.SPEAKER_FILTER_SET.format(speaker="All") in loguru_sink

    def test_no_word_picked_yet_only_records_the_choice(self, screen: SearchScreen) -> None:
        _press(_offer_speakers(screen)[1])

        screen._search.find_words.assert_not_called()
        assert screen._speaker_row.selected == "Donald"

    def test_clear_resets_the_filter(self, screen: SearchScreen) -> None:
        _offer_speakers(screen, selected="Scrooge")
        screen.on_word_clear()
        assert screen._speaker_row.selected == ""

    def test_clear_forgets_the_word_so_a_chip_cannot_revive_it(self, screen: SearchScreen) -> None:
        chips = _offer_speakers(screen)
        screen._selected_word = "money"
        screen.on_word_clear()
        _press(chips[2])

        assert screen._selected_word == ""
        screen._search.find_words.assert_not_called()

    def test_editing_the_box_forgets_the_word_so_a_chip_cannot_revive_it(
        self, screen: SearchScreen
    ) -> None:
        chips = _offer_speakers(screen)
        screen._search.get_words_matching.return_value = TermMatches([], 0)
        screen._selected_word = "money"
        screen.on_word_search_text("")
        _press(chips[2])

        assert screen._selected_word == ""
        screen._search.find_words.assert_not_called()

    def test_bubbles_popup_is_told_the_filter(self, screen: SearchScreen) -> None:
        _offer_speakers(screen, selected="Scrooge")
        screen._selected_word = "money"
        screen._speech_bubble_popup = MagicMock()
        screen._font_manager = MagicMock()
        info = MagicMock()
        with patch.object(search_screen, "show_speech_bubbles_popup") as show:
            screen._show_word_speech_bubbles("A Title", info)
        assert show.call_args.kwargs["speaker"] == "Scrooge"

    def test_bubbles_popup_gets_no_speaker_when_unfiltered(self, screen: SearchScreen) -> None:
        screen._selected_word = "money"
        screen._speech_bubble_popup = MagicMock()
        screen._font_manager = MagicMock()
        with patch.object(search_screen, "show_speech_bubbles_popup") as show:
            screen._show_word_speech_bubbles("A Title", MagicMock())
        assert show.call_args.kwargs["speaker"] is None


class TestSpeakerRowKeys:
    """The speaker row is a nav stop between the word list and the results.

    Ten-foot rule: everything below is reachable with only the arrows, Enter
    and Escape. The row's own walk is tested in test_search_chip_row.py; these
    are the ways between it and the rest of the screen.
    """

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Word"
            bare._nav_active = True
            bare._nav_on_exit_request = None
            bare._selected_word = "money"
            bare._nav_focus_area = "speakers"
            bare._nav_focused_result_idx = 0
            bare._nav_focused_chip_idx = 0
            bare._nav_word_sub_focus = "title"
            bare.chips = _offer_speakers(bare, selected="Donald")
            bare._speaker_row.enter_focus()  # on Donald, the one picked
            yield bare

    def test_right_and_left_walk_the_chips(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._speaker_row.focused == 2  # noqa: PLR2004
        assert 'Nav focus on MagicMock "Scrooge".' in loguru_sink

        assert screen.handle_key(search_screen.KEY_LEFT) is True
        assert screen._speaker_row.focused == 1

    def test_right_stops_at_the_last_chip(self, screen: SearchScreen) -> None:
        screen.handle_key(search_screen.KEY_RIGHT)
        assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._speaker_row.focused == 2  # noqa: PLR2004
        assert screen._nav_focus_area == "speakers"

    def test_left_off_the_first_chip_returns_to_the_word_list(self, screen: SearchScreen) -> None:
        screen.handle_key(search_screen.KEY_LEFT)  # on All
        word_chips = [MagicMock(text="cash"), MagicMock(text="money")]
        with (
            patch.object(screen, "_get_word_chip_buttons", return_value=word_chips),
            patch.object(screen, "_draw_chip_focus") as draw,
        ):
            assert screen.handle_key(search_screen.KEY_LEFT) is True

        assert screen._nav_focus_area == "tags"
        assert screen._nav_focused_chip_idx == 1  # back on the selected word
        assert screen._speaker_row.focused is None
        draw.assert_called_once()

    def test_left_off_the_first_chip_stays_without_a_word_list(self, screen: SearchScreen) -> None:
        screen.handle_key(search_screen.KEY_LEFT)  # on All
        with patch.object(screen, "_get_word_chip_buttons", return_value=[]):
            assert screen.handle_key(search_screen.KEY_LEFT) is True
        assert (screen._nav_focus_area, screen._speaker_row.focused) == ("speakers", 0)

    def test_enter_applies_the_focused_chip_and_stays(self, screen: SearchScreen) -> None:
        screen.handle_key(search_screen.KEY_RIGHT)  # on Scrooge
        assert screen.handle_key(search_screen.KEY_ENTER) is True
        screen.chips[2].trigger_action.assert_called_once_with(duration=0)
        assert screen._nav_focus_area == "speakers"

    def test_down_goes_to_the_era_row_under_the_speakers(self, screen: SearchScreen) -> None:
        assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert screen._nav_focus_area == "era"
        assert screen._era_rows["Word"].focused == 0  # on All years, the one picked
        assert screen._speaker_row.focused is None

    def test_up_returns_to_the_search_box(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_focus_active_input") as focus:
            assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "input"
        focus.assert_called_once()

    def test_escape_leaves_the_screen(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_nav_escape") as escape:
            assert screen.handle_key(KEY_ESCAPE) is True
        escape.assert_called_once_with()

    def test_other_keys_are_not_the_rows(self, screen: SearchScreen) -> None:
        assert screen.handle_key(ord("a")) is False

    def test_right_from_the_word_list_lands_on_the_selected_speaker(
        self, screen: SearchScreen
    ) -> None:
        screen._speaker_row.clear_focus()
        screen._nav_focus_area = "tags"
        with (
            patch.object(screen, "_get_active_chip_buttons", return_value=[MagicMock()]),
            patch.object(screen, "_clear_chip_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_focus_area == "speakers"
        assert screen._speaker_row.focused == 1  # "Donald" is selected

    def test_right_from_the_word_list_is_the_era_row_without_speakers(
        self, screen: SearchScreen
    ) -> None:
        screen._nav_focus_area = "tags"
        screen._speaker_row.set_options([])
        with (
            patch.object(screen, "_get_active_chip_buttons", return_value=[MagicMock()]),
            patch.object(screen, "_clear_chip_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_focus_area == "era"

    def test_up_from_the_first_result_climbs_to_the_era_then_the_speakers(
        self, screen: SearchScreen
    ) -> None:
        screen._speaker_row.clear_focus()
        screen._nav_focus_area = "results"
        with (
            patch.object(screen, "_get_active_result_rows", return_value=[MagicMock()]),
            patch.object(screen, "_clear_result_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "era"
        assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "speakers"
        assert screen._speaker_row.focused == 1  # Donald, the one picked

    def test_up_from_the_era_is_the_box_without_speakers(self, screen: SearchScreen) -> None:
        screen._speaker_row.set_options([])
        screen._nav_enter_era()
        with patch.object(screen, "_focus_active_input") as focus:
            assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "input"
        focus.assert_called_once_with()


class TestEra:
    """One era for both searches: it narrows what each lists, and a row in each panel picks it."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Tag"
            bare._search = MagicMock()
            bare._search.get_title_display_strings.side_effect = lambda ts: [t.name for t in ts]
            bare._tag_titles = []
            bare.on_search_results_title_changed = None
            bare._selected_tag = ""
            bare._selected_member = ""
            bare._current_tag = None
            bare._selected_word = ""
            bare._word_search_results = []
            bare._selected_result_button = None
            bare._nav_active = True
            bare.on_request_nav_focus = None
            bare._nav_on_exit_request = None
            bare._nav_focus_area = "tags"
            bare._nav_focused_chip_idx = 0
            bare._nav_focused_result_idx = 0
            bare._nav_word_sub_focus = "title"
            yield bare

    @staticmethod
    def _pick_era(screen: SearchScreen, index: int) -> None:
        _press(cast("MagicMock", screen._era_rows["Tag"].chips[index]))

    def test_a_tag_lists_only_its_stories_in_the_era(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._search.resolve_tag.return_value = (Tags.GYRO_GEARLOOSE, [PIRATE_GOLD, HELMET])
        screen._show_tag_titles("Gyro Gearloose")
        assert screen._tag_titles == [PIRATE_GOLD.name, HELMET.name]

        self._pick_era(screen, 2)  # 1951-54
        assert screen._tag_titles == [HELMET.name]  # listed again, in the era
        assert loguru_sink[-1] == log_markers.TAG_TITLES_LISTED.format(
            tag="Gyro Gearloose", count=1
        )

    def test_an_era_that_leaves_nothing_says_so(self, screen: SearchScreen) -> None:
        screen._search.resolve_tag.return_value = (Tags.GYRO_GEARLOOSE, [HELMET])
        self._pick_era(screen, 1)  # 1942-46
        screen._show_tag_titles("Gyro Gearloose")
        added = [c.args[0] for c in screen.ids.tag_title_results_layout.add_widget.call_args_list]
        assert added[-1].text == "None in 1942-46"

    def test_combined_tags_list_only_their_stories_in_the_era(self, screen: SearchScreen) -> None:
        screen._search.titles_for_tag_selection.return_value = [PIRATE_GOLD, HELMET]
        self._pick_era(screen, 1)  # 1942-46
        screen._toggle_tag_basket("Gyro")
        assert screen._tag_titles == [PIRATE_GOLD.name]

    def test_a_picked_word_lists_only_its_stories_in_the_era(self, screen: SearchScreen) -> None:
        screen._active_mode = "Word"
        screen._search.find_words.return_value = {
            ENUM_TO_STR_TITLE[PIRATE_GOLD]: TitleInfo(1),
            ENUM_TO_STR_TITLE[HELMET]: TitleInfo(11),
        }
        self._pick_era(screen, 2)  # 1951-54
        with patch.object(screen, "_list_word_stories") as listed:
            screen._show_word_results("gold")
        assert list(listed.call_args.args[0]) == [ENUM_TO_STR_TITLE[HELMET]]

    def test_a_typed_query_is_run_in_the_era(self, screen: SearchScreen) -> None:
        screen._search.run_word_query.return_value = WordQueryResult()
        self._pick_era(screen, 2)
        screen._run_word_query("gold -mine")
        assert screen._search.run_word_query.call_args.kwargs["search_filter"] == SearchFilter(
            years=(1951, 1954)
        )

    def test_picking_an_era_logs_it_shows_it_in_both_rows_and_lists_both_again(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        with (
            patch.object(screen, "_rerun_tag_results") as tags_again,
            patch.object(screen, "_rerun_word_results") as words_again,
        ):
            self._pick_era(screen, 2)
            self._pick_era(screen, 2)  # the same again: nothing to do
        assert loguru_sink.count(log_markers.ERA_FILTER_SET.format(era="1951-54")) == 1
        assert screen._era_rows["Word"].selected == "1951-1954"
        tags_again.assert_called_once_with()
        words_again.assert_called_once_with()

    @pytest.mark.parametrize("mode", ["Tag", "Word"])
    def test_clear_lifts_the_era(self, screen: SearchScreen, mode: str) -> None:
        self._pick_era(screen, 2)
        screen._active_mode = mode
        screen.on_tag_clear() if mode == "Tag" else screen.on_word_clear()
        assert (screen._era.years, screen._era_rows["Word"].selected) == (None, "")

    # --- keys, in the tag search ---

    def test_right_from_a_tag_reaches_the_era_row_down_the_stories(
        self, screen: SearchScreen
    ) -> None:
        with (
            patch.object(screen, "_get_active_chip_buttons", return_value=[MagicMock()]),
            patch.object(screen, "_clear_chip_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert (screen._nav_focus_area, screen._era_rows["Tag"].focused) == ("era", 0)
        with (
            patch.object(screen, "_get_active_result_rows", return_value=[MagicMock()]),
            patch.object(screen, "_draw_result_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert screen._nav_focus_area == "results"

    def test_the_tag_era_rows_ways_out(self, screen: SearchScreen) -> None:
        screen._nav_enter_era()
        with patch.object(screen, "_focus_active_input"):
            assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "input"

        screen._nav_enter_era()
        with (
            patch.object(screen, "_get_tag_chip_buttons", return_value=[MagicMock(text="x")]),
            patch.object(screen, "_draw_chip_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_LEFT) is True  # off All years
        assert screen._nav_focus_area == "tags"

    def test_enter_on_an_era_picks_it_and_stays(self, screen: SearchScreen) -> None:
        screen._nav_enter_era()
        screen.handle_key(search_screen.KEY_RIGHT)
        with (
            patch.object(screen, "_rerun_tag_results"),
            patch.object(screen, "_rerun_word_results"),
        ):
            assert screen.handle_key(search_screen.KEY_ENTER) is True
        assert (screen._era.label, screen._nav_focus_area) == ("1942-46", "era")
