# ruff: noqa: SLF001

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, ClassVar, cast
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.alpha_split import split_alpha_terms
from barks_reader.ui import search_screen
from barks_reader.ui.search_screen import SearchScreen, _SearchResultButton

if TYPE_CHECKING:
    from collections.abc import Iterator


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
    # Bucket keys are the prefix *ranges* `split_alpha_terms` produces for the
    # A-Z button bar, not two-character prefixes. A fixture keyed by "do"/"da"
    # passes even when the lookup indexes straight to `letter_group[query[:2]]`,
    # which is how a word search that matched nothing at all shipped green.
    TERMS: ClassVar[dict] = {
        "d": {
            "do-don": ["don", "Don Gaspar", "Don Quixote", "done", "Donna Duck"],
            "da-dan": ["dance", "Daniel Boone"],
        },
        "q": {"qu-qui": ["quixote"]},
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

    def test_matches_against_real_bucket_labels(self) -> None:
        """Regression: the matcher must work on what `split_alpha_terms` really returns.

        The screen gets its terms from `ComicSearch.get_alpha_split_terms`, which
        computes the split rather than reading the index's two-character sidecar.
        Building the fixture through the same function keeps this test honest if
        the bucket labelling ever changes again.
        """
        terms = ["egg", "eggbeater", "egghead", "eggs", "eggshell"]
        terms += ["eel", "elbow", "ember", "end", "eye"]
        screen = _make_screen(split_alpha_terms(sorted(terms)))

        assert screen._get_words_matching_prefix("eggs") == ["eggs", "eggshell"]
        assert screen._get_words_matching_prefix("eggnog") == []
        assert screen._get_words_matching_prefix("egg") == [
            "egg",
            "eggbeater",
            "egghead",
            "eggs",
            "eggshell",
        ]


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


def _speaker_chip(speaker: str, text: str) -> MagicMock:
    chip = MagicMock()
    chip.speaker = speaker
    chip.text = text
    return chip


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
            bare._selected_speaker = ""
            bare._speaker_chips_built = False
            bare.ids.speaker_chips_layout.children = []
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
        with patch.object(search_screen, "_SpeakerChipButton") as chip_cls:
            chip_cls.side_effect = lambda **kw: _speaker_chip(kw["speaker"], kw["text"])
            screen._build_speaker_chips()

        added = [c.args[0] for c in screen.ids.speaker_chips_layout.add_widget.call_args_list]
        # Roster order, sentinels other than the narrator left out, `other:` not offered.
        assert [(c.text, c.speaker) for c in added] == [
            ("All", ""),
            ("Donald", "Donald"),
            ("Scrooge", "Scrooge"),
            ("Caption", "narrator"),
        ]
        assert screen._speaker_chips_built is True

    def test_index_without_speakers_offers_no_row(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._search.get_speakers.return_value = {}

        screen._build_speaker_chips()

        screen.ids.speaker_chips_layout.add_widget.assert_not_called()
        assert "Word search: index has no speakers; no speaker filter." in loguru_sink

    def test_chips_are_built_once_on_the_first_word_typed(self, screen: SearchScreen) -> None:
        screen._word_terms = {}
        with patch.object(screen, "_build_speaker_chips") as build:
            screen.on_word_search_text("d")
            screen._speaker_chips_built = True
            screen.on_word_search_text("do")
        build.assert_called_once()

    def test_picking_a_speaker_reruns_the_search_filtered(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._selected_word = "money"
        screen._search.find_words.return_value = {"A Title": MagicMock()}
        with (
            patch.object(screen, "_build_word_results", return_value=[]),
            patch.object(screen, "_populate_word_results_layout"),
            patch.object(screen, "_get_speaker_chip_buttons", return_value=[]),
        ):
            screen._on_speaker_chip_selected("Scrooge")

        screen._search.find_words.assert_called_once_with("money", speaker="Scrooge")
        assert screen._selected_speaker == "Scrooge"
        assert 'Word search: speaker filter "Scrooge".' in loguru_sink

    def test_all_lifts_the_filter(self, screen: SearchScreen, loguru_sink: list[str]) -> None:
        screen._selected_word = "money"
        screen._selected_speaker = "Scrooge"
        screen._search.find_words.return_value = {"A Title": MagicMock()}
        with (
            patch.object(screen, "_build_word_results", return_value=[]),
            patch.object(screen, "_populate_word_results_layout"),
            patch.object(screen, "_get_speaker_chip_buttons", return_value=[]),
        ):
            screen._on_speaker_chip_selected("")

        screen._search.find_words.assert_called_once_with("money", speaker=None)
        assert 'Word search: speaker filter "All".' in loguru_sink

    def test_no_word_picked_yet_only_records_the_choice(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_get_speaker_chip_buttons", return_value=[]):
            screen._on_speaker_chip_selected("Donald")

        screen._search.find_words.assert_not_called()
        assert screen._selected_speaker == "Donald"

    def test_selected_chip_is_filled_and_focused_chip_bordered_and_logged(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        screen._selected_speaker = "Donald"
        chips = [_speaker_chip("", "All"), _speaker_chip("Donald", "Donald")]

        screen._update_speaker_chip_colors(cast("list", chips), focused_idx=0)

        assert chips[1].chip_bg_color == search_screen._chip_bg_active()
        assert chips[0].chip_bg_color == search_screen._chip_bg_normal()
        assert chips[0].chip_border_color == search_screen._chip_border_focused()
        assert chips[1].chip_border_color == search_screen._CHIP_BORDER_NONE
        assert 'Nav focus on MagicMock "All".' in loguru_sink

    def test_clear_resets_the_filter(self, screen: SearchScreen) -> None:
        screen._selected_speaker = "Scrooge"
        with patch.object(screen, "_get_speaker_chip_buttons", return_value=[]):
            screen.on_word_clear()
        assert screen._selected_speaker == ""

    def test_bubbles_popup_is_told_the_filter(self, screen: SearchScreen) -> None:
        screen._selected_word = "money"
        screen._selected_speaker = "Scrooge"
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
    and Escape.
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
            bare._selected_speaker = "Donald"
            bare._nav_focus_area = "speakers"
            bare._nav_focused_speaker_idx = 0
            bare._nav_focused_result_idx = 0
            bare._nav_focused_chip_idx = 0
            bare._nav_word_sub_focus = "title"
            bare.chips = [
                _speaker_chip("", "All"),
                _speaker_chip("Donald", "Donald"),
                _speaker_chip("Scrooge", "Scrooge"),
            ]
            with patch.object(
                SearchScreen,
                "_get_speaker_chip_buttons",
                lambda self: self.chips,
            ):
                yield bare

    def test_right_and_left_walk_the_chips(
        self, screen: SearchScreen, loguru_sink: list[str]
    ) -> None:
        assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_focused_speaker_idx == 1
        assert 'Nav focus on MagicMock "Donald".' in loguru_sink

        assert screen.handle_key(search_screen.KEY_LEFT) is True
        assert screen._nav_focused_speaker_idx == 0

    def test_right_stops_at_the_last_chip(self, screen: SearchScreen) -> None:
        screen._nav_focused_speaker_idx = 2
        assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_focused_speaker_idx == 2  # noqa: PLR2004

    def test_left_off_the_first_chip_returns_to_the_word_list(self, screen: SearchScreen) -> None:
        word_chips = [MagicMock(text="cash"), MagicMock(text="money")]
        with (
            patch.object(screen, "_get_word_chip_buttons", return_value=word_chips),
            patch.object(screen, "_draw_chip_focus") as draw,
        ):
            assert screen.handle_key(search_screen.KEY_LEFT) is True

        assert screen._nav_focus_area == "tags"
        assert screen._nav_focused_chip_idx == 1  # back on the selected word
        draw.assert_called_once()

    def test_enter_applies_the_focused_chip_and_stays(self, screen: SearchScreen) -> None:
        screen._nav_focused_speaker_idx = 2
        assert screen.handle_key(search_screen.KEY_ENTER) is True
        screen.chips[2].trigger_action.assert_called_once_with(duration=0)
        assert screen._nav_focus_area == "speakers"

    def test_down_drops_into_the_results(self, screen: SearchScreen) -> None:
        with (
            patch.object(screen, "_get_active_result_rows", return_value=[MagicMock()]),
            patch.object(screen, "_draw_result_focus") as draw,
        ):
            assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert screen._nav_focus_area == "results"
        assert screen._nav_focused_result_idx == 0
        draw.assert_called_once()

    def test_down_with_no_results_stays_put(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_get_active_result_rows", return_value=[]):
            assert screen.handle_key(search_screen.KEY_DOWN) is True
        assert screen._nav_focus_area == "speakers"

    def test_up_returns_to_the_search_box(self, screen: SearchScreen) -> None:
        with patch.object(screen, "_focus_active_input") as focus:
            assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "input"
        focus.assert_called_once()

    def test_right_from_the_word_list_lands_on_the_selected_speaker(
        self, screen: SearchScreen
    ) -> None:
        screen._nav_focus_area = "tags"
        with (
            patch.object(screen, "_get_active_chip_buttons", return_value=[MagicMock()]),
            patch.object(screen, "_clear_chip_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_focus_area == "speakers"
        assert screen._nav_focused_speaker_idx == 1  # "Donald" is selected

    def test_right_from_the_word_list_skips_to_results_without_a_row(
        self, screen: SearchScreen
    ) -> None:
        screen._nav_focus_area = "tags"
        screen.chips = []
        with (
            patch.object(screen, "_get_active_chip_buttons", return_value=[MagicMock()]),
            patch.object(screen, "_clear_chip_focus"),
            patch.object(screen, "_draw_result_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_RIGHT) is True
        assert screen._nav_focus_area == "results"

    def test_up_from_the_first_result_climbs_to_the_speaker_row(self, screen: SearchScreen) -> None:
        screen._nav_focus_area = "results"
        with (
            patch.object(screen, "_get_active_result_rows", return_value=[MagicMock()]),
            patch.object(screen, "_clear_result_focus"),
        ):
            assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "speakers"
        assert screen._nav_focused_speaker_idx == 1

    def test_up_from_the_first_result_is_a_no_op_without_a_row(self, screen: SearchScreen) -> None:
        screen._nav_focus_area = "results"
        screen.chips = []
        with patch.object(screen, "_get_active_result_rows", return_value=[MagicMock()]):
            assert screen.handle_key(search_screen.KEY_UP) is True
        assert screen._nav_focus_area == "results"
