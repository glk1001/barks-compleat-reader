#!/usr/bin/env python3
"""Record the website demo clips by driving the app on the nested Xephyr display.

For each beat: boot the app onto that beat's start node via ``gui-probe.sh``,
record the app window with ffmpeg x11grab while the beat injects keystrokes, then
concatenate the beat clips into the videos named in ``OUTPUTS``.

Why beats rather than one long take
    Every beat is an independent clip encoded with identical parameters, so the
    concatenation is a stream copy (lossless, instant) and re-shooting or adding
    one beat costs only that beat's runtime instead of a whole re-record. Beat
    clips persist in ``build/demo-beats/``, so ``--only <beat>`` re-shoots one and
    still rebuilds the complete video.

To add a beat
    Write a function, decorate it with ``@beat(...)``, and add its name to an
    entry in ``OUTPUTS``. Order of definition in this file is the order on
    screen. Everything a beat needs - its start node, its caption, its optional
    off-camera setup and its keystrokes - sits in that one place.

    ``node`` is the tree node to boot onto, leaf-to-root, as the app stores it in
    ``AAA_Settings.last_selected_node``. Leaf stories go in by enum name
    (``LOST_IN_THE_ANDES``), not display title, and the chain has to be exact -
    the app selects nothing if it is not. The surest way to get one is to
    navigate there by hand once and read back what the app saved. Booting expands
    the path, so the node's children are already on screen and a beat can walk
    straight into them.

    ``setup`` runs once the app is up but BEFORE the recorder starts, for
    navigation that should not appear on screen. Keep anything that must play
    without a cut inside a single beat.

Assumes
    - ``scripts/gui-probe.sh doctor`` passes (Xephyr, xte, the app's data dirs).
    - A graphical session for the nested display to open in, and nothing else
      already on ``BARKS_PROBE_DISPLAY``.
    - ffmpeg built with libx264 and libfreetype, and xdotool (the fullscreen beat
      resizes the app's X window by hand: see ``fit_app_window_to_screen``).

The keystroke driver and the app boot live in ``gui_driver.py``, shared with the
GUI test suite; this file is the beats, the camera, and the stitch. It reads the
series names from ``barks_fantagraphics``, so it runs from the workspace venv
(``uv run scripts/record_demo.py``).

The app rewrites its config on exit and appends to the reading history on every
read, so this backs up ``barks-reader.json`` and ``barks-reader-history.json``
before touching either and restores both on any exit, including a failure, a
Ctrl-C, and a SIGTERM/SIGHUP (the terminal closing). The backups' paths are
printed at the start of a run in case even that fails. It never writes to
``barks-reader.ini``.

Each boot also pins the last-read-page cues the beats depend on (``PINNED_CUES``)
and writes the reading history the Reading beat films (``CANNED_HISTORY``), so a
re-record opens every story on the same page as the clips it replaces and shows
the same journal, on any machine - and never the user's own reads.

Usage:
    uv run scripts/record_demo.py                       # every beat, every output
    uv run scripts/record_demo.py --list
    uv run scripts/record_demo.py --only browse_tree
    uv run scripts/record_demo.py --from read_story
    uv run scripts/record_demo.py --stitch              # rebuild from cached beats
    uv run scripts/record_demo.py --output demo.mp4     # build just this one
    uv run scripts/record_demo.py --out /tmp/preview
    uv run scripts/record_demo.py --clean               # drop cached clips, record everything

Env overrides: BARKS_PROBE_DISPLAY (:2), BARKS_PROBE_SCREEN (900x1300) - both are
passed straight through to gui-probe.sh.
"""

# cspell:ignore windowmove windowsize
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from barks_fantagraphics.fanta_series_info import SERIES_CS, SERIES_DDA
from gui_driver import DISPLAY, PROBE, Driver, DriverError, Pick, boot_app_at, probe

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_OUT_DIR = REPO_ROOT / "website"
WORK_DIR = REPO_ROOT / "build" / "demo-beats"

# ------------------------------------------------------------------ tuning --

# Encode settings, shared by every beat so the concat can be a stream copy.
# CRF 30 holds up on flat comic art; the 2-second keyframe interval gives the
# browser somewhere to seek to.
FPS = 30
CRF = 30
GOP = 60
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
CAPTION_SIZE = 30
# The app's own text_display colour - the "brighter cover-yellow" it uses for
# hero titles - so the caption reads as part of the product rather than an
# overlay on it. See reader_palette.py.
CAPTION_COLOR = "0xFFDB52"
CAPTION_BOX_ALPHA = 0.85
CAPTION_BOX_PAD = 18
CAPTION_SHADOW = 2
# How far the caption sits above the bottom of the frame. It has to clear the
# browser's own control bar, which the player draws across the bottom of the
# video once something is playing - at 36 the bar sat right on top of the one
# piece of text explaining what is on screen. 96 cleared it with room to spare,
# so this sits lower again while keeping a 36px margin over the value that failed.
CAPTION_BOTTOM = 72


# Where each output's poster frame comes from. A beat name takes that beat's
# resting frame; "first" takes the video's own opening frame.
#
# The hero plays by itself, so its still barely shows and wants to be composed -
# browse_tree's resting frame has the tree, a title card and the app's chrome.
# The tour is click-to-play, so its poster is the frame it will start from:
# anything else makes the player look like it jumped when play is pressed.
POSTER_BEAT = "browse_tree"
POSTERS = {"demo.mp4": POSTER_BEAT, "walkthrough.mp4": "first"}

# ffmpeg's JPEG quality for the posters, where lower is better. These are the only
# part of the recording that stays in git - the videos go to a release - so they are
# worth keeping small, and they are what the page paints before either video has
# arrived. 8 rather than 4 takes the pair from 324K to 200K with nothing visible in
# it: compared at 1:1 on the tree's small italic text, the hardest thing either
# poster contains, the two are indistinguishable.
POSTER_QUALITY = 8

# Where browse_tree goes once it has opened the tree, and how far down into that
# range's title list it walks. open_comic's setup repeats the same number of
# steps so the cut between the two beats lands on the same story - they share
# this constant rather than each carrying their own count.
BROWSE_RANGE = "1947-1950"
BROWSE_TITLE_STEPS = 7
# How much of browse_tree's on-camera pacing the off-camera replay keeps. The
# dwells are pacing only, so shortening them cannot change where the tree ends
# up - but they are not zero, because the app drops keys pressed at full speed.
SETUP_PACE = 0.25

# Pins the app's random image choices, so a re-recorded beat comes back with the
# same backgrounds and insets as the one it replaces and two runs can be compared
# frame for frame. Any fixed number does; it only has to be the same every time.
# Set to None to let the app pick freshly, as it does for a normal user.
RANDOM_SEED: int | None = 20260915

# What the two search beats type. Keep them short - every character is typed with
# a visible pause, so a long query makes for a slow beat.
SEARCH_TITLE_QUERY = "vacation"
# Which result row to take, counting from 1. Return in the search box hands the
# keyboard to the first row and Down walks them, each move waited on through the
# log; the beat still checks by name which story it landed on, so a reordered
# list fails the run instead of quietly demonstrating a different comic. (The
# rows were once clicked by pixel; scripts/repro_search_enter.py still does, as
# the bug it reproduces is in the mouse path.)
SEARCH_TITLE_RESULT = 2
SEARCH_WORD_QUERY = "airline"
# The story the word beat opens the speech bubbles for, spelled as the app logs it.
# Word results are sorted by title, so the pick is a row index into that list.
# Right on the row is its speech balloon, and the popup opens with its first bubble
# focused - page 1's "WE'LL FLY! THE AIRLINE TICKET OFFICE IS ON THE NEXT STREET!".
# Pressing it goes to that page of the story.
SEARCH_WORD_PICK = "Adventure Down Under"
SEARCH_WORD_RESULT = 1
# How long each step down the result rows rests, for the camera.
RESULT_STEP_PAUSE = 0.5

# Log lines the beats wait on. The recorder is stdlib-only, so these are copies
# of the app's markers (barks_reader.core.log_markers), with re.escape'd fields;
# scripts/tests/test_record_demo.py checks each against the line the app writes.
ALL_IMAGES_LOADED = "All images loaded"
# barks_reader.core.log_markers.HISTORY_SELECTED_VIEW, with its view pinned.
HISTORY_VIEW_SELECTED = "History: selected '{view}' view."
GOTO_TITLE = 'Goto title: "{name}"'
WORD_CHIP_SELECTED = "Word search: selected chip"
SHOW_BUBBLES_FOR = 'Show speech bubbles for: "{title}"'
BUBBLE_PRESS = 'Word search bubble press: "{title}"'
BUBBLES_POPUP_OPENED = "Speech bubbles popup opened."
BUBBLES_POPUP_DISMISSED = "Speech bubbles popup dismissed."
SEARCH_MODE_SET = "SearchScreen mode set to '{mode}'"
WIKI_ACTIVE = "Wiki reader screen is active"
NODE_SELECTED = 'New selected node: "{name}"'
LETTER_POPULATED = "Populated index page for letter"
ENTERED_FULLSCREEN = "Entered fullscreen mode on ComicBookReaderScreen"


# Stories the censored_stories beat opens. They must be in TREE order, which is
# chronological, because the beat only ever walks downward. The node holds these
# seventeen, in this order:
#
#   GOOD_DEEDS FROZEN_GOLD ICEBOX_ROBBER_THE FIREBUG_THE SILENT_NIGHT
#   TERROR_OF_THE_RIVER_THE SWIMMING_SWINDLERS BILL_COLLECTORS_THE
#   GOLDEN_CHRISTMAS_TREE_THE LOST_IN_THE_ANDES VOODOO_HOODOO TRICK_OR_TREAT
#   BACK_TO_THE_KLONDIKE GOLDEN_FLEECING_THE LAND_BENEATH_THE_GROUND
#   LOVELORN_FIREMAN_THE BONGO_ON_THE_CONGO
#
# To regenerate that list after a tag change:
#   uv run python -c "
#   from barks_fantagraphics.barks_tags import BARKS_TAGGED_TITLES  # noqa: ERA001
#   from barks_fantagraphics.barks_tags_enums import Tags  # noqa: ERA001
#   from barks_fantagraphics.barks_titles import Titles  # noqa: ERA001
#   order = {t: i for i, t in enumerate(Titles)}  # noqa: ERA001
#   print([t.name for t in sorted(
#       BARKS_TAGGED_TITLES[Tags.CENSORED_STORIES_BUT_FIXED], key=lambda t: order[t])])"
CENSORED_PICKS = (
    Pick("GOOD_DEEDS"),
    Pick("SILENT_NIGHT"),
    Pick("BILL_COLLECTORS_THE", pages=1),
    Pick("GOLDEN_FLEECING_THE", pages=1),
)

# The story read_story opens. Must be in the censored-but-fixed node, because
# that is the branch its setup walks.
READ_STORY_PICK = Pick("LOST_IN_THE_ANDES", pages=2, dwell=2.5)

# The story series_view walks the series list down to, and how much of it to read
# once it is open. It opens on whatever page the config has cued for it, the same
# as every other beat that opens a story.
SERIES_PICK = Pick("LOST_IN_THE_ANDES", pages=2, dwell=1.5)

# The story search_story finds, and how much of it to read. Its title must be
# what SEARCH_TITLE_RESULT actually lands on.
SEARCH_TITLE_PICK = Pick("VACATION_TIME", pages=3, dwell=1.0)


# How much of the story to read once the bubble has landed on it. Only `pages` and
# `dwell` are used here - the beat reaches the comic through the bubble, not by name.
SEARCH_WORD_READ = Pick(pages=4, dwell=1.0)

# open_comic reaches its story by walking, not by name, so this sets only its
# pacing: four pages means the one it opens on plus three turns.
OPEN_COMIC_PICK = Pick(pages=4, dwell=1.5)

# The story fullscreen opens, and how much of it to read before and after the
# switch. It reads the same story as read_story, from the same cued page.
FULLSCREEN_PICK = Pick("LOST_IN_THE_ANDES", pages=1, dwell=2.0)
FULLSCREEN_READ = Pick(pages=3, dwell=2.0)

# The page read_story jumps to through the goto-page dropdown, to show that the
# reader skips about rather than only turning forward.
#
# This is the reader's page *index* - what the app logs as "Showed page N" - and
# not the printed page number: the index counts the cover and the front matter,
# so it runs ahead of what is printed on the page. The dropdown lists pages in
# that same index order, which is why stepping by the difference between two of
# them lands exactly. Must exist in READ_STORY_PICK's story, or the jump ends up
# somewhere else - loudly, since the landing is checked against the log.
READ_STORY_GOTO_PAGE = 25

# How many Ups wiki_jump takes from the read portal to reach the wiki button.
#
# The title view's nav widgets run title-show, wiki, overrides, goto-page,
# portal, and the middle three only appear when they have something to show
# (bottom_title_view_screen._focusable_widgets). Entering at the portal and
# walking up therefore depends on what is between: three Ups is right when both
# the overrides row and the goto-page row are there, as they are for Lost in the
# Andes under the censored node - it has an edited inset to offer, and the tag's
# pages (with the pinned cue a step away) fill the goto row.
#
# That makes this beat depend on the data as much as the config - take away the
# edited inset, or the cue and the tag's pages, and the walk lands on the wrong
# widget. It fails loudly rather than filming the wrong thing, because the Enter
# that follows is checked against the log; the log's "Use overrides checkbox
# changed" after that Enter is the sign of one Up too few.
WIKI_UPS_FROM_PORTAL = 3
# Once in the wiki, how far down its sidebar to move from the story it opened on,
# and the enum name of the title that lands on. The beat waits on that name, so if
# the wiki's own ordering shifts underneath it the beat fails rather than quietly
# filming a different story.
WIKI_SIDEBAR_STEPS = 2
WIKI_SIDEBAR_PICK = "VOODOO_HOODOO"
# Escape lifts the wiki's keyboard focus to its top bar, landing on Back. The button
# that hands the story back to the reader is this far to its right; the bar runs
# Back, contrast, goto-title, quit.
WIKI_BAR_RIGHTS_TO_GOTO = 2

# The playlist the Reading beat opens. Playlists are themed runs of stories, each
# with its own blurb; this is the first of them.
READING_PLAYLIST = "The Bravery Stories"

# The last-read page the config cues for each story a beat opens, in the form the
# app writes it (json_settings_manager.save_last_read_page). Keyed by the DISPLAY
# title, which is the config's key - not the enum name the tree node uses.
#
# Where a story opens, and whether its title view shows the goto-page row at all,
# comes from this cue: the row is hidden when there is no cue or the cued page is
# "0" (navigation_coordinator._set_goto_page_checkbox). WIKI_UPS_FROM_PORTAL counts
# on that row being there, goto_page() steps from the cued page, and every
# read_pages() rests on it first. Left to the live config, a re-record differed
# from machine to machine and from one reading session to the next, so boot_at
# merges these over the config before every boot. None pins "no cue", which is
# what the sidebar story wiki_jump lands on had when the clips were shot.
#
# Under a tag node the tag's first page is offered instead, and the cued page is
# kept one step away on the row (navigation_coordinator._set_tag_goto_page_checkbox):
# censored_stories opens The Golden Fleecing on the tag's page 6, not the cued 24,
# and wiki_jump's row is there for the tag's pages as much as for the cue.
#
# To re-pin after deliberately reading a story to a new page, copy its entry out
# of barks-reader.json (`scripts/gui-probe.sh config` prints the path).
PINNED_CUES: dict[str, dict[str, int | str] | None] = {
    # read_story, series_view, wiki_jump: body page 29, so the goto-page row shows.
    "Lost in the Andes!": {
        "page_index": 34,
        "display_page_num": "29",
        "page_type": "BODY",
        "last_body_page": "32",
    },
    # search_story (SEARCH_TITLE_PICK).
    "Vacation Time": {
        "page_index": 35,
        "display_page_num": "34",
        "page_type": "BLANK_PAGE",
        "last_body_page": "33",
    },
    # search_words (SEARCH_WORD_PICK): the bubble picks the page, but the title
    # view it passes through is drawn from this.
    "Adventure Down Under": {
        "page_index": 0,
        "display_page_num": "0",
        "page_type": "FRONT",
        "last_body_page": "25",
    },
    # browse_tree / open_comic: the story BROWSE_TITLE_STEPS lands on. No goto row.
    "The Ghost of the Grotto": {
        "page_index": 0,
        "display_page_num": "0",
        "page_type": "FRONT",
        "last_body_page": "26",
    },
    # censored_stories (CENSORED_PICKS), in tree order.
    "Good Deeds": {
        "page_index": 7,
        "display_page_num": "7",
        "page_type": "BODY",
        "last_body_page": "10",
    },
    "Silent Night": {
        "page_index": 0,
        "display_page_num": "i",
        "page_type": "TITLE",
        "last_body_page": "10",
    },
    "The Bill Collectors": {
        "page_index": 3,
        "display_page_num": "3",
        "page_type": "BODY",
        "last_body_page": "10",
    },
    "The Golden Fleecing": {
        "page_index": 28,
        "display_page_num": "24",
        "page_type": "BODY",
        "last_body_page": "32",
    },
    # wiki_jump (WIKI_SIDEBAR_PICK): never read, so no cue.
    "Voodoo Hoodoo": None,
}


@dataclass(frozen=True)
class CannedRead:
    """One read in the canned history: a story opened on a day, and where it was left."""

    title: str  # the display title, which is the history's key
    opened_at: str  # ISO date and time to the second, no zone, as the app stamps it
    minutes: int  # how long it stayed open
    last_display_page: str  # "0" once finished; the body page it was left on otherwise
    last_body_page: str


# The reading history the Reading beat films, written in place of whatever the
# machine's own profile holds. The History views show every read, so the user's own
# journal - or the hundreds of entries a test run leaves - would be on camera.
# boot_at writes it whole before every boot, in the app's own file format
# (reading_history.ReadEvent.to_json), and the user's file goes back at the end of
# the run. Oldest first, as the app keeps the file; the journal shows it newest first.
# Fixed dates rather than days-before-today, so two recordings show the same journal;
# the page numbers are the stories' own.
HISTORY_FILE_NAME = "barks-reader-history.json"
HISTORY_STORE_VERSION = 1
CANNED_HISTORY: tuple[CannedRead, ...] = (
    CannedRead("The Ghost of the Grotto", "2026-09-27T20:05:12", 24, "0", "26"),
    CannedRead("Wintertime Wager", "2026-09-27T20:31:40", 9, "0", "10"),
    CannedRead("Lost in the Andes!", "2026-09-28T21:12:03", 19, "18", "32"),
    CannedRead("Lost in the Andes!", "2026-09-29T19:47:55", 15, "0", "32"),
    CannedRead("The Mighty Trapper", "2026-09-29T20:04:21", 8, "0", "10"),
    CannedRead("Vacation Time", "2026-10-01T21:30:08", 31, "0", "33"),
    CannedRead("Good Deeds", "2026-10-03T10:15:47", 9, "0", "10"),
    CannedRead("Silent Night", "2026-10-03T10:26:02", 10, "0", "10"),
    CannedRead("Adventure Down Under", "2026-10-04T16:40:19", 22, "0", "25"),
    CannedRead("The Golden Fleecing", "2026-10-06T21:02:33", 17, "14", "32"),
    CannedRead("Chugwagon Derby", "2026-10-08T19:55:10", 8, "0", "10"),
    CannedRead("The Golden Fleecing", "2026-10-09T20:18:44", 20, "0", "32"),
    CannedRead("Donald Duck's Atom Bomb", "2026-10-10T11:08:27", 9, "0", "10"),
    CannedRead("The Bill Collectors", "2026-10-11T15:22:51", 9, "0", "10"),
    CannedRead("Mastering the Matterhorn", "2026-10-11T15:33:06", 7, "0", "8"),
    CannedRead("The Librarian", "2026-10-12T21:41:15", 6, "0", "6"),
)


def canned_history_events() -> list[dict[str, str | None]]:
    """Return the canned reads as the app's history file holds each event.

    Event ids are derived from each read's position, so the file is the same on
    every run.
    """
    events: list[dict[str, str | None]] = []
    for i, read in enumerate(CANNED_HISTORY):
        opened = datetime.fromisoformat(read.opened_at)
        closed = opened + timedelta(minutes=read.minutes)
        events.append(
            {
                "id": uuid.uuid5(uuid.NAMESPACE_URL, f"barks-demo-history/{i}").hex,
                "title": read.title,
                "opened_at": opened.isoformat(timespec="seconds"),
                "closed_at": closed.isoformat(timespec="seconds"),
                "last_display_page": read.last_display_page,
                "last_body_page": read.last_body_page,
            }
        )
    return events


def canned_history_json() -> dict[str, object]:
    """Return the whole canned history file, as the app's store writes it."""
    return {"version": HISTORY_STORE_VERSION, "events": canned_history_events()}


# What gets stitched, and from which beats. A beat can appear in more than one
# output; it is only ever recorded once. The short hero loop is the one that plays
# by itself at the top of the intro tab; the walkthrough is the linked tour.
OUTPUTS: dict[str, tuple[str, ...]] = {
    "demo.mp4": ("browse_tree", "open_comic"),
    "walkthrough.mp4": (
        "browse_tree",
        "series_view",
        "read_story",
        "fullscreen",
        "search_story",
        "search_words",
        "censored_stories",
        "wiki_jump",
        "speech_index",
        "reading",
    ),
}

# The outputs that get a chapter manifest (``<video>-chapters.json``) beside them.
# The page's chapter buttons read the tour's; the hero autoplays with no buttons,
# so a manifest for it would be a file nothing reads.
CHAPTERED_OUTPUTS: frozenset[str] = frozenset({"walkthrough.mp4"})


def say(message: str = "") -> None:
    """Write a progress line to stdout."""
    print(message)  # noqa: T201


# The recorder's name for the driver's error: a beat could not reach a state it
# needed, so the run must not continue.
BeatError = DriverError


# ------------------------------------------------------------ beat registry --


@dataclass(frozen=True)
class Beat:
    """One recorded clip: where it starts, what it says, and what it does."""

    name: str
    node: list[str]
    label: str = ""
    body: Callable[[Driver], None] = field(default=lambda _d: None)
    setup: Callable[[Driver], None] | None = None
    # Film the whole nested screen, cropped and scaled to the other clips' size,
    # instead of the app window's own region: for a beat that goes fullscreen.
    whole_screen: bool = False


BEATS: list[Beat] = []


def beat(
    name: str,
    node: Sequence[str],
    label: str = "",
    setup: Callable[[Driver], None] | None = None,
    *,
    whole_screen: bool = False,
) -> Callable[[Callable[[Driver], None]], Callable[[Driver], None]]:
    """Register the decorated function as a beat.

    Args:
        name: Beat name, as used by --only/--from and in OUTPUTS.
        node: The tree node to boot onto, leaf-to-root.
        label: Caption burned along the bottom of the clip. May contain any
            characters; it is passed to ffmpeg through a file, not the filter
            string.
        setup: Optional off-camera navigation, run before recording starts.
        whole_screen: Film the whole nested screen rather than the app window,
            for a beat that goes fullscreen (`Beat.whole_screen`).

    Returns:
        The decorator, which returns the function unchanged.

    """

    def register(fn: Callable[[Driver], None]) -> Callable[[Driver], None]:
        BEATS.append(
            Beat(
                name=name,
                node=list(node),
                label=label,
                body=fn,
                setup=setup,
                whole_screen=whole_screen,
            )
        )
        return fn

    return register


def beat_names() -> list[str]:
    """Return every registered beat name, in definition order."""
    return [b.name for b in BEATS]


def find_beat(name: str) -> Beat:
    """Return the beat with this name, or raise if there is none."""
    for b in BEATS:
        if b.name == name:
            return b
    msg = f"no such beat: {name}"
    raise BeatError(msg)


# ---------------------------------------------------------------- the beats --


def _collapse_tree(d: Driver) -> None:
    """Shut the tree back to its top level.

    Booting expands the whole chain down to the node, including the node itself,
    so there is no start node that gives a closed tree. One Left collapses The
    Stories again, leaving every top-level node shut and the selection still on
    it.
    """
    d.key("Left")
    d.settle()


def _open_tree_to_title(d: Driver, pace: float = 1.0) -> None:
    """Open the tree from closed down to the story the demo reads.

    browse_tree plays this on camera and open_comic's setup replays it off
    camera, and they must run the same keys in the same order: where the tree
    is scrolled comes from how it was opened, not just from which node ends up
    selected. Reaching the same story a different way - by booting with the path
    already expanded, say - leaves the list sitting at a different offset, and
    the cut between the two beats jumps even though both are on the right story.

    Args:
        d: The driver.
        pace: Scales the dwells, so the replay can get through this quickly.

    """
    d.key("Return")  # open The Stories
    d.settle()
    d.hold(0.6 * pace)
    d.select_node("Chronological")
    d.hold(0.5 * pace)
    d.key("Return")  # open it, showing the year ranges
    d.settle()
    d.hold(0.7 * pace)
    d.select_node(BROWSE_RANGE)
    d.hold(0.5 * pace)
    d.key("Return")  # open the range, showing its stories
    d.settle()
    d.hold(1.0 * pace)
    # Each Down waits for the selection it makes: at the replay's pace the app
    # drops keys, and one lost Down would put open_comic on the story above.
    for _ in range(BROWSE_TITLE_STEPS):
        d.key_then_wait(d.NODE_SELECTED, "Down")
        d.hold(0.7 * pace)
    d.settle()


def _collapse_back(d: Driver) -> None:
    """Shut the open node and step back out to its parent.

    Left on an expanded node collapses it; Left again leaves it for the parent,
    collapsed. Two presses is the whole "back" gesture on this tree.
    """
    for _ in range(2):
        d.key("Left")
        d.settle()
    d.hold(0.8)


def _setup_browse_tree(d: Driver) -> None:
    _collapse_tree(d)


@beat(
    "browse_tree",
    node=["The Stories", "root"],
    label="Every Barks Disney story, in order",
    setup=_setup_browse_tree,
)
def browse_tree(d: Driver) -> None:
    """Open the tree a level at a time and walk down to a story.

    Arrows down the chronological list and settles on a title, letting the bottom
    panel render its title view. Keyboard only: this doubles as the 10-foot/remote
    story, and it keeps the pointer out of the frame.
    """
    d.hold(1.2)
    _open_tree_to_title(d)
    d.hold(1.0)


def _setup_open_comic(d: Driver) -> None:
    # Replay browse_tree exactly, off camera, so this beat opens on the tree the
    # previous one left behind - same story selected AND same scroll offset, so
    # the cut between them does not jump. Booting straight onto the range would
    # reach the same story with the list sitting somewhere else.
    _collapse_tree(d)
    _open_tree_to_title(d, pace=SETUP_PACE)
    # Let the title view finish fading in, so this beat opens on the same fully
    # drawn panel browse_tree ended on rather than mid-fade. The fade runs a random
    # 0-4s; the app logs both its ends, so this waits on the log, not the clock.
    d.wait_title_fade()


@beat(
    "open_comic",
    node=["The Stories", "root"],
    label="Open any story and read it",
    setup=_setup_open_comic,
)
def open_comic(d: Driver) -> None:
    """Open the story browse_tree stopped on and turn a few of its pages."""
    d.key("Return")  # focus the title view's read portal
    d.key("Return")  # open the comic
    d.wait_for(ALL_IMAGES_LOADED, 30)
    # Right is next-page in the reader (reader_keyboard_nav._handle_reading_key).
    d.read_pages(OPEN_COMIC_PICK)
    d.hold(2.5)


@beat(
    "series_view",
    node=["Series", "The Stories", "root"],
    label="Or by the series they ran in",
)
def series_view(d: Driver) -> None:
    """Walk into a series, down its story list, and read a page or two.

    Booting here has already expanded Series, so the three series are on screen and
    this only has to walk into them.
    """
    d.hold(1.0)
    d.select_node(SERIES_CS)
    d.hold(1.0)
    d.select_node(SERIES_DDA)
    d.hold(1.0)
    d.key("Return")  # expand it: a series lists its stories directly, no volumes
    d.settle()
    d.hold(1.0)

    # Walking the list down to one story is the point of the beat - it is what shows
    # the series in order. Name-driven rather than a counted run of Downs, so a title
    # added upstream shifts the walk instead of landing this on the wrong story.
    d.select_node(SERIES_PICK.title)
    d.hold(1.0)
    d.open_story(SERIES_PICK)


@beat(
    "search_story",
    node=["Titles", "Search", "root"],
    label="Find a story by name",
)
def search_story(d: Driver) -> None:
    """Search titles, pick a result, read a page of it, and come back.

    A whole round trip, ending on the search still holding the query.
    """
    d.hold(1.0)
    d.key("Return")  # open the title search and focus its box
    d.settle()
    d.hold(0.6)
    d.type_slowly(SEARCH_TITLE_QUERY)
    d.settle()
    d.hold(1.2)

    # Return leaves the box for the first result row; Down walks the rows.
    d.key_then_wait(d.FOCUS_MOVED, "Return")
    for _ in range(SEARCH_TITLE_RESULT - 1):
        d.move_focus("Down")
        d.hold(RESULT_STEP_PAUSE)
    d.hold(0.6)
    # A result picked from the keyboard hands focus to the title view's read portal,
    # so one Enter there opens the comic - but not while the panel is still fading
    # in, when the Enter is lost. The app logs the fade's end, so wait on that.
    with (
        d.expect(GOTO_TITLE.format(name=re.escape(SEARCH_TITLE_PICK.title))),
        d.expect(d.ENTERED_AT_PORTAL),
    ):
        d.key("Return")
    d.wait_title_fade()
    d.key_then_wait(ALL_IMAGES_LOADED, "Return", timeout=30)
    d.read_pages(SEARCH_TITLE_PICK)
    d.close_reader()
    d.hold(1.0)
    d.key("Escape")  # leave the bottom focus region for the tree
    d.settle()
    # The counting form: the search logged this same mode line when the beat booted
    # onto it, so a plain wait_for would return before the Go Back had landed.
    d.go_back_then_wait(SEARCH_MODE_SET.format(mode="Title"))
    d.settle()
    d.hold(2.5)


@beat(
    "search_words",
    node=["Words", "Search", "root"],
    label="Search every word the characters speak",
)
def search_words(d: Driver) -> None:
    """Find a spoken word, open one story's bubbles, jump in from one, and come back.

    A whole round trip, like search_story.
    """
    d.hold(1.0)
    d.key("Return")
    d.settle()
    d.hold(0.5)
    d.type_slowly(SEARCH_WORD_QUERY)
    d.settle()
    d.hold(0.3)
    # Return in the box picks the first matching word chip and lands focus on it
    # (the box keeps every other key, so there is no Down to it).
    d.key_then_wait(WORD_CHIP_SELECTED, "Return")
    d.hold(2.0)  # the list of every story the word is spoken in

    # Return on the chip enters the result rows; Right on a row is its speech
    # balloon, which opens just that story's matching bubbles.
    d.key_then_wait(d.FOCUS_MOVED, "Return")
    for _ in range(SEARCH_WORD_RESULT - 1):
        d.move_focus("Down")
        d.hold(RESULT_STEP_PAUSE)
    d.move_focus("Right")
    d.hold(0.6)
    with (
        d.expect(SHOW_BUBBLES_FOR.format(title=re.escape(SEARCH_WORD_PICK))),
        d.expect(BUBBLES_POPUP_OPENED),
        d.expect(d.FOCUS_MOVED),  # the popup opens with its first bubble focused
    ):
        d.key("Return")
    d.hold(3.5)  # every line the word is spoken in, with the word picked out

    # A bubble goes to its story at the page that line is on.
    with (
        d.expect(BUBBLE_PRESS.format(title=re.escape(SEARCH_WORD_PICK))),
        d.expect(BUBBLES_POPUP_DISMISSED),
    ):
        d.key("Return")
    d.settle()
    d.hold(3.0)  # the title view for the story the bubble came from
    d.wait_title_fade()  # the Enter below is lost while the panel is still fading in

    # Straight on into the story. Only the index screens hand focus to the read portal
    # after a popup goto (main_screen._bind_screen_callbacks wires
    # on_after_popup_goto_title for those alone), so this Enter is what enters the title
    # panel's nav focus - and it lands on the portal, which is what ced49f7's sibling
    # 63b4a42 made true while the panel is still fading in.
    d.key_then_wait(ALL_IMAGES_LOADED, "Return", timeout=30)
    d.read_pages(SEARCH_WORD_READ)
    d.close_reader()
    d.hold(1.0)

    # Closing the reader leaves focus in the bottom region, so hand it back before the
    # action bar's Go Back can be reached - the same two-step search_story needs.
    d.key("Escape")
    d.settle()
    d.go_back_then_wait(SEARCH_MODE_SET.format(mode="Word"))
    d.settle()
    d.hold(2.5)  # back on the search, query and results still there


def _setup_read_story(d: Driver) -> None:
    # Off camera: reach the story this beat reads, so the recording opens on it.
    d.open_branch("Series")
    d.open_branch(SERIES_DDA)
    d.select_node(READ_STORY_PICK.title)


@beat(
    "read_story",
    node=["The Stories", "root"],
    label="Skip to any page, or read two-up as printed",
    setup=_setup_read_story,
)
def read_story(d: Driver) -> None:
    """Read a story, skip to a page through the page list, and go two-up.

    The two-up stays in this windowed beat rather than the fullscreen one: the
    window is as wide as the clip, so a spread shows whole here, where the
    fullscreen beat's crop of the screen would take a strip off each side of it.
    """
    d.hold(1.0)
    # The setup's select_node starts the title view's fade, and a Return during
    # it is lost: focus_portal waits the fade out, then for focus on the portal.
    d.focus_portal()
    d.hold(0.6)
    d.key_then_wait(ALL_IMAGES_LOADED, "Return", timeout=30)
    d.read_pages(READ_STORY_PICK)
    # Skip to a page rather than turning to it, showing the page list on the way.
    d.goto_page(READ_STORY_GOTO_PAGE)
    d.hold(1.0)
    d.press_menu_button("double_page")
    d.settle()
    d.hold(3.5)


def _go_fullscreen(d: Driver) -> None:
    """Press the reader's fullscreen button, and give the X window the screen.

    With no window manager on the nested display, the app's fullscreen switch
    changes what it draws but not its X window: the page is laid out for the
    whole screen and shown through the old window, clipped. The app logs the
    switch, so this waits for that and then resizes the window by hand; until
    then, a frame or two of the clipped page goes by.
    """
    with d.expect(ENTERED_FULLSCREEN, 20):
        d.press_menu_button("fullscreen")
    fit_app_window_to_screen()
    d.settle()


@beat(
    "fullscreen",
    node=["The Stories", "root"],
    label="Or fill the screen",
    setup=_setup_read_story,
    whole_screen=True,
)
def fullscreen(d: Driver) -> None:
    """Open the story and fill the screen with it, a page at a time.

    Filmed from the whole nested screen rather than the app window, so the
    window is seen to grow into the frame: it opens at the other clips' scale
    with the screen's black around it, and the fullscreen page then fills the
    frame edge to edge. The crop and scale back to the shared clip size are the
    recorder's (`Beat.whole_screen`). Single page only: the crop takes a strip
    off each side of a spread, which fills the screen's width, so two-up is
    read_story's.
    """
    d.hold(1.0)
    d.focus_portal()
    d.hold(0.6)
    d.key_then_wait(ALL_IMAGES_LOADED, "Return", timeout=30)
    d.read_pages(FULLSCREEN_PICK)
    _go_fullscreen(d)
    d.hold(2.5)
    d.read_pages(FULLSCREEN_READ)
    d.hold(2.0)


@beat(
    "wiki_jump",
    node=[
        "LOST_IN_THE_ANDES",
        "censored but fixed stories",
        "Themes",
        "Categories",
        "The Stories",
        "root",
    ],
    label="Every story linked to the Carl Barks Wiki",
)
def wiki_jump(d: Driver) -> None:
    """Open a story's wiki page, browse the wiki, and come back into the reader."""
    d.hold(1.5)
    # Enter enters the title view at its last nav widget, the read portal, and
    # the wiki button is WIKI_UPS_FROM_PORTAL above it.
    #
    # Do not be tempted to enter at the first widget with Right and walk down
    # instead: that route reads better but wedges the app. It logs "entered nav
    # focus" and then stops responding to the keyboard entirely, sitting at
    # around 58% CPU with nothing further in the log, so the beat times out
    # waiting for a button press that never happened.
    d.key("Return")
    d.settle()
    d.hold(0.5)
    for _ in range(WIKI_UPS_FROM_PORTAL):
        d.key("Up")
        d.hold(0.3)
    d.settle()
    d.hold(0.8)
    d.key_then_wait(WIKI_ACTIVE, "Return", timeout=30)
    d.hold(2.5)
    for _ in range(3):
        d.key("Down")  # scroll the page
        d.hold(0.9)
    d.hold(1.0)

    # The wiki is a whole bundle, not one page: Left moves the focus off the page and
    # into the sidebar of titles, where Down walks them and Enter opens one.
    d.key("Left")
    d.settle()
    d.hold(1.0)
    for _ in range(WIKI_SIDEBAR_STEPS):
        d.key("Down")
        d.hold(0.6)
    d.settle()
    d.hold(0.8)
    d.key("Return")
    d.settle()
    d.hold(3.0)  # the wiki page for the story picked out of the sidebar

    # And back out again the way a remote would: Escape lifts focus to the top bar on
    # Back, Right walks along it to the goto-title button, Enter takes that story into
    # the reader. Nothing in the viewer writes to the log, so the waiting above is on
    # settle and the clock - but the landing is checked, by name, on the reader side.
    d.key("Escape")
    d.hold(0.8)
    for _ in range(WIKI_BAR_RIGHTS_TO_GOTO):
        d.key("Right")
        d.hold(0.5)
    d.hold(0.6)
    d.key_then_wait(NODE_SELECTED.format(name=re.escape(WIKI_SIDEBAR_PICK)), "Return", timeout=20)
    d.settle()
    d.hold(2.5)  # the reader, now on the story the wiki sent it to


@beat(
    "speech_index",
    node=["Speech Bubble Index", "Indexes", "root"],
    label="A full speech-bubble index, A to Z",
)
def speech_index(d: Driver) -> None:
    """Open the speech-bubble index and step through a few of its letters."""
    d.hold(1.2)
    d.key("Return")  # open the index screen
    d.settle()
    d.hold(2.5)
    # Walk the A-Z letters; each one repopulates the word grid.
    for _ in range(3):
        d.key_then_wait(LETTER_POPULATED, "Down")
        d.hold(1.6)
    d.hold(1.0)


@beat(
    "censored_stories",
    node=["The Stories", "root"],
    label="By category - censored stories, restored",
)
def censored_stories(d: Driver) -> None:
    """Drill down to the censored-but-fixed theme and open each configured pick.

    The Stories > Categories > Themes > censored but fixed stories, on camera: the
    thematic indexes are the point of the beat, not just the stories.
    """
    d.hold(1.0)
    d.open_branch("Categories")
    d.open_branch("Themes")
    d.open_branch("censored but fixed stories")
    d.hold(1.0)
    for pick in CENSORED_PICKS:
        d.select_node(pick.title)
        d.hold(0.8)
        d.open_story(pick)


@beat(
    "reading",
    node=["Reading", "root"],
    label="Choose for me, playlists, and your history",
)
def reading(d: Driver) -> None:
    """Walk the three ways the Reading node hands you something to read.

    Booting expands the path to the node, so Reading's three children are already
    on screen and this opens straight into them.

    The tree walk waits on select_node (name-driven: it fails rather than landing
    somewhere else); the history's tab bar on its focus lines and on the view
    each Return selects, so a lost key fails the beat instead of filming the
    wrong tab.
    """
    d.hold(1.5)

    # "Choose for me" is a dozen ways to be handed a story; Surprise me deals five
    # from across the whole run.
    d.open_branch("Choose for me")
    d.hold(0.8)
    d.open_branch("Surprise me")
    d.hold(4.0)
    _collapse_back(d)

    # Playlists are themed runs, each carrying its own description.
    d.open_branch("Playlists")
    d.hold(1.2)
    d.open_branch(READING_PLAYLIST)
    d.hold(4.5)
    _collapse_back(d)

    # And the history itself: the journal, then the same log counted by title.
    d.open_branch("History")
    d.hold(3.0)
    # Up off the first row enters the top bar, landing on the tab for the view that
    # is showing (history_screen._enter_bar_zone): Journal, which Enter would leave
    # as it is (_activate_bar_focus only switches views). Right steps to Titles,
    # and Enter shows it.
    d.key_then_wait(d.FOCUS_MOVED, "Up")
    d.hold(2.8)
    d.key_then_wait(d.FOCUS_MOVED, "Right")
    d.hold(0.7)
    d.key_then_wait(re.escape(HISTORY_VIEW_SELECTED.format(view="titles")), "Return")
    d.settle()
    d.hold(4.0)


# ----------------------------------------------------------- pure helpers --


def even(value: int) -> int:
    """Round down to an even number, which is what libx264 requires."""
    return value // 2 * 2


def parse_geometry(xwininfo_output: str, window_name: str) -> tuple[int, int, int, int]:
    """Pull an x11grab region out of ``xwininfo -root -children`` output.

    Args:
        xwininfo_output: The raw command output.
        window_name: Substring identifying the app's window line.

    Returns:
        ``(width, height, x, y)``, with the size rounded down to even.

    Raises:
        BeatError: If no line names that window.

    """
    for line in xwininfo_output.splitlines():
        if window_name not in line:
            continue
        found = re.search(r"(\d+)x(\d+)\+(\d+)\+(\d+)", line)
        if found:
            width, height, pos_x, pos_y = (int(g) for g in found.groups())
            return even(width), even(height), pos_x, pos_y
    msg = f"could not find the app window ({window_name}) on {DISPLAY}"
    raise BeatError(msg)


def parse_window_id(xwininfo_output: str, window_name: str) -> str:
    """Pull the app window's X id out of ``xwininfo -root -children`` output.

    Raises:
        BeatError: If no line names that window.

    """
    for line in xwininfo_output.splitlines():
        found = re.match(r"\s*(0x[0-9a-fA-F]+)\s+\"", line)
        if found and window_name in line:
            return found.group(1)
    msg = f"could not find the app window ({window_name}) on {DISPLAY}"
    raise BeatError(msg)


def parse_root_size(xwininfo_root_output: str) -> tuple[int, int]:
    """Pull the screen size out of ``xwininfo -root`` output.

    Raises:
        BeatError: If the output names no width and height.

    """
    width = re.search(r"^\s*Width:\s*(\d+)", xwininfo_root_output, re.MULTILINE)
    height = re.search(r"^\s*Height:\s*(\d+)", xwininfo_root_output, re.MULTILINE)
    if not width or not height:
        msg = f"could not read the screen size on {DISPLAY}"
        raise BeatError(msg)
    return int(width.group(1)), int(height.group(1))


def crop_to_aspect(
    root_width: int, root_height: int, width: int, height: int
) -> tuple[int, int, int, int]:
    """Return the largest centred crop of the screen with the clips' aspect.

    The fullscreen page is centred on the screen with its margins at the sides
    (or top and bottom), so trimming the screen to the clips' shape loses only
    margin; scaling that crop to the clips' size then gives one encode across
    every beat, which the stitch needs.

    Args:
        root_width: The screen's width.
        root_height: The screen's height.
        width: The other clips' width.
        height: The other clips' height.

    Returns:
        ``(crop_width, crop_height, x, y)`` for ffmpeg's crop filter, even-sized.

    """
    if root_width * height >= root_height * width:
        # The screen is wider than the clips: keep its height, trim the sides.
        crop_width, crop_height = even(root_height * width // height), even(root_height)
    else:
        crop_width, crop_height = even(root_width), even(root_width * height // width)
    return crop_width, crop_height, (root_width - crop_width) // 2, (root_height - crop_height) // 2


def _xwininfo(*args: str) -> str:
    return subprocess.run(  # noqa: S603  (fixed argv, absolute path, no shell)
        ["/usr/bin/xwininfo", *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "DISPLAY": DISPLAY},
    ).stdout


def fit_app_window_to_screen() -> None:
    """Resize the app's X window to the whole nested screen.

    There is no window manager on the nested display, so the app's own
    fullscreen switch moves nothing: SDL asks the (absent) window manager for
    the screen and carries on as if it had it, drawing for the screen's size
    into the old window. Without a window manager any client may place a
    window directly, so this does what the window manager would have.

    Raises:
        BeatError: If xdotool is missing, or could not place the window.

    """
    xdotool = shutil.which("xdotool")
    if xdotool is None:
        msg = "xdotool is needed to film fullscreen (apt install xdotool)"
        raise BeatError(msg)
    width, height = parse_root_size(_xwininfo("-root"))
    window = parse_window_id(_xwininfo("-root", "-children"), WINDOW_NAME)
    placed = subprocess.run(  # noqa: S603  (fixed argv, resolved path, no shell)
        [xdotool, "windowmove", window, "0", "0", "windowsize", window, str(width), str(height)],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "DISPLAY": DISPLAY},
    )
    if placed.returncode != 0:
        msg = f"xdotool could not place the app window: {placed.stderr.strip()}"
        raise BeatError(msg)


def select_beats(
    names: Sequence[str],
    only: str | None,
    start_from: str | None,
    stitch_only: bool,
) -> list[str]:
    """Work out which beats this run records.

    Beats that are not recorded are reused from the clip cache.

    Args:
        names: Every registered beat name, in order.
        only: Record just this beat.
        start_from: Record this beat and everything after it.
        stitch_only: Record nothing.

    Returns:
        The names to record, in order.

    """
    if stitch_only:
        return []
    if only:
        return [only]
    if start_from:
        return list(names[names.index(start_from) :])
    return list(names)


def missing_clips(beats: Iterable[str], work_dir: Path) -> list[str]:
    """Return the beats in `beats` that have no cached clip yet."""
    return [b for b in beats if not (work_dir / f"{b}.mp4").is_file()]


# ------------------------------------------------------------- the recorder --


# The app window's title on the nested display, as xwininfo lists it.
WINDOW_NAME = "Compleat Barks Disney Reader"


@dataclass(frozen=True)
class Grab:
    """What ffmpeg captures for one beat, and how it is fitted to the clip size."""

    width: int
    height: int
    x: int
    y: int
    # For a whole-screen beat: the crop (width, height, x, y) and the size it is
    # scaled to, which is the app window's, so the clip matches the others.
    crop: tuple[int, int, int, int] | None = None
    out_size: tuple[int, int] | None = None


class Recorder:
    """Runs the app, records beats, and puts the user's config back afterwards."""

    WINDOW_NAME = WINDOW_NAME

    FFMPEG_STOP_TIMEOUT = 30

    def __init__(self, out_dir: Path, work_dir: Path = WORK_DIR) -> None:
        self.out_dir = out_dir
        self.work_dir = work_dir
        self._ffmpeg: subprocess.Popen[bytes] | None = None
        self._config = Path(probe("config").strip())
        if not self._config.is_file():
            msg = f"app config not found: {self._config}"
            raise BeatError(msg)
        self._history = self._config.with_name(HISTORY_FILE_NAME)
        # Named up front so that if the process is killed outright, the user knows
        # where the pristine copies are.
        self._backup = self._back_up(self._config, "config")
        # A profile that has never read a comic has no history file: None then,
        # and close() removes the canned one rather than restoring anything.
        self._history_backup = (
            self._back_up(self._history, "history") if self._history.is_file() else None
        )

    @staticmethod
    def _back_up(path: Path, what: str) -> Path:
        handle, backup = tempfile.mkstemp(prefix=f"barks-demo-{what}.", suffix=".json")
        os.close(handle)
        shutil.copy2(path, backup)
        say(f"record-demo: {what} backed up to {backup}")
        return Path(backup)

    def close(self) -> None:
        """Stop everything and restore the user's config and reading history.

        Safe to call twice, and must not raise: it is the only thing standing
        between a failed run and a config left pointing at a beat's start node.
        """
        if self._ffmpeg is not None:
            self._stop_ffmpeg()
        try:
            probe("stop")
        except BeatError as exc:
            say(f"record-demo: WARNING {exc}")
        # gui-probe restores its own backups, which are the files we edited (and
        # deletes them, so a later manual `gui-probe.sh stop` cannot re-apply them);
        # put the user's originals back on top.
        if self._backup.is_file():
            shutil.copy2(self._backup, self._config)
            self._backup.unlink(missing_ok=True)
        if self._history_backup is None:
            self._history.unlink(missing_ok=True)
        elif self._history_backup.is_file():
            shutil.copy2(self._history_backup, self._history)
            self._history_backup.unlink(missing_ok=True)

    def _check_ffmpeg_running(self) -> None:
        """Fail now if the recorder has already exited, rather than after the beat.

        Raises:
            BeatError: With ffmpeg's stderr, if it is no longer running.

        """
        if self._ffmpeg is not None and self._ffmpeg.poll() is not None:
            msg = self._stop_ffmpeg() or "ffmpeg exited before recording started"
            raise BeatError(msg)

    def _stop_ffmpeg(self) -> str | None:
        """Stop the recorder cleanly and say why it failed, if it did.

        SIGINT makes ffmpeg stop cleanly and write the trailer; killing it outright
        leaves an unplayable file. ffmpeg answers that SIGINT with exit status 255
        even after a clean stop, so the failure signs are an exit before it was
        asked for one, any other non-zero status, or not stopping at all.

        Returns:
            A description of the failure, or None if the clip was written cleanly.

        """
        process, self._ffmpeg = self._ffmpeg, None
        if process is None:
            return None
        died_early = process.poll() is not None
        if not died_early:
            process.send_signal(signal.SIGINT)
        try:
            _, err = process.communicate(timeout=self.FFMPEG_STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return f"ffmpeg did not stop within {self.FFMPEG_STOP_TIMEOUT}s and was killed"
        stderr = err.decode(errors="replace").strip() if err else ""
        if died_early:
            return f"ffmpeg exited during the beat (status {process.returncode}): {stderr}"
        if process.returncode not in (0, 255):
            return f"ffmpeg failed (status {process.returncode}): {stderr}"
        if stderr:
            say(f"record-demo: ffmpeg: {stderr}")
        return None

    def boot_at(self, node: Sequence[str]) -> None:
        """Start the app with its tree selection set to `node` and the canned history.

        Each beat opens on a known screen instead of inheriting wherever the
        previous beat left the selection, and on the same journal, whatever the
        beats before it read.
        """
        self._history.write_text(
            json.dumps(canned_history_json(), indent=2) + "\n", encoding="utf-8"
        )
        boot_app_at(node, config=self._config, seed=RANDOM_SEED, cues=PINNED_CUES)

    def app_region(self) -> tuple[int, int, int, int]:
        """Return the app window's x11grab region on the nested display.

        There is no window manager there, so this is the app's own geometry with
        no decorations - cropping to it drops the Xephyr letterboxing.
        """
        return parse_geometry(_xwininfo("-root", "-children"), self.WINDOW_NAME)

    def root_size(self) -> tuple[int, int]:
        """Return the nested screen's size."""
        return parse_root_size(_xwininfo("-root"))

    def grab_for(self, item: Beat) -> Grab:
        """Work out what to capture for `item`: its window, or the whole screen fitted."""
        width, height, pos_x, pos_y = self.app_region()
        if not item.whole_screen:
            return Grab(width, height, pos_x, pos_y)
        root_width, root_height = self.root_size()
        crop = crop_to_aspect(root_width, root_height, width, height)
        return Grab(root_width, root_height, 0, 0, crop=crop, out_size=(width, height))

    def record(self, item: Beat) -> Path:
        """Record one beat to its cached clip and return the path.

        The clip is written under a ``.partial.mp4`` name and only takes its final
        name once the beat has run to the end and ffmpeg has stopped cleanly. A
        beat that fails part way therefore leaves nothing the cache would mistake
        for a finished clip - the partial stays behind for inspection, and a
        later ``--stitch`` or ``--from`` records the beat again.

        Raises:
            BeatError: If the beat failed, or ffmpeg did not record it cleanly.

        """
        clip = self.work_dir / f"{item.name}.mp4"
        partial = self.work_dir / f"{item.name}.partial.mp4"
        say(f"record-demo: [{item.name}] booting")
        self.boot_at(item.node)
        driver = Driver()
        if item.setup is not None:
            say(f"record-demo: [{item.name}] setup")
            item.setup(driver)

        grab = self.grab_for(item)
        say(
            f"record-demo: [{item.name}] recording {grab.width}x{grab.height} at +{grab.x}+{grab.y}"
        )
        if grab.crop and grab.out_size:
            crop_w, crop_h, crop_x, crop_y = grab.crop
            say(
                f"record-demo: [{item.name}] the whole screen, cropped to"
                f" {crop_w}x{crop_h} at +{crop_x}+{crop_y} and scaled to"
                f" {grab.out_size[0]}x{grab.out_size[1]}"
            )
        with _caption_file(item.label) as caption:
            self._ffmpeg = self._start_ffmpeg(partial, grab, caption)
            try:
                time.sleep(0.5)  # let the first frames land before anything moves
                self._check_ffmpeg_running()
                item.body(driver)
            except BaseException:
                self._stop_ffmpeg()
                say(f"record-demo: [{item.name}] failed; partial clip left at {partial}")
                raise
            failure = self._stop_ffmpeg()
        if failure is not None:
            msg = f"[{item.name}] {failure}"
            raise BeatError(msg)
        if not partial.is_file():
            msg = f"[{item.name}] ffmpeg stopped cleanly but wrote no clip at {partial}"
            raise BeatError(msg)
        partial.replace(clip)
        probe("stop")
        say(f"record-demo: [{item.name}] {_human_size(clip)}")
        return clip

    def _start_ffmpeg(
        self,
        clip: Path,
        grab: Grab,
        caption: Path | None,
    ) -> subprocess.Popen[bytes]:
        # The caption is burned in at record time, not at stitch time, because the
        # stitch is a stream copy - there is no re-encode later to draw it into.
        # A whole-screen grab is cropped and scaled to the clip size first, so the
        # caption is drawn at the same size and place as on every other beat.
        filters: list[str] = []
        if grab.crop and grab.out_size:
            crop_w, crop_h, crop_x, crop_y = grab.crop
            filters.append(f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}")
            filters.append(f"scale={grab.out_size[0]}:{grab.out_size[1]}:flags=lanczos")
        if caption is not None:
            filters.append(
                f"drawtext=fontfile={FONT}:textfile={caption}:"
                f"fontcolor={CAPTION_COLOR}:fontsize={CAPTION_SIZE}:"
                f"box=1:boxcolor=black@{CAPTION_BOX_ALPHA}:"
                f"boxborderw={CAPTION_BOX_PAD}:"
                f"shadowcolor=black@0.9:shadowx={CAPTION_SHADOW}:"
                f"shadowy={CAPTION_SHADOW}:x=(w-text_w)/2:y=h-th-{CAPTION_BOTTOM}"
            )
        video_filter = ["-vf", ",".join(filters)] if filters else []
        return subprocess.Popen(  # noqa: S603  (fixed argv, absolute path, no shell)
            [
                "/usr/bin/ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-nostdin",
                "-f",
                "x11grab",
                "-framerate",
                str(FPS),
                "-draw_mouse",
                "0",
                "-video_size",
                f"{grab.width}x{grab.height}",
                "-i",
                f"{DISPLAY}+{grab.x},{grab.y}",
                *video_filter,
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                str(CRF),
                "-g",
                str(GOP),
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(clip),
            ],
            stderr=subprocess.PIPE,  # read back by _stop_ffmpeg, for the error report
        )


class _caption_file:  # noqa: N801  (context manager used lowercase, like open())
    """Write a caption to a temp file for ffmpeg's ``textfile=``.

    Passing the text through a file rather than the filter string means a caption
    can contain colons, quotes and backslashes without any escaping.
    """

    def __init__(self, label: str) -> None:
        self._label = label
        self._path: Path | None = None

    def __enter__(self) -> Path | None:
        if not self._label:
            return None
        handle, name = tempfile.mkstemp(prefix="barks-demo-caption.", suffix=".txt")
        os.close(handle)
        self._path = Path(name)
        self._path.write_text(self._label)
        return self._path

    def __exit__(self, *_exc: object) -> None:
        if self._path is not None:
            self._path.unlink(missing_ok=True)


def _human_size(path: Path) -> str:
    size = path.stat().st_size
    for unit in ("B", "K", "M", "G"):
        if size < 1024 or unit == "G":  # noqa: PLR2004
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}G"


def _run_ffmpeg(args: Sequence[str]) -> None:
    subprocess.run(  # noqa: S603  (fixed argv, no shell)
        ["/usr/bin/ffmpeg", "-y", "-loglevel", "error", *args],
        check=True,
    )


def stream_signature(path: Path) -> str:
    """Return a clip's codec, size and pixel format, as one comparable string."""
    return subprocess.run(  # noqa: S603  (fixed argv, no shell)
        [
            "/usr/bin/ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,pix_fmt",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()


def check_same_encode(beats: Sequence[str], work_dir: Path) -> None:
    """Refuse to stitch clips that do not share one encode.

    The concat is a stream copy, so ffmpeg never looks at what it is joining: two
    clips of different sizes concatenate without a word, the container declares
    the first clip's size throughout, and browsers stall or jump at the splice.
    That is easy to reach - ``--only`` mixes a fresh clip with cached ones, and the
    window is sized to the nested screen at boot, so a changed BARKS_PROBE_SCREEN
    between recordings does it.

    Raises:
        BeatError: If any two clips differ in codec, size or pixel format.

    """
    signatures = {b: stream_signature(work_dir / f"{b}.mp4") for b in beats}
    if len(set(signatures.values())) > 1:
        detail = "\n".join(f"  {b}: {s or 'unreadable'}" for b, s in signatures.items())
        msg = (
            "cached clips do not share one encode, so they cannot be stitched -"
            f" re-record the odd ones out:\n{detail}"
        )
        raise BeatError(msg)


def duration_of(path: Path) -> float:
    """Return a media file's duration in seconds."""
    output = subprocess.run(  # noqa: S603  (fixed argv, no shell)
        [
            "/usr/bin/ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return float(output) if output else 0.0


@dataclass(frozen=True)
class Chapter:
    """Where one beat falls in a stitched video, in seconds from its start."""

    beat: str
    title: str
    start: float
    end: float


def chapter_list(beats: Sequence[str], work_dir: Path) -> list[Chapter]:
    """Describe where each beat falls in the stitched video.

    Generated rather than written down: the times move whenever a beat's pacing
    changes or it is re-recorded, and a hand-maintained list would be wrong the
    first time someone changed a dwell - silently, since nothing would check it.

    Args:
        beats: The beats making up the video, in order.
        work_dir: Where the cached beat clips live.

    Returns:
        One entry per beat, with its caption as the chapter title and its start
        and end in seconds from the beginning of the video.

    """
    chapters: list[Chapter] = []
    start = 0.0
    for name in beats:
        length = duration_of(work_dir / f"{name}.mp4")
        chapters.append(
            Chapter(
                beat=name,
                title=find_beat(name).label or name,
                start=round(start, 2),
                end=round(start + length, 2),
            )
        )
        start += length
    return chapters


def write_chapters(video: Path, beats: Sequence[str], work_dir: Path) -> Path:
    """Write the chapter manifest beside its video, and check it lines up."""
    chapters = chapter_list(beats, work_dir)
    manifest = video.with_name(f"{video.stem}-chapters.json")
    manifest.write_text(json.dumps([asdict(c) for c in chapters], indent=2) + "\n")

    # The concat is a stream copy, so the parts should add up to the whole. If
    # they ever do not, every chapter after the drift points at the wrong moment.
    total = duration_of(video)
    last_end = chapters[-1].end if chapters else 0.0
    drift = abs(total - last_end)
    if drift > 0.5:  # noqa: PLR2004
        say(
            f"record-demo: WARNING {manifest.name} ends at {last_end:.1f}s"
            f" but {video.name} runs {total:.1f}s"
        )
    return manifest


def stitch(name: str, beats: Sequence[str], out_dir: Path, work_dir: Path) -> Path:
    """Concatenate cached beat clips into one output video.

    Stream copy: the beats already share an encode, so this rewrites the container
    without re-compressing. ``+faststart`` puts the index first so the browser can start
    playing before the whole file has arrived. An output in ``CHAPTERED_OUTPUTS`` gets
    its chapter manifest written beside it.

    Raises:
        BeatError: If any of the named beats has no cached clip, or the clips do
            not share one encode.

    """
    absent = missing_clips(beats, work_dir)
    if absent:
        msg = (
            f"{name}: no clip for {' '.join(absent)} - record them first, or drop them from OUTPUTS"
        )
        raise BeatError(msg)
    check_same_encode(beats, work_dir)

    list_file = work_dir / f"concat-{Path(name).stem}.txt"
    list_file.write_text("".join(f"file '{work_dir / f'{b}.mp4'}'\n" for b in beats))
    final = out_dir / name
    _run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(final),
        ],
    )
    chapters = ""
    if name in CHAPTERED_OUTPUTS:
        manifest = write_chapters(final, beats, work_dir)
        chapters = f", {len(beats)} chapters -> {manifest.name}"
    say(f"record-demo: {final}  ({_human_size(final)}, {duration_of(final):.0f}s{chapters})")
    return final


def write_poster(video: Path, work_dir: Path) -> None:
    """Write a poster frame beside one output video, per POSTERS."""
    want = POSTERS.get(video.name, "first")
    poster = video.with_name(f"{video.stem}-poster.jpg")

    if want == "first":
        source, seek = video, ["-i", str(video)]
    else:
        clip = work_dir / f"{want}.mp4"
        source = clip if clip.is_file() else video
        seek = ["-sseof", "-0.5", "-i", str(source)]
    if not source.is_file():
        return

    _run_ffmpeg([*seek, "-update", "1", "-frames:v", "1", "-q:v", str(POSTER_QUALITY), str(poster)])
    say(f"record-demo: {poster.name} ({_human_size(poster)}, from {want})")


# ---------------------------------------------------------------------- CLI --


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        description="Record the Barks Reader demo clips.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--list", action="store_true", help="print the beat names and exit")
    parser.add_argument("--only", metavar="BEAT", help="record just this beat")
    parser.add_argument("--from", dest="start_from", metavar="BEAT", help="record from here on")
    parser.add_argument("--output", metavar="FILE", help="build just this output video")
    parser.add_argument("--out", metavar="DIR", type=Path, help="write videos here")
    parser.add_argument("--stitch", action="store_true", help="rebuild from cached clips only")
    parser.add_argument(
        "--clean", action="store_true", help="drop every cached clip first (full runs only)"
    )
    return parser.parse_args(argv)


def validate(args: argparse.Namespace) -> None:
    """Check that the command line names things that exist and fit together.

    Raises:
        BeatError: If an output, a beat, or the probe script is missing; if
            ``--clean`` is combined with a selector; if ``--only`` names a
            beat the requested ``--output`` does not contain; or if a beat to
            be recorded films the whole screen and xdotool is not installed.

    """
    if args.output and args.output not in OUTPUTS:
        msg = f"no such output: {args.output} (have: {' '.join(OUTPUTS)})"
        raise BeatError(msg)
    for name in (args.only, args.start_from):
        if name:
            find_beat(name)
    # A selector re-records its beats whether or not they are cached, so --clean
    # adds nothing to it - and it would empty the cache the stitch then needs,
    # failing only after the recording had been done.
    if args.clean and (args.only or args.start_from or args.stitch):
        msg = (
            "--clean records everything from scratch; it cannot go with --only, --from or --stitch"
        )
        raise BeatError(msg)
    if args.only and args.output and args.only not in OUTPUTS[args.output]:
        msg = f"{args.output} does not contain {args.only}, so recording it would change nothing"
        raise BeatError(msg)
    if not PROBE.is_file():
        msg = f"missing {PROBE}"
        raise BeatError(msg)
    # Only a beat filmed from the whole screen places the window by hand, so a
    # stitch, or a run that records none of them, needs no xdotool.
    recording = select_beats(beat_names(), args.only, args.start_from, args.stitch)
    if any(find_beat(b).whole_screen for b in recording) and shutil.which("xdotool") is None:
        msg = "xdotool is needed to film the fullscreen beat (apt install xdotool)"
        raise BeatError(msg)


def _raise_on_signal(signal_number: int, _frame: object) -> None:
    # Turned into an exception so record_all's finally runs and the config goes
    # back: a plain SIGTERM or SIGHUP (the terminal closing) would otherwise end
    # the process with the config still pointing at a beat's node.
    msg = f"stopped by {signal.Signals(signal_number).name}"
    raise BeatError(msg)


def record_all(names: Sequence[str], out_dir: Path) -> None:
    """Record each named beat, always restoring the user's config afterwards."""
    if not names:
        return
    recorder = Recorder(out_dir)
    previous = {s: signal.signal(s, _raise_on_signal) for s in (signal.SIGTERM, signal.SIGHUP)}
    try:
        for name in names:
            recorder.record(find_beat(name))
    finally:
        recorder.close()
        for signal_number, handler in previous.items():
            signal.signal(signal_number, handler)


def build_outputs(only: str | None, out_dir: Path) -> None:
    """Stitch every output video, or just `only` if one is named."""
    for output, beats in OUTPUTS.items():
        # --output narrows the stitch to one file, which also means a missing
        # clip for some other output does not block previewing this one.
        if only and output != only:
            continue
        write_poster(stitch(output, beats, out_dir, WORK_DIR), WORK_DIR)


def main(argv: Sequence[str] | None = None) -> int:
    """Record and stitch according to the command line. Returns a process exit code."""
    args = parse_args(argv)
    names = beat_names()

    if args.list:
        say("\n".join(names))
        return 0

    out_dir: Path = args.out or DEFAULT_OUT_DIR
    try:
        validate(args)
        WORK_DIR.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        if args.clean:
            for clip in WORK_DIR.glob("*.mp4"):
                clip.unlink()
        record_all(select_beats(names, args.only, args.start_from, args.stitch), out_dir)
        say()
        build_outputs(args.output, out_dir)
    except BeatError as exc:
        print(f"record-demo: {exc}", file=sys.stderr)  # noqa: T201
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
