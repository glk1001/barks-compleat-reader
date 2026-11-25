"""The places Go Back returns to: a capped stack of tree locations.

The history records jumps and not steps. A step (an arrow key moving along the tree,
or a selection the app makes inside one gesture) only moves where you are; a jump (a
press on a node, a go-to-title, the bar's Search, a Collapse) first remembers the
place it leaves. Go Back pops the last place remembered and remembers nothing itself.
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

    @property
    def current(self) -> TreeLocation | None:
        """Where the tree is now, or None when nothing is selected."""
        return self._current

    @property
    def depth(self) -> int:
        """How many places there are to go back to."""
        return len(self._entries)

    def visit(self, location: TreeLocation | None, kind: VisitKind) -> None:
        """Arrive at `location`, remembering the place left if this is a jump.

        A jump to where the tree already is remembers nothing, and neither does one
        that leaves the place already on top of the stack.

        Args:
            location: The node arrived at, or None for the collapsed tree.
            kind: Whether this is a step or a jump.

        """
        left = self._current
        self._current = location
        if kind is VisitKind.STEP or left is None or left == location:
            return
        if self._entries and self._entries[-1] == left:
            return
        self._entries.append(left)
        if len(self._entries) > self._max_entries:
            del self._entries[0]

    def back(self) -> TreeLocation | None:
        """Go back one place: it becomes the current location, and nothing is remembered.

        Returns:
            The place gone back to, or None when there is none. The tree is then
            nowhere: the caller collapses it.

        """
        self._current = self._entries.pop() if self._entries else None
        return self._current
