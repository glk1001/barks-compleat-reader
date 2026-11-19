# The reading history intentionally records naive local times.
# ruff: noqa: DTZ001

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import barks_reader.core.read_state
import pytest
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE
from barks_fantagraphics.comic_book_info import COVERS, ONE_PAGERS
from barks_reader.core.read_state import (
    ReadState,
    ReadStates,
    ReadStateSource,
    get_read_states,
    is_finished_event,
    is_single_page_title,
)
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE
from barks_reader.core.reading_history import ReadEvent, ReadingHistoryStore

if TYPE_CHECKING:
    from pathlib import Path

_OPENED = datetime(2026, 11, 1, 20, 0)
_ANDES = "Lost in the Andes!"
_VACATION = "Vacation Time"


def _event(
    title_str: str = _ANDES,
    *,
    day: int = 0,
    page: str = "",
    finished: bool | None = None,
    closed: bool = True,
    event_id: str = "",
) -> ReadEvent:
    opened_at = _OPENED + timedelta(days=day)
    return ReadEvent(
        event_id or f"{title_str}-{day}",
        title_str,
        opened_at,
        closed_at=opened_at + timedelta(minutes=20) if closed else None,
        last_display_page=page,
        last_body_page="32",
        finished=finished,
    )


class TestIsFinishedEvent:
    @pytest.mark.parametrize("finished", [True, False])
    def test_a_session_that_says_is_believed_whatever_its_page(self, finished: bool) -> None:
        # Closed on the cover and closed on the last page both save COMIC_BEGIN_PAGE.
        assert is_finished_event(_event(page=COMIC_BEGIN_PAGE, finished=finished)) is finished

    def test_an_old_session_closed_back_at_the_beginning_is_finished(self) -> None:
        assert is_finished_event(_event(page=COMIC_BEGIN_PAGE))

    def test_an_old_session_closed_mid_comic_is_not(self) -> None:
        assert not is_finished_event(_event(page="12"))

    def test_an_old_session_with_no_page_is_not(self) -> None:
        assert not is_finished_event(_event(page=""))

    def test_a_session_never_closed_is_not(self) -> None:
        assert not is_finished_event(_event(page=COMIC_BEGIN_PAGE, closed=False))


class TestIsSinglePageTitle:
    def test_a_one_pager_and_a_cover_are(self) -> None:
        assert is_single_page_title(ENUM_TO_STR_TITLE[ONE_PAGERS[0]])
        assert is_single_page_title(ENUM_TO_STR_TITLE[COVERS[0]])

    def test_a_story_is_not(self) -> None:
        assert not is_single_page_title(_ANDES)

    def test_a_title_the_app_does_not_know_is_not(self) -> None:
        assert not is_single_page_title("No Such Story")


class TestGetReadStates:
    def test_no_history_is_all_unread(self) -> None:
        states = get_read_states([])

        assert states == ReadStates()
        assert states.state_of(_ANDES) is ReadState.UNREAD

    def test_a_finished_session_finishes_its_title(self) -> None:
        states = get_read_states([_event(page=COMIC_BEGIN_PAGE, finished=True)])

        assert states.state_of(_ANDES) is ReadState.FINISHED
        assert states.left_mid_way == ()

    def test_a_session_left_mid_comic_is_part_read(self) -> None:
        states = get_read_states([_event(page="12", finished=False)])

        assert states.state_of(_ANDES) is ReadState.PART_READ
        assert states.left_mid_way == (_ANDES,)
        assert states.finished == frozenset()

    def test_a_comic_closed_on_its_cover_stays_unread(self) -> None:
        states = get_read_states([_event(page=COMIC_BEGIN_PAGE, finished=False)])

        assert states.state_of(_ANDES) is ReadState.UNREAD

    def test_finishing_what_was_left_mid_way_takes_it_off_the_list(self) -> None:
        states = get_read_states(
            [
                _event(day=0, page="12", finished=False),
                _event(day=1, page=COMIC_BEGIN_PAGE, finished=True),
            ]
        )

        assert states.state_of(_ANDES) is ReadState.FINISHED
        assert states.left_mid_way == ()

    def test_a_finished_story_being_read_again_is_part_read_until_it_is_finished_again(
        self,
    ) -> None:
        states = get_read_states(
            [
                _event(day=0, page=COMIC_BEGIN_PAGE, finished=True),
                _event(day=1, page="7", finished=False),
            ]
        )

        # 'Continue reading' lists it, so its mark is the half dot, not the full one.
        assert states.state_of(_ANDES) is ReadState.PART_READ
        assert states.left_mid_way == (_ANDES,)
        assert states.finished == frozenset({_ANDES})  # it still counts as read

        again = get_read_states(
            [
                _event(day=0, page=COMIC_BEGIN_PAGE, finished=True),
                _event(day=1, page="7", finished=False),
                _event(day=2, page=COMIC_BEGIN_PAGE, finished=True),
            ]
        )
        assert again.state_of(_ANDES) is ReadState.FINISHED

    def test_left_mid_way_is_most_recently_opened_first(self) -> None:
        states = get_read_states(
            [
                _event(_ANDES, day=0, page="12", finished=False),
                _event(_VACATION, day=2, page="3", finished=False),
            ]
        )

        assert states.left_mid_way == (_VACATION, _ANDES)

    def test_a_crashed_latest_session_does_not_hide_the_place(self) -> None:
        states = get_read_states(
            [_event(day=0, page="12", finished=False), _event(day=1, page="", closed=False)]
        )

        assert states.left_mid_way == (_ANDES,)

    def test_a_one_pager_is_finished_by_being_opened(self) -> None:
        # It is a page inside its collection, so its session closes "mid-comic".
        one_pager = ENUM_TO_STR_TITLE[ONE_PAGERS[0]]

        states = get_read_states([_event(one_pager, page="17", finished=False)])

        assert states.state_of(one_pager) is ReadState.FINISHED
        assert states.left_mid_way == ()

    def test_the_single_page_rule_can_be_given(self) -> None:
        states = get_read_states([_event(page="12")], is_single_page=lambda _title: True)

        assert states.finished == frozenset({_ANDES})
        assert states.left_mid_way == ()


class TestReadStateSource:
    def test_it_follows_the_store(self, tmp_path: Path) -> None:
        store = ReadingHistoryStore(tmp_path / "history.json")
        source = ReadStateSource(store)
        assert source.states() == ReadStates()

        store.add_event(_event(page=COMIC_BEGIN_PAGE, finished=True))
        assert source.states().state_of(_ANDES) is ReadState.FINISHED

        store.delete_events_for_title(_ANDES)
        assert source.states().state_of(_ANDES) is ReadState.UNREAD

    def test_an_unchanged_store_is_not_worked_out_again(self, tmp_path: Path) -> None:
        store = ReadingHistoryStore(tmp_path / "history.json")
        store.add_event(_event(page="12", finished=False))
        source = ReadStateSource(store)

        with patch.object(
            barks_reader.core.read_state,
            "get_read_states",
            wraps=barks_reader.core.read_state.get_read_states,
        ) as worked_out:
            first = source.states()
            second = source.states()
            store.add_event(_event(_VACATION, day=1, page="3", finished=False))
            third = source.states()

        assert worked_out.call_count == 2  # noqa: PLR2004
        assert second is first
        assert third.left_mid_way == (_VACATION, _ANDES)

    def test_the_values_are_the_names_the_tree_s_kv_reads(self) -> None:
        assert [state.value for state in ReadState] == ["unread", "part_read", "finished"]
