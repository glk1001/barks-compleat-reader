"""Record and browse the user's comic reading history (Kivy-free).

Every comic open is appended to a JSON event log (``barks-reader-history.json``)
as a :class:`ReadEvent`; closing the reader fills in the close time and last-read
page. Pure derivation helpers turn the raw log into the two history views:
a day-grouped journal (:func:`group_events_by_day`) and a per-title summary
(:func:`summarize_titles`).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Self

from loguru import logger

from .reader_consts_and_types import COMIC_BEGIN_PAGE

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .saved_page_info import SavedPageInfo

JsonReadEvent = dict[str, Any]

_STORE_VERSION = 1
_MINS_PER_HOUR = 60


@dataclass(slots=True)
class ReadEvent:
    """One reading session: a comic was opened (and usually closed)."""

    event_id: str
    title_str: str
    opened_at: datetime
    closed_at: datetime | None = None
    last_display_page: str = ""
    last_body_page: str = ""

    @staticmethod
    def new_event_id() -> str:
        """Return a fresh unique event id."""
        return uuid.uuid4().hex

    def to_json(self) -> JsonReadEvent:
        """Serialize this event to a JSON-compatible dict."""
        return {
            "id": self.event_id,
            "title": self.title_str,
            "opened_at": self.opened_at.isoformat(timespec="seconds"),
            "closed_at": (
                None if self.closed_at is None else self.closed_at.isoformat(timespec="seconds")
            ),
            "last_display_page": self.last_display_page,
            "last_body_page": self.last_body_page,
        }

    @classmethod
    def from_json(cls, json_event: JsonReadEvent) -> Self:
        """Deserialize an event from a JSON-compatible dict."""
        closed_at = json_event["closed_at"]
        return cls(
            event_id=json_event["id"],
            title_str=json_event["title"],
            opened_at=datetime.fromisoformat(json_event["opened_at"]),
            closed_at=None if closed_at is None else datetime.fromisoformat(closed_at),
            last_display_page=json_event["last_display_page"],
            last_body_page=json_event["last_body_page"],
        )


class ReadingHistoryStore:
    """Persist the reading-history event log to a JSON file."""

    def __init__(self, store_path: Path) -> None:
        """Load the store, tolerating a missing or empty file.

        Args:
            store_path: Path of the history JSON file.

        """
        self._store_path = store_path
        self._events: list[ReadEvent] = []

        if store_path.exists() and (contents := store_path.read_text(encoding="utf-8").strip()):
            try:
                self._events = [ReadEvent.from_json(e) for e in json.loads(contents)["events"]]
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                logger.error(f'History: Could not load "{store_path}": {e}. Starting empty.')

    def _sync(self) -> None:
        json_data = {"version": _STORE_VERSION, "events": [e.to_json() for e in self._events]}
        self._store_path.write_text(json.dumps(json_data, indent=4), encoding="utf-8")

    def get_events(self) -> list[ReadEvent]:
        """Return all events in chronological (oldest-first) order."""
        return list(self._events)

    def add_event(self, event: ReadEvent) -> None:
        """Append a new event and persist."""
        self._events.append(event)
        self._sync()

    def update_event(self, event: ReadEvent) -> None:
        """Replace the stored event with the same ``event_id`` and persist."""
        for i, existing in enumerate(self._events):
            if existing.event_id == event.event_id:
                self._events[i] = event
                self._sync()
                return
        logger.warning(f'History: Cannot update unknown event "{event.event_id}".')

    def delete_event(self, event_id: str) -> None:
        """Delete the event with the given id and persist."""
        self._events = [e for e in self._events if e.event_id != event_id]
        self._sync()

    def delete_events_for_title(self, title_str: str) -> None:
        """Delete all events for a title and persist."""
        self._events = [e for e in self._events if e.title_str != title_str]
        self._sync()

    def clear(self) -> None:
        """Delete all events and persist."""
        self._events = []
        self._sync()


class ReadingHistoryTracker:
    """Record reading sessions to a :class:`ReadingHistoryStore`.

    A session is bracketed by :meth:`begin` (comic opened) and :meth:`end`
    (reader closed), mirroring ``LastReadPageTracker``. Recording is gated by
    the injected ``is_enabled`` callable so the settings toggle applies without
    any UI dependency.
    """

    def __init__(
        self,
        store: ReadingHistoryStore,
        is_enabled: Callable[[], bool],
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        """Initialize the tracker.

        Args:
            store: The persistent event log.
            is_enabled: Returns whether history recording is currently on.
            now: Clock function (injectable for tests).

        """
        self._store = store
        self._is_enabled = is_enabled
        self._now = now
        self._open_event: ReadEvent | None = None

    def begin(self, title_str: str) -> None:
        """Record that a comic has been opened (no-op when recording is off)."""
        if not self._is_enabled():
            self._open_event = None
            return

        if self._open_event is not None:
            logger.warning(f'History: "{self._open_event.title_str}" was never closed.')

        self._open_event = ReadEvent(ReadEvent.new_event_id(), title_str, self._now())
        self._store.add_event(self._open_event)
        logger.debug(f'History: Recorded open of "{title_str}".')

    def end(self, last_read_page: SavedPageInfo | None) -> None:
        """Record the close of the current session (no-op without an open one)."""
        if self._open_event is None:
            return

        self._open_event.closed_at = self._now()
        if last_read_page is not None:
            self._open_event.last_display_page = last_read_page.display_page_num
            self._open_event.last_body_page = last_read_page.last_body_page
        self._store.update_event(self._open_event)

        logger.debug(f'History: Recorded close of "{self._open_event.title_str}".')
        self._open_event = None


@dataclass(frozen=True, slots=True)
class DayGroup:
    """All events of one calendar day, newest first."""

    heading: str
    events: list[ReadEvent] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TitleSummary:
    """Per-title aggregate of the event log."""

    title_str: str
    last_opened_at: datetime
    read_count: int
    last_display_page: str = ""
    last_body_page: str = ""


def get_day_heading(day: date, today: date) -> str:
    """Return the journal heading for a calendar day (e.g. "Today")."""
    if day == today:
        return "Today"
    if day == today - timedelta(days=1):
        return "Yesterday"
    return f"{day:%A} {day.day} {day:%B %Y}"


def group_events_by_day(events: list[ReadEvent], today: date) -> list[DayGroup]:
    """Group events by calendar day, newest day and newest event first.

    Args:
        events: The event log in any order.
        today: The current date (for "Today"/"Yesterday" headings).

    Returns:
        Day groups, newest day first; events within a group are newest first.

    """
    events_by_day: dict[date, list[ReadEvent]] = {}
    for event in sorted(events, key=lambda e: e.opened_at, reverse=True):
        events_by_day.setdefault(event.opened_at.date(), []).append(event)

    return [
        DayGroup(get_day_heading(day, today), day_events)
        for day, day_events in events_by_day.items()
    ]


def summarize_titles(events: list[ReadEvent]) -> list[TitleSummary]:
    """Aggregate the event log per title, most recently read first.

    The summary's page fields come from the most recent event that recorded a
    page, so a crash-truncated latest read doesn't hide the reading position.

    Args:
        events: The event log in any order.

    Returns:
        One summary per title, ordered by last-opened time descending.

    """
    events_by_title: dict[str, list[ReadEvent]] = {}
    for event in events:
        events_by_title.setdefault(event.title_str, []).append(event)

    summaries = []
    for title, title_events in events_by_title.items():
        title_events.sort(key=lambda e: e.opened_at, reverse=True)
        last_paged = next((e for e in title_events if e.last_display_page), None)
        summaries.append(
            TitleSummary(
                title_str=title,
                last_opened_at=title_events[0].opened_at,
                read_count=len(title_events),
                last_display_page="" if last_paged is None else last_paged.last_display_page,
                last_body_page="" if last_paged is None else last_paged.last_body_page,
            )
        )

    return sorted(summaries, key=lambda s: s.last_opened_at, reverse=True)


def format_unfinished_page(summary: TitleSummary) -> str:
    """Return "at p N" when the title was left mid-comic, else "".

    A finished comic's position is normalised to ``COMIC_BEGIN_PAGE``, so
    only genuinely mid-comic positions produce a fragment.
    """
    if summary.last_display_page and summary.last_display_page != COMIC_BEGIN_PAGE:
        return f"at p {summary.last_display_page}"
    return ""


def format_event_time(event: ReadEvent) -> str:
    """Return the open time of an event as "HH:MM"."""
    return f"{event.opened_at:%H:%M}"


def format_event_duration(event: ReadEvent) -> str:
    """Return the session's duration, e.g. "25 min", "1 hr 5 min", "" (crash)."""
    if event.closed_at is None:
        return ""

    total_mins = round((event.closed_at - event.opened_at).total_seconds() / 60)
    hours, mins = divmod(total_mins, _MINS_PER_HOUR)
    if hours:
        return f"{hours} hr {mins} min" if mins else f"{hours} hr"
    return f"{mins} min" if mins else "< 1 min"


def format_event_page(event: ReadEvent) -> str:
    """Return "to p N" when the session ended mid-comic, else "".

    A finished comic's position is normalised to ``COMIC_BEGIN_PAGE``, so
    only genuinely mid-comic positions produce a fragment.
    """
    if event.last_display_page and event.last_display_page != COMIC_BEGIN_PAGE:
        return f"to p {event.last_display_page}"
    return ""
