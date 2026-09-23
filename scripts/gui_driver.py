"""Drive the Barks Reader on the nested Xephyr display, with the app's log as oracle.

Shared by the demo recorder (``record_demo.py``), the repro scripts, and the GUI
test suite (``src/barks-reader/tests/gui/``). Everything here waits on lines the
app writes to its own log rather than on the clock or the pixels: a wait either
sees the line it asked for or raises, so a caller never carries on against the
wrong screen and a test either passes on evidence or fails with a reason.

On Linux it drives ``scripts/gui-probe.sh`` (Xephyr, xte) and assumes nothing
else is on the nested display; on Windows, ``scripts/gui_probe.py`` (SendInput on
the real desktop), which has the same commands and output. Only the standard
library is used, so this runs without the workspace venv.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
# The Linux probe runs the app on a nested X server; elsewhere the Python probe
# drives it on the real desktop. Both take the same commands and print the same.
PROBE = REPO_ROOT / "scripts" / ("gui_probe.py" if sys.platform == "win32" else "gui-probe.sh")
DISPLAY = os.environ.get("BARKS_PROBE_DISPLAY", ":2")
# The app reads this on startup and seeds its random module from it; gui-probe
# launches the app as a child, so setting it here is enough to reach it.
RANDOM_SEED_ENV_VAR = "BARKS_READER_RANDOM_SEED"
# Where the app keeps its config (.ini, barks-reader.json, reading history, Kivy
# home). Exported before a boot it wins over .env.runtime, for the app and for
# gui-probe.sh alike, which is how a run is pointed at a scratch profile.
CONFIG_DIR_ENV_VAR = "BARKS_READER_CONFIG_DIR"

# ------------------------------------------------------------------ pacing --

# Gaps between injected events. The typing gap is not only camera pacing: at
# full speed the app's search-as-you-type handler drops characters, so a driver
# that types faster than this lands a different query. Every other gap is camera
# pacing alone: each of those moves is waited on through the app's log (every
# selection and focus move logs itself) and the gap is added afterwards, only
# when the driver was built `paced` (the demo recorder).
WALK_PAUSE = 0.45  # a single Down while walking the tree
TYPE_PAUSE = 0.4  # a single character into a search box
GOTO_LIST_DWELL = 1.5  # time the open page list stays up before stepping
GOTO_STEP_PAUSE = 0.12  # a single step through the page list
GOTO_PICK_PAUSE = 0.6  # on the chosen page entry, before picking it
MENU_OPEN_PAUSE = 0.6  # after Escape opens an action-bar menu, before moving in it
MENU_STEP_PAUSE = 0.4  # a single Left/Right along an action bar
BRANCH_OPEN_PAUSE = 0.4  # after a tree node expands, before moving on
READER_CLOSED_PAUSE = 0.5  # after the reader closes, before leaving the bottom region
# How long the app log must stay unchanged for settle() to call the app idle.
SETTLE_QUIET_MS = 1000


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


class DriverError(RuntimeError):
    """The app did not reach a state the caller needed, so it must not carry on."""


def probe(*args: str, script: Path = PROBE) -> str:
    """Run one ``gui-probe.sh`` command and return its stdout.

    The one place the probe is called from, so a failure is never dropped: a
    ``start`` that died (a stale Xephyr still up, the app never becoming ready)
    used to return normally, and the beat was then driven against a half-booted
    or leftover app and a wrong clip cached with no error.

    Args:
        *args: The probe subcommand and its arguments.
        script: The probe script to run.

    Returns:
        The command's stdout.

    Raises:
        DriverError: If the probe exits non-zero, with what it wrote to stderr.

    """
    # A Python probe runs under this interpreter: Windows has no shebangs, and
    # its screenshots need the workspace's Pillow.
    launcher = [sys.executable] if script.suffix == ".py" else []
    result = subprocess.run(  # noqa: S603  (fixed argv, no shell)
        [*launcher, str(script), *args],
        capture_output=True,
        # Both probes print UTF-8 (the app log is UTF-8); Windows' default would
        # be its code page, which mangles or rejects the log's box drawing.
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        msg = f"gui-probe {' '.join(args)} failed (exit {result.returncode}): {detail}"
        raise DriverError(msg)
    return result.stdout


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
    # The main screen's action bar, in the order main_screen.py passes to
    # _setup_action_bar_nav. Its menu opens on go_back (default_focus_idx=2,
    # deliberately, so that Escape then Enter can never hit the quit button).
    _MAIN_MENU_BUTTONS = (
        "icon",
        "fullscreen",
        "go_back",
        "collapse",
        "change_pics",
        "menu",
        "quit",
    )
    _MAIN_MENU_DEFAULT = "go_back"

    # Menu focus is sticky on both bars, so the driver remembers where it left
    # each. Class-level defaults so a stub driver (no __init__) still has them.
    _menu_focus: str = _MENU_BUTTONS[0]
    _main_menu_focus: str = _MAIN_MENU_DEFAULT
    _paced: bool = True

    # Log lines the app writes for keyboard focus moves and dropdowns, which every
    # menu walk and dropdown step here waits on (reader_keyboard_nav, okf trace).
    FOCUS_MOVED = "Nav focus on"
    NODE_SELECTED = "New selected node"
    NODE_EXPANDED = "Node expanded: '{name}'"
    SHOWED_PAGE = "Showed page"
    ALL_IMAGES_LOADED = "All images loaded"
    MAIN_SCREEN_ACTIVE = "Main screen is active"
    EXITED_BOTTOM_FOCUS = "Exited bottom focus region."
    GOTO_PAGE_DROPDOWN_OPENED = "Goto page dropdown opened."
    # A ring on a bar button or result row, or the tree's selection band moving.
    WIKI_FOCUS_MOVED = r"OKFViewer: (Focus ring on|Sidebar focus on)"
    DROPDOWN_DISMISSED = "Dropdown dismissed."
    MENU_ENTERED = "Entered menu mode."

    def __init__(
        self,
        probe_script: Path = PROBE,
        *,
        settle_quiet_ms: int = SETTLE_QUIET_MS,
        paced: bool = True,
    ) -> None:
        """Attach to the running app through the probe.

        Args:
            probe_script: The gui-probe script to drive the app through.
            settle_quiet_ms: How long the log must stay quiet for `settle`.
            paced: Keep the camera gaps after each log-driven move (the demo
                recorder). The GUI tests pass False and run on the log alone.

        """
        self._probe = probe_script
        self._settle_quiet_ms = settle_quiet_ms
        self._paced = paced
        self._log = Path(self._run(["log"]).strip())
        self._menu_focus = self._MENU_BUTTONS[0]
        self._main_menu_focus = self._MAIN_MENU_DEFAULT

    def _run(self, args: Sequence[str]) -> str:
        return probe(*args, script=self._probe)

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

    def shot(self, path: Path) -> Path:
        """Capture the nested display to a PNG at `path` and return it."""
        self._run(["shot", str(path)])
        return path

    # A position can be negative: a window on a monitor left of or above the primary.
    _GEOMETRY_RE = re.compile(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)")

    def window_geometry(self) -> tuple[int, int, int, int]:
        """Return the app window's ``(width, height, x, y)`` on the nested display.

        Raises:
            DriverError: If the probe cannot find the window, or prints something
                that is not a geometry.

        """
        text = self._run(["geometry"]).strip()
        found = self._GEOMETRY_RE.fullmatch(text)
        if not found:
            msg = f"gui-probe geometry printed {text!r}, not WxH+X+Y"
            raise DriverError(msg)
        width, height, pos_x, pos_y = (int(g) for g in found.groups())
        return width, height, pos_x, pos_y

    def settle(self) -> None:
        """Block until the app has stopped writing to its log, i.e. stopped drawing."""
        self._run(["settle", str(self._settle_quiet_ms)])

    @staticmethod
    def hold(seconds: float) -> None:
        """Dwell on the current frame.

        Pacing only - never use this to wait for the app to reach a state. Use
        `wait_for` or `key_then_wait`, which fail loudly instead of silently
        recording the wrong screen.
        """
        time.sleep(seconds)

    def _pace(self, seconds: float) -> None:
        """Dwell for the camera, when this driver is paced; nothing otherwise."""
        if self._paced:
            self.hold(seconds)

    def type_slowly(self, text: str, marker: Callable[[str], str | None] | None = None) -> None:
        """Type into a focused text box one character at a time.

        ``gui-probe type`` sends the whole string through ``xte str`` and the
        app's search-as-you-type handler drops most of it - a ten-character query
        arrived in the box as four characters. Per-character is reliable: each
        character either waits on the line the app logs for the text typed so far
        (`marker`, given what has been typed, returns the pattern or None for no
        line) or, with no marker, rests for the camera-paced typing gap.

        Args:
            text: What to type.
            marker: Maps the text typed so far to the log pattern that its
                keystroke produces, or None where it produces no line.

        """
        typed = ""
        for char in text:
            typed += char
            pattern = marker(typed) if marker is not None else None
            if pattern is None:
                self._run(["type", char])
                time.sleep(TYPE_PAUSE)
            else:
                with self.expect(pattern):
                    self._run(["type", char])

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

    def last_line(self, pattern: str) -> str:
        """Return the most recent log line matching `pattern`, or "" if none has."""
        lines = [
            ln
            for ln in self._log.read_text(errors="replace").splitlines()
            if re.search(pattern, ln)
        ]
        return lines[-1] if lines else ""

    def select_node(self, want: str, max_steps: int = 60, step_timeout: float = 8) -> None:
        """Walk the tree downward until `want` is the selected node.

        Name-driven rather than a counted run of Downs, so a title added upstream
        shifts the walk instead of silently landing the demo on the wrong story.
        It only ever goes down, so picks have to be in tree order. Each Down waits
        on the selection line the app logs for it, so the walk runs as fast as the
        app takes keys and never mistakes a slow render for the bottom of the tree.

        Args:
            want: The node name as the app logs it in "New selected node".
            max_steps: Downs to allow before giving up.
            step_timeout: Seconds to allow each Down to move the selection. A Down
                on the last node logs nothing, so this is how the bottom is found.

        Raises:
            DriverError: If the selection stops moving, or `want` is never reached.

        """
        current = self.current_node()
        for _ in range(max_steps):
            if current == want:
                return
            try:
                self.key_then_wait(self.NODE_SELECTED, "Down", timeout=step_timeout)
            except DriverError as exc:
                msg = (
                    f'tree stopped at "{current}" before reaching "{want}" - is it above '
                    f"the current position, or in another branch?"
                )
                raise DriverError(msg) from exc
            self._pace(WALK_PAUSE)
            current = self.current_node()
        msg = f'never reached node "{want}" in {max_steps} steps'
        raise DriverError(msg)

    @contextmanager
    def expect(self, pattern: str, timeout: float = 15) -> Iterator[None]:
        """Run the block, then block until a NEW occurrence of `pattern` is logged.

        The general form of `key_then_wait`: whatever the block does - a key, a
        click, a whole composite move - must produce a fresh match, or this
        raises. It counts occurrences before the block and waits for one more,
        because ``gui-probe wait`` greps the whole log: a marker that fires once
        per comic matches the previous comic and returns instantly, which would
        carry on (or cut away) before this one had drawn.

            with d.expect("All images loaded", 30):
                d.key("Return")

        Args:
            pattern: Regex to look for in the app log.
            timeout: Seconds to wait after the block for a new match.

        Raises:
            DriverError: If no new match arrives within `timeout` seconds.

        """
        before = self.match_count(pattern)
        yield
        self._await_new(pattern, timeout, before)

    def key_then_wait(self, pattern: str, *keys: str, timeout: float = 15) -> None:
        """Press keys, then block until a NEW occurrence of `pattern` is logged.

        Args:
            pattern: Regex to look for in the app log.
            *keys: X11 key names, pressed in order.
            timeout: Seconds to wait after the last key for a new match.

        Raises:
            DriverError: If no new match arrives within `timeout` seconds.

        """
        with self.expect(pattern, timeout):
            self.key(*keys)

    def click_then_wait(self, pattern: str, x: int, y: int, timeout: float = 15) -> None:
        """Click, then block until a NEW occurrence of `pattern` is logged.

        Args:
            pattern: Regex to look for in the app log.
            x: Screenshot pixel column to click.
            y: Screenshot pixel row to click.
            timeout: Seconds to wait after the click for a new match.

        Raises:
            DriverError: If no new match arrives within `timeout` seconds.

        """
        with self.expect(pattern, timeout):
            self.click(x, y)

    def _await_new(self, pattern: str, timeout: float, before: int) -> None:
        deadline = time.monotonic() + timeout
        while self.match_count(pattern) <= before:
            if time.monotonic() > deadline:
                msg = f"beat stalled: no new /{pattern}/ in the app log after {timeout}s"
                raise DriverError(msg)
            time.sleep(0.25)

    FADE_STARTED = "Title view fade started"
    FADE_FINISHED = "Title view fade finished"
    ENTERED_AT_PORTAL = "BottomTitleViewScreen: entered nav focus at portal."

    def wait_title_fade(self, timeout: float = 10) -> None:
        """Block until the most recently started title-view fade has finished.

        The panel fades in over a random 0-4s and the app logs both ends, so
        this waits on the log rather than the worst case. Only the latest fade
        counts: walking the tree starts a fade per title and each is superseded
        by the next, and a superseded fade never logs a finish. Returns at
        once when the latest fade is already over, and blocks while it runs -
        or until one has started at all, so a caller that has just triggered a
        fade may call this before its start line has landed.

        Raises:
            DriverError: If the latest fade has not finished within `timeout`.

        """
        deadline = time.monotonic() + timeout
        while not self._latest_fade_finished():
            if time.monotonic() > deadline:
                msg = f"beat stalled: the title view fade never finished within {timeout}s"
                raise DriverError(msg)
            time.sleep(0.25)

    def _latest_fade_finished(self) -> bool:
        text = self._log.read_text(errors="replace")
        return text.rfind(self.FADE_FINISHED) > text.rfind(self.FADE_STARTED)

    def expect_no_new(self, pattern: str, window: float = 2.0) -> None:
        """Assert that no NEW occurrence of `pattern` is logged for `window` seconds.

        The one sanctioned wait on the clock, for negatives only - "the quit
        fence must not quit", "Escape in the reader must not close it". Call it
        right after the action; it counts from now.

        Raises:
            DriverError: If a new match appears within the window.

        """
        before = self.match_count(pattern)
        deadline = time.monotonic() + window
        while time.monotonic() < deadline:
            if self.match_count(pattern) > before:
                msg = f"unexpected new /{pattern}/ in the app log within {window}s"
                raise DriverError(msg)
            time.sleep(0.25)

    def wait_for(self, pattern: str, timeout: float = 15) -> None:
        """Block until `pattern` appears anywhere in the app log.

        Raises:
            DriverError: If it never appears within `timeout` seconds.

        """
        deadline = time.monotonic() + timeout
        while self.match_count(pattern) == 0:
            if time.monotonic() > deadline:
                msg = f"beat stalled: never saw /{pattern}/ in the app log"
                raise DriverError(msg)
            time.sleep(0.25)

    def move_focus(self, *keys: str, pattern: str | None = None, timeout: float = 15) -> None:
        """Press each key in turn, waiting for the focus ring to land after every one.

        For moves within a screen - along an action bar, a tab row, a ring of
        widgets, a dropdown's items - which the app marks by drawing the focus
        ring on the new widget, and logs as it does. Waiting on that line is
        what lets keys go out as fast as the app takes them.

        Args:
            keys: X11 key names, pressed one at a time.
            pattern: The log line to wait for after each; the Barks Reader's
                focus line by default, `WIKI_FOCUS_MOVED` inside the wiki.
            timeout: Seconds to allow each move.

        """
        pattern = self.FOCUS_MOVED if pattern is None else pattern
        for key in keys:
            self.key_then_wait(pattern, key, timeout=timeout)

    # -- composite moves ----------------------------------------------------

    def open_branch(self, name: str) -> None:
        """Walk down to a collapsed node and expand it, and let its children lay out.

        The expansion is logged before the new children have been drawn, and a
        Down sent into that layout pass is swallowed, so this also waits for the
        log to go quiet (under four parallel workers the pass can take a while).
        """
        self.select_node(name)
        self.key_then_wait(self.NODE_EXPANDED.format(name=name), "Return")
        self.settle()
        self._pace(BRANCH_OPEN_PAUSE)

    def read_pages(self, pick: Pick) -> None:
        """Rest on the page the comic opened at, then turn through the rest.

        Waits on the bare "Showed page" marker rather than a page number: a story
        opens on whatever page the user cued, so the number is not known here,
        and `key_then_wait` only needs a new render rather than a specific one.
        """
        self.hold(pick.dwell)
        for _ in range(pick.pages - 1):
            self.key_then_wait(self.SHOWED_PAGE, "Right")
            self.hold(pick.dwell)

    def _walk_menu_to(self, name: str) -> None:
        """Open the reader's action-bar menu and move its focus to one button.

        Menu mode does not reopen on a fixed button: ``_enter_menu_mode`` restores
        ``_last_used_btn_idx``, so it comes back focused on whatever was activated
        last. A fixed run of arrow presses is therefore only right the first time
        - after a goto-page, the same two Rights that used to reach double-page
        reach fullscreen instead, which on a nested display with no window
        manager resizes the window out from under the recorder.

        Tracking the last activation here is what makes the second press land
        where it says. Nothing else drives the app, so this stays in step. The
        caller presses Return, so it can wait on whatever that button logs.

        Args:
            name: One of `_MENU_BUTTONS`.

        Raises:
            DriverError: If `name` is not a menu button.

        """
        self._walk_bar_to(self._MENU_BUTTONS, self._menu_focus, name)
        self._menu_focus = name

    def _walk_bar_to(self, buttons: Sequence[str], here_name: str, name: str) -> None:
        """Escape into an action-bar menu and walk its focus from one button to another.

        Takes the shorter way round: both bars wrap.

        Raises:
            DriverError: If `name` is not one of `buttons`.

        """
        if name not in buttons:
            msg = f"no such menu button: {name} (have: {', '.join(buttons)})"
            raise DriverError(msg)

        count = len(buttons)
        here = buttons.index(here_name)
        there = buttons.index(name)
        forward = (there - here) % count
        backward = (here - there) % count

        self.key_then_wait(self.MENU_ENTERED, "Escape")
        self._pace(MENU_OPEN_PAUSE)
        step, presses = ("Right", forward) if forward <= backward else ("Left", backward)
        for _ in range(presses):
            self.move_focus(step)
            self._pace(MENU_STEP_PAUSE)

    def main_menu_button(self, name: str) -> None:
        """Open the main screen's action-bar menu and activate one button by name.

        Sticky like the reader's menu: the bar reopens on whatever was activated
        last, and this tracks that. Nothing else drives the app, so it stays in
        step.

        Args:
            name: One of `_MAIN_MENU_BUTTONS`.

        Raises:
            DriverError: If `name` is not a main-screen button.

        """
        self._walk_bar_to(self._MAIN_MENU_BUTTONS, self._main_menu_focus, name)
        self._main_menu_focus = name
        self.key("Return")

    def main_menu_button_then_wait(self, name: str, pattern: str, timeout: float = 15) -> None:
        """Activate a main-screen button and wait for a NEW `pattern` from the press itself.

        For a button whose effect logs a line the walk to it also logs - the dots
        menu, whose opening lands the focus ring on its first entry just as each
        step of the walk landed it on a bar button. Counting from after the walk
        keeps the wait on the press.
        """
        self._walk_bar_to(self._MAIN_MENU_BUTTONS, self._main_menu_focus, name)
        self._main_menu_focus = name
        with self.expect(pattern, timeout):
            self.key("Return")

    def press_menu_button(self, name: str) -> None:
        """Open the reader's action-bar menu and activate one button by name.

        Args:
            name: One of `_MENU_BUTTONS`.

        Raises:
            DriverError: If `name` is not a menu button.

        """
        self._walk_menu_to(name)
        self.key("Return")

    def go_back(self) -> None:
        """Press Go Back on the main screen's action bar, from the tree."""
        self.main_menu_button("go_back")

    def go_back_then_wait(self, pattern: str, timeout: float = 15) -> None:
        """Press Go Back, then block until a NEW occurrence of `pattern` is logged.

        The counting form, for the same reason as `key_then_wait`: the screen a beat
        goes back to logged its mode on the way in, so a plain `wait_for` matches that
        older line and returns before anything has moved.

        Raises:
            DriverError: If no new match arrives within `timeout` seconds.

        """
        with self.expect(pattern, timeout):
            self.go_back()

    def close_reader(self) -> None:
        """Shut the comic reader through its menu, and wait for the main screen."""
        self._walk_menu_to("close")
        self.key_then_wait(self.MAIN_SCREEN_ACTIVE, "Return")

    def goto_page(self, target: int, shows: int | None = None) -> None:
        """Jump to a body page through the reader's goto-page dropdown.

        The dropdown opens focused on the *current* page and lists the pages in
        index order, so the number of steps is just the difference between the
        two page numbers - the non-body entries in front of page 1 do not come
        into it.

        Args:
            target: The body page to land on.
            shows: The page the reader then renders, when that is not `target`:
                two-up it renders the unit holding the target, named by its left
                page.

        """
        shows = target if shows is None else shows
        current = self.current_page()
        self._walk_menu_to("goto_page")
        # Opening the list puts the focus ring on the current page's entry.
        with self.expect(self.GOTO_PAGE_DROPDOWN_OPENED), self.expect(self.FOCUS_MOVED):
            self.key("Return")
        self._pace(GOTO_LIST_DWELL)
        step = "Down" if target > current else "Up"
        for _ in range(abs(target - current)):
            self.move_focus(step)
            self._pace(GOTO_STEP_PAUSE)
        self._pace(GOTO_PICK_PAUSE)
        # Anchored on the log line's next word: a bare "Showed page 3" is a prefix
        # of "Showed page 34", so a dropped key landing anywhere in the thirties
        # would have passed for page 3. The dropdown dismisses itself a frame or
        # more after the pick and owns the window's keys until it has, so the
        # next key is held back until it says so.
        with self.expect(f"{self.SHOWED_PAGE} {shows} in "), self.expect(self.DROPDOWN_DISMISSED):
            self.key("Return")

    def focus_portal(self) -> None:
        """Put nav focus on the selected title's read portal, once its view has faded in.

        Return enters the title view at the portal, but not while the panel is
        still fading in: then it re-enters the view instead, so this waits for
        the fade and then for the app to confirm where focus landed.
        """
        self.wait_title_fade()
        self.key_then_wait(self.ENTERED_AT_PORTAL, "Return")

    def open_selected_story(self) -> None:
        """Open the title selected in the tree and wait for its images to load.

        The comic opens on the page cued in the user's config: a saved last-read
        page inside the body puts a ticked "Goto page N" on the title view and the
        read portal honours it. That checkbox appears only once the title view has
        finished rendering, so `focus_portal` waits first - pressing Enter early
        on a heavy title view opens the story at the cover instead, silently.
        """
        self.focus_portal()
        self.key_then_wait(self.ALL_IMAGES_LOADED, "Return", timeout=30)

    def open_story(self, pick: Pick) -> None:
        """Open the selected title, read `pick.pages` pages, and return to the tree."""
        self.open_selected_story()
        self.read_pages(pick)
        self.close_reader()
        self._pace(READER_CLOSED_PAUSE)
        # Closing the reader leaves focus in the bottom region, where Down does
        # nothing to the tree. Escape hands it back (main_screen_nav:243).
        self.key_then_wait(self.EXITED_BOTTOM_FOCUS, "Escape")


def boot_app_at(
    node: Sequence[str],
    *,
    config: Path | None = None,
    config_dir: Path | None = None,
    seed: int | None = None,
    template: Path | None = None,
    cues: Mapping[str, dict[str, int | str] | None] | None = None,
) -> None:
    """Point the app's config at `node`, pin the cues and the seed, and start it.

    Args:
        node: The tree node to boot onto, leaf-to-root.
        config: The app's ``barks-reader.json``, which is rewritten. Defaults to
            the one inside `config_dir`; one of the two must be given.
        config_dir: A whole config directory to boot from (``barks-reader.ini``,
            ``barks-reader.json``, history, Kivy home). Exported as the app's
            config-dir env var so both the app and gui-probe.sh use it - the way
            a test run keeps its hands off the user's real profile.
        seed: Value for the app's random seed, or None to leave it unpinned.
        template: Read the settings from here instead of from `config`, for a
            caller that keeps a pristine copy and rebuilds `config` each boot.
        cues: Last-read-page cues to merge in, keyed by display title; a None
            value removes that story's cue. Pin these for any story the caller
            opens by name, or where it opens depends on the machine's config.

    Raises:
        DriverError: If the probe could not start the app.
        ValueError: If neither `config` nor `config_dir` is given.

    """
    if config_dir is not None:
        os.environ[CONFIG_DIR_ENV_VAR] = str(config_dir)
        config = config or config_dir / "barks-reader.json"
    if config is None:
        msg = "boot_app_at needs config= or config_dir="
        raise ValueError(msg)
    settings = json.loads((template or config).read_text())
    settings.setdefault("AAA_Settings", {})["last_selected_node"] = list(node)
    for title, cue in (cues or {}).items():
        if cue is None:
            settings.pop(title, None)
        else:
            settings[title] = {"last_read_page": dict(cue)}
    config.write_text(json.dumps(settings, indent=2))
    if seed is None:
        os.environ.pop(RANDOM_SEED_ENV_VAR, None)
    else:
        os.environ[RANDOM_SEED_ENV_VAR] = str(seed)
    probe("start")
