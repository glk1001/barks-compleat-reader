"""Main-screen tree moves shared by the GUI tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gui_driver import Driver


def collapse_all(d: Driver) -> None:
    """Shut the tree back to its top level after a boot expanded a chain into it.

    Booting expands the whole chain down to the node, including the node itself,
    so one Left on the top-level node collapses it again and leaves the
    selection there.
    """
    d.key("Left")
    d.settle()


def open_path(d: Driver, *names: str) -> None:
    """Walk down and expand each named node in turn, ending inside the last one."""
    for name in names:
        d.open_branch(name)
