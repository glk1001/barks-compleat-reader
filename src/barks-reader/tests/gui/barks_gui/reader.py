"""Comic-reader moves shared by the GUI tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gui_driver import Driver

# Once a title is selected in the tree, Return enters its title view at the read
# portal; a second Return opens the comic. The pause between them is functional:
# the portal has to take focus before it can be pressed.
PORTAL_FOCUS_PAUSE = 0.6
IMAGES_TIMEOUT = 30


def open_selected_story(d: Driver) -> None:
    """Open the story selected in the tree and wait for its images to load."""
    d.settle()
    d.key("Return")
    d.hold(PORTAL_FOCUS_PAUSE)
    d.key_then_wait("All images loaded", IMAGES_TIMEOUT, "Return")
