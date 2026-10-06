# ruff: noqa: SLF001
# cspell:ignore scroge

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, ClassVar, cast
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.search_evaluate import Suggestion, WordQueryResult
from barks_fantagraphics.search_filters import SearchFilter
from barks_fantagraphics.search_results import PageInfo, SpeechInfo, TitleInfo
from barks_fantagraphics.search_terms import TermMatches
from barks_fantagraphics.tag_query import ParsedTagQuery, TagMatch, TagSelection
from barks_reader.core import log_markers
from barks_reader.core.image_selector import ImageInfo
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
    _title_detail,
    _WordRow,
)
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


def _make_bare_screen() -> SearchScreen:
    """Create a SearchScreen with no state, for exercising individual methods."""
    with patch.object(SearchScreen, "__init__", lambda _self, *_a, **_kw: None):
        screen = SearchScreen.__new__(SearchScreen)
    # The word search's typed-query state, which every word path reads: none yet.
    screen._word_query = ""
    screen._word_query_result = None
    screen._box_query = ""
    # The speaker filter: anyone; its chip's row over a stand-in layout, its chip a
    # stand-in too (`_speaker_chip`); an index with no speakers, so no chip shows
    # (`_offer_speakers` gives it some); and its list, a stand-in.
    screen._speaker = ""
    screen._speaker_row = ChipRow(MagicMock(), _speaker_chip, screen._on_said_by_chip_pressed)
    screen._offered_speakers = []
    screen._said_by_dropdown = _FakeSpeakerList(screen)
    screen._setup_dropdown_nav()
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
    # The tag list's groups, and its open subgroup: none.
    screen._tag_chip_groups = set()
    screen._open_subgroup = None
    # The era: all years, a row in each results panel, over stand-ins.
    screen._listed_tag = ""
    screen._era = EraChoice(ERA_RANGES)
    screen._era_rows = {
        mode: ChipRow(MagicMock(), _live_chip, screen._on_era_selected) for mode in ("Tag", "Word")
    }
    for row in screen._era_rows.values():
        row.set_options(screen._era.options())
    # The word search's tag scope: none offered.
    screen._scope_row = ChipRow(MagicMock(), _live_chip, screen._on_scope_selected)
    screen._scope_tags = ""
    screen._scope_titles = frozenset()
    screen._scope_counts = {}
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


class _FakeSpeakerList:
    """Stands in for the speaker filter's dropdown: holds its rows, selects and closes as Kivy's.

    A pick tells the screen, then closes the list, which tells the screen too.
    """

    def __init__(self, screen: SearchScreen) -> None:
        self._screen = screen
        self.container = SimpleNamespace(children=[])
        self.is_open = False

    @property
    def rows(self) -> list[search_screen._SaidByItem]:
        return list(reversed(self.container.children))  # Kivy: last first

    def clear_widgets(self) -> None:
        self.container.children = []

    def add_widget(self, row: search_screen._SaidByItem) -> None:
        self.container.children.insert(0, row)

    def open_if_shown(self, _widget: object) -> bool:
        self.is_open = True
        return True

    def select(self, value: str) -> None:
        self._screen._on_said_by_item_selected(cast("Any", self), value)
        self.dismiss()

    def dismiss(self) -> None:
        self.is_open = False
        self._screen._on_said_by_dismissed(cast("Any", self))


# What the speaker list counts in `_pick_speaker`: anyone, then Donald and Scrooge.
_SPEAKER_COUNTS = [("", 3), ("Donald", 2), ("Scrooge", 1)]


def _offer_speakers(screen: SearchScreen, speaker: str = "") -> None:
    """Give the screen Donald and Scrooge to offer, with `speaker` picked, and show its chip.

    The chip shows only while a word search is listed: set its word or query first.
    """
    screen._offered_speakers = ["Donald", "Scrooge"]
    screen._speaker = speaker
    screen._show_said_by_chip()


def _said_by_chip(screen: SearchScreen) -> MagicMock:
    [chip] = screen._speaker_row.chips
    return cast("MagicMock", chip)


def _pick_speaker(screen: SearchScreen, speaker: str) -> None:
    """Open the speaker list from its chip, as a click does, and click `speaker`'s row."""
    with patch.object(screen, "_speaker_story_counts", return_value=_SPEAKER_COUNTS):
        _press(_said_by_chip(screen))
    speaker_list = cast("_FakeSpeakerList", screen._said_by_dropdown)
    [row] = [r for r in speaker_list.rows if r.value == speaker]
    row.dispatch("on_release")


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
        screen._word_query = "gold -mine"
        _offer_speakers(screen)
        with patch.object(screen, "_run_word_query") as run:
            _pick_speaker(screen, "Scrooge")
        run.assert_called_once_with("gold -mine", list_words=True, new_search=False)
        assert screen._speaker == "Scrooge"

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

    def test_in_the_tag_search_it_goes_where_a_tag_query_hands_it(
        self, screen: SearchScreen
    ) -> None:
        screen._active_mode = "Tag"
        with (
            patch.object(screen, "_blur_all_inputs"),
            patch.object(screen, "_focus_after_tag_query") as after_tags,
        ):
            screen._focus_after_query()
        after_tags.assert_called_once_with()

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

    def test_a_picked_word_s_row_is_marked_selected_and_the_last_one_unmarked(
        self, screen: SearchScreen
    ) -> None:
        # Marked by `selected`, which the kv rule paints: a colour set directly was
        # painted over when a mouse click's press state lapsed.
        screen._search.find_words.return_value = {}
        screen._on_word_chip_selected("gold")
        assert [r.word_button.selected for r in screen.rows] == [True, False]
        screen._on_word_chip_selected("golden")
        assert [r.word_button.selected for r in screen.rows] == [False, True]

    def test_the_speaker_filter_reruns_the_basket_beside_the_list(
        self, screen: SearchScreen
    ) -> None:
        screen._toggle_basket_word("gold")
        _offer_speakers(screen)
        with patch.object(screen, "_run_word_query") as run:
            _pick_speaker(screen, "Donald")
        run.assert_called_once_with('"gold"', list_words=False, new_search=False)

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

    def test_right_from_the_plus_goes_on_to_the_era_row(self, screen: SearchScreen) -> None:
        screen.handle_key(search_screen.KEY_RIGHT)
        assert screen.handle_key(search_screen.KEY_RIGHT) is True
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
            bare._selected_member = ""
            bare._current_tag = None
            bare._tag_chip_counts = {}
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

    def test_a_subgroup_member_is_marked_by_its_flag_not_its_name(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        """The arrow is drawn from `is_group`: the font has none, and the name stays the tag's."""
        screen._search.get_tag_group_members.return_value = [TagGroups.AFRICA, Tags.DUCKBURG]
        screen._search.get_tag_title_count.return_value = 7
        [stack] = screen._make_member_stacks(TagGroups.COUNTRIES)
        chips = [row.chip for row in reversed(stack.children)]
        assert [(c.text, c.is_group, c.is_open) for c in chips] == [
            ("Africa", True, False),
            ("Duckburg", False, False),
        ]

        with (
            patch.object(screen, "_show_tag_titles") as listed,
            patch.object(screen, "_rebuild_tag_chips"),
        ):
            chips[0].dispatch("on_release")
        listed.assert_called_once_with("Africa")
        assert log_markers.TAG_SELECTED_MEMBER.format(member="Africa") in loguru_sink

    @staticmethod
    def _chemistry(screen: SearchScreen) -> None:
        """List chemistry, a group whose members hold a subgroup, chemical names."""
        members = {
            TagGroups.CHEMISTRY: [Tags.DUCKMITE, TagGroups.CHEMICAL_NAMES, Tags.WEEMITE],
            TagGroups.CHEMICAL_NAMES: [Tags.GYRO_GEARLOOSE, Tags.DUCKBURG],
        }
        screen._search.get_tag_group_members.side_effect = lambda group: members[group]
        screen._search.get_tag_title_count.return_value = 3
        screen._search.resolve_tag.return_value = (TagGroups.CHEMISTRY, [])
        screen._tag_chip_strings = ["chemistry"]
        screen._tag_chip_groups = {"chemistry"}

    def test_a_group_left_out_of_a_new_search_opens_no_members(self, screen: SearchScreen) -> None:
        """Typing on with a group open: the new chips list without it, and nothing opens."""
        screen._selected_tag = "Africa"
        screen._current_tag = TagGroups.AFRICA
        screen._tag_chip_strings = ["Europe", "Asia"]
        with patch.object(screen, "_make_member_stacks") as members:
            screen._rebuild_tag_chips()
        members.assert_not_called()
        [stack] = [c.args[0] for c in screen.ids.tag_chips_layout.add_widget.call_args_list]
        assert [row.chip.text for row in reversed(stack.children)] == ["Europe", "Asia"]

    def test_a_subgroup_last_in_its_group_ends_the_stacks_with_its_members(
        self, screen: SearchScreen
    ) -> None:
        members = {
            TagGroups.CHEMISTRY: [Tags.DUCKMITE, TagGroups.CHEMICAL_NAMES],
            TagGroups.CHEMICAL_NAMES: [Tags.GYRO_GEARLOOSE, Tags.DUCKBURG],
        }
        screen._search.get_tag_group_members.side_effect = lambda group: members[group]
        screen._search.get_tag_title_count.return_value = 3
        screen._open_subgroup = TagGroups.CHEMICAL_NAMES

        stacks = screen._make_member_stacks(TagGroups.CHEMISTRY)

        texts = [[row.chip.text for row in reversed(st.children)] for st in stacks]
        assert texts == [["duckmite", "chemical names"], ["Gyro Gearloose", "Duckburg"]]

    def test_a_chip_given_its_colour_keeps_it(self) -> None:
        chip = search_screen._TagChipButton(text="Africa", chip_bg_color=(0.1, 0.2, 0.3, 1))
        assert tuple(chip.chip_bg_color) == pytest.approx((0.1, 0.2, 0.3, 1))

    def test_a_picked_group_pressed_again_closes_then_opens(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        self._chemistry(screen)
        with (
            patch.object(screen, "_rebuild_tag_chips"),
            patch.object(screen, "_show_tag_titles") as listed,
        ):
            screen._on_tag_chip_pressed("chemistry")
            assert screen._current_tag is TagGroups.CHEMISTRY  # open: its members listed
            screen._on_tag_chip_pressed("chemistry")
            assert screen._current_tag is None  # closed
            assert screen._selected_tag == "chemistry"  # still picked: its stories listed
            screen._on_tag_chip_pressed("chemistry")
            assert screen._current_tag is TagGroups.CHEMISTRY  # open again
        assert [c.args[0] for c in listed.call_args_list] == ["chemistry"] * 3
        assert log_markers.TAG_GROUP_CLOSED.format(group="chemistry") in loguru_sink

    def test_a_plain_tag_pressed_again_stays_picked(self, screen: SearchScreen) -> None:
        screen._search.resolve_tag.return_value = (Tags.DUCKBURG, [])
        screen._tag_chip_strings = ["Duckburg"]
        with patch.object(screen, "_rebuild_tag_chips"), patch.object(screen, "_show_tag_titles"):
            screen._on_tag_chip_pressed("Duckburg")
            screen._on_tag_chip_pressed("Duckburg")
        assert (screen._selected_tag, screen._current_tag) == ("Duckburg", Tags.DUCKBURG)

    def test_the_open_group_s_chip_points_down(self, screen: SearchScreen) -> None:
        self._chemistry(screen)
        screen._current_tag = TagGroups.CHEMISTRY
        stack = screen._make_main_chip_stack(["chemistry"], selected="chemistry")
        [row] = stack.children
        assert (row.chip.is_group, row.chip.is_open) == (True, True)

    def test_an_open_subgroup_s_members_follow_its_chip_a_level_in(
        self, screen: SearchScreen
    ) -> None:
        self._chemistry(screen)
        screen._open_subgroup = TagGroups.CHEMICAL_NAMES
        stacks = screen._make_member_stacks(TagGroups.CHEMISTRY)
        texts = [[row.chip.text for row in reversed(st.children)] for st in stacks]
        assert texts == [
            ["duckmite", "chemical names"],
            ["Gyro Gearloose", "Duckburg"],  # chemical names', a level in
            ["weemite"],
        ]
        assert [st.padding[0] for st in stacks] == [dp(24), dp(38), dp(24)]
        assert all(st.is_member_layout for st in stacks)  # all walked as members
        [_, subgroup] = [row.chip for row in reversed(stacks[0].children)]
        assert (subgroup.is_group, subgroup.is_open) == (True, True)

    def test_a_subgroup_member_opens_then_closes(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        self._chemistry(screen)
        with (
            patch.object(screen, "_rebuild_tag_chips") as rebuilt,
            patch.object(screen, "_show_tag_titles") as listed,
        ):
            screen._on_member_chip_pressed(TagGroups.CHEMICAL_NAMES)
            assert screen._open_subgroup is TagGroups.CHEMICAL_NAMES
            screen._on_member_chip_pressed(TagGroups.CHEMICAL_NAMES)
            assert screen._open_subgroup is None
        assert rebuilt.call_count == 2  # noqa: PLR2004
        assert [c.args[0] for c in listed.call_args_list] == ["chemical names"] * 2
        assert screen._selected_member == "chemical names"  # still picked: its stories listed
        assert log_markers.TAG_GROUP_OPENED.format(group="chemical names") in loguru_sink
        assert log_markers.TAG_GROUP_CLOSED.format(group="chemical names") in loguru_sink

    def test_picking_another_tag_closes_the_open_subgroup(self, screen: SearchScreen) -> None:
        self._chemistry(screen)
        screen._open_subgroup = TagGroups.CHEMICAL_NAMES
        with patch.object(screen, "_rebuild_tag_chips"), patch.object(screen, "_show_tag_titles"):
            screen._on_tag_result_selected("chemistry")
        assert screen._open_subgroup is None

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

    def test_a_listed_story_is_gone_to_with_the_tag_that_listed_it(
        self, screen: SearchScreen
    ) -> None:
        screen._listed_tag = "first Daisy appearance"
        screen._search.resolve_tag.return_value = (Tags.FIRST_DAISY, [])
        screen.on_goto_title = MagicMock()
        screen._on_tag_result_goto_title("The Mighty Trapper")
        screen._search.resolve_tag.assert_called_once_with("first daisy appearance")
        screen.on_goto_title.assert_called_once_with("The Mighty Trapper", [Tags.FIRST_DAISY])

    def test_a_group_s_listed_story_is_gone_to_with_no_tag(self, screen: SearchScreen) -> None:
        screen._listed_tag = "Africa"
        screen._search.resolve_tag.return_value = (TagGroups.AFRICA, [])
        screen.on_goto_title = MagicMock()
        screen._on_tag_result_goto_title("Story 1")
        screen.on_goto_title.assert_called_once_with("Story 1", [])


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

    def test_a_combined_story_is_gone_to_with_the_included_tags(self, screen: SearchScreen) -> None:
        items = {
            "daisy": Tags.DAISY,
            "gyro": Tags.GYRO_GEARLOOSE,
            "scrooge": Tags.FIRST_UNCLE_SCROOGE,
        }
        screen._search.resolve_tag.side_effect = lambda name: (items[name], [])
        screen.on_goto_title = MagicMock()
        with patch.object(screen, "_populate_title_results"):
            for name in ("Gyro", "Daisy", "Scrooge"):
                screen._toggle_tag_basket(name)
            _press(self._basket_chips(screen)[3])  # Scrooge: left out
        screen._on_tag_result_goto_title("Story 1")
        screen.on_goto_title.assert_called_once_with("Story 1", [Tags.GYRO_GEARLOOSE, Tags.DAISY])

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

    def test_a_typed_year_range_is_a_chip_that_enter_takes_out(self, screen: SearchScreen) -> None:
        screen._search.parse_tag_query.return_value = ParsedTagQuery(
            TagSelection(("gyro",), years=(1950, 1955), volumes=(5, 8))
        )
        with patch.object(screen, "_populate_title_results"):
            screen._run_tag_query("gyro year:1950-55 vol:5-8")
            assert [(c.value, c.text) for c in self._basket_chips(screen)] == [
                ("", "ALL"),
                ("Gyro", "Gyro"),
                ("year:", "years 1950-55"),
                ("vol:", "vols 5-8"),
            ]
            selection = screen._search.titles_for_tag_selection.call_args.args[0]
            assert (selection.years, selection.volumes) == ((1950, 1955), (5, 8))
            _press(self._basket_chips(screen)[2])  # the years: out, not stepped on
        assert [c.value for c in self._basket_chips(screen)] == ["", "Gyro", "vol:"]
        selection = screen._search.titles_for_tag_selection.call_args.args[0]
        assert (selection.years, selection.volumes) == (None, (5, 8))

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
    """One chip, while a word search is listed, opens the list of who says it, with counts."""

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
            bare._nav_focus_area = "input"
            yield bare

    def test_the_offered_speakers_are_the_roster_ones_the_index_has(
        self, screen: SearchScreen
    ) -> None:
        screen._offered_speakers = None  # not read yet
        screen._search.get_speakers.return_value = {
            "none": 900,
            "Scrooge": 50,
            "Donald": 300,
            "narrator": 40,
            "other:Witch Hazel": 12,
            "unknown": 3,
        }
        # Roster order, sentinels other than the narrator left out, `other:` not offered.
        assert screen._get_offered_speakers() == ["Donald", "Scrooge", "narrator"]
        assert screen._get_offered_speakers() == ["Donald", "Scrooge", "narrator"]
        screen._search.get_speakers.assert_called_once_with()  # read once

    def test_the_chip_is_a_said_by_chip(self) -> None:
        """Its class is in the focus line the app logs, which the GUI tests match."""
        chip = search_screen._make_said_by_chip("said by", "Said by: anyone")
        assert type(chip).__name__ == "_SaidByChipButton"
        assert (chip.value, chip.text) == ("said by", "Said by: anyone")

    def test_an_index_without_speakers_offers_no_chip(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._offered_speakers = None
        screen._search.get_speakers.return_value = {}
        screen._selected_word = "money"
        screen._show_said_by_chip()
        assert screen._speaker_row.chips == []
        assert "speakers" not in dict(screen._panel_rows())
        assert "Word search: index has no speakers; no speaker filter." in loguru_sink

    def test_the_chip_shows_only_while_a_search_is_listed(self, screen: SearchScreen) -> None:
        _offer_speakers(screen)
        assert screen._speaker_row.chips == []  # nothing searched

        screen._selected_word = "money"
        screen._show_said_by_chip()
        assert _said_by_chip(screen).text == "Said by: anyone"
        assert screen._speaker_row.selected == ""  # not filled: no filter

        screen._speaker = "narrator"
        screen._show_said_by_chip()
        assert _said_by_chip(screen).text == "Said by: Narrator"
        assert screen._speaker_row.selected == search_screen._SAID_BY  # filled: a filter

    def test_the_list_counts_each_speakers_stories_most_first(self, screen: SearchScreen) -> None:
        screen._offered_speakers = ["Donald", "Scrooge", "Gyro", "narrator"]
        screen._selected_word = "money"
        stories = {None: 5, "Donald": 2, "Scrooge": 4, "Gyro": 0, "narrator": 2}
        screen._search.find_words.side_effect = lambda _word, speaker: {
            f"Story {i}": MagicMock() for i in range(stories[speaker])
        }
        # Gyro, who never says it, is left out; Donald before the narrator, as the roster has.
        assert screen._speaker_story_counts() == [
            ("", 5),
            ("Scrooge", 4),
            ("Donald", 2),
            ("narrator", 2),
        ]

    def test_the_picked_speaker_stays_listed_at_none(self, screen: SearchScreen) -> None:
        screen._offered_speakers = ["Donald", "Gyro"]
        screen._speaker = "Gyro"
        screen._selected_word = "money"
        screen._search.find_words.side_effect = lambda _word, speaker: (
            {} if speaker == "Gyro" else {"A Story": MagicMock()}
        )
        assert screen._speaker_story_counts() == [("", 1), ("Donald", 1), ("Gyro", 0)]

    def test_a_typed_query_is_counted_by_running_it_under_each_speaker(
        self, screen: SearchScreen
    ) -> None:
        """Not from everyone's bubbles: under a speaker, every bubble found must be theirs."""
        screen._offered_speakers = ["Donald", "Scrooge"]
        screen._word_query = "gold mine"
        stories = {None: 3, "Donald": 0, "Scrooge": 1}
        screen._search.run_word_query.side_effect = lambda _q, speaker, **_kw: WordQueryResult(
            title_dict=_found(*(f"Story {i}" for i in range(stories[speaker])))
        )
        assert screen._speaker_story_counts() == [("", 3), ("Scrooge", 1)]
        assert [c.kwargs["speaker"] for c in screen._search.run_word_query.call_args_list] == [
            None,
            "Donald",
            "Scrooge",
        ]

    def test_the_counts_are_in_the_era(self, screen: SearchScreen) -> None:
        screen._offered_speakers = ["Donald"]
        screen._selected_word = "gold"
        screen._search.find_words.return_value = _found(
            ENUM_TO_STR_TITLE[PIRATE_GOLD], ENUM_TO_STR_TITLE[HELMET]
        )
        with (
            patch.object(screen, "_rerun_word_results"),
            patch.object(screen, "_rerun_tag_results"),
        ):
            screen._set_era("1951-1954")
        assert screen._speaker_story_counts() == [("", 1), ("Donald", 1)]  # the Helmet, 1951

    def test_the_chip_opens_the_list_of_who_says_it(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._selected_word = "money"
        _offer_speakers(screen, "Donald")
        with patch.object(screen, "_speaker_story_counts", return_value=_SPEAKER_COUNTS):
            _press(_said_by_chip(screen))

        speaker_list = cast("_FakeSpeakerList", screen._said_by_dropdown)
        assert speaker_list.is_open
        assert [(r.text, r.count_text, r.selected) for r in speaker_list.rows] == [
            ("anyone", "3", False),
            ("Donald", "2", True),  # the one picked now
            ("Scrooge", "1", False),
        ]
        assert screen._speaker_row.selected == search_screen._SAID_BY  # still filled
        assert log_markers.SPEAKER_LIST_OPENED.format(count=2) in loguru_sink
        assert screen._nav_focus_area == "input"  # a click: the keyboard stays where it was

    def test_picking_a_speaker_reruns_the_search_filtered(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._selected_word = "money"
        _offer_speakers(screen)
        screen._search.find_words.return_value = {"A Title": MagicMock()}
        with (
            patch.object(screen, "_build_word_results", return_value=[]),
            patch.object(screen, "_populate_word_results_layout"),
        ):
            _pick_speaker(screen, "Scrooge")

        screen._search.find_words.assert_called_once_with("money", speaker="Scrooge")
        assert not cast("_FakeSpeakerList", screen._said_by_dropdown).is_open
        assert _said_by_chip(screen).text == "Said by: Scrooge"
        assert 'Word search: speaker filter "Scrooge".' in loguru_sink  # the line is unchanged

    def test_anyone_lifts_the_filter(self, screen: SearchScreen, loguru_sink: list[str]) -> None:
        screen._selected_word = "money"
        _offer_speakers(screen, "Scrooge")
        screen._search.find_words.return_value = {"A Title": MagicMock()}
        with (
            patch.object(screen, "_build_word_results", return_value=[]),
            patch.object(screen, "_populate_word_results_layout"),
        ):
            _pick_speaker(screen, "")

        screen._search.find_words.assert_called_once_with("money", speaker=None)
        assert screen._speaker == ""
        assert log_markers.SPEAKER_FILTER_SET.format(speaker="All") in loguru_sink

    def test_clear_resets_the_filter_and_hides_the_chip(self, screen: SearchScreen) -> None:
        screen._selected_word = "money"
        _offer_speakers(screen, "Scrooge")
        screen.on_word_clear()
        assert (screen._speaker, screen._speaker_row.chips) == ("", [])

    def test_editing_the_box_hides_the_chip_with_the_results(self, screen: SearchScreen) -> None:
        screen._selected_word = "money"
        _offer_speakers(screen, "Scrooge")
        screen._search.get_words_matching.return_value = TermMatches([], 0)
        screen.on_word_search_text("mon")
        assert screen._speaker_row.chips == []
        assert screen._speaker == "Scrooge"  # kept for the next word

    def test_the_list_closes_with_the_screen(self, screen: SearchScreen) -> None:
        screen._selected_word = "money"
        _offer_speakers(screen)
        with patch.object(screen, "_speaker_story_counts", return_value=_SPEAKER_COUNTS):
            _press(_said_by_chip(screen))
        screen.on_is_visible(screen, value=False)
        assert not cast("_FakeSpeakerList", screen._said_by_dropdown).is_open

    @staticmethod
    def _stories_by(says: dict[str | None, int]) -> object:
        """Return a find_words stand-in: so many stories for each speaker (None: anyone)."""
        return lambda _word, speaker: {f"Story {i}": MagicMock() for i in range(says[speaker])}

    @pytest.mark.parametrize(
        ("says", "speaker_after", "stories"),
        [
            ({"Gladstone": 0, None: 4}, "", 4),  # he never says it, others do: lifted
            ({"Gladstone": 2, None: 4}, "Gladstone", 2),  # he says it: kept
            ({"Gladstone": 0, None: 0}, "Gladstone", 0),  # nobody says it: not his doing
        ],
        ids=["lifted", "kept", "nobody"],
    )
    def test_a_new_word_keeps_the_speaker_only_if_they_say_it(
        self,
        screen: SearchScreen,
        loguru_sink: list[str],
        says: dict[str | None, int],
        speaker_after: str,
        stories: int,
    ) -> None:
        screen._speaker = "Gladstone"
        screen._search.find_words.side_effect = self._stories_by(says)
        with patch.object(screen, "_list_word_stories") as listed:
            screen._on_word_chip_selected("bumps-a-daisy")
        assert screen._speaker == speaker_after
        assert len(listed.call_args.args[0]) == stories
        lifted = log_markers.SPEAKER_FILTER_LIFTED.format(speaker="Gladstone", text="bumps-a-daisy")
        assert (lifted in loguru_sink) == (speaker_after == "")

    def test_a_filter_changed_under_the_same_word_is_never_lifted(
        self, screen: SearchScreen
    ) -> None:
        """An era or scope the speaker says none of lists nothing, as asked."""
        screen._speaker = "Gladstone"
        screen._selected_word = "bumps-a-daisy"
        screen._search.find_words.side_effect = self._stories_by({"Gladstone": 0, None: 4})
        with patch.object(screen, "_list_word_stories") as listed:
            screen._rerun_word_results()
        assert screen._speaker == "Gladstone"
        assert listed.call_args.args[0] == {}

    def test_a_new_query_the_speaker_says_none_of_lifts_the_filter(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._speaker = "Gladstone"
        screen._search.run_word_query.side_effect = lambda _q, speaker, **_kw: WordQueryResult(
            title_dict=_found() if speaker else _found("Story A", "Story B")
        )
        with patch.object(screen, "_list_query_words"), patch.object(screen, "_list_word_stories"):
            screen._run_word_query("bumps-a-daisy AND hat")
        assert screen._speaker == ""
        assert log_markers.WORD_QUERY_RUN.format(text="bumps-a-daisy AND hat", count=2) in (
            loguru_sink
        )

    def test_a_new_query_nobody_says_keeps_the_speaker(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        """Not the speaker's doing: lifting the filter would find nothing either."""
        screen._speaker = "Gladstone"
        screen._search.run_word_query.return_value = WordQueryResult(title_dict=_found())
        with patch.object(screen, "_list_query_words"), patch.object(screen, "_list_word_stories"):
            screen._run_word_query("bumps-a-daisy AND hat")
        assert screen._speaker == "Gladstone"
        assert screen._search.run_word_query.call_count == 2  # noqa: PLR2004
        assert not any(line.startswith("Speaker filter lifted") for line in loguru_sink)

    def test_bubbles_popup_is_told_the_filter(self, screen: SearchScreen) -> None:
        screen._speaker = "Scrooge"
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


class TestSpeakerChipKeys:
    """The speaker chip is a nav stop between the word list and the results; Enter opens its list.

    Ten-foot rule: everything below is reachable with only the arrows, Enter
    and Escape.
    """

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
            patch.object(SearchScreen, "_speaker_story_counts", return_value=_SPEAKER_COUNTS),
            patch.object(SearchScreen, "_rerun_word_results"),
        ):
            bare = _make_bare_screen()
            # A chip that Enter presses, as a Kivy button's trigger_action does.
            bare._speaker_row = ChipRow(MagicMock(), _live_chip, bare._on_said_by_chip_pressed)
            bare._active_mode = "Word"
            bare._nav_active = True
            bare._nav_on_exit_request = None
            bare._selected_word = "money"
            bare._nav_focused_result_idx = 0
            bare._nav_focused_chip_idx = 0
            bare._nav_word_sub_focus = "title"
            _offer_speakers(bare, "Donald")
            bare._nav_focus_area = "speakers"
            bare._speaker_row.enter_focus()
            yield bare

    @staticmethod
    def _list(screen: SearchScreen) -> _FakeSpeakerList:
        return cast("_FakeSpeakerList", screen._said_by_dropdown)

    def test_enter_opens_the_list_on_the_speaker_picked_now(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        assert screen.handle_key(search_screen.KEY_ENTER) is True
        assert self._list(screen).is_open
        assert screen._nav_focus_area == "said_by_list"
        assert screen._dropdown_focused_idx == 1  # Donald
        assert screen._speaker_row.focused is None
        assert loguru_sink[-1] == 'Nav focus on _SaidByItem "Donald".'

    def test_down_and_enter_pick_a_speaker_and_return_to_the_chip(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen.handle_key(search_screen.KEY_ENTER)
        assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert loguru_sink[-1] == 'Nav focus on _SaidByItem "Scrooge".'
        assert screen.handle_key(search_screen.KEY_ENTER) is True

        assert screen._speaker == "Scrooge"
        assert log_markers.SPEAKER_FILTER_SET.format(speaker="Scrooge") in loguru_sink
        assert not self._list(screen).is_open
        assert (screen._nav_focus_area, screen._speaker_row.focused) == ("speakers", 0)
        assert _said_by_chip(screen).text == "Said by: Scrooge"

    def test_escape_closes_the_list_and_keeps_the_filter(self, screen: SearchScreen) -> None:
        screen.handle_key(search_screen.KEY_ENTER)
        screen.handle_key(search_screen.KEY_DOWN)
        assert screen.handle_key(KEY_ESCAPE) is True
        assert screen._speaker == "Donald"
        assert not self._list(screen).is_open
        assert (screen._nav_focus_area, screen._speaker_row.focused) == ("speakers", 0)

    def test_the_open_list_keeps_every_key(self, screen: SearchScreen) -> None:
        screen.handle_key(search_screen.KEY_ENTER)
        for key in (search_screen.KEY_LEFT, search_screen.KEY_RIGHT, ord("a")):
            assert screen.handle_key(key) is True
        assert screen._nav_focus_area == "said_by_list"

    def test_right_stays_on_the_chip(self, screen: SearchScreen) -> None:
        assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert (screen._nav_focus_area, screen._speaker_row.focused) == ("speakers", 0)

    def test_left_returns_to_the_word_list(self, screen: SearchScreen) -> None:
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

    def test_left_stays_without_a_word_list(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_get_word_chip_buttons", return_value=[]):
            assert screen.handle_key(search_screen.KEY_LEFT) is True
        assert (screen._nav_focus_area, screen._speaker_row.focused) == ("speakers", 0)

    def test_down_goes_to_the_stories_under_the_chip(self, screen: SearchScreen) -> None:
        with (
            patch.object(screen, "_get_active_result_rows", return_value=[MagicMock()]),
            patch.object(screen, "_draw_result_focus") as draw,
        ):
            assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert screen._nav_focus_area == "results"
        assert screen._speaker_row.focused is None
        draw.assert_called_once_with()

    def test_up_goes_to_the_era_row_over_the_chip(self, screen: SearchScreen) -> None:
        assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "era"
        assert screen._era_rows["Word"].focused == 0  # on All years, the one picked
        assert screen._speaker_row.focused is None

    def test_escape_leaves_the_screen(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_nav_escape") as escape:
            assert screen.handle_key(KEY_ESCAPE) is True
        escape.assert_called_once_with()

    def test_other_keys_are_not_the_chips(self, screen: SearchScreen) -> None:
        assert screen.handle_key(ord("a")) is False

    @pytest.mark.parametrize("has_chip", [True, False], ids=["chip", "no-chip"])
    def test_right_from_the_word_list_lands_on_the_era_row_first(
        self, screen: SearchScreen, has_chip: bool
    ) -> None:
        screen._speaker_row.clear_focus()
        if not has_chip:
            screen._speaker_row.set_options([])
        screen._nav_focus_area = "tags"
        with (
            patch.object(screen, "_get_active_chip_buttons", return_value=[MagicMock()]),
            patch.object(screen, "_clear_chip_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert (screen._nav_focus_area, screen._era_rows["Word"].focused) == ("era", 0)

    def test_down_from_the_era_is_the_chip(self, screen: SearchScreen) -> None:
        screen._speaker_row.clear_focus()
        screen._nav_enter_era()
        assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert (screen._nav_focus_area, screen._speaker_row.focused) == ("speakers", 0)

    def test_up_from_the_first_result_climbs_to_the_chip_then_the_era(
        self, screen: SearchScreen
    ) -> None:
        screen._speaker_row.clear_focus()
        screen._nav_focus_area = "results"
        with (
            patch.object(screen, "_get_active_result_rows", return_value=[MagicMock()]),
            patch.object(screen, "_clear_result_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_UP) is True
        assert (screen._nav_focus_area, screen._speaker_row.focused) == ("speakers", 0)
        assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "era"

    def test_up_from_the_era_is_the_box(self, screen: SearchScreen) -> None:
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


class TestTagScope:
    """The word search can be limited to the stories of the tags the tag search selected."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Word"
            bare._search = MagicMock()
            bare._search.resolve_tag.return_value = (Tags.GYRO_GEARLOOSE, [PIRATE_GOLD, HELMET])
            bare._search.titles_for_tag_selection.return_value = [HELMET]
            bare._search.run_word_query.return_value = WordQueryResult()
            # A word listed in two stories, one of them the tag's: the scope would narrow.
            bare._selected_word = "gold"
            bare._search.find_words.return_value = {
                ENUM_TO_STR_TITLE[HELMET]: TitleInfo(11, {"3": PageInfo("3", [])}),
                ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]: TitleInfo(7, {"5": PageInfo("5", [])}),
            }
            bare._word_search_results = []
            bare._selected_result_button = None
            bare.on_search_results_title_changed = None
            bare._nav_active = True
            bare.on_request_nav_focus = None
            bare._nav_on_exit_request = None
            bare._nav_focus_area = "era"
            bare._nav_focused_chip_idx = 0
            bare._nav_focused_result_idx = 0
            bare._nav_word_sub_focus = "title"
            yield bare

    @staticmethod
    def _scope_chips(screen: SearchScreen) -> list[MagicMock]:
        return cast("list[MagicMock]", screen._scope_row.chips)

    def test_no_tags_selected_offers_no_scope(self, screen: SearchScreen) -> None:
        screen._refresh_tag_scope()
        assert screen._scope_row.chips == []
        assert "scope" not in dict(screen._panel_rows())

    def test_the_tag_listed_alone_is_offered(self, screen: SearchScreen) -> None:
        screen._listed_tag = "Gyro Gearloose"
        screen._refresh_tag_scope()
        assert [(c.value, c.text) for c in self._scope_chips(screen)] == [
            ("", "Everywhere"),
            ("tags", "Only in: Gyro Gearloose"),
        ]
        assert screen._scope_titles == frozenset(
            ENUM_TO_STR_TITLE[t] for t in (PIRATE_GOLD, HELMET)
        )
        assert screen._scope_row.selected == ""  # offered, not in force

    def test_picked_tags_come_before_the_one_listed(self, screen: SearchScreen) -> None:
        screen._listed_tag = "Gyro Gearloose"
        screen._tag_basket.toggle("Scrooge")
        screen._tag_basket.toggle("Christmas")
        screen._tag_basket.cycle("Christmas")
        screen._refresh_tag_scope()
        assert self._scope_chips(screen)[1].text == "Only in: Scrooge -Christmas"
        assert screen._scope_titles == frozenset({ENUM_TO_STR_TITLE[HELMET]})

    def test_a_long_selection_is_shortened_on_its_chip(self, screen: SearchScreen) -> None:
        for tag in ("Scrooge", "Gyro Gearloose", "The Beagle Boys", "Gladstone"):
            screen._tag_basket.toggle(tag)
        screen._refresh_tag_scope()
        label = self._scope_chips(screen)[1].text
        assert label.startswith("Only in: Scrooge")
        assert label.endswith("…")
        assert len(label) <= 40  # noqa: PLR2004

    def test_only_in_limits_a_typed_query_and_a_picked_word(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._listed_tag = "Gyro Gearloose"
        screen._refresh_tag_scope()
        screen._word_query = "gold -mine"
        _press(self._scope_chips(screen)[1])

        titles = frozenset(ENUM_TO_STR_TITLE[t] for t in (PIRATE_GOLD, HELMET))
        listing = screen._search.run_word_query.call_args_list[0]  # then the row's count
        assert listing.kwargs["search_filter"] == SearchFilter(tag_titles=titles)
        assert log_markers.WORD_TAG_FILTER_SET.format(tags="Gyro Gearloose") in loguru_sink

        screen._word_query = ""
        screen._search.find_words.return_value = {
            ENUM_TO_STR_TITLE[HELMET]: TitleInfo(11),
            ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]: TitleInfo(7),
        }
        with patch.object(screen, "_list_word_stories") as listed:
            screen._show_word_results("gold")
        assert list(listed.call_args.args[0]) == [ENUM_TO_STR_TITLE[HELMET]]

    def test_the_scope_and_the_era_filter_together(self, screen: SearchScreen) -> None:
        screen._listed_tag = "Gyro Gearloose"
        screen._refresh_tag_scope()
        _press(self._scope_chips(screen)[1])
        screen._era.select("1951-1954")
        assert screen._word_search_filter() == SearchFilter(
            years=(1951, 1954), tag_titles=screen._scope_titles
        )

    def test_everywhere_lifts_the_limit(self, screen: SearchScreen, loguru_sink: list[str]) -> None:
        screen._listed_tag = "Gyro Gearloose"
        screen._refresh_tag_scope()
        _press(self._scope_chips(screen)[1])
        _press(self._scope_chips(screen)[0])
        assert screen._word_search_filter() is None
        assert log_markers.WORD_TAG_FILTER_SET.format(tags="Everywhere") in loguru_sink

    def test_a_scope_in_force_follows_the_tags_or_lifts_with_them(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._listed_tag = "Gyro Gearloose"
        screen._refresh_tag_scope()
        _press(self._scope_chips(screen)[1])
        screen._tag_basket.toggle("Scrooge")  # picked since: the scope follows
        with patch.object(screen, "_rerun_word_results") as again:
            screen._refresh_tag_scope()
        again.assert_called_once_with()
        assert screen._scope_titles == frozenset({ENUM_TO_STR_TITLE[HELMET]})

        screen._tag_basket.clear()
        screen._listed_tag = ""
        with patch.object(screen, "_rerun_word_results") as again:
            screen._refresh_tag_scope()
        again.assert_called_once_with()
        assert (screen._scope_row.chips, screen._word_search_filter()) == ([], None)
        assert loguru_sink[-1] == log_markers.WORD_TAG_FILTER_SET.format(tags="Everywhere")

    def test_entering_the_word_search_refreshes_the_scope(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_refresh_tag_scope") as refresh:
            screen.set_mode("Word")
            screen.set_mode("Tag")
        refresh.assert_called_once_with()

    @staticmethod
    def _found_in(*titles: Titles) -> dict[str, TitleInfo]:
        return {ENUM_TO_STR_TITLE[t]: TitleInfo(1, {"1": PageInfo("1", [])}) for t in titles}

    @pytest.mark.parametrize(
        ("found", "offered"),
        [
            ((HELMET, Titles.LOST_IN_THE_ANDES), True),  # the tag's and another: it narrows
            ((HELMET, PIRATE_GOLD), False),  # all the tag's: Only in would change nothing
            ((Titles.LOST_IN_THE_ANDES,), False),  # none the tag's: Only in would list nothing
        ],
        ids=["some", "all", "none"],
    )
    def test_the_scope_is_offered_only_while_it_would_narrow_the_list(
        self, screen: SearchScreen, found: tuple[Titles, ...], *, offered: bool
    ) -> None:
        screen._listed_tag = "Gyro Gearloose"  # tags Pirate Gold and the Helmet
        screen._search.find_words.return_value = self._found_in(*found)
        screen._refresh_tag_scope()
        assert bool(screen._scope_row.chips) is offered
        assert ("scope" in dict(screen._panel_rows())) is offered

    def test_each_choice_counts_its_stories(self, screen: SearchScreen) -> None:
        screen._listed_tag = "Gyro Gearloose"
        screen._refresh_tag_scope()
        assert screen._scope_counts == {"": 2, "tags": 1}  # the fixture's word: 2, 1 the tag's
        chip = screen._make_scope_chip("tags", "Only in: Gyro Gearloose")
        assert (type(chip).__name__, chip.text, chip.count_text) == (
            "_ScopeChipButton",
            "Only in: Gyro Gearloose",
            "1",
        )

    def test_a_scope_in_force_stays_offered_when_it_no_longer_narrows(
        self, screen: SearchScreen
    ) -> None:
        """So it can be lifted: a new word all of whose stories are the tag's."""
        screen._listed_tag = "Gyro Gearloose"
        screen._refresh_tag_scope()
        _press(self._scope_chips(screen)[1])
        screen._search.find_words.return_value = self._found_in(HELMET, PIRATE_GOLD)
        screen._show_scope_row()
        assert [c.value for c in self._scope_chips(screen)] == ["", "tags"]

    def test_the_chip_the_keyboard_is_on_keeps_it_when_the_row_is_relisted(
        self, screen: SearchScreen
    ) -> None:
        screen._listed_tag = "Gyro Gearloose"
        screen._refresh_tag_scope()
        screen._scope_row.enter_focus(1)
        screen._show_scope_row()
        assert screen._scope_row.focused == 1

    @pytest.mark.parametrize("how", ["box emptied", "clear button", "picked words emptied"])
    def test_the_scope_goes_with_the_results_it_counted(
        self, screen: SearchScreen, how: str
    ) -> None:
        """Its chips and counts are the listed search's: when that empties, so does the row."""
        screen._listed_tag = "Gyro Gearloose"
        screen._refresh_tag_scope()
        assert screen._scope_row.chips  # offered, with its counts
        screen._search.get_words_matching.return_value = TermMatches([], 0)
        if how == "box emptied":
            screen.on_word_search_text("")
        elif how == "clear button":
            screen.on_word_clear()
        else:
            screen._selected_word = ""
            screen._word_query = '"gold"'  # the picked words' query, its last word then taken out
            screen._basket_results = True
            screen._run_basket()
        assert screen._scope_row.chips == []

    def test_nothing_searched_offers_no_scope(self, screen: SearchScreen) -> None:
        screen._listed_tag = "Gyro Gearloose"
        screen._selected_word = ""
        screen._refresh_tag_scope()
        assert screen._scope_row.chips == []
        screen._search.find_words.assert_not_called()

    def test_the_scope_is_counted_in_the_era_and_under_the_speaker(
        self, screen: SearchScreen
    ) -> None:
        screen._listed_tag = "Gyro Gearloose"
        screen._speaker = "Gyro"
        screen._era.select("1951-1954")  # the Andes (1948) is out: the Helmet alone is left
        screen._refresh_tag_scope()
        assert screen._scope_row.chips == []  # all that is left is the tag's
        assert screen._search.find_words.call_args.kwargs["speaker"] == "Gyro"

    def test_the_scope_row_sits_between_the_era_and_the_stories(self, screen: SearchScreen) -> None:
        screen._listed_tag = "Gyro Gearloose"
        screen._refresh_tag_scope()
        screen._nav_enter_era()
        assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert (screen._nav_focus_area, screen._scope_row.focused) == ("scope", 0)
        with (
            patch.object(screen, "_get_active_result_rows", return_value=[MagicMock()]),
            patch.object(screen, "_draw_result_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_DOWN) is True
            assert screen._nav_focus_area == "results"
            with patch.object(screen, "_clear_result_focus"):
                assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "scope"
        assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "era"


class TestClearButtonKeys:
    """The x beside the box is Right from the text's end, in every mode: the remote reaches it."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._nav_active = True
            bare._nav_on_exit_request = None
            bare._nav_focus_area = "input"
            bare._nav_focused_result_idx = 0
            bare._nav_word_sub_focus = "title"
            yield bare

    @staticmethod
    def _box(screen: SearchScreen, text: str, cursor: int) -> None:
        box = MagicMock(text=text)
        box.cursor_index.return_value = cursor
        screen.ids.__getitem__.side_effect = lambda _id: box

    @pytest.mark.parametrize("mode", ["Title", "Tag", "Word"])
    def test_right_at_the_texts_end_is_the_clear_button(
        self, screen: SearchScreen, mode: str
    ) -> None:
        screen._active_mode = mode
        self._box(screen, "gold", 4)
        with (
            patch.object(screen, "_blur_all_inputs"),
            patch.object(screen, "_draw_clear_focus") as draw,
        ):
            assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_focus_area == "clear"
        draw.assert_called_once_with()

    def test_right_inside_the_text_moves_the_cursor(self, screen: SearchScreen) -> None:
        screen._active_mode = "Word"
        self._box(screen, "gold", 2)
        assert screen.handle_key(search_screen.KEY_RIGHT) is False  # the box's own key
        assert screen._nav_focus_area == "input"

    def test_right_from_the_clear_button_is_the_results(self, screen: SearchScreen) -> None:
        screen._active_mode = "Word"
        screen._nav_focus_area = "clear"
        with (
            patch.object(screen, "_get_active_result_rows", return_value=[MagicMock()]),
            patch.object(screen, "_clear_clear_focus"),
            patch.object(screen, "_draw_result_focus") as draw,
        ):
            assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_focus_area == "results"
        draw.assert_called_once_with()

    def test_with_no_results_the_focus_stays_on_the_clear_button(
        self, screen: SearchScreen
    ) -> None:
        screen._active_mode = "Word"
        screen._nav_focus_area = "clear"
        with patch.object(screen, "_get_active_result_rows", return_value=[]):
            assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_focus_area == "clear"

    def test_enter_on_the_clear_button_clears_and_returns_to_the_box(
        self, screen: SearchScreen
    ) -> None:
        screen._active_mode = "Word"
        screen._nav_focus_area = "clear"
        clear_button = MagicMock()
        with (
            patch.object(screen, "_get_active_clear_button", return_value=clear_button),
            patch.object(screen, "_clear_clear_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_ENTER) is True
        clear_button.trigger_action.assert_called_once_with(duration=0)
        assert screen._nav_focus_area == "input"


class _Ids(dict):
    """The screen's kv ids, by attribute as by key, as Kivy's are."""

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _released_into(pressed: list[str]) -> Callable[[Button], None]:
    return lambda button: pressed.append(button.text)


def _word_result_row(title: str, pressed: list[str]) -> BoxLayout:
    """Return a word result row as the screen builds one: the story, then its bubbles button."""
    row = BoxLayout()
    for part in ("title", "speech"):
        button = Button(text=f"{title} {part}")
        button.bind(on_release=_released_into(pressed))
        row.add_widget(button)
    return row


class TestResultsKeys:
    """The remote on the stories listed: walking them, a story's two parts, and the ways out.

    Over real result rows, so the focus is drawn (and logged) as on screen.
    """

    @pytest.fixture
    def pressed(self) -> list[str]:
        return []

    @pytest.fixture
    def screen(self, pressed: list[str]) -> Iterator[SearchScreen]:
        word_results = BoxLayout(orientation="vertical")
        for title in ("Story A", "Story B", "Story C"):
            word_results.add_widget(_word_result_row(title, pressed))
        tag_results = BoxLayout(orientation="vertical")
        for title in ("Story X", "Story Y"):
            button = Button(text=title)
            button.bind(on_release=_released_into(pressed))
            tag_results.add_widget(button)
        ids = _Ids(
            {f"{mode}_search_input": MagicMock() for mode in ("title", "tag", "word")}
            | {f"{mode}_clear_button": MagicMock() for mode in ("title", "tag", "word")}
            | {f"{mode}_results_scroll": MagicMock() for mode in ("title", "tag", "word")}
            | {
                "word_results_layout": word_results,
                "tag_title_results_layout": tag_results,
                "title_results_layout": BoxLayout(),
                "word_chips_layout": MagicMock(children=[]),
                "tag_chips_layout": MagicMock(children=[]),
            }
        )
        with (
            patch.object(SearchScreen, "ids", ids),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Word"
            bare._nav_active = True
            bare._nav_on_exit_request = MagicMock()
            bare._nav_focus_area = "results"
            bare._nav_focused_result_idx = 0
            bare._nav_word_sub_focus = "title"
            bare._nav_focused_chip_idx = 0
            bare._last_activated_result_idx = None
            bare._last_activated_word_sub_focus = "title"
            bare._selected_word = ""
            bare._selected_tag = ""
            bare._selected_member = ""
            bare._tag_titles = []
            yield bare

    @staticmethod
    def _key(screen: SearchScreen, key: int) -> bool:
        return screen.handle_key(key)

    def test_down_walks_the_stories_and_stops_at_the_last(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        for expected_idx in (1, 2, 2):
            assert self._key(screen, search_screen.KEY_DOWN) is True
            assert screen._nav_focused_result_idx == expected_idx
        assert loguru_sink[-1] == 'Nav focus on Button "Story C title".'

    def test_right_and_left_move_between_a_story_and_its_bubbles(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        assert self._key(screen, search_screen.KEY_RIGHT) is True
        assert loguru_sink[-1] == 'Nav focus on Button "Story A speech".'
        assert self._key(screen, search_screen.KEY_RIGHT) is False  # nothing further right
        assert self._key(screen, search_screen.KEY_LEFT) is True
        assert (screen._nav_word_sub_focus, loguru_sink[-1]) == (
            "title",
            'Nav focus on Button "Story A title".',
        )

    def test_enter_presses_the_focused_part_and_remembers_it(
        self, screen: SearchScreen, pressed: list[str]
    ) -> None:
        self._key(screen, search_screen.KEY_DOWN)
        self._key(screen, search_screen.KEY_RIGHT)
        assert self._key(screen, search_screen.KEY_ENTER) is True
        assert pressed == ["Story B speech"]
        assert (screen._last_activated_result_idx, screen._last_activated_word_sub_focus) == (
            1,
            "speech",
        )

    def test_up_walks_back_then_climbs_to_the_lowest_chip_row(self, screen: SearchScreen) -> None:
        self._key(screen, search_screen.KEY_DOWN)
        assert self._key(screen, search_screen.KEY_UP) is True
        assert screen._nav_focused_result_idx == 0
        assert self._key(screen, search_screen.KEY_UP) is True  # off the first story
        assert (screen._nav_focus_area, screen._era_rows["Word"].focused) == ("era", 0)

    def test_left_from_a_story_is_the_word_list_or_else_the_clear_button(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        with (
            patch.object(screen, "_get_word_chip_buttons", return_value=[MagicMock()]),
            patch.object(screen, "_nav_back_to_word_chips") as back,
        ):
            assert self._key(screen, search_screen.KEY_LEFT) is True
        back.assert_called_once_with()

        screen._nav_focus_area = "results"
        assert self._key(screen, search_screen.KEY_LEFT) is True  # no word list
        assert screen._nav_focus_area == "clear"
        assert loguru_sink[-1].startswith("Nav focus on MagicMock")  # the clear button's fill

    def test_tab_is_the_box_escape_leaves_and_other_keys_pass(self, screen: SearchScreen) -> None:
        assert self._key(screen, search_screen.KEY_TAB) is True
        assert screen._nav_focus_area == "input"
        assert screen.ids.word_search_input.focus is True

        screen._nav_focus_area = "results"
        assert self._key(screen, ord("a")) is False
        assert self._key(screen, KEY_ESCAPE) is True
        assert (screen._nav_focus_area, screen.ids.word_search_input.focus) == ("input", False)
        screen._nav_on_exit_request.assert_called_once_with()

    def test_a_tag_story_has_no_bubbles_and_left_is_the_tag_list(
        self, screen: SearchScreen, pressed: list[str]
    ) -> None:
        screen._active_mode = "Tag"
        assert self._key(screen, search_screen.KEY_RIGHT) is False
        assert self._key(screen, search_screen.KEY_ENTER) is True
        assert pressed == ["Story X"]
        with (
            patch.object(screen, "_get_tag_chip_buttons", return_value=[MagicMock()]),
            patch.object(screen, "_nav_back_to_tag_chips") as back,
        ):
            assert self._key(screen, search_screen.KEY_LEFT) is True
        back.assert_called_once_with()

    def test_coming_back_lands_on_the_last_story_pressed_and_its_part(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._nav_active = False
        screen._last_activated_result_idx = 9  # since shortened: the last story there is
        screen._last_activated_word_sub_focus = "speech"
        exit_request = MagicMock()
        screen.enter_nav_focus_at_last_result(exit_request)
        assert (screen._nav_focus_area, screen._nav_focused_result_idx) == ("results", 2)
        assert screen._nav_word_sub_focus == "speech"
        assert screen._nav_on_exit_request is exit_request
        assert loguru_sink[-1] == "SearchScreen: entered nav focus at last result."

        screen._last_activated_result_idx = None  # none pressed: the box
        screen.enter_nav_focus_at_last_result(exit_request)
        assert screen._nav_focus_area == "input"
        assert screen.ids.word_search_input.focus is True

    def test_entering_and_leaving_the_screen_by_remote(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._nav_active = False
        screen.enter_nav_focus(MagicMock())
        assert (screen._nav_active, screen._nav_focus_area) == (True, "input")
        assert log_markers.SEARCH_ENTERED_NAV in loguru_sink
        screen._nav_focus_area = "results"
        screen.exit_nav_focus()
        assert (screen._nav_active, screen._nav_focus_area) == (False, "input")
        assert loguru_sink[-1] == log_markers.SEARCH_EXITED_NAV


class TestOtherNavKeys:
    """The clear button, the list's Tab and Right, the box's Right and Escape, the picked row."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        rows = BoxLayout(orientation="vertical")
        rows.add_widget(_word_result_row("Story A", []))
        ids = _Ids(
            {f"{mode}_search_input": MagicMock() for mode in ("title", "tag", "word")}
            | {f"{mode}_clear_button": MagicMock() for mode in ("title", "tag", "word")}
            | {f"{mode}_results_scroll": MagicMock() for mode in ("title", "tag", "word")}
            | {
                "word_results_layout": rows,
                "tag_title_results_layout": BoxLayout(),
                "title_results_layout": BoxLayout(),
                "word_chips_layout": MagicMock(children=[]),
                "tag_chips_layout": MagicMock(children=[]),
            }
        )
        with (
            patch.object(SearchScreen, "ids", ids),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Word"
            bare._nav_active = True
            bare._nav_on_exit_request = MagicMock()
            bare._nav_focus_area = "clear"
            bare._nav_focused_result_idx = 0
            bare._nav_word_sub_focus = "title"
            bare._nav_focused_chip_idx = 0
            bare._selected_word = ""
            bare._tag_titles = []
            yield bare

    def test_the_clear_button_s_keys(self, screen: SearchScreen) -> None:
        clear_button = screen.ids.word_clear_button
        assert screen.handle_key(search_screen.KEY_RIGHT) is True  # on to the stories
        assert screen._nav_focus_area == "results"

        screen._nav_focus_area = "clear"
        assert screen.handle_key(search_screen.KEY_ENTER) is True
        clear_button.trigger_action.assert_called_once_with(duration=0)
        assert screen._nav_focus_area == "input"

        screen._nav_focus_area = "clear"
        assert screen.handle_key(search_screen.KEY_LEFT) is True
        assert (screen._nav_focus_area, screen.ids.word_search_input.focus) == ("input", True)

        screen._nav_focus_area = "clear"
        assert screen.handle_key(ord("a")) is False
        with patch.object(screen, "_nav_escape") as escape:
            assert screen.handle_key(KEY_ESCAPE) is True
        escape.assert_called_once_with()

    def test_right_from_the_clear_button_stays_with_no_stories(self, screen: SearchScreen) -> None:
        screen.ids.word_results_layout.clear_widgets()
        assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_focus_area == "clear"

    def test_tab_from_the_list_is_the_stories_and_right_the_top_chip_row(
        self, screen: SearchScreen
    ) -> None:
        screen._nav_focus_area = "tags"
        with (
            patch.object(screen, "_get_active_chip_buttons", return_value=[]),
            patch.object(screen, "_handle_list_row_key", return_value=False),
        ):
            assert screen.handle_key(search_screen.KEY_TAB) is True
            assert screen._nav_focus_area == "results"
            screen._nav_focus_area = "tags"
            assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert (screen._nav_focus_area, screen._era_rows["Word"].focused) == ("era", 0)

    def test_right_in_the_box_is_the_clear_button_only_at_the_text_s_end(
        self, screen: SearchScreen
    ) -> None:
        box = screen.ids.word_search_input
        box.text = "gold"
        box.cursor_index.return_value = 2
        screen._nav_focus_area = "input"
        assert screen.handle_key(search_screen.KEY_RIGHT) is False  # the box moves its cursor
        box.cursor_index.return_value = 4
        assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_focus_area == "clear"

    def test_escape_in_the_box_leaves_the_screen(self, screen: SearchScreen) -> None:
        screen._nav_focus_area = "input"
        assert screen.handle_key(KEY_ESCAPE) is True
        screen._nav_on_exit_request.assert_called_once_with()

    @pytest.mark.parametrize(
        ("titles", "basket", "box_query", "area"),
        [
            (["Story A"], False, "", "results"),  # their first story
            ([], True, "", "basket"),  # none listed, but tags picked
            ([], False, "scrooge +", "tags"),  # could not combine: its chip, with the notice
            ([], False, "", "input"),  # nothing at all: the box
        ],
        ids=["stories", "picked", "notice", "box"],
    )
    def test_after_combining_tags_the_focus_goes_to_what_they_left(
        self,
        screen: SearchScreen,
        titles: list[str],
        *,
        basket: bool,
        box_query: str,
        area: str,
    ) -> None:
        screen._active_mode = "Tag"
        screen._tag_titles = titles
        screen._tag_box_query = box_query
        if basket:
            screen._tag_basket.toggle("Scrooge")
            screen._show_tag_basket()
        with patch.object(screen, "_draw_chip_focus"):
            screen._focus_after_tag_query()
        assert screen._nav_focus_area == area

    @pytest.mark.parametrize(
        ("chips", "area"), [(True, "tags"), (False, "results")], ids=["list", "no-list"]
    )
    def test_down_from_the_picked_words_is_the_list_or_else_the_stories(
        self, screen: SearchScreen, *, chips: bool, area: str
    ) -> None:
        with (
            patch.object(screen, "_run_word_query"),
            patch.object(
                screen, "_get_word_chip_buttons", return_value=[MagicMock()] if chips else []
            ),
            patch.object(screen, "_draw_chip_focus"),
        ):
            screen._toggle_basket_word("gold")
            screen._nav_enter_basket()
            assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert screen._nav_focus_area == area
        assert screen._basket_row.focused is None

    def test_up_from_the_picked_words_is_the_box_and_escape_leaves(
        self, screen: SearchScreen
    ) -> None:
        with patch.object(screen, "_run_word_query"):
            screen._toggle_basket_word("gold")
        screen._nav_enter_basket()
        assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "input"
        screen._nav_enter_basket()
        with patch.object(screen, "_nav_escape") as escape:
            assert screen.handle_key(KEY_ESCAPE) is True
        escape.assert_called_once_with()


class TestBackgroundAndGoto:
    """The panel's background follows the stories listed; its arrow goes to the one shown."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with patch.object(SearchScreen, "ids", MagicMock()):
            bare = _make_bare_screen()
            bare._search_result_titles = []
            bare._image_change_event = None
            bare._current_image_info = None
            bare.on_search_results_title_changed = MagicMock()
            bare.on_goto_background_title_func = MagicMock()
            bare.on_goto_title_with_page = MagicMock()
            bare._selected_result_button = None
            yield bare

    def test_the_background_cycles_through_the_stories_listed(self, screen: SearchScreen) -> None:
        with patch.object(search_screen.Clock, "schedule_interval") as every:
            screen._update_background_from_results([PIRATE_GOLD, HELMET])
        assert screen.on_search_results_title_changed.call_args.args[0] in (PIRATE_GOLD, HELMET)
        every.assert_called_once()
        screen._next_background_image()
        assert screen.on_search_results_title_changed.call_count == 2  # noqa: PLR2004
        screen._cancel_image_change_event()
        every.return_value.cancel.assert_called_once_with()
        assert screen._image_change_event is None

    def test_no_stories_or_no_listener_changes_no_background(self, screen: SearchScreen) -> None:
        screen._update_background_from_results([])
        screen._next_background_image()
        screen.on_search_results_title_changed.assert_not_called()

    def test_the_arrow_goes_to_the_story_the_background_shows(self, screen: SearchScreen) -> None:
        screen.on_goto_background_title()  # none shown yet
        screen.on_goto_background_title_func.assert_not_called()
        info = ImageInfo(from_title=HELMET, filename=None)
        screen.set_background_image(info)
        assert screen.current_title_str == ENUM_TO_STR_TITLE[HELMET]
        screen.on_goto_background_title()
        screen.on_goto_background_title_func.assert_called_once_with(info)

    def test_a_word_result_goes_to_its_story_at_its_page(self, screen: SearchScreen) -> None:
        goto = cast("MagicMock", screen.on_goto_title_with_page)
        row = _SearchResultButton(text="The Golden Helmet, 3")
        screen._on_word_result_row_released(row, ENUM_TO_STR_TITLE[HELMET], "3")
        assert row.selected
        goto.assert_called_once_with(ImageInfo(from_title=HELMET, filename=None), "3")

    def test_a_title_result_with_no_listener_is_only_logged(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen.on_goto_title = None
        screen._on_result_goto_title(ENUM_TO_STR_TITLE[HELMET])
        assert log_markers.SEARCH_SELECTED_TITLE.format(title=ENUM_TO_STR_TITLE[HELMET]) in (
            loguru_sink
        )

    def test_a_word_result_with_no_listener_goes_nowhere(self, screen: SearchScreen) -> None:
        screen.on_goto_title_with_page = None
        screen._goto_title_with_page(ENUM_TO_STR_TITLE[HELMET], "3")  # nothing to call

    def test_a_title_no_story_has_goes_nowhere(self, screen: SearchScreen) -> None:
        screen._goto_title_with_page("No Such Story", "3")
        cast("MagicMock", screen.on_goto_title_with_page).assert_not_called()

    def test_a_bubble_pressed_closes_its_popup_and_goes_to_its_page(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._speech_bubble_popup = MagicMock()
        title = ENUM_TO_STR_TITLE[HELMET]
        with (
            patch.object(search_screen.Clock, "schedule_once", side_effect=lambda cb, *_a: cb(0)),
            patch.object(screen, "_goto_title_with_page") as goto,
        ):
            screen._handle_bubble_title_press(title, "3")
        screen._speech_bubble_popup.dismiss.assert_called_once_with()
        goto.assert_called_once_with(title, "3")
        assert log_markers.WORD_BUBBLE_PRESS.format(title=title, page="3") in loguru_sink

    def test_the_title_info_setting_shows_or_hides_the_title(self, screen: SearchScreen) -> None:
        screen._reader_settings = MagicMock(show_fun_view_title_info=False)
        screen._on_change_show_current_title()
        assert screen.show_current_title is False
        screen._reader_settings.show_fun_view_title_info = True
        screen._on_change_show_current_title()
        assert screen.show_current_title is True


class TestCombinedTagsListingNothing:
    """Picked tags no story has together say so, in the era or not; a new era relists them."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Tag"
            bare._search = MagicMock()
            bare._search.titles_for_tag_selection.return_value = []
            bare._search.get_title_display_strings.side_effect = lambda ts: [t.name for t in ts]
            bare._search.resolve_tag.side_effect = lambda name: (
                SimpleNamespace(value=name.title()),
                [],
            )
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
            bare.ids.tag_chips_layout.children = [_tag_stack("Scrooge", "Gyro")]
            yield bare

    @staticmethod
    def _last_row_text(screen: SearchScreen) -> str:
        added = screen.ids.tag_title_results_layout.add_widget.call_args_list
        return added[-1].args[0].text

    def test_no_story_with_all_of_them_says_so(self, screen: SearchScreen) -> None:
        screen._toggle_tag_basket("Scrooge")
        assert self._last_row_text(screen) == "No story has these tags"

    def test_none_in_the_era_says_which_era(self, screen: SearchScreen) -> None:
        _press(cast("MagicMock", screen._era_rows["Tag"].chips[1]))  # 1942-46
        screen._toggle_tag_basket("Scrooge")
        assert self._last_row_text(screen) == "None in 1942-46"

    def test_a_new_era_lists_the_picked_tags_stories_again(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._search.titles_for_tag_selection.return_value = [PIRATE_GOLD, HELMET]
        screen._toggle_tag_basket("Scrooge")
        assert screen._tag_titles == [PIRATE_GOLD.name, HELMET.name]

        _press(cast("MagicMock", screen._era_rows["Tag"].chips[2]))  # 1951-54

        assert screen._tag_titles == [HELMET.name]
        assert loguru_sink[-1] == log_markers.TAG_COMBINED_RESULTS.format(tags="Scrooge", count=1)


class TestBeforeTheLayoutIsBuilt:
    """Until the kv layout gives the screen its lists, they read as empty, not as errors."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with patch.object(SearchScreen, "ids", _Ids()):
            yield _make_bare_screen()

    def test_every_list_reads_empty(self, screen: SearchScreen) -> None:
        assert screen._tag_rows() == []
        assert screen._word_rows() == []
        assert screen._get_main_tag_chip_buttons() == []
        assert screen._get_member_chip_buttons() == []
        assert screen._get_tag_chip_buttons() == []
        assert screen._get_word_chip_buttons() == []


class TestPanelRowsOutsideTheListSearches:
    def test_the_title_search_has_no_panel_rows(self) -> None:
        with patch.object(SearchScreen, "ids", MagicMock()):
            screen = _make_bare_screen()
        screen._active_mode = "Title"
        assert screen._panel_rows() == []


class TestEmptiedBasketWithNoList:
    """Taking the last picked word out, with no word list to go to, puts the keyboard in the box."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        ids = _Ids(
            {f"{mode}_search_input": MagicMock() for mode in ("title", "tag", "word")}
            | {f"{mode}_clear_button": MagicMock() for mode in ("title", "tag", "word")}
            | {f"{mode}_results_scroll": MagicMock() for mode in ("title", "tag", "word")}
            | {
                "word_results_layout": BoxLayout(),
                "tag_title_results_layout": BoxLayout(),
                "title_results_layout": BoxLayout(),
                "word_chips_layout": MagicMock(children=[]),
                "tag_chips_layout": MagicMock(children=[]),
            }
        )
        with (
            patch.object(SearchScreen, "ids", ids),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Word"
            bare._search = MagicMock()
            bare._search.run_word_query.return_value = WordQueryResult(
                title_dict=_found("Story A"), hit_counts={"Story A": 1}
            )
            bare._selected_word = ""
            bare._word_search_results = []
            bare._selected_result_button = None
            bare._nav_active = True
            bare.on_request_nav_focus = None
            bare._nav_on_exit_request = None
            bare._nav_focus_area = "basket"
            bare._nav_focused_chip_idx = 0
            bare._nav_focused_result_idx = 0
            bare._nav_word_sub_focus = "title"
            yield bare

    def test_the_keyboard_goes_to_the_search_box(self, screen: SearchScreen) -> None:
        screen._toggle_basket_word("gold")
        screen._nav_enter_basket()
        screen.handle_key(search_screen.KEY_RIGHT)  # onto the word's chip
        screen.handle_key(search_screen.KEY_ENTER)  # takes it out

        assert screen._word_basket.words == []
        assert screen._nav_focus_area == "input"
        assert screen.ids.word_search_input.focus is True

    def test_a_key_the_picked_row_does_not_take_is_left_to_the_host(
        self, screen: SearchScreen
    ) -> None:
        screen._toggle_basket_word("gold")
        screen._nav_enter_basket()
        assert screen.handle_key(ord("a")) is False
        assert screen._nav_focus_area == "basket"


class TestSaidByChipEdges:
    """The speaker chip keeps the keyboard as it changes, and a list that cannot open is quiet."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        with (
            patch.object(SearchScreen, "ids", MagicMock()),
            patch.object(SearchScreen, "_cancel_image_change_event"),
            patch.object(SearchScreen, "_speaker_story_counts", return_value=_SPEAKER_COUNTS),
            patch.object(SearchScreen, "_rerun_word_results"),
        ):
            bare = _make_bare_screen()
            bare._speaker_row = ChipRow(MagicMock(), _live_chip, bare._on_said_by_chip_pressed)
            bare._active_mode = "Word"
            bare._nav_active = True
            bare._nav_on_exit_request = None
            bare._selected_word = "money"
            bare._nav_focused_result_idx = 0
            bare._nav_focused_chip_idx = 0
            bare._nav_word_sub_focus = "title"
            _offer_speakers(bare, "Donald")
            bare._nav_focus_area = "speakers"
            bare._speaker_row.enter_focus()
            yield bare

    def test_the_chip_keeps_the_keyboard_when_its_speaker_changes(
        self, screen: SearchScreen
    ) -> None:
        screen._speaker = "Scrooge"
        screen._show_said_by_chip()
        assert _said_by_chip(screen).text == "Said by: Scrooge"
        assert screen._speaker_row.focused == 0

    def test_a_list_that_cannot_open_logs_nothing_and_keeps_the_chip(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        with patch.object(search_screen, "open_dropdown", return_value=False):
            assert screen.handle_key(search_screen.KEY_ENTER) is True
        assert not any(line.startswith("Word search: speaker list opened") for line in loguru_sink)
        assert screen._nav_focus_area == "speakers"
        assert screen._speaker_row.focused == 0


class TestNavEdges:
    """The keys' edges: nothing to focus, a key no area takes, and the box's Enter."""

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        rows = BoxLayout(orientation="vertical")
        ids = _Ids(
            {f"{mode}_search_input": MagicMock() for mode in ("title", "tag", "word")}
            | {f"{mode}_clear_button": MagicMock() for mode in ("title", "tag", "word")}
            | {f"{mode}_results_scroll": MagicMock() for mode in ("title", "tag", "word")}
            | {
                "word_results_layout": rows,
                "tag_title_results_layout": BoxLayout(),
                "title_results_layout": BoxLayout(),
                "word_chips_layout": MagicMock(children=[]),
                "tag_chips_layout": MagicMock(children=[]),
            }
        )
        with (
            patch.object(SearchScreen, "ids", ids),
            patch.object(SearchScreen, "_cancel_image_change_event"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Word"
            bare._nav_active = True
            bare._nav_on_exit_request = MagicMock()
            bare._nav_focus_area = "input"
            bare._nav_focused_result_idx = 0
            bare._nav_word_sub_focus = "title"
            bare._nav_focused_chip_idx = 0
            bare._selected_word = ""
            bare._tag_titles = []
            yield bare

    @pytest.mark.parametrize("stray", [None, Button()], ids=["no widget", "a widget not listed"])
    def test_a_focus_the_list_does_not_hold_is_not_drawn(
        self, screen: SearchScreen, stray: Button | None
    ) -> None:
        screen.ids.word_results_layout.add_widget(_word_result_row("Story A", []))
        screen._nav_focus_area = "results"
        with (
            patch.object(screen, "_get_focused_result_widget", return_value=stray),
            patch.object(search_screen, "update_focus_in_list") as draw,
        ):
            screen._draw_result_focus()
        draw.assert_not_called()

    def test_escape_in_the_box_with_nowhere_to_return_leaves_the_box(
        self, screen: SearchScreen
    ) -> None:
        screen._nav_on_exit_request = None
        with patch.object(screen, "_blur_all_inputs") as blur:
            assert screen.handle_key(KEY_ESCAPE) is True
        blur.assert_called_once_with()

    def test_enter_on_an_empty_results_list_picks_nothing(self, screen: SearchScreen) -> None:
        screen._nav_focus_area = "results"
        assert screen.handle_key(search_screen.KEY_ENTER) is True
        assert getattr(screen, "_last_activated_result_idx", None) is None

    def test_up_from_the_first_title_result_stays_there(self, screen: SearchScreen) -> None:
        """The title search has no chip rows above its results to go up to."""
        screen._active_mode = "Title"
        screen._nav_focus_area = "results"
        assert screen.handle_key(search_screen.KEY_UP) is True
        assert (screen._nav_focus_area, screen._nav_focused_result_idx) == ("results", 0)

    def test_escape_from_the_results_with_nowhere_to_return_goes_to_the_box(
        self, screen: SearchScreen
    ) -> None:
        screen._nav_on_exit_request = None
        screen._nav_focus_area = "results"
        assert screen.handle_key(KEY_ESCAPE) is True
        assert screen._nav_focus_area == "input"

    def test_no_key_is_taken_while_the_screen_is_not_navigating(self, screen: SearchScreen) -> None:
        screen._nav_active = False
        assert screen.handle_key(search_screen.KEY_DOWN) is False

    def test_enter_in_the_box_runs_the_search(self, screen: SearchScreen) -> None:
        with patch.object(screen, "on_search_input_enter") as run:
            assert screen.handle_key(search_screen.KEY_ENTER) is True
        run.assert_called_once_with()

    def test_a_typing_key_in_the_box_is_left_to_the_box(self, screen: SearchScreen) -> None:
        assert screen.handle_key(ord("a")) is False

    def test_on_an_empty_list_escape_leaves_and_other_keys_are_not_taken(
        self, screen: SearchScreen
    ) -> None:
        screen._nav_focus_area = "tags"
        assert screen.handle_key(ord("a")) is False
        assert screen.handle_key(search_screen.KEY_ENTER) is True  # nothing to pick
        assert screen._nav_focus_area == "tags"
        assert screen.handle_key(KEY_ESCAPE) is True
        assert screen._nav_focus_area == "input"
        cast("MagicMock", screen._nav_on_exit_request).assert_called_once_with()

    def test_with_nothing_listed_nothing_takes_the_focus(self, screen: SearchScreen) -> None:
        screen._nav_focus_area = "tags"
        screen._nav_focused_chip_idx = 3
        screen._focus_selected_or_first_chip()
        screen._draw_chip_focus()
        screen._focus_first_result_row()
        screen._draw_result_focus()
        assert (screen._nav_focus_area, screen._nav_focused_chip_idx) == ("tags", 3)
        assert screen._get_focused_result_widget([]) is None

    def test_a_notice_row_among_word_results_takes_the_focus_whole(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        rows = screen.ids.word_results_layout
        rows.add_widget(_word_result_row("Story A", []))
        rows.add_widget(_SearchResultButton(text="None in 1942-46"))
        screen._nav_focus_area = "results"
        screen._nav_focused_result_idx = 1

        screen._draw_result_focus()

        assert loguru_sink[-1] == 'Nav focus on _SearchResultButton "None in 1942-46".'


class TestTagListKeys:
    """The tag list by remote, over real chip stacks: walking it, groups opened and closed.

    Chemistry is a group whose members hold a subgroup, chemical names; Duckburg a tag.
    """

    MEMBERS: ClassVar[dict[TagGroups, list[Tags | TagGroups]]] = {
        TagGroups.CHEMISTRY: [Tags.DUCKMITE, TagGroups.CHEMICAL_NAMES, Tags.WEEMITE],
        TagGroups.CHEMICAL_NAMES: [Tags.GYRO_GEARLOOSE, Tags.FIRST_DAISY],
    }
    ITEMS: ClassVar[dict[str, Tags | TagGroups]] = {
        "chemistry": TagGroups.CHEMISTRY,
        "duckburg": Tags.DUCKBURG,
    }

    @pytest.fixture
    def screen(self) -> Iterator[SearchScreen]:
        results = BoxLayout(orientation="vertical")
        results.add_widget(Button(text="A Story"))
        ids = _Ids(
            {f"{mode}_search_input": MagicMock() for mode in ("title", "tag", "word")}
            | {f"{mode}_clear_button": MagicMock() for mode in ("title", "tag", "word")}
            | {f"{mode}_results_scroll": MagicMock() for mode in ("title", "tag", "word")}
            | {
                "tag_chips_layout": BoxLayout(orientation="vertical"),
                "tag_title_results_layout": results,
                "word_results_layout": BoxLayout(),
                "title_results_layout": BoxLayout(),
                "word_chips_layout": MagicMock(children=[]),
            }
        )
        with (
            patch.object(SearchScreen, "ids", ids),
            patch.object(SearchScreen, "_cancel_image_change_event"),
            patch.object(SearchScreen, "_show_tag_titles"),
        ):
            bare = _make_bare_screen()
            bare._active_mode = "Tag"
            bare._search = MagicMock()
            bare._search.get_tag_group_members.side_effect = lambda group: self.MEMBERS[group]
            bare._search.get_tag_title_count.return_value = 3
            bare._search.resolve_tag.side_effect = lambda name: (self.ITEMS[name], [])
            bare._tag_chip_strings = ["chemistry", "Duckburg"]
            bare._tag_chip_counts = {"chemistry": 24, "Duckburg": 5}
            bare._tag_chip_groups = {"chemistry"}
            bare._selected_tag = ""
            bare._selected_member = ""
            bare._current_tag = None
            bare._nav_active = True
            bare._nav_on_exit_request = MagicMock()
            bare._nav_focus_area = "tags"
            bare._nav_focused_chip_idx = 0
            bare._nav_focused_result_idx = 0
            bare._nav_word_sub_focus = "title"
            bare._rebuild_tag_chips()
            yield bare

    @staticmethod
    def _texts(chips: list[Any]) -> list[str]:
        return [chip.text for chip in chips]

    def test_the_open_group_s_members_sit_between_it_and_the_chips_after(
        self, screen: SearchScreen
    ) -> None:
        screen._on_tag_result_selected("chemistry")
        assert self._texts(screen._get_tag_chip_buttons()) == [
            "chemistry",
            "duckmite",
            "chemical names",
            "weemite",
            "Duckburg",
        ]
        assert self._texts(screen._get_main_tag_chip_buttons()) == ["chemistry", "Duckburg"]
        assert self._texts(screen._get_member_chip_buttons()) == [
            "duckmite",
            "chemical names",
            "weemite",
        ]
        [chemistry, *_] = screen._get_tag_chip_buttons()
        assert (chemistry.is_group, chemistry.is_open) == (True, True)

    def test_enter_on_a_group_opens_it_and_picks_its_first_member(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        assert screen.handle_key(search_screen.KEY_ENTER) is True
        assert screen._current_tag is TagGroups.CHEMISTRY
        assert screen._selected_member == "duckmite"
        assert screen._nav_focused_chip_idx == 1  # on the first member, once drawn
        assert log_markers.TAG_SELECTED_MEMBER.format(member="duckmite") in loguru_sink

    def test_enter_on_the_open_group_closes_it_and_stays_on_it(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._on_tag_result_selected("chemistry")
        screen._nav_focused_chip_idx = 0
        assert screen.handle_key(search_screen.KEY_ENTER) is True
        assert self._texts(screen._get_tag_chip_buttons()) == ["chemistry", "Duckburg"]
        assert screen._nav_focused_chip_idx == 0
        assert loguru_sink[-1] == 'Nav focus on _TagChipButton "chemistry".'
        assert log_markers.TAG_GROUP_CLOSED.format(group="chemistry") in loguru_sink

    def test_enter_on_a_subgroup_opens_it_in_place_and_stays_on_it(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._on_tag_result_selected("chemistry")
        screen._nav_focused_chip_idx = 2  # chemical names
        assert screen.handle_key(search_screen.KEY_ENTER) is True
        assert self._texts(screen._get_tag_chip_buttons()) == [
            "chemistry",
            "duckmite",
            "chemical names",
            "Gyro Gearloose",
            "first Daisy appearance",
            "weemite",
            "Duckburg",
        ]
        assert screen._nav_focused_chip_idx == 2  # noqa: PLR2004
        assert loguru_sink[-1] == 'Nav focus on _TagChipButton "chemical names".'

        assert screen.handle_key(search_screen.KEY_ENTER) is True  # and again: closed
        assert "Gyro Gearloose" not in self._texts(screen._get_tag_chip_buttons())
        assert screen._nav_focused_chip_idx == 2  # noqa: PLR2004

    def test_enter_on_a_plain_member_lists_it_and_goes_to_its_stories(
        self, screen: SearchScreen
    ) -> None:
        screen._on_tag_result_selected("chemistry")
        screen._nav_focused_chip_idx = 3  # weemite
        assert screen.handle_key(search_screen.KEY_ENTER) is True
        assert screen._selected_member == "weemite"
        assert screen._nav_focus_area == "results"

    def test_enter_on_a_plain_tag_goes_to_its_stories(self, screen: SearchScreen) -> None:
        screen._nav_focused_chip_idx = 1  # Duckburg
        assert screen.handle_key(search_screen.KEY_ENTER) is True
        assert (screen._selected_tag, screen._current_tag) == ("Duckburg", Tags.DUCKBURG)
        assert screen._nav_focus_area == "results"

    def test_enter_past_the_last_chip_does_nothing(self, screen: SearchScreen) -> None:
        screen._nav_focused_chip_idx = 9
        screen._handle_tags_enter(cast("list[Button]", screen._get_tag_chip_buttons()))
        assert (screen._selected_tag, screen._nav_focus_area) == ("", "tags")

    def test_down_walks_the_list_and_stops_at_its_end(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert loguru_sink[-1] == 'Nav focus on _TagChipButton "Duckburg".'
        assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert screen._nav_focused_chip_idx == 1

    def test_up_walks_back_and_off_the_top_is_the_box(self, screen: SearchScreen) -> None:
        screen._nav_focused_chip_idx = 1
        assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focused_chip_idx == 0
        assert screen.handle_key(search_screen.KEY_UP) is True
        assert (screen._nav_focus_area, screen.ids.tag_search_input.focus) == ("input", True)

    def test_up_off_the_top_is_the_picked_tags_when_there_are_some(
        self, screen: SearchScreen
    ) -> None:
        with patch.object(screen, "_run_tag_basket"):
            screen._toggle_tag_basket("Duckburg")
        assert screen.handle_key(search_screen.KEY_UP) is True
        assert (screen._nav_focus_area, screen._tag_basket_row.focused) == ("basket", 0)

    def test_tab_is_the_stories_and_right_the_era(self, screen: SearchScreen) -> None:
        assert screen.handle_key(search_screen.KEY_TAB) is True
        assert screen._nav_focus_area == "results"
        screen._nav_focus_area = "tags"
        assert screen.handle_key(search_screen.KEY_RIGHT) is True  # onto the +
        assert screen.handle_key(search_screen.KEY_RIGHT) is True  # then the era row
        assert (screen._nav_focus_area, screen._era_rows["Tag"].focused) == ("era", 0)

    def test_down_from_the_box_is_the_list_or_else_the_stories(self, screen: SearchScreen) -> None:
        screen._nav_focus_area = "input"
        assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert (screen._nav_focus_area, screen._nav_focused_chip_idx) == ("tags", 0)

        screen.ids.tag_chips_layout.clear_widgets()
        screen._nav_focus_area = "input"
        assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert screen._nav_focus_area == "results"


def test_a_story_row_shows_its_issue_and_the_year_it_came_out() -> None:
    assert _title_detail("The Golden Helmet") == "FC 408, 1952"
    assert _title_detail("(The Victory Garden)") == "CS 31, 1943"  # its display form


def test_a_row_that_is_no_story_shows_no_detail() -> None:
    assert _title_detail("None in 1950-55") == ""


def test_listed_stories_carry_their_detail_and_keep_their_title() -> None:
    screen = _make_bare_screen()
    layout = BoxLayout()
    screen._populate_title_results(layout, ["The Golden Helmet"], MagicMock())
    [row] = layout.children
    assert row.text == "The Golden Helmet"
    assert row.detail == "FC 408, 1952"


def test_a_cover_row_says_cover_and_opens_the_cover() -> None:
    screen = _make_bare_screen()
    screen._mark_result_selected = MagicMock()
    layout = BoxLayout()
    on_select = MagicMock()
    screen._populate_title_results(layout, ["(Four Color #223 Cover)"], on_select)
    [row] = layout.children
    assert row.text == "[Cover]"
    assert row.is_cover
    assert row.detail == "FC 223, 1949"
    row.dispatch("on_release")
    on_select.assert_called_once_with("(Four Color #223 Cover)")


def test_a_story_row_is_no_cover() -> None:
    screen = _make_bare_screen()
    layout = BoxLayout()
    screen._populate_title_results(layout, ["Lost in the Andes!"], MagicMock())
    [row] = layout.children
    assert row.text == "Lost in the Andes!"
    assert not row.is_cover


def test_one_letter_in_the_title_box_lists_nothing() -> None:
    """A single letter would list too many titles to be any use: the list is cleared."""
    with patch.object(SearchScreen, "ids", MagicMock()):
        screen = _make_bare_screen()
        screen._search = MagicMock()
        screen.on_title_search_text("g")
        screen.ids.title_results_layout.clear_widgets.assert_called_once_with()
    screen._search.search.assert_not_called()
