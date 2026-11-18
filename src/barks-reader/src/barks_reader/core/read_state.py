"""Which stories the user has finished, and which were left mid-way (Kivy-free).

Derived from the reading history's event log, and from nothing else: with the history
not recorded, or deleted, a story is unread.

A session says whether it finished its story (`ReadEvent.finished`). One recorded
before that was kept does not, and is judged by its page: closed back at the comic's
beginning, it is taken as finished, which is also what a comic closed on its cover
looks like. A one-pager or a cover is one page of a collection, so opening it is
reading it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM
from barks_fantagraphics.comic_book_info import COVERS_SET, ONE_PAGERS

from .reader_consts_and_types import COMIC_BEGIN_PAGE
from .reading_history import summarize_titles

if TYPE_CHECKING:
    from collections.abc import Callable

    from .reading_history import ReadEvent

_SINGLE_PAGE_TITLES = COVERS_SET | frozenset(ONE_PAGERS)


class ReadState(Enum):
    """How far the user has got with a story."""

    UNREAD = auto()
    PART_READ = auto()
    FINISHED = auto()


@dataclass(frozen=True, slots=True)
class ReadStates:
    """The read state of every story in the reading history.

    Attributes:
        finished: The titles some session finished.
        left_mid_way: The titles whose latest session stopped inside the story, most
            recently opened first. A finished story being read again is in both.

    """

    finished: frozenset[str] = frozenset()
    left_mid_way: tuple[str, ...] = ()

    def state_of(self, title_str: str) -> ReadState:
        """Return a story's state: finished, once it has been, whatever came after.

        Args:
            title_str: The story's title, as the history records it.

        Returns:
            The story's read state.

        """
        if title_str in self.finished:
            return ReadState.FINISHED
        if title_str in self.left_mid_way:
            return ReadState.PART_READ
        return ReadState.UNREAD


def is_single_page_title(title_str: str) -> bool:
    """Return whether the title is a one-pager or a cover: one page of a collection."""
    return STR_TITLE_TO_ENUM.get(title_str) in _SINGLE_PAGE_TITLES


def is_finished_event(event: ReadEvent) -> bool:
    """Return whether a session reached its story's end.

    Args:
        event: One reading session.

    Returns:
        What the session recorded; for one recorded before that was kept, whether it
        closed back at the comic's beginning.

    """
    if event.finished is not None:
        return event.finished
    return event.closed_at is not None and event.last_display_page == COMIC_BEGIN_PAGE


def get_read_states(
    events: list[ReadEvent], is_single_page: Callable[[str], bool] = is_single_page_title
) -> ReadStates:
    """Work out every story's read state from the event log.

    Args:
        events: The event log in any order.
        is_single_page: Whether a title is read by being opened.

    Returns:
        The finished titles and those left mid-way.

    """
    finished = frozenset(
        event.title_str
        for event in events
        if is_single_page(event.title_str) or is_finished_event(event)
    )
    left_mid_way = tuple(
        summary.title_str
        for summary in summarize_titles(events)
        if summary.last_display_page not in ("", COMIC_BEGIN_PAGE)
        and not is_single_page(summary.title_str)
    )
    return ReadStates(finished, left_mid_way)
