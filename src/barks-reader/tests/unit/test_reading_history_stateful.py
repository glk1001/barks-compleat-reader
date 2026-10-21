"""The reading history under any sequence of sessions and edits: a Hypothesis state machine.

The stateful pilot of docs/BACKLOG.md. Hypothesis draws a sequence of the rules below
(a comic opened, the reader closed, the clock moved, recording switched, an event
deleted or the log cleared) and checks every invariant after each step: the store
holds exactly the events the model expects, the file on disk reads back as the store,
the revision counts the writes, and the two history views agree with the log.

The machine runs from a module-level function through ``run_state_machine_as_test``,
not as the class-scoped ``TestCase`` Hypothesis generates: mutmut runs pytest many
times in one process, and a class-scoped Hypothesis test trips its differing-executors
health check from the second run on (docs/mutation-testing.md).

The reading history intentionally records naive local times.
"""
# ruff: noqa: DTZ001

from __future__ import annotations

import tempfile
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from barks_fantagraphics.comics_consts import PageType
from barks_reader.core.reading_history import (
    ReadEvent,
    ReadingHistoryStore,
    ReadingHistoryTracker,
    get_day_heading,
    group_events_by_day,
    summarize_titles,
)
from barks_reader.core.saved_page_info import SavedPageInfo
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)

_TITLES = st.sampled_from(["Lost in the Andes!", "Vacation Time", "Trick or Treat"])
_PAGES = st.none() | st.builds(
    SavedPageInfo,
    page_index=st.integers(min_value=0, max_value=40),
    display_page_num=st.sampled_from(["1", "7", "12", "32"]),
    page_type=st.sampled_from([PageType.BODY, PageType.FRONT]),
    last_body_page=st.just("32"),
)


class ReadingHistoryMachine(RuleBasedStateMachine):
    """A tracker over a store on disk, beside a model of the log the store should hold."""

    def __init__(self) -> None:
        super().__init__()
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name) / "history.json"
        self.store = ReadingHistoryStore(self.path)
        self.enabled = True
        self.now = datetime(2026, 7, 17, 9, 0)
        self.tracker = ReadingHistoryTracker(
            self.store, is_enabled=lambda: self.enabled, now=lambda: self.now
        )
        # The model: the events the store should hold, in order; the session begun and
        # not yet ended, as the tracker made it; the sessions a second begin orphaned;
        # and how many times the store should have written its file.
        self.model: list[ReadEvent] = []
        self.open_event: ReadEvent | None = None
        self.orphaned: set[str] = set()
        self.writes = 0

    def teardown(self) -> None:
        self._dir.cleanup()

    # --- rules: the tracker's sessions ---

    @rule(title=_TITLES)
    def begin(self, title: str) -> None:
        before = self.store.get_events()
        self.tracker.begin(title)
        after = self.store.get_events()
        if not self.enabled:
            assert after == before
            if self.open_event is not None:  # Forgotten, never closed, like a crash.
                self.orphaned.add(self.open_event.event_id)
            self.open_event = None
            return
        assert len(after) == len(before) + 1
        if self.open_event is not None:
            self.orphaned.add(self.open_event.event_id)
        self.open_event = ReadEvent(after[-1].event_id, title, self.now)
        self.model.append(replace(self.open_event))
        self.writes += 1

    @rule(page=_PAGES)
    def end(self, page: SavedPageInfo | None) -> None:
        self.tracker.end(page)
        if self.open_event is None:
            return
        closed = replace(
            self.open_event,
            closed_at=self.now,
            last_display_page="" if page is None else page.display_page_num,
            last_body_page="" if page is None else page.last_body_page,
        )
        self.open_event = None
        # A session whose event was deleted meanwhile has nothing to update.
        for i, event in enumerate(self.model):
            if event.event_id == closed.event_id:
                self.model[i] = closed
                self.writes += 1
                return

    @rule(minutes=st.integers(min_value=0, max_value=180))
    def advance_the_clock(self, minutes: int) -> None:
        self.now += timedelta(minutes=minutes)

    @rule(enabled=st.booleans())
    def switch_recording(self, enabled: bool) -> None:
        self.enabled = enabled

    # --- rules: edits of the log ---

    @precondition(lambda self: self.model)
    @rule(data=st.data())
    def delete_an_event(self, data: st.DataObject) -> None:
        event_id = data.draw(st.sampled_from([e.event_id for e in self.model]))
        self.store.delete_event(event_id)
        self.model = [e for e in self.model if e.event_id != event_id]
        self.writes += 1

    @rule()
    def delete_an_unknown_event(self) -> None:
        self.store.delete_event("no such event")
        self.writes += 1  # Deleting writes the file whether or not anything matched.

    @rule(title=_TITLES)
    def delete_a_title(self, title: str) -> None:
        self.store.delete_events_for_title(title)
        self.model = [e for e in self.model if e.title_str != title]
        self.writes += 1

    @precondition(lambda self: self.model)
    @rule(data=st.data(), page=st.sampled_from(["", "3", "9"]))
    def update_an_event(self, data: st.DataObject, page: str) -> None:
        event = replace(data.draw(st.sampled_from(self.model)), last_display_page=page)
        self.store.update_event(event)
        self.model = [event if e.event_id == event.event_id else e for e in self.model]
        self.writes += 1

    @rule()
    def update_an_unknown_event(self) -> None:
        self.store.update_event(ReadEvent("no such event", "Vacation Time", self.now))

    @rule()
    def clear(self) -> None:
        self.store.clear()
        self.model = []
        self.writes += 1

    # --- invariants ---

    @invariant()
    def the_store_holds_the_model_s_events(self) -> None:
        assert self.store.get_events() == self.model

    @invariant()
    def the_file_reads_back_as_the_store(self) -> None:
        assert ReadingHistoryStore(self.path).get_events() == self.store.get_events()

    @invariant()
    def the_revision_counts_the_writes(self) -> None:
        assert self.store.revision == self.writes

    @invariant()
    def no_session_closes_before_it_opens_and_only_open_sessions_lack_a_close(self) -> None:
        unclosed = {e.event_id for e in self.model if e.closed_at is None}
        open_ids = self.orphaned | ({self.open_event.event_id} if self.open_event else set())
        assert unclosed == open_ids & {e.event_id for e in self.model}
        for event in self.model:
            if event.closed_at is not None:
                assert event.closed_at >= event.opened_at

    @invariant()
    def the_title_summaries_count_every_event_once(self) -> None:
        summaries = summarize_titles(self.model)
        assert {s.title_str for s in summaries} == {e.title_str for e in self.model}
        assert len(summaries) == len({s.title_str for s in summaries})
        opened = [s.last_opened_at for s in summaries]
        assert opened == sorted(opened, reverse=True)  # Titles opened the same second tie.
        assert sum(s.read_count for s in summaries) == len(self.model)
        for summary in summaries:
            title_events = [e for e in self.model if e.title_str == summary.title_str]
            assert summary.read_count == len(title_events)
            assert summary.last_opened_at == max(e.opened_at for e in title_events)
            paged = [e for e in title_events if e.last_display_page]
            if paged:
                latest = max(paged, key=lambda e: e.opened_at)
                assert (summary.last_display_page, summary.last_body_page) == (
                    latest.last_display_page,
                    latest.last_body_page,
                )
            else:
                assert (summary.last_display_page, summary.last_body_page) == ("", "")

    @invariant()
    def the_journal_lists_every_event_newest_first_under_its_day(self) -> None:
        today = self.now.date()
        groups = group_events_by_day(self.model, today)
        assert [e for g in groups for e in g.events] == sorted(
            self.model, key=lambda e: e.opened_at, reverse=True
        )
        days = [g.events[0].opened_at.date() for g in groups]
        assert days == sorted(set(days), reverse=True)
        for group, day in zip(groups, days, strict=True):
            assert group.heading == get_day_heading(day, today)
            assert all(e.opened_at.date() == day for e in group.events)


def test_the_reading_history_keeps_its_log_under_any_sequence_of_sessions_and_edits() -> None:
    run_state_machine_as_test(
        ReadingHistoryMachine, settings=settings(stateful_step_count=40, deadline=None)
    )
