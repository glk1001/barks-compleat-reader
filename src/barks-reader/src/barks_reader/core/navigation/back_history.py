"""The places Go Back returns to: a capped stack of tree locations.

The history records jumps and not steps. A step (an arrow key moving along the tree,
or a selection the app makes inside one gesture) only moves where you are; a jump (a
press on a node, a go-to-title, the bar's Search, a Collapse) first remembers the
place it leaves. Go Back pops the last place remembered and remembers nothing itself.

One thing more is remembered. The arrows can walk a long way from a story, and a walk
is all steps: the story last rested on would be lost. So that title is remembered too,
before the place a jump leaves, and when Enter opens a node it does not sit under.
The design and the reasons for it are in `docs/plans/back-history.md`.
"""

from __future__ import annotations

from enum import Enum, auto

type TreeLocation = tuple[str, ...]
"""A tree node, named by its own name and its ancestors' (`get_tree_view_node_path`)."""

DEFAULT_MAX_ENTRIES = 30


class VisitKind(Enum):
    """How a location was arrived at."""

    STEP = auto()
    """Moved to from the place before: nothing to go back to."""
    JUMP = auto()
    """Gone to from somewhere else: the place left is remembered."""


class BackHistory:
    """Where the tree is now, and the places Go Back returns to, newest last.

    The current location is None while the tree is collapsed with nothing selected.
    The stack never holds None: there is no going back to nowhere.
    """

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        """Start nowhere, with nothing to go back to.

        Args:
            max_entries: How many places are remembered; the oldest is dropped first.

        Raises:
            ValueError: `max_entries` is less than one.

        """
        if max_entries < 1:
            msg = f"A back history needs room for at least one entry, not {max_entries}."
            raise ValueError(msg)
        self._max_entries = max_entries
        self._current: TreeLocation | None = None
        self._entries: list[TreeLocation] = []
        # The title last arrived at and not yet remembered: steps have since walked
        # off it, or it is still where the tree is.
        self._rested_title: TreeLocation | None = None

    @property
    def current(self) -> TreeLocation | None:
        """Where the tree is now, or None when nothing is selected."""
        return self._current

    @property
    def depth(self) -> int:
        """How many places there are to go back to."""
        return len(self._entries)

    def visit(
        self, location: TreeLocation | None, kind: VisitKind, *, is_title: bool = False
    ) -> None:
        """Arrive at `location`, remembering the place left if this is a jump.

        A jump also remembers, first, the title last rested on, unless the place left
        is that title or a node over it. A jump to where the tree already is remembers
        nothing, and no place is remembered twice running.

        Args:
            location: The node arrived at, or None for the collapsed tree.
            kind: Whether this is a step or a jump.
            is_title: Whether `location` is a story's row.

        """
        left = self._current
        self._current = location
        if kind is VisitKind.JUMP and left is not None and left != location:
            rested = self._rested_title
            if rested is not None and rested != location and not _is_at_or_under(rested, left):
                self._remember(rested)
            self._remember(left)
            self._rested_title = None
        if is_title:
            self._rested_title = location

    def opened(self, location: TreeLocation) -> None:
        """Remember the title last rested on, as Enter opens the node at `location`.

        Nothing is remembered when that title is `location` or sits under it: the
        arrows are still within reach of it.

        Args:
            location: The node Enter was pressed on.

        """
        rested = self._rested_title
        if rested is None or _is_at_or_under(rested, location):
            return
        self._remember(rested)
        self._rested_title = None

    def back(self) -> TreeLocation | None:
        """Go back one place: it becomes the current location, and nothing is remembered.

        A place that is where the tree already is gets passed over: Go Back always
        moves.

        Returns:
            The place gone back to, or None when there is none. The tree is then
            nowhere: the caller collapses it.

        """
        here = self._current
        self._rested_title = None
        self._current = None
        while self._entries:
            place = self._entries.pop()
            if place != here:
                self._current = place
                break
        return self._current

    def _remember(self, place: TreeLocation) -> None:
        if self._entries and self._entries[-1] == place:
            return
        self._entries.append(place)
        if len(self._entries) > self._max_entries:
            del self._entries[0]


def _is_at_or_under(location: TreeLocation, node: TreeLocation) -> bool:
    """Whether `location` is `node` or a row beneath it (paths run leaf to root)."""
    return len(location) >= len(node) and location[len(location) - len(node) :] == node
