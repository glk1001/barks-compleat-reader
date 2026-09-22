"""The scratch profile a GUI test boots from, and the artifacts a failure leaves.

A test never runs against the user's real profile. Once per session the live
config directory is copied to a template with a few settings pinned (no
fullscreen on start, quit asks first, no alternate Escape, window sized from the
screen); every test gets a fresh copy of that template, its own canned
``barks-reader.json`` and reading history, and the app is booted with the
config-dir env var pointing at it. Whatever the app writes on exit lands there
and is thrown away with the test's tmp dir.
"""

# cspell:ignore lctrl rctrl capslock numlock
from __future__ import annotations

import configparser
import contextlib
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import gui_driver as gd
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[5]
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
# Under build/, which is gitignored and where record_demo keeps its beat clips.
ARTIFACTS_ROOT = REPO_ROOT / "build" / "gui-tests"

# Pins the app's random draws, so backgrounds and the title-view fade are the
# same every run. Any fixed number does.
SEED = 1

# Test-speed pacing. The probe's default key gap (0.4s) and settle window (1s)
# are camera pacing inherited from the demo recorder; the driver adds its own
# functional pauses on top, so these can come down. Set by a pacing study on
# 2026-09-16: 0.15s/500ms stayed green across consecutive full runs, headless
# (four workers) and visible; 0.05s/300ms flaked once (a word-search bubble's
# Return raced the title view) and was no faster, the wall time being bound by
# boot and teardown. Raise these if a test starts dropping keys.
# BARKS_GUI_KEY_GAP and BARKS_GUI_SETTLE_MS override them for a pacing run.
KEY_GAP_SECS = float(os.environ.get("BARKS_GUI_KEY_GAP", "0.15"))
SETTLE_QUIET_MS = int(os.environ.get("BARKS_GUI_SETTLE_MS", "500"))
PROBE_KEY_GAP_ENV_VAR = "BARKS_PROBE_KEY_GAP"
# Set by the runner so every parallel worker writes into one artifacts directory.
RUN_STAMP_ENV_VAR = "BARKS_GUI_RUN_STAMP"

INI_SECTION = "Barks Reader"
# What the scratch profile pins, whatever the live ini says. Everything else -
# the data directories above all - is copied from the live ini verbatim.
INI_OVERRIDES: dict[str, str] = {
    "confirm_quit": "1",  # so a quit test can cancel; the fence must never quit
    "goto_fullscreen_on_app_start": "0",
    "goto_fullscreen_on_comic_read": "0",
    "alt_escape_key": "0",  # 0 = unset; the default 114 is "r", which tests may type
    "goto_saved_node_on_start": "1",  # boot_app_at works by saving the node
    "is_first_use_of_reader": "0",
    "double_page_mode": "0",
    "record_reading_history": "1",  # hermetic, so a test can assert the append
    "main_window_height": "0",  # 0 = size from the (nested) screen
    "main_window_left": "-1",
    "main_window_top": "-1",
    "log_level": "DEBUG",  # the log is the oracle
}
# Settings for the whole run, on top of the live ini: "key=value;key=value", set
# by run_gui_tests.sh --ini/--prebuilt/--png-images. A key the harness pins
# above is refused, since the suite depends on those values.
INI_ENV_VAR = "BARKS_GUI_INI"
COPIED_FILES = ("barks-reader.ini", "log-config.yaml", "never-crop.txt")
COPIED_KIVY_DIR = "kivy"  # Kivy home: config.ini, icon/, mods/; logs/ is skipped

# Tells gui-probe.sh not to back up and restore the profile around a run: the
# scratch profile is disposable, and a test reads what the app wrote on exit.
PROBE_NO_RESTORE_ENV_VAR = "BARKS_PROBE_NO_RESTORE"


def ini_overrides_from_env(value: str) -> dict[str, str]:
    """Parse the run-wide settings in `value` ("key=value;key=value", blanks ignored).

    Args:
        value: The BARKS_GUI_INI environment variable's text.

    Returns:
        The settings, in order.

    Raises:
        ValueError: If an entry is not key=value, or names a setting the harness pins.

    """
    overrides: dict[str, str] = {}
    for entry in value.split(";"):
        entry = entry.strip()  # noqa: PLW2901
        if not entry:
            continue
        key, sep, val = entry.partition("=")
        key, val = key.strip(), val.strip()
        if not sep or not key:
            msg = f"{INI_ENV_VAR}: expected key=value, got {entry!r}"
            raise ValueError(msg)
        if key in INI_OVERRIDES:
            msg = f"{INI_ENV_VAR}: {key!r} is pinned by the GUI harness and cannot be overridden"
            raise ValueError(msg)
        overrides[key] = val
    return overrides


def build_template(live_dir: Path, template: Path) -> Path:
    """Copy the live config directory into `template` with INI_OVERRIDES applied.

    Settings in the BARKS_GUI_INI environment variable go on top, for a whole
    run on another comic or panel source than the live profile's.

    Args:
        live_dir: The user's config directory.
        template: An empty directory to fill.

    Returns:
        `template`.

    Raises:
        FileNotFoundError: If the live ini is missing.

    """
    for name in COPIED_FILES:
        source = live_dir / name
        if source.is_file():
            shutil.copy2(source, template / name)
    kivy_dir = live_dir / COPIED_KIVY_DIR
    if kivy_dir.is_dir():
        shutil.copytree(kivy_dir, template / COPIED_KIVY_DIR, ignore=shutil.ignore_patterns("logs"))

    ini = template / "barks-reader.ini"
    if not ini.is_file():
        msg = f"no barks-reader.ini in {live_dir}"
        raise FileNotFoundError(msg)
    apply_ini_overrides(ini, INI_OVERRIDES)
    run_overrides = ini_overrides_from_env(os.environ.get(INI_ENV_VAR, ""))
    if run_overrides:
        apply_ini_overrides(ini, run_overrides)
    return template


def apply_ini_overrides(ini: Path, overrides: Mapping[str, str]) -> None:
    """Set keys in the ini's Barks Reader section, keeping every other key and its case."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # ty: ignore[invalid-assignment]  (keep key case, as the app does)
    parser.read(ini)
    if not parser.has_section(INI_SECTION):
        parser.add_section(INI_SECTION)
    for key, value in overrides.items():
        parser.set(INI_SECTION, key, value)
    with ini.open("w") as out:
        parser.write(out)


def read_ini_value(ini: Path, key: str) -> str:
    """Return one Barks Reader setting from an ini, as the raw string."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # ty: ignore[invalid-assignment]
    parser.read(ini)
    return parser.get(INI_SECTION, key)


def artifacts_dir() -> Path:
    """Return this run's artifacts directory, created on first use."""
    if _RUN.dir is None:
        stamp = os.environ.get(RUN_STAMP_ENV_VAR) or datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005
        _RUN.dir = ARTIFACTS_ROOT / stamp
        _RUN.dir.mkdir(parents=True, exist_ok=True)
    return _RUN.dir


def display_for_worker(worker_id: str, base_display: str) -> str:
    """Return the X display a pytest worker owns: ``:N`` for the main process, ``:N+k`` for ``gwk``.

    Each parallel worker drives its own X server, and the probe keeps one run
    directory per display, so workers never share a log or an app.
    """
    base = int(base_display.lstrip(":") or "2")
    if worker_id.startswith("gw") and worker_id[2:].isdigit():
        return f":{base + int(worker_id[2:])}"
    return f":{base}"


def artifact_name(nodeid: str, suffix: str) -> str:
    """Turn a pytest node id into a file name safe for the artifacts directory."""
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", nodeid.split("::", 1)[-1])
    return f"{stem}{suffix}"


# The sizes the app itself saw, from every resize event it logs.
_RESIZE_RE = re.compile(
    pattern(markers.WINDOW_RESIZED, width=re.compile(r"(\d+)"), height=re.compile(r"(\d+)"))
)


_KEY_PRESSED_RE = re.compile(
    pattern(markers.KEY_PRESSED, key=re.compile(r"\d+"), name=re.compile(r"([^)]*)"))
)
# Keys xte's `str` presses on the way to a character (Shift for a capital), which
# the app logs and the probe's input log does not list one by one.
MODIFIER_KEY_NAMES = frozenset(
    {
        "shift",
        "rshift",
        "alt",
        "alt-gr",
        "lctrl",
        "rctrl",
        "super",
        "compose",
        "capslock",
        "numlock",
        "pipe",
    }
)
_INPUT_LINE_RE = re.compile(r"^\S+ (key|type|click) ?(.*)$")


def stray_key_presses(app_log: str, input_log: str) -> int:
    """Return how many key presses the app logged beyond what the probe injected.

    The app logs every key press it receives; the probe logs every key and every
    typed string it sends. A surplus is input from somewhere else - the host
    keyboard, while a visible test window has focus - which no test can survive
    and no test can be blamed for.

    Args:
        app_log: The app log's text.
        input_log: The probe's input log text.

    Returns:
        The surplus, never negative.

    """
    received = sum(
        1 for found in _KEY_PRESSED_RE.finditer(app_log) if found[1] not in MODIFIER_KEY_NAMES
    )
    injected = 0
    for line in input_log.splitlines():
        found = _INPUT_LINE_RE.match(line)
        if not found:
            continue
        if found[1] == "key":
            injected += 1
        elif found[1] == "type":
            injected += len(found[2])
    return max(0, received - injected)


_LEVEL_RE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+ \| (ERROR|CRITICAL)\b")
# Text no line of a clean run carries, whatever its level.
_PROBLEM_TEXTS = (
    "Traceback (most recent call last)",
    "Unable to load image",
    "Error loading texture",
    "Error reading file",
)
_SCREEN_ENTERED_RE = re.compile(pattern(markers.SCREEN_ENTERED, name=re.compile(r"([^']+)")))
_SCREEN_LEFT_RE = re.compile(pattern(markers.SCREEN_LEFT, name=re.compile(r"([^']+)")))


# How many of a log's problems a failure message lists before "... and N more".
PROBLEMS_SHOWN = 12


def log_problems(app_log: str) -> list[str]:
    """Return what a passing test must not leave in the app log.

    Error-level lines and tracebacks; Kivy's image-load failures, which it logs
    below error level; and screens whose entered and left lines do not pair up
    (each screen may be the one still showing, so a surplus of one is allowed,
    once).

    Args:
        app_log: The app log's text.

    Returns:
        One short line per problem, in log order.

    """
    problems: list[str] = [
        line.strip()[:200]
        for line in app_log.splitlines()
        if _LEVEL_RE.match(line) or any(text in line for text in _PROBLEM_TEXTS)
    ]
    entered = [found[1] for found in _SCREEN_ENTERED_RE.finditer(app_log)]
    left = [found[1] for found in _SCREEN_LEFT_RE.finditer(app_log)]
    showing = 0
    for screen in sorted(set(entered)):
        surplus = entered.count(screen) - left.count(screen)
        if surplus < 0 or surplus > 1:
            times, lefts = entered.count(screen), left.count(screen)
            problems.append(f"screen '{screen}' entered {times} times, left {lefts}")
        showing += max(surplus, 0)
    if showing > 1:
        problems.append(f"{showing} screens entered and never left - only one can be showing")
    return problems


def resize_events(log_text: str) -> list[tuple[int, int]]:
    """Return every window size the app logged a resize event for, in order."""
    return [(int(w), int(h)) for w, h in _RESIZE_RE.findall(log_text)]


@dataclass
class _Run:
    dir: Path | None = None


_RUN = _Run()


@dataclass
class AppBoot:
    """Boots the app once for a test, from this test's own scratch profile.

    Call it with a node to boot onto; it returns the Driver. `scratch` is the
    profile directory, for a test that asserts what the app persisted after
    the teardown stopped it.

    Attributes:
        scratch: This test's config directory.
        nodeid: The pytest node id, for artifact names.
        driver: The Driver once booted.

    """

    scratch: Path
    nodeid: str
    driver: gd.Driver | None = None
    boot_geometry: tuple[int, int, int, int] | None = None
    _shots: list[Path] = field(default_factory=list)
    # Set before the probe is asked to start, not after the Driver exists: a
    # boot that fails part-way (the app never logs its ready line, say) has
    # still left an X server and pid files behind that `stop` must clear, or
    # every later test on this worker dies with "already running".
    _started: bool = False

    @property
    def booted(self) -> bool:
        """Whether a boot has been attempted for this test."""
        return self._started

    def __call__(
        self,
        node: Sequence[str],
        *,
        cues: Mapping[str, dict[str, int | str] | None] | None = None,
        ini: Mapping[str, str] | None = None,
        history: bool = True,
    ) -> gd.Driver:
        """Boot the app onto `node` and return its Driver.

        Args:
            node: The tree node to boot onto, leaf-to-root.
            cues: Last-read-page cues to pin, keyed by display title; None
                removes a cue. Pin one for any story the test opens by name.
            ini: Barks Reader settings to override for this test only.
            history: False starts with an empty reading history instead of the
                canned one.

        Raises:
            AssertionError: On a second boot in one test - navigate from where
                you are instead.

        """
        assert not self.booted, "one boot per test - navigate from where you are instead"
        if ini:
            apply_ini_overrides(self.scratch / "barks-reader.ini", ini)
        if not history:
            (self.scratch / "barks-reader-history.json").write_text(
                '{"version": 1, "events": []}\n'
            )
        os.environ[PROBE_NO_RESTORE_ENV_VAR] = "1"
        os.environ[PROBE_KEY_GAP_ENV_VAR] = str(KEY_GAP_SECS)
        self._started = True
        gd.boot_app_at(node, config_dir=self.scratch, seed=SEED, cues=cues)
        # Not paced: every move waits on the app's log, none on the camera clock.
        self.driver = gd.Driver(settle_quiet_ms=SETTLE_QUIET_MS, paced=False)
        # The size every test must hand back: a window that shrank after a reader
        # close or a fullscreen round trip is a defect even when every assertion
        # the test made passed (assert_window_size_kept, from the fixture teardown).
        self.boot_geometry = self.driver.window_geometry()
        return self.driver

    def assert_window_size_kept(self) -> None:
        """Fail the test if the app window is not the size it booted at.

        Called from the fixture teardown once the test body has passed. Two
        views are compared, since they can disagree: the X window's geometry as
        the probe measures it, and the size the app itself last logged a resize
        event for (on the nested display without a window manager, fullscreen
        changes only the latter). The failure artifacts are saved first, so the
        app log says what resized the window. A window the probe cannot find is
        not a failure here: a quit test has closed it, and a crash has already
        failed the test.

        Raises:
            AssertionError: If either size differs from what the app booted at.

        """
        if self.driver is None or self.boot_geometry is None:
            return
        try:
            self.driver.settle()
            now = self.driver.window_geometry()
        except gd.DriverError:
            return
        problems: list[str] = []
        if now[:2] != self.boot_geometry[:2]:
            problems.append(
                f"the X window is {now[:2]}, not the {self.boot_geometry[:2]} it booted at"
            )
        sizes = resize_events(self.driver.log_path.read_text(errors="replace"))
        if sizes and sizes[-1] != sizes[0]:
            problems.append(f"the app's last resize event was {sizes[-1]}, its first {sizes[0]}")
        if not problems:
            return
        listing = "\n".join(str(p) for p in self.save_failure_artifacts())
        msg = f"the app window did not keep its size: {'; '.join(problems)}; artifacts:\n{listing}"
        raise AssertionError(msg)

    def checkpoint(self, name: str) -> Path | None:
        """Save a screenshot named `name` when BARKS_GUI_SHOTS=1; otherwise do nothing.

        Returns:
            The PNG's path, or None when checkpoints are off.

        """
        if os.environ.get("BARKS_GUI_SHOTS") != "1" or self.driver is None:
            return None
        path = artifacts_dir() / artifact_name(self.nodeid, f"-{name}.png")
        self.driver.shot(path)
        self._shots.append(path)
        return path

    def save_failure_artifacts(self) -> list[Path]:
        """Save a screenshot, the logs and the scratch profile for a failed test.

        Returns:
            The files written, for the report.

        """
        saved: list[Path] = []
        out = artifacts_dir()
        if self.driver is not None:
            with contextlib.suppress(gd.DriverError):
                saved.append(self.driver.shot(out / artifact_name(self.nodeid, ".png")))
            with contextlib.suppress(gd.DriverError):
                tail = out / artifact_name(self.nodeid, "-tail.log")
                tail.write_text(gd.probe("tail", "80"))
                saved.append(tail)
            # Every key and click the probe sent, timestamped: read it against
            # app.log to tell an ignored key from one that never went out.
            input_log = self.driver.log_path.with_name("input.log")
            if input_log.is_file():
                target = out / artifact_name(self.nodeid, "-input.log")
                shutil.copy2(input_log, target)
                saved.append(target)
        for log in (self.scratch / COPIED_KIVY_DIR / "logs").glob("*.log"):
            target = out / artifact_name(self.nodeid, f"-{log.name}")
            shutil.copy2(log, target)
            saved.append(target)
        # The profile the app booted from, as it stands now: what a hand reboot
        # into the failing state needs (BARKS_READER_CONFIG_DIR at a copy of it).
        for name in ("barks-reader.ini", "barks-reader.json"):
            source = self.scratch / name
            if source.is_file():
                target = out / artifact_name(self.nodeid, f"-{name}")
                shutil.copy2(source, target)
                saved.append(target)
        return saved

    def assert_log_clean(self) -> None:
        """Fail the test if the app log holds an error, a broken screen pairing or a stray key.

        Called from the fixture teardown once the test body has passed, on every
        path the suite walks. The failure artifacts are saved first.

        Raises:
            AssertionError: Naming the offending lines.

        """
        if self.driver is None:
            return
        try:
            app_log = self.driver.log_path.read_text(errors="replace")
        except OSError:
            return
        problems = log_problems(app_log)
        stray = self.stray_key_note()
        if stray:
            problems.append(stray)
        if not problems:
            return
        listing = "\n".join(str(p) for p in self.save_failure_artifacts())
        shown = "\n".join(problems[:PROBLEMS_SHOWN])
        hidden = len(problems) - PROBLEMS_SHOWN
        more = f"\n... and {hidden} more" if hidden > 0 else ""
        msg = f"the app log is not clean:\n{shown}{more}\nartifacts:\n{listing}"
        raise AssertionError(msg)

    def stray_key_note(self) -> str | None:
        """Return a line for the failure report when keys the probe never sent reached the app."""
        if self.driver is None:
            return None
        input_log = self.driver.log_path.with_name("input.log")
        try:
            app_text = self.driver.log_path.read_text(errors="replace")
            input_text = input_log.read_text(errors="replace") if input_log.is_file() else ""
        except OSError:
            return None
        stray = stray_key_presses(app_text, input_text)
        if stray == 0:
            return None
        return (
            f"STRAY INPUT: {stray} key press(es) reached the app that the probe did not send."
            " In a visible run the test window takes the host keyboard: was something typed?"
        )

    def stop(self) -> None:
        """Stop the app if a boot was attempted, never raising."""
        if not self._started:
            return
        try:
            gd.probe("stop")
        except gd.DriverError as exc:
            print(f"gui-tests: WARNING {exc}")  # noqa: T201
        os.environ.pop(gd.CONFIG_DIR_ENV_VAR, None)
        os.environ.pop(PROBE_NO_RESTORE_ENV_VAR, None)
        os.environ.pop(PROBE_KEY_GAP_ENV_VAR, None)
