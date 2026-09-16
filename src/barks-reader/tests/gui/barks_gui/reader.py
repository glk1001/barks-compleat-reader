"""Comic-reader moves shared by the GUI tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gui_driver import Driver

# Once a title is selected in the tree, Return enters its title view at the read
# portal; a second Return opens the comic. Neither may be sent early: while the
# panel is still fading in a Return re-enters the view instead of pressing the
# portal, so the first waits for the fade and the second for the first's log line.
ENTERED_AT_PORTAL = "BottomTitleViewScreen: entered nav focus at portal."
IMAGES_TIMEOUT = 30


def open_selected_story(d: Driver) -> None:
    """Open the story selected in the tree and wait for its images to load."""
    d.wait_title_fade()
    d.key_then_wait(ENTERED_AT_PORTAL, 15, "Return")
    d.key_then_wait("All images loaded", IMAGES_TIMEOUT, "Return")
