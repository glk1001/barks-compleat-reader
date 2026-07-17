# The reading history intentionally records naive local times.
# ruff: noqa: DTZ001

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_reader.core.reading_history import (
    ReadEvent,
    ReadingHistoryStore,
    ReadingHistoryTracker,
    TitleSummary,
    format_event_duration,
    format_event_page,
    format_event_time,
    format_unfinished_page,
    group_events_by_day,
    summarize_titles,
)
from barks_reader.core.saved_page_info import SavedPageInfo

if TYPE_CHECKING:
    from pathlib import Path

_TODAY = date(2026, 7, 17)


def _make_event(
    title_str: str = "Lost in the Andes!",
    opened_at: datetime = datetime(2026, 7, 17, 14, 30),
    closed_at: datetime | None = None,
    event_id: str = "abc123",
) -> ReadEvent:
    return ReadEvent(event_id, title_str, opened_at, closed_at)


class TestReadEventJson:
    def test_round_trip(self) -> None:
        event = ReadEvent(
            event_id="deadbeef",
            title_str="Vacation Time",
            opened_at=datetime(2026, 7, 16, 20, 5, 33),
            closed_at=datetime(2026, 7, 16, 21, 2, 1),
            last_display_page="12",
            last_body_page="32",
        )
        assert ReadEvent.from_json(event.to_json()) == event

    def test_round_trip_with_no_close(self) -> None:
        event = _make_event()
        restored = ReadEvent.from_json(event.to_json())
        assert restored == event
        assert restored.closed_at is None


class TestReadingHistoryStore:
    def test_missing_file_starts_empty(self, tmp_path: Path) -> None:
        store = ReadingHistoryStore(tmp_path / "history.json")
        assert store.get_events() == []

    def test_corrupt_file_starts_empty(self, tmp_path: Path) -> None:
        store_path = tmp_path / "history.json"
        store_path.write_text("not json at all", encoding="utf-8")
        store = ReadingHistoryStore(store_path)
        assert store.get_events() == []

    def test_add_event_persists_across_reload(self, tmp_path: Path) -> None:
        store_path = tmp_path / "history.json"
        event = _make_event()
        ReadingHistoryStore(store_path).add_event(event)

        reloaded = ReadingHistoryStore(store_path)
        assert reloaded.get_events() == [event]

    def test_update_event_replaces_by_id(self, tmp_path: Path) -> None:
        store_path = tmp_path / "history.json"
        store = ReadingHistoryStore(store_path)
        event = _make_event()
        store.add_event(event)

        event.closed_at = datetime(2026, 7, 17, 15, 0)
        event.last_display_page = "5"
        store.update_event(event)

        reloaded = ReadingHistoryStore(store_path)
        assert reloaded.get_events() == [event]

    def test_update_unknown_event_is_noop(self, tmp_path: Path) -> None:
        store = ReadingHistoryStore(tmp_path / "history.json")
        store.update_event(_make_event(event_id="unknown"))
        assert store.get_events() == []

    def test_delete_event(self, tmp_path: Path) -> None:
        store = ReadingHistoryStore(tmp_path / "history.json")
        keep = _make_event(event_id="keep")
        store.add_event(_make_event(event_id="gone"))
        store.add_event(keep)

        store.delete_event("gone")
        assert store.get_events() == [keep]

    def test_delete_events_for_title(self, tmp_path: Path) -> None:
        store = ReadingHistoryStore(tmp_path / "history.json")
        keep = _make_event(title_str="Vacation Time", event_id="keep")
        store.add_event(_make_event(title_str="Trick or Treat", event_id="a"))
        store.add_event(keep)
        store.add_event(_make_event(title_str="Trick or Treat", event_id="b"))

        store.delete_events_for_title("Trick or Treat")
        assert store.get_events() == [keep]

    def test_clear(self, tmp_path: Path) -> None:
        store_path = tmp_path / "history.json"
        store = ReadingHistoryStore(store_path)
        store.add_event(_make_event())
        store.clear()

        assert store.get_events() == []
        assert ReadingHistoryStore(store_path).get_events() == []


class _FixedClock:
    def __init__(self, *times: datetime) -> None:
        self._times = list(times)

    def __call__(self) -> datetime:
        return self._times.pop(0)


class TestReadingHistoryTracker:
    def _make_tracker(
        self, tmp_path: Path, clock: _FixedClock, *, enabled: bool = True
    ) -> tuple[ReadingHistoryTracker, ReadingHistoryStore]:
        store = ReadingHistoryStore(tmp_path / "history.json")
        tracker = ReadingHistoryTracker(store, is_enabled=lambda: enabled, now=clock)
        return tracker, store

    def test_begin_and_end_record_one_event(self, tmp_path: Path) -> None:
        opened = datetime(2026, 7, 17, 14, 0)
        closed = datetime(2026, 7, 17, 14, 25)
        tracker, store = self._make_tracker(tmp_path, _FixedClock(opened, closed))

        tracker.begin("Lost in the Andes!")
        last_page = SavedPageInfo(
            page_index=11, display_page_num="12", page_type=PageType.BODY, last_body_page="32"
        )
        tracker.end(last_page)

        (event,) = store.get_events()
        assert event.title_str == "Lost in the Andes!"
        assert event.opened_at == opened
        assert event.closed_at == closed
        assert event.last_display_page == "12"
        assert event.last_body_page == "32"

    def test_end_with_no_page_still_records_close_time(self, tmp_path: Path) -> None:
        opened = datetime(2026, 7, 17, 14, 0)
        closed = datetime(2026, 7, 17, 14, 1)
        tracker, store = self._make_tracker(tmp_path, _FixedClock(opened, closed))

        tracker.begin("Vacation Time")
        tracker.end(None)

        (event,) = store.get_events()
        assert event.closed_at == closed
        assert event.last_display_page == ""

    def test_end_without_begin_is_noop(self, tmp_path: Path) -> None:
        tracker, store = self._make_tracker(tmp_path, _FixedClock())
        tracker.end(None)
        assert store.get_events() == []

    def test_disabled_records_nothing(self, tmp_path: Path) -> None:
        tracker, store = self._make_tracker(tmp_path, _FixedClock(), enabled=False)
        tracker.begin("Lost in the Andes!")
        tracker.end(None)
        assert store.get_events() == []

    def test_double_begin_records_both_opens(self, tmp_path: Path) -> None:
        clock = _FixedClock(datetime(2026, 7, 17, 14, 0), datetime(2026, 7, 17, 15, 0))
        tracker, store = self._make_tracker(tmp_path, clock)

        tracker.begin("Vacation Time")
        tracker.begin("Trick or Treat")

        titles = [e.title_str for e in store.get_events()]
        assert titles == ["Vacation Time", "Trick or Treat"]


class TestGroupEventsByDay:
    def test_headings_and_ordering(self) -> None:
        today_event = _make_event(opened_at=datetime(2026, 7, 17, 9, 0), event_id="a")
        today_later = _make_event(opened_at=datetime(2026, 7, 17, 14, 0), event_id="b")
        yesterday_event = _make_event(opened_at=datetime(2026, 7, 16, 21, 0), event_id="c")
        older_event = _make_event(opened_at=datetime(2026, 6, 12, 20, 0), event_id="d")

        groups = group_events_by_day(
            [older_event, today_event, yesterday_event, today_later], _TODAY
        )

        assert [g.heading for g in groups] == ["Today", "Yesterday", "Friday 12 June 2026"]
        assert [e.event_id for e in groups[0].events] == ["b", "a"]
        assert groups[1].events == [yesterday_event]
        assert groups[2].events == [older_event]

    def test_no_events(self) -> None:
        assert group_events_by_day([], _TODAY) == []


class TestSummarizeTitles:
    def test_counts_and_ordering(self) -> None:
        events = [
            _make_event("Vacation Time", datetime(2026, 7, 15, 9, 0), event_id="a"),
            _make_event("Trick or Treat", datetime(2026, 7, 16, 9, 0), event_id="b"),
            _make_event("Vacation Time", datetime(2026, 7, 17, 9, 0), event_id="c"),
        ]

        summaries = summarize_titles(events)

        assert [(s.title_str, s.read_count) for s in summaries] == [
            ("Vacation Time", 2),
            ("Trick or Treat", 1),
        ]
        assert summaries[0].last_opened_at == datetime(2026, 7, 17, 9, 0)

    def test_page_fields_come_from_most_recent_paged_event(self) -> None:
        older = _make_event("Vacation Time", datetime(2026, 7, 15, 9, 0), event_id="a")
        older.last_display_page = "5"
        older.last_body_page = "33"
        newer = _make_event("Vacation Time", datetime(2026, 7, 16, 9, 0), event_id="b")
        newer.last_display_page = "12"
        newer.last_body_page = "33"
        crashed_latest = _make_event("Vacation Time", datetime(2026, 7, 17, 9, 0), event_id="c")

        (summary,) = summarize_titles([older, crashed_latest, newer])

        # The crash event has no page - falls back to the newest event that has one.
        assert summary.last_display_page == "12"
        assert summary.last_body_page == "33"
        assert summary.last_opened_at == datetime(2026, 7, 17, 9, 0)

    def test_page_fields_empty_when_no_event_has_a_page(self) -> None:
        (summary,) = summarize_titles([_make_event()])
        assert summary.last_display_page == ""
        assert summary.last_body_page == ""


class TestFormatUnfinishedPage:
    @staticmethod
    def _make_summary(last_display_page: str) -> TitleSummary:
        return TitleSummary(
            title_str="Vacation Time",
            last_opened_at=datetime(2026, 7, 17, 9, 0),
            read_count=1,
            last_display_page=last_display_page,
            last_body_page="33",
        )

    def test_mid_comic_position(self) -> None:
        assert format_unfinished_page(self._make_summary("12")) == "at p 12"

    def test_finished_comic_shows_nothing(self) -> None:
        assert format_unfinished_page(self._make_summary("0")) == ""  # COMIC_BEGIN_PAGE

    def test_no_page_shows_nothing(self) -> None:
        assert format_unfinished_page(self._make_summary("")) == ""


class TestFormatting:
    def test_format_event_time(self) -> None:
        assert format_event_time(_make_event(opened_at=datetime(2026, 7, 17, 9, 5))) == "09:05"

    @pytest.mark.parametrize(
        ("opened", "closed", "expected"),
        [
            (datetime(2026, 7, 17, 14, 0), datetime(2026, 7, 17, 14, 25), "25 min"),
            (datetime(2026, 7, 17, 14, 0), datetime(2026, 7, 17, 14, 0, 20), "< 1 min"),
            (datetime(2026, 7, 17, 14, 0), datetime(2026, 7, 17, 15, 0), "1 hr"),
            (datetime(2026, 7, 17, 14, 0), datetime(2026, 7, 17, 16, 5), "2 hr 5 min"),
        ],
    )
    def test_format_event_duration(self, opened: datetime, closed: datetime, expected: str) -> None:
        assert format_event_duration(_make_event(opened_at=opened, closed_at=closed)) == expected

    def test_format_event_duration_crash_during_read(self) -> None:
        assert format_event_duration(_make_event()) == ""

    def test_format_event_page_mid_comic(self) -> None:
        event = _make_event()
        event.last_display_page = "12"
        assert format_event_page(event) == "to p 12"

    def test_format_event_page_skips_begin_page(self) -> None:
        event = _make_event()
        event.last_display_page = "0"  # COMIC_BEGIN_PAGE: finished/normalized
        assert format_event_page(event) == ""

    def test_format_event_page_no_page(self) -> None:
        assert format_event_page(_make_event()) == ""
