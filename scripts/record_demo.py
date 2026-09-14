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
    - ffmpeg built with libx264 and libfreetype.

Only the standard library is used, so this runs without the workspace venv, the
same as the gui-probe script it drives.

The app rewrites its config on exit, so this backs up ``barks-reader.json``
before touching ``last_selected_node`` and restores it on any exit, including a
failure or a Ctrl-C. It never writes to ``barks-reader.ini``. The probe looks
after the reading-history file.

Usage:
    scripts/record_demo.py                       # every beat, every output
    scripts/record_demo.py --list
    scripts/record_demo.py --only browse_tree
    scripts/record_demo.py --from read_story
    scripts/record_demo.py --stitch              # rebuild from cached beats
    scripts/record_demo.py --output demo.mp4     # build just this one
    scripts/record_demo.py --out /tmp/preview
    scripts/record_demo.py --clean               # drop cached clips first

Env overrides: BARKS_PROBE_DISPLAY (:2), BARKS_PROBE_SCREEN (900x1300) - both are
passed straight through to gui-probe.sh.
"""

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
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
PROBE = REPO_ROOT / "scripts" / "gui-probe.sh"
DISPLAY = os.environ.get("BARKS_PROBE_DISPLAY", ":2")
# The app reads this on startup and seeds its random module from it; gui-probe
# launches the app as a child, so setting it here is enough to reach it.
RANDOM_SEED_ENV_VAR = "BARKS_READER_RANDOM_SEED"

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

WALK_PAUSE = 0.45  # pace of a single Down while walking the tree on camera
TYPE_PAUSE = 0.4  # pace of a single character into a search box

# Where each output's poster frame comes from. A beat name takes that beat's
# resting frame; "first" takes the video's own opening frame.
#
# The hero plays by itself, so its still barely shows and wants to be composed -
# browse_tree's resting frame has the tree, a title card and the app's chrome.
# The tour is click-to-play, so its poster is the frame it will start from:
# anything else makes the player look like it jumped when play is pressed.
POSTER_BEAT = "browse_tree"
POSTERS = {"demo.mp4": POSTER_BEAT, "walkthrough.mp4": "first"}

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

# How long a setup that ends on a title view waits before the camera rolls.
# The bottom title view fades in over a random 0-4s (the app's
# TITLE_PORTAL_OPENING_ANIMATION_MAX_DURATION_SECS), and nothing is written to the
# log while it animates - so settle(), which waits on the log, returns with the fade
# still running and the beat opens on a part-transparent panel with the tree showing
# through. Measured on a clip recorded without this wait, the panel was still
# settling 1.4s in. That makes the cut from the beat before jump in opacity even
# when both are on the same story and, since the seed was fixed, the same artwork.
# Covers the worst case with a little margin; there is nothing to wait on but time.
TITLE_FADE_SECS = 4.5

# Pins the app's random image choices, so a re-recorded beat comes back with the
# same backgrounds and insets as the one it replaces and two runs can be compared
# frame for frame. Any fixed number does; it only has to be the same every time.
# Set to None to let the app pick freshly, as it does for a normal user.
RANDOM_SEED: int | None = 20260915

# What the two search beats type. Keep them short - every character is typed with
# a visible pause, so a long query makes for a slow beat.
SEARCH_TITLE_QUERY = "vacation"
# Which result row to take, counting from 1, and where the rows sit on the
# nested display.
#
# The rows are clicked rather than keyed. There is no keyboard path that
# survives: the search box keeps the keyboard, so Down moves the text cursor
# instead of the selection, and whether a press reaches the list at all varies
# run to run. Clicking is exact here - the nested display has no compositor and
# no HiDPI scaling, so a screenshot pixel is the pixel to click - and the beat
# still checks by name which story it landed on, so a layout change fails the
# run instead of quietly demonstrating a different comic.
SEARCH_TITLE_RESULT = 2
SEARCH_RESULT_X = 450
SEARCH_RESULT_TOP_Y = 695  # centre of the first row
SEARCH_RESULT_ROW_H = 30
SEARCH_WORD_QUERY = "airline"
# The story the word beat opens the speech bubbles for, spelled as the app logs it.
# Word results are sorted by title, so the pick is a row index into that list.
SEARCH_WORD_PICK = "Adventure Down Under"
SEARCH_WORD_RESULT = 1
# The word-results geometry, in screenshot pixels: every row ends in a speech
# balloon that opens just that story's matching bubbles.
SEARCH_WORD_BALLOON_X = 728
SEARCH_WORD_RESULT_TOP_Y = 697  # centre of the first row
SEARCH_WORD_ROW_H = 29
# The bubble to press in the popup - the first one, page 1's "WE'LL FLY! THE AIRLINE
# TICKET OFFICE IS ON THE NEXT STREET!". Pressing it goes to that page of the story.
SEARCH_WORD_BUBBLE_X = 232
SEARCH_WORD_BUBBLE_Y = 843


@dataclass(frozen=True)
class Pick:
    """A story a beat opens, with its own pacing.

    Args:
        title: The app's title enum, as logged in "New selected node". Empty for
            a beat that reaches its comic positionally rather than by name.
        pages: Pages to show, counting the one it opens on. 1 opens and closes
            without turning.
        dwell: Seconds to rest on each of those pages.

    """

    title: str = ""
    pages: int = 2
    dwell: float = 2.5


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

# The story search_story finds, and how much of it to read. Its title must be
# what SEARCH_TITLE_RESULT actually lands on.
SEARCH_TITLE_PICK = Pick("VACATION_TIME", pages=3, dwell=1.0)

# How much of the story to read once the bubble has landed on it. Only `pages` and
# `dwell` are used here - the beat reaches the comic through the bubble, not by name.
SEARCH_WORD_READ = Pick(pages=4, dwell=1.0)

# open_comic reaches its story by walking, not by name, so this sets only its
# pacing: five pages means the one it opens on plus four turns.
OPEN_COMIC_PICK = Pick(pages=4, dwell=1.5)

# The page read_story jumps to through the goto-page dropdown, to show that the
# reader skips about rather than only turning forward.
#
# This is the reader's page *index* - what the app logs as "Showed page N" - and
# not the printed page number: the index counts the cover and the front matter,
# so it runs ahead of what is printed on the page. The dropdown lists pages in
# that same index order, which is why stepping by the difference between two of
# them lands exactly. Must exist in READ_STORY_PICK's story, or the jump ends up
# somewhere else - loudly, since the landing is checked against the log.
READ_STORY_GOTO_PAGE = 18

# How many Ups wiki_jump takes from the read portal to reach the wiki button.
#
# The title view's nav widgets run title-show, wiki, overrides, goto-page,
# portal, and the middle three only appear when they have something to show.
# Entering at the portal and walking up therefore depends on what is between:
# two Ups is right when the goto-page row is there and the overrides row is not,
# which is the case for a story that has a cued last-read page.
#
# That makes this beat depend on the user's own config - clear the cue for
# NODE_wiki_jump's story and the walk lands on the wrong widget. It fails loudly
# rather than filming the wrong thing, because the Enter that follows is checked
# against the log.
WIKI_UPS_FROM_PORTAL = 2
# Once in the wiki, how far down its sidebar to move from the story it opened on,
# and the enum name of the title that lands on. The beat waits on that name, so if
# the wiki's own ordering shifts underneath it the beat fails rather than quietly
# filming a different story.
WIKI_SIDEBAR_STEPS = 2
WIKI_SIDEBAR_PICK = "GOLDEN_CHRISTMAS_TREE_THE"
# Escape lifts the wiki's keyboard focus to its top bar, landing on Back. The button
# that hands the story back to the reader is this far to its right; the bar runs
# Back, contrast, goto-title, quit.
WIKI_BAR_RIGHTS_TO_GOTO = 2
GOTO_LIST_DWELL = 1.5  # time the open page list stays on screen before stepping
GOTO_STEP_PAUSE = 0.12  # pace of a single step through the page list

# What gets stitched, and from which beats. A beat can appear in more than one
# output; it is only ever recorded once. The short hero loop is the one that plays
# by itself at the top of the intro tab; the walkthrough is the linked tour.
OUTPUTS: dict[str, tuple[str, ...]] = {
    "demo.mp4": ("browse_tree", "open_comic"),
    "walkthrough.mp4": (
        "browse_tree",
        "series_view",
        "search_story",
        "search_words",
        "read_story",
        "wiki_jump",
        "speech_index",
        "censored_stories",
        "history",
    ),
}


def say(message: str = "") -> None:
    """Write a progress line to stdout."""
    print(message)  # noqa: T201


class BeatError(RuntimeError):
    """A beat could not reach a state it needed, so the run must not continue."""


# ------------------------------------------------------------ beat registry --


@dataclass(frozen=True)
class Beat:
    """One recorded clip: where it starts, what it says, and what it does."""

    name: str
    node: list[str]
    label: str = ""
    body: Callable[[Driver], None] = field(default=lambda _d: None)
    setup: Callable[[Driver], None] | None = None


BEATS: list[Beat] = []


def beat(
    name: str,
    node: Sequence[str],
    label: str = "",
    setup: Callable[[Driver], None] | None = None,
) -> Callable[[Callable[[Driver], None]], Callable[[Driver], None]]:
    """Register the decorated function as a beat.

    Args:
        name: Beat name, as used by --only/--from and in OUTPUTS.
        node: The tree node to boot onto, leaf-to-root.
        label: Caption burned along the bottom of the clip. May contain any
            characters; it is passed to ffmpeg through a file, not the filter
            string.
        setup: Optional off-camera navigation, run before recording starts.

    Returns:
        The decorator, which returns the function unchanged.

    """

    def register(fn: Callable[[Driver], None]) -> Callable[[Driver], None]:
        BEATS.append(Beat(name=name, node=list(node), label=label, body=fn, setup=setup))
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


# -------------------------------------------------------------- the driver --


class Driver:
    """Keystroke-level control of the app on the nested display.

    Every method that waits does so on the app's own log, which is a more
    precise oracle than the pixels and is never stale.
    """

    _NODE_RE = re.compile(r'New selected node: "([^"]+)"')
    _PAGE_RE = re.compile(r"Showed page (\d+)")

    # The reader's action-bar menu, in the order it is navigated - which is the
    # order comic_book_reader.py passes to _setup_action_bar_nav, NOT the order
    # the buttons appear in the .kv file. Focus starts on the first of these.
    _MENU_BUTTONS = (
        "close",
        "fullscreen",
        "double_page",
        "goto_start",
        "goto_end",
        "goto_page",
    )

    def __init__(self, probe: Path = PROBE) -> None:
        self._probe = probe
        self._log = Path(self._run(["log"]).strip())
        # Menu focus is sticky, so the driver has to remember where it left it.
        self._menu_focus = self._MENU_BUTTONS[0]

    def _run(self, args: Sequence[str]) -> str:
        result = subprocess.run(  # noqa: S603  (fixed argv, no shell)
            [str(self._probe), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout

    @property
    def log_path(self) -> Path:
        """Path of the running app's log file."""
        return self._log

    def key(self, *keys: str) -> None:
        """Inject one or more X11 key names, e.g. ``Down``, ``Return``, ``Escape``."""
        self._run(["key", *keys])

    def click(self, x: int, y: int) -> None:
        """Click at a screenshot pixel on the nested display."""
        self._run(["click", str(x), str(y)])

    def settle(self) -> None:
        """Block until the app has stopped writing to its log, i.e. stopped drawing."""
        self._run(["settle"])

    @staticmethod
    def hold(seconds: float) -> None:
        """Dwell on the current frame.

        Pacing only - never use this to wait for the app to reach a state. Use
        `wait_for` or `key_then_wait`, which fail loudly instead of silently
        recording the wrong screen.
        """
        time.sleep(seconds)

    def type_slowly(self, text: str) -> None:
        """Type into a focused text box one character at a time.

        ``gui-probe type`` sends the whole string through ``xte str`` and the
        app's search-as-you-type handler drops most of it - a ten-character query
        arrived in the box as four characters. Per-character with a gap is
        reliable, and reads as a natural typing pace on video.
        """
        for char in text:
            self._run(["type", char])
            time.sleep(TYPE_PAUSE)

    def current_node(self) -> str:
        """Return the node the app last logged as selected.

        Title nodes log their enum name (``FROZEN_GOLD``), category nodes their
        text (``Themes``). Empty if the app has not logged a selection yet.
        """
        matches = self._NODE_RE.findall(self._log.read_text(errors="replace"))
        return matches[-1] if matches else ""

    def current_page(self) -> int:
        """Return the body page the reader last rendered, per the app log.

        Read rather than calculated: a story opens on whatever page the user
        cued in their config, so the caller cannot know where the reader is
        without assuming that cue.
        """
        matches = self._PAGE_RE.findall(self._log.read_text(errors="replace"))
        return int(matches[-1]) if matches else 0

    def match_count(self, pattern: str) -> int:
        """Return how many log lines have matched `pattern` so far."""
        return len(re.findall(pattern, self._log.read_text(errors="replace")))

    def select_node(self, want: str, max_steps: int = 60) -> None:
        """Walk the tree downward until `want` is the selected node.

        Name-driven rather than a counted run of Downs, so a title added upstream
        shifts the walk instead of silently landing the demo on the wrong story.
        It only ever goes down, so picks have to be in tree order.

        Raises:
            BeatError: If the selection stops moving, or `want` is never reached.

        """
        current = self.current_node()
        stalled = 0
        for _ in range(max_steps):
            if current == want:
                return
            previous = current
            self.key("Down")
            time.sleep(WALK_PAUSE)
            current = self.current_node()
            if current != previous:
                stalled = 0
                continue
            # One swallowed keypress during a render is normal; two in a row
            # means the selection cannot move any further down.
            stalled += 1
            if stalled >= 2:  # noqa: PLR2004
                msg = (
                    f'tree stopped at "{current}" before reaching "{want}" - is it above '
                    f"the current position, or in another branch?"
                )
                raise BeatError(msg)
        msg = f'never reached node "{want}" in {max_steps} steps'
        raise BeatError(msg)

    def key_then_wait(self, pattern: str, timeout: float, *keys: str) -> None:
        """Press keys, then block until a NEW occurrence of `pattern` is logged.

        ``gui-probe wait`` greps the whole log, so a marker that fires once per
        comic matches the previous comic and returns instantly - which would cut
        away from a story before it had drawn. Counting occurrences and blocking
        for a new one is the only reliable form when a beat opens more than one.

        Raises:
            BeatError: If no new match arrives within `timeout` seconds.

        """
        before = self.match_count(pattern)
        self.key(*keys)
        self._await_new(pattern, timeout, before)

    def click_then_wait(self, pattern: str, timeout: float, x: int, y: int) -> None:
        """Click, then block until a NEW occurrence of `pattern` is logged.

        Raises:
            BeatError: If no new match arrives within `timeout` seconds.

        """
        before = self.match_count(pattern)
        self.click(x, y)
        self._await_new(pattern, timeout, before)

    def _await_new(self, pattern: str, timeout: float, before: int) -> None:
        deadline = time.monotonic() + timeout
        while self.match_count(pattern) <= before:
            if time.monotonic() > deadline:
                msg = f"beat stalled: no new /{pattern}/ in the app log after {timeout}s"
                raise BeatError(msg)
            time.sleep(0.25)

    def wait_for(self, pattern: str, timeout: float = 15) -> None:
        """Block until `pattern` appears anywhere in the app log.

        Raises:
            BeatError: If it never appears within `timeout` seconds.

        """
        deadline = time.monotonic() + timeout
        while self.match_count(pattern) == 0:
            if time.monotonic() > deadline:
                msg = f"beat stalled: never saw /{pattern}/ in the app log"
                raise BeatError(msg)
            time.sleep(0.25)

    # -- composite moves ----------------------------------------------------

    def open_branch(self, name: str) -> None:
        """Walk down to a collapsed node and expand it."""
        self.select_node(name)
        self.hold(0.3)
        self.key("Return")
        self.settle()
        self.hold(0.4)

    def read_pages(self, pick: Pick) -> None:
        """Rest on the page the comic opened at, then turn through the rest.

        Waits on the bare "Showed page" marker rather than a page number: a story
        opens on whatever page the user cued, so the number is not known here,
        and `key_then_wait` only needs a new render rather than a specific one.
        """
        self.hold(pick.dwell)
        for _ in range(pick.pages - 1):
            self.key_then_wait("Showed page", 15, "Right")
            self.hold(pick.dwell)

    def press_menu_button(self, name: str) -> None:
        """Open the reader's action-bar menu and activate one button by name.

        Menu mode does not reopen on a fixed button: ``_enter_menu_mode`` restores
        ``_last_used_btn_idx``, so it comes back focused on whatever was activated
        last. A fixed run of arrow presses is therefore only right the first time
        - after a goto-page, the same two Rights that used to reach double-page
        reach fullscreen instead, which on a nested display with no window
        manager resizes the window out from under the recorder.

        Tracking the last activation here is what makes the second press land
        where it says. Nothing else drives the app, so this stays in step.

        Args:
            name: One of `_MENU_BUTTONS`.

        Raises:
            BeatError: If `name` is not a menu button.

        """
        if name not in self._MENU_BUTTONS:
            msg = f"no such menu button: {name} (have: {', '.join(self._MENU_BUTTONS)})"
            raise BeatError(msg)

        count = len(self._MENU_BUTTONS)
        here = self._MENU_BUTTONS.index(self._menu_focus)
        there = self._MENU_BUTTONS.index(name)
        forward = (there - here) % count
        backward = (here - there) % count

        self.key("Escape")  # reader menu mode
        self.hold(0.5)
        step, presses = ("Right", forward) if forward <= backward else ("Left", backward)
        for _ in range(presses):
            self.key(step)
            self.hold(0.4)
        self.key("Return")
        self._menu_focus = name

    def go_back(self) -> None:
        """Press Go Back on the main screen's action bar, from the tree.

        The main screen has its own action-bar menu, whose focus starts on
        go-back (main_screen.py sets default_focus_idx=2, deliberately, so that
        Escape then Enter can never hit the quit button). No beat moves that
        focus, so unlike the reader's menu this needs no tracking - but the same
        stickiness would apply if one ever did.
        """
        self.key("Escape")  # main screen menu mode, focused on go-back
        self.hold(0.6)
        self.key("Return")

    def go_back_then_wait(self, pattern: str, timeout: float = 15) -> None:
        """Press Go Back, then block until a NEW occurrence of `pattern` is logged.

        The counting form, for the same reason as `key_then_wait`: the screen a beat
        goes back to logged its mode on the way in, so a plain `wait_for` matches that
        older line and returns before anything has moved.

        Raises:
            BeatError: If no new match arrives within `timeout` seconds.

        """
        before = self.match_count(pattern)
        self.go_back()
        self._await_new(pattern, timeout, before)

    def close_reader(self) -> None:
        """Shut the comic reader through its menu, and wait for the main screen."""
        count = len(self._MENU_BUTTONS)
        here = self._MENU_BUTTONS.index(self._menu_focus)
        there = self._MENU_BUTTONS.index("close")
        forward, backward = (there - here) % count, (here - there) % count

        self.key("Escape")
        self.hold(0.4)
        step, presses = ("Right", forward) if forward <= backward else ("Left", backward)
        for _ in range(presses):
            self.key(step)
            self.hold(0.4)
        self.key_then_wait("Main screen is active", 15, "Return")
        self._menu_focus = "close"

    def goto_page(self, target: int) -> None:
        """Jump to a body page through the reader's goto-page dropdown.

        The dropdown opens focused on the *current* page and lists the pages in
        index order, so the number of steps is just the difference between the
        two page numbers - the non-body entries in front of page 1 do not come
        into it.

        Args:
            target: The body page to land on.

        """
        current = self.current_page()
        self.press_menu_button("goto_page")  # opens the page list
        self.settle()
        self.hold(GOTO_LIST_DWELL)
        step = "Down" if target > current else "Up"
        for _ in range(abs(target - current)):
            self.key(step)
            self.hold(GOTO_STEP_PAUSE)
        self.hold(0.6)
        self.key_then_wait(f"Showed page {target}", 15, "Return")

    def open_story(self, pick: Pick) -> None:
        """Open the selected title, read `pick.pages` pages, and return to the tree.

        The comic opens on the page cued in the user's config: a saved last-read
        page inside the body puts a ticked "Goto page N" on the title view and the
        read portal honours it. That checkbox appears only once the title view has
        finished rendering, so settle first - pressing Enter early on a heavy title
        view opens the story at the cover instead, silently.
        """
        self.settle()
        self.key("Return")  # focus the title view read portal
        self.hold(0.6)
        self.key_then_wait("All images loaded", 30, "Return")
        self.read_pages(pick)
        self.close_reader()
        self.hold(0.5)
        # Closing the reader leaves focus in the bottom region, where Down does
        # nothing to the tree. Escape hands it back (main_screen_nav:243).
        self.key("Escape")
        self.settle()


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
    for _ in range(BROWSE_TITLE_STEPS):
        d.key("Down")
        d.hold(0.7 * pace)
    d.settle()


def _setup_browse_tree(d: Driver) -> None:
    _collapse_tree(d)


@beat(
    "browse_tree",
    node=["The Stories", "root"],
    label="Every Barks Disney story, in order",
    setup=_setup_browse_tree,
)
def browse_tree(d: Driver) -> None:
    # Open the tree a level at a time, then arrow down the chronological list and
    # settle on a title, letting the bottom panel render its title view. Keyboard
    # only: this doubles as the 10-foot/remote story, and it keeps the pointer
    # out of the frame.
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
    # drawn panel browse_tree ended on rather than mid-fade.
    d.hold(TITLE_FADE_SECS)


@beat(
    "open_comic",
    node=["The Stories", "root"],
    label="Open any story and read it",
    setup=_setup_open_comic,
)
def open_comic(d: Driver) -> None:
    d.hold(0.0)
    d.key("Return")  # focus the title view's read portal
    d.hold(0.0)
    d.key("Return")  # open the comic
    d.wait_for("All images loaded", 30)
    # Right is next-page in the reader (reader_keyboard_nav._handle_reading_key).
    d.read_pages(OPEN_COMIC_PICK)
    d.hold(2.5)


@beat(
    "series_view",
    node=["Series", "The Stories", "root"],
    label="Or by the series they ran in",
)
def series_view(d: Driver) -> None:
    # Booting here has already expanded Series, so the three series are on screen
    # and this only has to walk into them.
    d.hold(1.2)
    d.select_node("Comics and Stories")
    d.hold(0.9)
    d.select_node("Donald Duck Adventures")
    d.hold(0.9)
    d.select_node("Uncle Scrooge Adventures")
    d.hold(1.0)
    d.key("Return")  # expand it to show the volumes
    d.settle()
    d.hold(2.0)


@beat(
    "search_story",
    node=["Titles", "Search", "root"],
    label="Find a story by name",
)
def search_story(d: Driver) -> None:
    # A whole round trip: search, pick a result, read a page of it, and come
    # back to the search still holding the query.
    d.hold(1.0)
    d.key("Return")  # open the title search and focus its box
    d.settle()
    d.hold(0.6)
    d.type_slowly(SEARCH_TITLE_QUERY)
    d.settle()
    d.hold(1.2)

    row_y = SEARCH_RESULT_TOP_Y + (SEARCH_TITLE_RESULT - 1) * SEARCH_RESULT_ROW_H
    d.click_then_wait(f'Goto title: "{SEARCH_TITLE_PICK.title}"', 15, SEARCH_RESULT_X, row_y)
    # Let the title view finish fading before the Enter below. Only a *key*-driven
    # goto-title is handed to enter_nav_focus_at_portal; picking the result with the
    # mouse schedules no hand-off, so that Enter lazily enters nav focus instead
    # (main_screen_nav:241) and takes its default from _is_panel_content_visible() -
    # which reads the very opacity the fade is still animating. Pressed early, focus
    # lands on the eye toggle, the Enter toggles that, and no comic ever opens. At
    # hold(2.5) this beat was winning the race on luck and lost it as soon as a
    # different fade duration came up.
    d.hold(TITLE_FADE_SECS)

    # Focus defaults to the read portal now the panel is up, so one Enter opens the
    # comic - unlike the other beats, which have to focus the portal first.
    d.key_then_wait("All images loaded", 30, "Return")
    d.read_pages(SEARCH_TITLE_PICK)
    d.close_reader()
    d.hold(1.0)
    d.key("Escape")  # leave the bottom focus region for the tree
    d.settle()
    d.go_back()
    d.wait_for("SearchScreen mode set to 'Title'", 15)
    d.settle()
    d.hold(2.5)


@beat(
    "search_words",
    node=["Words", "Search", "root"],
    label="Search every word the characters speak",
)
def search_words(d: Driver) -> None:
    # A whole round trip, like search_story: find a spoken word, open one story's
    # matching speech bubbles, jump from a bubble into that story, and come back.
    d.hold(1.0)
    d.key("Return")
    d.settle()
    d.hold(0.5)
    d.type_slowly(SEARCH_WORD_QUERY)
    d.settle()
    d.hold(0.1)
    d.key("Down")  # focus the first matching word chip
    d.settle()
    d.hold(0.1)
    d.key_then_wait("Word search: selected chip", 15, "Return")
    d.hold(2.0)  # the list of every story the word is spoken in

    row_y = SEARCH_WORD_RESULT_TOP_Y + (SEARCH_WORD_RESULT - 1) * SEARCH_WORD_ROW_H
    d.click_then_wait(
        f'Show speech bubbles for: "{SEARCH_WORD_PICK}"', 15, SEARCH_WORD_BALLOON_X, row_y
    )
    d.hold(3.5)  # every line the word is spoken in, with the word picked out

    # A bubble goes to its story at the page that line is on.
    d.click_then_wait(
        f'Word search bubble press: "{SEARCH_WORD_PICK}"',
        15,
        SEARCH_WORD_BUBBLE_X,
        SEARCH_WORD_BUBBLE_Y,
    )
    d.settle()
    d.hold(3.0)  # the title view for the story the bubble came from

    # Straight on into the story. Only the index screens hand focus to the read portal
    # after a popup goto (main_screen._bind_screen_callbacks wires
    # on_after_popup_goto_title for those alone), so this Enter is what enters the title
    # panel's nav focus - and it lands on the portal, which is what ced49f7's sibling
    # 63b4a42 made true while the panel is still fading in.
    d.key_then_wait("All images loaded", 30, "Return")
    d.read_pages(SEARCH_WORD_READ)
    d.close_reader()
    d.hold(1.0)

    # Closing the reader leaves focus in the bottom region, so hand it back before the
    # action bar's Go Back can be reached - the same two-step search_story needs.
    d.key("Escape")
    d.settle()
    d.go_back_then_wait("SearchScreen mode set to 'Word'", 15)
    d.settle()
    d.hold(2.5)  # back on the search, query and results still there


def _setup_read_story(d: Driver) -> None:
    # Off camera: reach the story this beat reads, so the recording opens on it.
    d.open_branch("Categories")
    d.open_branch("Themes")
    d.open_branch("censored but fixed stories")
    d.select_node(READ_STORY_PICK.title)


@beat(
    "read_story",
    node=["The Stories", "root"],
    label="Skip to any page, or read two-up as printed",
    setup=_setup_read_story,
)
def read_story(d: Driver) -> None:
    d.hold(1.0)
    d.settle()
    d.key("Return")  # focus the title view read portal
    d.hold(0.6)
    d.key_then_wait("All images loaded", 30, "Return")
    d.read_pages(READ_STORY_PICK)
    # Skip to a page rather than turning to it, showing the page list on the way.
    d.goto_page(READ_STORY_GOTO_PAGE)
    d.hold(1.0)
    # Fullscreen is deliberately never pressed: with no window manager on the
    # nested display it resizes the window, and the recorder grabs a fixed region.
    d.press_menu_button("double_page")
    d.settle()
    d.hold(3.5)


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
    d.key_then_wait("Wiki reader screen is active", 30, "Return")
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
    d.key_then_wait(f'New selected node: "{WIKI_SIDEBAR_PICK}"', 20, "Return")
    d.settle()
    d.hold(2.5)  # the reader, now on the story the wiki sent it to


@beat(
    "speech_index",
    node=["Speech Bubble Index", "Indexes", "root"],
    label="A full speech-bubble index, A to Z",
)
def speech_index(d: Driver) -> None:
    d.hold(1.2)
    d.key("Return")  # open the index screen
    d.settle()
    d.hold(2.5)
    # Walk the A-Z letters; each one repopulates the word grid.
    for _ in range(3):
        d.key_then_wait("Populated index page for letter", 15, "Down")
        d.hold(1.6)
    d.hold(1.0)


@beat(
    "censored_stories",
    node=["The Stories", "root"],
    label="By category - censored stories, restored",
)
def censored_stories(d: Driver) -> None:
    # Drill down The Stories > Categories > Themes > censored but fixed stories,
    # then open each configured pick. The drill-down stays on camera: the
    # thematic indexes are the point of the beat, not just the stories.
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
    "history",
    node=["History", "Reading", "root"],
    label="Pick up where you left off",
)
def history(d: Driver) -> None:
    d.hold(1.2)
    d.key("Return")  # open the reading journal
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


class Recorder:
    """Runs the app, records beats, and puts the user's config back afterwards."""

    WINDOW_NAME = "Compleat Barks Disney Reader"

    def __init__(self, out_dir: Path, work_dir: Path = WORK_DIR) -> None:
        self.out_dir = out_dir
        self.work_dir = work_dir
        self._ffmpeg: subprocess.Popen[bytes] | None = None
        self._config = Path(self._probe("config").strip())
        if not self._config.is_file():
            msg = f"app config not found: {self._config}"
            raise BeatError(msg)
        handle, backup = tempfile.mkstemp(prefix="barks-demo-config.", suffix=".json")
        os.close(handle)
        self._backup = Path(backup)
        shutil.copy2(self._config, self._backup)

    @staticmethod
    def _probe(*args: str) -> str:
        result = subprocess.run(  # noqa: S603  (fixed argv, no shell)
            [str(PROBE), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout

    def close(self) -> None:
        """Stop everything and restore the user's config.

        Safe to call twice, and must not raise: it is the only thing standing
        between a failed run and a config left pointing at a beat's start node.
        """
        if self._ffmpeg is not None:
            self._stop_ffmpeg()
        self._probe("stop")
        # gui-probe restores its own backup, which is the file we edited; put the
        # user's original back on top of it.
        if self._backup.is_file():
            shutil.copy2(self._backup, self._config)
            self._backup.unlink(missing_ok=True)

    def _stop_ffmpeg(self) -> None:
        # SIGINT makes ffmpeg stop cleanly and write the trailer; killing it
        # outright leaves an unplayable file.
        process, self._ffmpeg = self._ffmpeg, None
        if process is None:
            return
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()

    def boot_at(self, node: Sequence[str]) -> None:
        """Start the app with its tree selection set to `node`.

        Each beat opens on a known screen instead of inheriting wherever the
        previous beat left the selection.
        """
        config = json.loads(self._config.read_text())
        config.setdefault("AAA_Settings", {})["last_selected_node"] = list(node)
        self._config.write_text(json.dumps(config, indent=2))
        if RANDOM_SEED is None:
            os.environ.pop(RANDOM_SEED_ENV_VAR, None)
        else:
            os.environ[RANDOM_SEED_ENV_VAR] = str(RANDOM_SEED)
        self._probe("start")

    def app_region(self) -> tuple[int, int, int, int]:
        """Return the app window's x11grab region on the nested display.

        There is no window manager there, so this is the app's own geometry with
        no decorations - cropping to it drops the Xephyr letterboxing.
        """
        output = subprocess.run(
            ["/usr/bin/xwininfo", "-root", "-children"],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "DISPLAY": DISPLAY},
        ).stdout
        return parse_geometry(output, self.WINDOW_NAME)

    def record(self, item: Beat) -> Path:
        """Record one beat to its cached clip and return the path."""
        clip = self.work_dir / f"{item.name}.mp4"
        say(f"record-demo: [{item.name}] booting")
        self.boot_at(item.node)
        driver = Driver()
        if item.setup is not None:
            say(f"record-demo: [{item.name}] setup")
            item.setup(driver)

        width, height, pos_x, pos_y = self.app_region()
        say(f"record-demo: [{item.name}] recording {width}x{height} at +{pos_x}+{pos_y}")
        with _caption_file(item.label) as caption:
            self._ffmpeg = self._start_ffmpeg(clip, width, height, pos_x, pos_y, caption)
            time.sleep(0.5)  # let the first frames land before anything moves
            try:
                item.body(driver)
            finally:
                self._stop_ffmpeg()
        self._probe("stop")
        say(f"record-demo: [{item.name}] {_human_size(clip)}")
        return clip

    def _start_ffmpeg(
        self,
        clip: Path,
        width: int,
        height: int,
        pos_x: int,
        pos_y: int,
        caption: Path | None,
    ) -> subprocess.Popen[bytes]:
        # The caption is burned in at record time, not at stitch time, because the
        # stitch is a stream copy - there is no re-encode later to draw it into.
        video_filter: list[str] = []
        if caption is not None:
            video_filter = [
                "-vf",
                (
                    f"drawtext=fontfile={FONT}:textfile={caption}:"
                    f"fontcolor={CAPTION_COLOR}:fontsize={CAPTION_SIZE}:"
                    f"box=1:boxcolor=black@{CAPTION_BOX_ALPHA}:"
                    f"boxborderw={CAPTION_BOX_PAD}:"
                    f"shadowcolor=black@0.9:shadowx={CAPTION_SHADOW}:"
                    f"shadowy={CAPTION_SHADOW}:x=(w-text_w)/2:y=h-th-{CAPTION_BOTTOM}"
                ),
            ]
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
                f"{width}x{height}",
                "-i",
                f"{DISPLAY}+{pos_x},{pos_y}",
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
    playing before the whole file has arrived.

    Raises:
        BeatError: If any of the named beats has no cached clip.

    """
    absent = missing_clips(beats, work_dir)
    if absent:
        msg = (
            f"{name}: no clip for {' '.join(absent)} - record them first, or drop them from OUTPUTS"
        )
        raise BeatError(msg)

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
    manifest = write_chapters(final, beats, work_dir)
    say(
        f"record-demo: {final}  ({_human_size(final)}, {duration_of(final):.0f}s,"
        f" {len(beats)} chapters -> {manifest.name})"
    )
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

    _run_ffmpeg([*seek, "-update", "1", "-frames:v", "1", "-q:v", "4", str(poster)])
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
    parser.add_argument("--clean", action="store_true", help="drop cached clips first")
    return parser.parse_args(argv)


def validate(args: argparse.Namespace) -> None:
    """Check that the command line names things that exist.

    Raises:
        BeatError: If an output, a beat, or the probe script is missing.

    """
    if args.output and args.output not in OUTPUTS:
        msg = f"no such output: {args.output} (have: {' '.join(OUTPUTS)})"
        raise BeatError(msg)
    for name in (args.only, args.start_from):
        if name:
            find_beat(name)
    if not PROBE.is_file():
        msg = f"missing {PROBE}"
        raise BeatError(msg)


def record_all(names: Sequence[str], out_dir: Path) -> None:
    """Record each named beat, always restoring the user's config afterwards."""
    if not names:
        return
    recorder = Recorder(out_dir)
    try:
        for name in names:
            recorder.record(find_beat(name))
    finally:
        recorder.close()


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
