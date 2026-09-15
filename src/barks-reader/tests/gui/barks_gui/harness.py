"""The scratch profile a GUI test boots from, and the artifacts a failure leaves.

A test never runs against the user's real profile. Once per session the live
config directory is copied to a template with a few settings pinned (no
fullscreen on start, quit asks first, no alternate Escape, window sized from the
screen); every test gets a fresh copy of that template, its own canned
``barks-reader.json`` and reading history, and the app is booted with the
config-dir env var pointing at it. Whatever the app writes on exit lands there
and is thrown away with the test's tmp dir.
"""

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

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[5]
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
# Under build/, which is gitignored and where record_demo keeps its beat clips.
ARTIFACTS_ROOT = REPO_ROOT / "build" / "gui-tests"

# Pins the app's random draws, so backgrounds and the title-view fade are the
# same every run. Any fixed number does.
SEED = 1

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
COPIED_FILES = ("barks-reader.ini", "log-config.yaml", "never-crop.txt")
COPIED_KIVY_DIR = "kivy"  # Kivy home: config.ini, icon/, mods/; logs/ is skipped

# Tells gui-probe.sh not to back up and restore the profile around a run: the
# scratch profile is disposable, and a test reads what the app wrote on exit.
PROBE_NO_RESTORE_ENV_VAR = "BARKS_PROBE_NO_RESTORE"

# The app window at the pinned nested screen (BARKS_PROBE_SCREEN=900x1300), as
# measured. Every pixel coordinate in the suite assumes it. (The demo recorder
# reports 1224: it rounds the height down to even for the video encoder.)
EXPECTED_WINDOW = (782, 1225)


def build_template(live_dir: Path, template: Path) -> Path:
    """Copy the live config directory into `template` with INI_OVERRIDES applied.

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
        _RUN.dir = ARTIFACTS_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005
        _RUN.dir.mkdir(parents=True, exist_ok=True)
    return _RUN.dir


def artifact_name(nodeid: str, suffix: str) -> str:
    """Turn a pytest node id into a file name safe for the artifacts directory."""
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", nodeid.split("::", 1)[-1])
    return f"{stem}{suffix}"


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
        geometry: The window's (width, height, x, y) once booted.

    """

    scratch: Path
    nodeid: str
    driver: gd.Driver | None = None
    geometry: tuple[int, int, int, int] | None = None
    _shots: list[Path] = field(default_factory=list)

    @property
    def booted(self) -> bool:
        """Whether the app has been started for this test."""
        return self.driver is not None

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
        gd.boot_app_at(node, config_dir=self.scratch, seed=SEED, cues=cues)
        self.driver = gd.Driver()
        self.geometry = self.driver.window_geometry()
        return self.driver

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
        """Save a screenshot, the log tail and the app's log file for a failed test.

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
        for log in (self.scratch / COPIED_KIVY_DIR / "logs").glob("*.log"):
            target = out / artifact_name(self.nodeid, f"-{log.name}")
            shutil.copy2(log, target)
            saved.append(target)
        return saved

    def stop(self) -> None:
        """Stop the app if it was booted, never raising."""
        if self.driver is None:
            return
        try:
            gd.probe("stop")
        except gd.DriverError as exc:
            print(f"gui-tests: WARNING {exc}")  # noqa: T201
        os.environ.pop(gd.CONFIG_DIR_ENV_VAR, None)
        os.environ.pop(PROBE_NO_RESTORE_ENV_VAR, None)


def require_geometry(boot: AppBoot) -> None:
    """Refuse to click by pixel unless the window is the size the coordinates assume.

    Fails rather than skips: a wrong size means the runner or the probe's screen
    setting has drifted, which is a harness bug to fix, not a reason to test less.

    Raises:
        AssertionError: If the window is not EXPECTED_WINDOW.

    """
    assert boot.geometry is not None, "boot the app before clicking"
    width, height = boot.geometry[:2]
    assert (width, height) == EXPECTED_WINDOW, (
        f"app window is {width}x{height}, but every pixel coordinate was measured at "
        f"{EXPECTED_WINDOW[0]}x{EXPECTED_WINDOW[1]} - is BARKS_PROBE_SCREEN pinned?"
    )
