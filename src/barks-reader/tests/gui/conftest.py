"""Fixtures for the GUI path tests: a scratch profile and a booted app per test.

These boot the real app on the nested Xephyr display through ``scripts/gui-probe.sh``
and drive it with ``scripts/gui_driver.py``, so they are not part of the default
``uv run pytest`` run (this directory is outside ``testpaths``, like the benchmarks).
Run them with ``bash scripts/run_gui_tests.sh``.

The user's real profile is never booted from. Once per session it is copied to a
template with a few settings pinned (``barks_gui.harness.INI_OVERRIDES``) and any
run-wide settings from ``BARKS_GUI_INI`` applied (``run_gui_tests.sh --prebuilt``,
``--png-images``, ``--ini``); every test gets its own copy of that template plus
canned ``barks-reader.json`` and reading-history files, and the app is pointed at
it through the config-dir env var. The session's teardown proves the live profile
came through untouched.

Each test boots the app onto the node it asks for and gets a Driver. Booting is
the fixed cost - a few seconds on a desktop - so a test that can reach its second
screen from its first should do so rather than ask for another boot; one boot per
test is asserted.

A test that passes must also leave things clean, and the teardown checks that with
the failure artifacts saved when not: the window is the size it booted at (an
intermittent shrink seen while watching a run then becomes a report naming what
resized it), the app log holds no error, traceback, image-load failure,
unpaired screen entry or key the probe never sent, and every read the app logged
left its last-read cue and history event in the profile as logged.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

GUI_DIR = Path(__file__).resolve().parent
REPO_ROOT = GUI_DIR.parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _path in (SCRIPTS_DIR, GUI_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

# The driver is a sibling script and the harness a package beside this file,
# neither installed, so the paths above have to be in place before either import.
import gui_driver as gd  # noqa: E402
from barks_gui import harness  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Iterator

# The live files a run must leave byte-identical.
WATCHED_LIVE_FILES = ("barks-reader.json", "barks-reader-history.json", "barks-reader.ini")
DISPLAY_ENV_VAR = "BARKS_PROBE_DISPLAY"
HEADLESS_ENV_VAR = "BARKS_PROBE_HEADLESS"
KEEP_XSERVER_ENV_VAR = "BARKS_PROBE_KEEP_XSERVER"
# Set by the report hook: whether the test body failed, so the teardown's window
# size check does not pile a second report onto a test that already failed.
CALL_FAILED = pytest.StashKey[bool]()


@pytest.fixture(scope="session", autouse=True)
def probe_display(request: pytest.FixtureRequest) -> Iterator[str]:
    """Give this pytest process its own nested display, so parallel workers never collide.

    Under pytest-xdist each worker gets the base display plus its worker number
    (gw0 -> :2, gw1 -> :3, ...); a plain run keeps the base. The probe reads the
    variable on every call, and keeps a run directory per display.

    The X server on it lives for the whole session: each test boots and stops
    only the app. So a visible run opens one Xephyr window, which takes the host
    keyboard focus once, when it appears, rather than once per test.
    """
    worker_input = getattr(request.config, "workerinput", None) or {}
    worker_id = worker_input.get("workerid", "master")
    display = harness.display_for_worker(worker_id, os.environ.get(DISPLAY_ENV_VAR, ":2"))
    os.environ[DISPLAY_ENV_VAR] = display
    os.environ[KEEP_XSERVER_ENV_VAR] = "1"
    try:
        yield display
    finally:
        os.environ.pop(KEEP_XSERVER_ENV_VAR, None)
        try:
            gd.probe("stop-xserver")
        except gd.DriverError as exc:
            print(f"gui-tests: WARNING {exc}")  # noqa: T201


@dataclass(frozen=True)
class LiveProfile:
    """The user's real config directory and what its watched files held at session start."""

    dir: Path
    snapshot: dict[str, bytes]


@pytest.fixture(scope="session")
def live_profile() -> Iterator[LiveProfile]:
    """Locate the live profile, snapshot it, and prove afterwards that it is untouched."""
    # Xephyr opens a window on the host display; Xvfb needs none (the same
    # rule gui-probe.sh's doctor applies).
    headless = bool(os.environ.get(HEADLESS_ENV_VAR))
    if not headless and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        pytest.skip("no graphical session for the nested display to open in")
    live = Path(gd.probe("config").strip()).parent
    if not (live / "barks-reader.ini").is_file():
        pytest.skip(f"app config not found in {live}")
    snapshot = {n: (live / n).read_bytes() for n in WATCHED_LIVE_FILES if (live / n).is_file()}
    yield LiveProfile(dir=live, snapshot=snapshot)
    changed = [n for n, data in snapshot.items() if (live / n).read_bytes() != data]
    assert not changed, f"the GUI tests changed the live profile: {changed} in {live}"


@pytest.fixture(scope="session")
def scratch_template(live_profile: LiveProfile, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the pinned copy of the live profile that every test's scratch dir starts from."""
    return harness.build_template(live_profile.dir, tmp_path_factory.mktemp("config-template"))


@pytest.fixture
def boot(
    scratch_template: Path, tmp_path: Path, request: pytest.FixtureRequest
) -> Iterator[harness.AppBoot]:
    """Give the test its own scratch profile and a one-shot app app_boot; stop it afterwards.

    Usage::

        def test_something(boot: AppBoot) -> None:
            d = boot(["Reading", "root"])
            ...
            # after the teardown, boot.scratch holds what the app persisted

    """
    scratch = tmp_path / "config"
    shutil.copytree(scratch_template, scratch)
    for name in ("barks-reader.json", "barks-reader-history.json"):
        shutil.copy2(harness.FIXTURES_DIR / name, scratch / name)
    app_boot = harness.AppBoot(scratch=scratch, nodeid=request.node.nodeid)
    try:
        yield app_boot
    finally:
        try:
            if not request.node.stash.get(CALL_FAILED, False):
                app_boot.assert_window_size_kept()
                app_boot.assert_log_clean()
                app_boot.assert_reads_persisted()
        finally:
            app_boot.stop()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Iterator[None]:
    """On a failure, save the screenshot and logs and put the log tail in the report.

    The log is the oracle every wait reads, so its last lines are the first thing
    to look at when a wait timed out - and the app is still up here, since the
    call-phase report is made before the fixtures tear down.
    """
    outcome = yield
    report = outcome.get_result()  # ty: ignore[unresolved-attribute]
    if call.when != "call":
        return
    item.stash[CALL_FAILED] = bool(report.failed)
    if not report.failed:
        return
    try:
        tail = gd.probe("tail", "40")
    except gd.DriverError as exc:
        tail = str(exc)
    # Appended to this report's own sections: item.add_report_section would land
    # on the *next* report made (the teardown's), which pytest does not print.
    report.sections.append(("app log tail", tail))
    funcargs: dict[str, object] = getattr(item, "funcargs", {})
    app_boot = funcargs.get("boot")
    if isinstance(app_boot, harness.AppBoot):
        saved = app_boot.save_failure_artifacts()
        lines = [str(p) for p in saved]
        # A key the probe never sent explains a stall better than any log tail.
        stray = app_boot.stray_key_note()
        if stray:
            lines.insert(0, stray)
        report.sections.append(("gui artifacts", "\n".join(lines)))
