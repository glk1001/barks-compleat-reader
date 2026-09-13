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
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
PROBE = REPO_ROOT / "scripts" / "gui-probe.sh"
DISPLAY = os.environ.get("BARKS_PROBE_DISPLAY", ":2")

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

WALK_PAUSE = 0.45  # pace of a single Down while walking the tree on camera
TYPE_PAUSE = 0.4  # pace of a single character into a search box

# Poster frame comes from the end of this beat rather than the end of a video:
# the browse view carries the app's chrome, tree and title card, which says
# "this is a reader app" better than a bare comic page does.
POSTER_BEAT = "browse_tree"

# What the two search beats type. Keep them short - every character is typed with
# a visible pause, so a long query makes for a slow beat.
SEARCH_TITLE_QUERY = "gold"
SEARCH_WORD_QUERY = "egg"


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
    Pick("BILL_COLLECTORS_THE"),
    Pick("LOST_IN_THE_ANDES"),
)

# The story read_story opens. Must be in the censored-but-fixed node, because
# that is the branch its setup walks.
READ_STORY_PICK = Pick("LOST_IN_THE_ANDES", pages=2, dwell=2.5)

# open_comic reaches its story by walking, not by name, so this sets only its
# pacing: five pages means the one it opens on plus four turns.
OPEN_COMIC_PICK = Pick(pages=5, dwell=2.2)

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

    def __init__(self, probe: Path = PROBE) -> None:
        self._probe = probe
        self._log = Path(self._run(["log"]).strip())

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
        self.key("Escape")  # reader menu mode; Go Back is focused by default
        self.hold(0.4)
        self.key_then_wait("Main screen is active", 15, "Return")
        self.hold(0.5)
        # Closing the reader leaves focus in the bottom region, where Down does
        # nothing to the tree. Escape hands it back (main_screen_nav:243).
        self.key("Escape")
        self.settle()


# ---------------------------------------------------------------- the beats --


@beat(
    "browse_tree",
    node=["1947-1950", "Chronological", "The Stories", "root"],
    label="Every Barks Disney story, in order",
)
def browse_tree(d: Driver) -> None:
    # Arrow down the chronological list and settle on a title, letting the bottom
    # panel render its title view. Keyboard only: this doubles as the
    # 10-foot/remote story, and it keeps the pointer out of the frame.
    d.hold(1.2)
    for _ in range(7):
        d.key("Down")
        d.hold(0.75)
    d.settle()
    d.hold(2.2)


def _setup_open_comic(d: Driver) -> None:
    # Land on the title browse_tree settles on, off camera, so this beat opens
    # already on the title view and reads as a continuation of the cut before it.
    # It could boot straight onto the title node instead - leaf titles are stored
    # under their enum name, as wiki_jump does - but repeating the previous
    # beat's Downs is what makes the two cuts line up, so the counts must match.
    d.key(*["Down"] * 7)
    d.settle()


@beat(
    "open_comic",
    node=["1947-1950", "Chronological", "The Stories", "root"],
    label="Open any story and read it",
    setup=_setup_open_comic,
)
def open_comic(d: Driver) -> None:
    d.hold(0.8)
    d.key("Return")  # focus the title view's read portal
    d.hold(0.7)
    d.key("Return")  # open the comic
    d.wait_for("All images loaded", 30)
    # Right is next-page in the reader (reader_keyboard_nav._handle_reading_key).
    d.read_pages(OPEN_COMIC_PICK)
    d.hold(0.8)


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
    d.hold(1.0)
    d.key("Return")  # open the title search and focus its box
    d.settle()
    d.hold(0.6)
    d.type_slowly(SEARCH_TITLE_QUERY)
    d.settle()
    d.hold(1.2)
    d.key("Down")  # move focus from the box into the result list
    d.settle()
    d.hold(0.8)
    d.key("Return")  # jump the tree to that story
    d.settle()
    d.hold(2.5)


@beat(
    "search_words",
    node=["Words", "Search", "root"],
    label="Search every word the characters speak",
)
def search_words(d: Driver) -> None:
    d.hold(1.0)
    d.key("Return")
    d.settle()
    d.hold(0.6)
    d.type_slowly(SEARCH_WORD_QUERY)
    d.settle()
    d.hold(1.5)
    d.key("Down")  # focus the first matching word chip
    d.settle()
    d.hold(0.6)
    d.key_then_wait("Word search: selected chip", 15, "Return")
    d.hold(3.5)  # the list of every story the word is spoken in


def _setup_read_story(d: Driver) -> None:
    # Off camera: reach the story this beat reads, so the recording opens on it.
    d.open_branch("Categories")
    d.open_branch("Themes")
    d.open_branch("censored but fixed stories")
    d.select_node(READ_STORY_PICK.title)


@beat(
    "read_story",
    node=["The Stories", "root"],
    label="Two-page spreads, the way it was printed",
    setup=_setup_read_story,
)
def read_story(d: Driver) -> None:
    d.hold(1.0)
    d.settle()
    d.key("Return")  # focus the title view read portal
    d.hold(0.6)
    d.key_then_wait("All images loaded", 30, "Return")
    d.read_pages(READ_STORY_PICK)
    # Reader action bar order is fullscreen, double page, start, end, goto, close,
    # and menu mode opens focused on close - so two Rights wrap round to the
    # double-page button. Fullscreen is deliberately not shown: with no window
    # manager on the nested display it resizes the window, and the recorder is
    # grabbing a fixed region.
    d.key("Escape")
    d.hold(0.5)
    d.key("Right")
    d.hold(0.4)
    d.key("Right")
    d.hold(0.4)
    d.key("Return")
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
    # Right enters the title view at its first nav widget; the wiki button is
    # always the second when a story has a wiki page, so one Down reaches it
    # whatever else the title view is showing. (Enter enters at the last widget,
    # the read portal, instead.)
    d.key("Right")
    d.settle()
    d.hold(0.5)
    d.key("Down")
    d.settle()
    d.hold(0.8)
    d.key_then_wait("Wiki reader screen is active", 30, "Return")
    d.hold(2.5)
    for _ in range(3):
        d.key("Down")  # scroll the page
        d.hold(0.9)
    d.hold(1.0)


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
    label="Browse by theme - censored stories, restored",
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
                    f"drawtext=fontfile={FONT}:textfile={caption}:fontcolor=white:"
                    f"fontsize={CAPTION_SIZE}:box=1:boxcolor=black@0.6:boxborderw=16:"
                    f"x=(w-text_w)/2:y=h-th-36"
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
    say(f"record-demo: {final}  ({_human_size(final)}, {duration_of(final):.0f}s)")
    return final


def write_poster(out_dir: Path, work_dir: Path) -> None:
    """Write the poster frame beside the videos, from POSTER_BEAT's resting frame."""
    source = work_dir / f"{POSTER_BEAT}.mp4"
    if not source.is_file():
        source = out_dir / "demo.mp4"
    if not source.is_file():
        return
    poster = out_dir / "demo-poster.jpg"
    _run_ffmpeg(["-sseof", "-0.5", "-i", str(source), "-update", "1", "-q:v", "4", str(poster)])
    say(f"record-demo: {poster} ({_human_size(poster)})")


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
        stitch(output, beats, out_dir, WORK_DIR)
    write_poster(out_dir, WORK_DIR)


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
