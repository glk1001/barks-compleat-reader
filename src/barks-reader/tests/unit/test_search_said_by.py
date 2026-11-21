"""Tests for the word search's speaker filter, driven on its own with plain callables."""
# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.search_results import PageInfo, SpeechInfo, TitleInfo
from barks_reader.core import log_markers
from barks_reader.core.keys import KEY_DOWN, KEY_ENTER, KEY_ESCAPE
from barks_reader.core.search_focus import FocusArea, SearchFocus
from barks_reader.ui import reader_keyboard_nav, search_said_by
from barks_reader.ui.search_said_by import SaidByFilter
from barks_reader.ui.search_widgets import _SAID_BY
from unit_helpers import FakeSpeakerList, press, stand_in_chip

if TYPE_CHECKING:
    from collections.abc import Iterator


def _said_in(stories: dict[str, list[str]]) -> dict[str, TitleInfo]:
    """Return found stories, each with a found bubble said by each speaker it names."""
    return {
        title: TitleInfo(
            1,
            {
                "001": PageInfo(
                    "3",
                    [
                        SpeechInfo(str(i), 1, "GOLD!", "GOLD!", speaker=speaker)
                        for i, speaker in enumerate(speakers)
                    ],
                )
            },
        )
        for title, speakers in stories.items()
    }


class _Host:
    """What a screen is to its filter: the index's speakers, the search, its stories."""

    def __init__(self) -> None:
        self.speakers: set[str] = {"Scrooge", "Donald"}
        self.searched: tuple[str, str, None] = ("", "gold", None)
        # A picked word's stories: each with who says the word in it.
        self.found = _said_in({"A": ["Donald"], "B": ["Donald", "Scrooge"], "C": []})
        self.stories_with: dict[str, tuple[str, ...]] = {"Donald": ("A", "B"), "Scrooge": ("B",)}
        self.asked: list[str | None] = []
        self.picks = 0

    def find_stories(self, speaker: str | None) -> dict[str, TitleInfo]:
        """Return the stories found: all of them, or those `speaker` says a bubble in."""
        self.asked.append(speaker)
        if speaker is None:
            return self.found
        return {
            title: info
            for title, info in self.found.items()
            if title in self.stories_with.get(speaker, ())
        }

    def on_picked(self) -> None:
        self.picks += 1


@pytest.fixture
def host() -> _Host:
    return _Host()


@pytest.fixture
def said_by(host: _Host) -> Iterator[SaidByFilter]:
    with (
        patch.object(search_said_by, "_make_said_by_chip", stand_in_chip),
        patch.object(search_said_by, "ReaderDropDown", FakeSpeakerList),
        patch.object(reader_keyboard_nav, "draw_focus_highlight"),
        patch.object(reader_keyboard_nav, "clear_focus_highlight"),
    ):
        yield SaidByFilter(
            MagicMock(),
            SearchFocus(),
            indexed_speakers=lambda: host.speakers,
            searched=lambda: host.searched,
            find_stories=host.find_stories,
            on_picked=host.on_picked,
        )


def _chip(said_by: SaidByFilter) -> MagicMock:
    [chip] = said_by.row.chips
    return cast("MagicMock", chip)


def _list(said_by: SaidByFilter) -> FakeSpeakerList:
    return cast("FakeSpeakerList", said_by.dropdown)


class TestTheChip:
    """One chip, naming the speaker, while a search is listed and the index has speakers."""

    def test_it_names_anyone_and_is_not_filled(self, said_by: SaidByFilter) -> None:
        said_by.show()
        assert (_chip(said_by).value, _chip(said_by).text) == (_SAID_BY, "Said by: anyone")
        assert said_by.row.selected == ""

    def test_it_names_the_speaker_picked_and_is_filled(self, said_by: SaidByFilter) -> None:
        said_by.speaker = "Donald"
        said_by.show()
        assert _chip(said_by).text == "Said by: Donald"
        assert said_by.row.selected == _SAID_BY

    def test_nothing_searched_shows_no_chip(self, said_by: SaidByFilter, host: _Host) -> None:
        host.searched = ("", "", None)
        said_by.show()
        assert said_by.row.chips == []

    def test_an_index_without_speakers_shows_no_chip_and_says_so_once(
        self, said_by: SaidByFilter, host: _Host, loguru_sink: list[str]
    ) -> None:
        host.speakers = set()
        said_by.show()
        said_by.show()
        assert said_by.row.chips == []
        assert loguru_sink.count(log_markers.SPEAKER_FILTER_NO_SPEAKERS) == 1

    def test_the_keyboard_stays_on_it_as_its_text_changes(self, said_by: SaidByFilter) -> None:
        said_by.show()
        said_by.row.enter_focus(0)
        said_by.speaker = "Scrooge"
        said_by.show()
        assert said_by.row.focused == 0

    def test_lifting_goes_back_to_anyone_and_says_why(
        self, said_by: SaidByFilter, loguru_sink: list[str]
    ) -> None:
        said_by.speaker = "Donald"
        said_by.lift("zounds")
        assert said_by.speaker == ""
        assert loguru_sink[-1] == log_markers.SPEAKER_FILTER_LIFTED.format(
            speaker="Donald", text="zounds"
        )


class TestTheCounts:
    """Anyone's stories, then each speaker's who says what was searched, most first."""

    def test_a_picked_word_is_counted_from_its_one_search(
        self, said_by: SaidByFilter, host: _Host
    ) -> None:
        assert said_by.story_counts() == [("", 3), ("Donald", 2), ("Scrooge", 1)]
        assert host.asked == [None]

    def test_a_typed_query_is_run_again_under_each_speaker(
        self, said_by: SaidByFilter, host: _Host
    ) -> None:
        host.searched = ("gold -mine", "", None)
        assert said_by.story_counts() == [("", 3), ("Donald", 2), ("Scrooge", 1)]
        assert host.asked == [None, "Donald", "Scrooge"]  # the roster's order

    def test_the_same_search_is_counted_once(self, said_by: SaidByFilter, host: _Host) -> None:
        said_by.story_counts()
        said_by.story_counts()
        assert host.asked == [None]
        host.searched = ("", "silver", None)
        said_by.story_counts()
        assert host.asked == [None, None]

    def test_the_picked_speaker_stays_listed_at_none(
        self, said_by: SaidByFilter, host: _Host
    ) -> None:
        host.found = _said_in({"A": ["Donald"]})
        host.stories_with = {"Donald": ("A",)}
        said_by.speaker = "Scrooge"
        assert said_by.story_counts() == [("", 1), ("Donald", 1), ("Scrooge", 0)]


class TestTheList:
    """The chip opens the list; a row picked narrows the search; closed, the chip has the keys."""

    def test_a_click_opens_it_with_each_speakers_stories(
        self, said_by: SaidByFilter, loguru_sink: list[str]
    ) -> None:
        said_by.speaker = "Donald"
        said_by.show()
        press(_chip(said_by))
        assert [(r.text, r.count_text, r.selected) for r in _list(said_by).rows] == [
            ("anyone", "3", False),
            ("Donald", "2", True),
            ("Scrooge", "1", False),
        ]
        assert loguru_sink[-1] == log_markers.SPEAKER_LIST_OPENED.format(count=2)
        assert said_by.list_open_without_the_keys() is True
        assert said_by._focus.area == FocusArea.INPUT  # a click moves no keyboard focus

    def test_a_list_that_cannot_open_is_not_logged_as_opened(
        self, said_by: SaidByFilter, loguru_sink: list[str]
    ) -> None:
        said_by.show()
        with patch.object(FakeSpeakerList, "open_if_shown", return_value=False):
            press(_chip(said_by))
        assert log_markers.SPEAKER_LIST_OPENED.format(count=2) not in loguru_sink

    def test_a_row_picked_sets_the_speaker_tells_the_screen_and_closes(
        self, said_by: SaidByFilter, host: _Host, loguru_sink: list[str]
    ) -> None:
        said_by.show()
        press(_chip(said_by))
        _list(said_by).rows[2].dispatch("on_release")  # Scrooge
        assert said_by.speaker == "Scrooge"
        assert host.picks == 1
        assert _list(said_by).is_open is False
        assert log_markers.SPEAKER_FILTER_SET.format(speaker="Scrooge") in loguru_sink
        assert loguru_sink[-1] == log_markers.DROPDOWN_DISMISSED

    def test_anyone_picked_lifts_the_filter(
        self, said_by: SaidByFilter, loguru_sink: list[str]
    ) -> None:
        said_by.speaker = "Donald"
        said_by.show()
        press(_chip(said_by))
        _list(said_by).rows[0].dispatch("on_release")
        assert said_by.speaker == ""
        assert log_markers.SPEAKER_FILTER_SET.format(speaker="All") in loguru_sink

    def test_by_the_remote_the_keys_walk_it_from_the_speaker_picked(
        self, said_by: SaidByFilter
    ) -> None:
        said_by.speaker = "Donald"
        said_by.show()
        said_by._focus.area = FocusArea.SPEAKERS
        said_by.row.enter_focus(0)
        press(_chip(said_by))
        assert said_by._focus.area == FocusArea.SAID_BY_LIST
        assert said_by.row.focused is None
        assert said_by._dropdown_focused_idx == 1  # Donald
        assert said_by.list_open_without_the_keys() is False

        assert said_by.handle_list_key(KEY_DOWN) is True
        assert _list(said_by).scrolled_to is _list(said_by).rows[2]
        assert said_by.handle_list_key(KEY_ENTER) is True
        assert said_by.speaker == "Scrooge"
        # Closed under the keys: they are the chip's again.
        assert (said_by._focus.area, said_by.row.focused) == (FocusArea.SPEAKERS, 0)
        assert said_by._dropdown_nav_mode is False

    def test_escape_closes_it_and_keeps_the_speaker(self, said_by: SaidByFilter) -> None:
        said_by.show()
        said_by._focus.area = FocusArea.SPEAKERS
        said_by.row.enter_focus(0)
        press(_chip(said_by))
        assert said_by.handle_list_key(KEY_ESCAPE) is True
        assert (_list(said_by).is_open, said_by.speaker) == (False, "")
        assert (said_by._focus.area, said_by.row.focused) == (FocusArea.SPEAKERS, 0)

    def test_a_list_the_mouse_closes_moves_no_keyboard_focus(self, said_by: SaidByFilter) -> None:
        said_by.show()
        press(_chip(said_by))
        said_by.close_list()
        assert (said_by._focus.area, said_by.row.focused) == (FocusArea.INPUT, None)

    def test_the_keys_taken_onto_a_list_the_mouse_opened(self, said_by: SaidByFilter) -> None:
        said_by.speaker = "Scrooge"
        said_by.show()
        press(_chip(said_by))
        said_by.take_keys_onto_list()
        assert said_by._focus.area == FocusArea.SAID_BY_LIST
        assert said_by._dropdown_focused_idx == 2  # noqa: PLR2004
        assert said_by.list_open_without_the_keys() is False
