"""The bottom title view: its keyboard ring, the overrides row and the goto-page row.

The ring runs eye, wiki chip, overrides row, goto-page row, read portal, top to
bottom, and the middle three appear only when they have something to show.
Return from the tree enters at the portal; Up climbs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_gui import nodes

if TYPE_CHECKING:
    from barks_gui.harness import AppBoot

ROW_PAUSE = 0.3  # between an Up/Down along the ring and the next key
ANDES_WITH_CUE = {nodes.LOST_IN_THE_ANDES_TITLE: nodes.LOST_IN_THE_ANDES_CUE}


def test_return_enters_at_the_portal_and_escape_leaves(boot: AppBoot) -> None:
    d = boot(nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES)
    d.focus_portal()
    d.key_then_wait("Exited bottom focus region.", 15, "Escape")


def test_overrides_row_toggles(boot: AppBoot) -> None:
    """On a story with an override, Up from the portal is the overrides checkbox.

    The row exists only when the comics come from the Fantagraphics volumes: a
    prebuilt comic has its override baked in, and the coordinator hides the row
    (navigation_coordinator._set_use_overrides_checkbox). No cue, so no goto-page
    row sits between the portal and it.
    """
    d = boot(nodes.THE_FIREBUG, cues=nodes.NO_CUES, ini={"use_prebuilt_comics": "0"})
    d.focus_portal()
    d.key("Up")
    d.hold(ROW_PAUSE)
    d.key_then_wait("Use overrides checkbox changed: use_overrides = False", 15, "Return")
    d.key_then_wait("Use overrides checkbox changed: use_overrides = True", 15, "Return")


def test_a_cued_story_opens_at_its_cued_page(boot: AppBoot) -> None:
    """With the goto-page row ticked, the reader opens on the cue, not the front."""
    d = boot(nodes.LOST_IN_THE_ANDES, cues=ANDES_WITH_CUE)
    d.open_selected_story()
    d.wait_for(f"Showed page {nodes.LOST_IN_THE_ANDES_PAGE} in ")
    d.close_reader()


def test_unchecking_the_goto_page_row_opens_at_the_front(boot: AppBoot) -> None:
    """Up from the portal is the goto-page row; unchecked, the story opens at the front."""
    d = boot(nodes.LOST_IN_THE_ANDES, cues=ANDES_WITH_CUE)
    d.focus_portal()
    d.key("Up")  # the goto-page row sits right above the portal
    d.hold(ROW_PAUSE)
    d.key("Return")  # uncheck it
    d.hold(ROW_PAUSE)
    d.key("Down")  # back to the portal
    d.hold(ROW_PAUSE)
    d.key_then_wait("All images loaded", 30, "Return")
    d.wait_for("Showed page")
    assert d.current_page() < nodes.LOST_IN_THE_ANDES_PAGE
    d.close_reader()


def test_the_fade_is_logged_from_start_to_finish(boot: AppBoot) -> None:
    """Both ends of the random-length fade are logged, so nothing waits on the clock."""
    d = boot(nodes.GHOST_OF_THE_GROTTO, cues=nodes.NO_CUES)
    d.wait_title_fade()
    assert d.match_count(r"Title view fade started: \d+s\.") >= 1
    assert d.match_count("Title view fade finished.") >= 1
