"""Drive the Barks Reader on the nested Xephyr display, with the app's log as oracle.

Shared by the demo recorder (``record_demo.py``), the repro scripts, and the GUI
test suite (``src/barks-reader/tests/gui/``). Everything here waits on lines the
app writes to its own log rather than on the clock or the pixels: a wait either
sees the line it asked for or raises, so a caller never carries on against the
wrong screen and a test either passes on evidence or fails with a reason.

Assumes ``scripts/gui-probe.sh`` (Xephyr, xte) and nothing else already on the
nested display. Only the standard library is used, so this runs without the
workspace venv, the same as the probe script it drives.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
PROBE = REPO_ROOT / "scripts" / "gui-probe.sh"
DISPLAY = os.environ.get("BARKS_PROBE_DISPLAY", ":2")
# The app reads this on startup and seeds its random module from it; gui-probe
# launches the app as a child, so setting it here is enough to reach it.
RANDOM_SEED_ENV_VAR = "BARKS_READER_RANDOM_SEED"

# ------------------------------------------------------------------ pacing --

# Gaps between injected events. They read well on camera, but they are not only
# camera pacing: at full speed the app drops keys pressed while it is rendering,
# so a driver that sends faster than this lands somewhere else.
WALK_PAUSE = 0.45  # a single Down while walking the tree
TYPE_PAUSE = 0.4  # a single character into a search box
GOTO_LIST_DWELL = 1.5  # time the open page list stays up before stepping
GOTO_STEP_PAUSE = 0.12  # a single step through the page list


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
    result = subprocess.run(  # noqa: S603  (fixed argv, no shell)
        [str(script), *args],
        capture_output=True,
        text=True,
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

    def __init__(self, probe_script: Path = PROBE) -> None:
        self._probe = probe_script
        self._log = Path(self._run(["log"]).strip())
        # Menu focus is sticky, so the driver has to remember where it left it.
        self._menu_focus = self._MENU_BUTTONS[0]

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
            DriverError: If the selection stops moving, or `want` is never reached.

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
                raise DriverError(msg)
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

    def key_then_wait(self, pattern: str, timeout: float, *keys: str) -> None:
        """Press keys, then block until a NEW occurrence of `pattern` is logged.

        Raises:
            DriverError: If no new match arrives within `timeout` seconds.

        """
        with self.expect(pattern, timeout):
            self.key(*keys)

    def click_then_wait(self, pattern: str, timeout: float, x: int, y: int) -> None:
        """Click, then block until a NEW occurrence of `pattern` is logged.

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
        if name not in self._MENU_BUTTONS:
            msg = f"no such menu button: {name} (have: {', '.join(self._MENU_BUTTONS)})"
            raise DriverError(msg)

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
        self._menu_focus = name

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
            DriverError: If no new match arrives within `timeout` seconds.

        """
        with self.expect(pattern, timeout):
            self.go_back()

    def close_reader(self) -> None:
        """Shut the comic reader through its menu, and wait for the main screen."""
        self._walk_menu_to("close")
        self.key_then_wait("Main screen is active", 15, "Return")

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
        # Anchored on the log line's next word: a bare "Showed page 3" is a prefix
        # of "Showed page 34", so a dropped key landing anywhere in the thirties
        # would have passed for page 3.
        self.key_then_wait(f"Showed page {target} in ", 15, "Return")

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


def boot_app_at(
    node: Sequence[str],
    *,
    config: Path,
    seed: int | None = None,
    template: Path | None = None,
    cues: Mapping[str, dict[str, int | str] | None] | None = None,
) -> None:
    """Point the app's config at `node`, pin the cues and the seed, and start it.

    Args:
        node: The tree node to boot onto, leaf-to-root.
        config: The app's ``barks-reader.json``, which is rewritten.
        seed: Value for the app's random seed, or None to leave it unpinned.
        template: Read the settings from here instead of from `config`, for a
            caller that keeps a pristine copy and rebuilds `config` each boot.
        cues: Last-read-page cues to merge in, keyed by display title; a None
            value removes that story's cue. Pin these for any story the caller
            opens by name, or where it opens depends on the machine's config.

    Raises:
        DriverError: If the probe could not start the app.

    """
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
