"""Fixtures for the GUI path tests: a booted app per test, and the config put back.

These boot the real app on the nested Xephyr display through ``scripts/gui-probe.sh``
and drive it with ``scripts/gui_driver.py``, so they are not part of the default
``uv run pytest`` run (this directory is outside ``testpaths``, like the benchmarks).
Run them with ``bash scripts/run_gui_tests.sh``.

Each test boots the app onto the node it asks for and gets a Driver. Booting is
the fixed cost - a few seconds on a desktop (the speech-index test boots, opens
the index and steps three letters in 7s) - so a test that can reach its second
screen from its first should still do so rather than ask for another boot, but
one boot per screen family is affordable.

The app rewrites its config on exit and the boot rewrites it before, so the
user's ``barks-reader.json`` is copied once per session and restored after every
test, on top of the probe's own restore.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# The driver is a sibling script, not an installed module, so the path above has
# to be in place before it can be imported.
import gui_driver as gd  # noqa: E402

# Pins the app's random draws, so backgrounds and the title-view fade are the
# same every run. Any fixed number does.
SEED = 1

# Stories the tests open by name. Pinned to "no cue" so each opens at its front
# page with no goto-page row, whatever this machine's reading history says.
CUES: dict[str, dict[str, int | str] | None] = {
    "The Ghost of the Grotto": None,
    "Lost in the Andes!": None,
}


@dataclass(frozen=True)
class AppConfig:
    """The app's live config and the session's pristine copy of it."""

    live: Path
    pristine: Path

    def restore(self) -> None:
        shutil.copy2(self.pristine, self.live)


@pytest.fixture(scope="session")
def app_config() -> Iterator[AppConfig]:
    """Back up the user's config for the session and put it back at the end."""
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        pytest.skip("no graphical session for the nested display to open in")
    live = Path(gd.probe("config").strip())
    if not live.is_file():
        pytest.skip(f"app config not found: {live}")
    handle, name = tempfile.mkstemp(prefix="barks-gui-tests-config.", suffix=".json")
    os.close(handle)
    config = AppConfig(live=live, pristine=Path(name))
    shutil.copy2(live, config.pristine)
    try:
        yield config
    finally:
        config.restore()
        config.pristine.unlink(missing_ok=True)


@pytest.fixture
def boot(app_config: AppConfig) -> Iterator[Callable[[Sequence[str]], gd.Driver]]:
    """Boot the app onto a node and hand back a Driver; stop it afterwards.

    Usage::

        def test_something(boot):
            d = boot(["Reading", "root"])
            ...

    The teardown stops the app whether the test passed or not, then restores
    the config the session started with over whatever the app wrote on exit.
    """
    booted = False

    def _boot(node: Sequence[str]) -> gd.Driver:
        nonlocal booted
        assert not booted, "one boot per test - navigate from where you are instead"
        gd.boot_app_at(node, config=app_config.live, seed=SEED, cues=CUES)
        booted = True
        return gd.Driver()

    try:
        yield _boot
    finally:
        if booted:
            try:
                gd.probe("stop")
            except gd.DriverError as exc:
                print(f"gui-tests: WARNING {exc}")  # noqa: T201
        # The probe's own restore only undoes what the app wrote on exit, not
        # what the boot wrote before it; the session copy is the pristine one.
        app_config.restore()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Iterator[None]:
    """On a failure, append the tail of the app log to the report.

    The log is the oracle every wait reads, so its last lines are the first thing
    to look at when a wait timed out - and they are gone once the next test boots.
    """
    outcome = yield
    report = outcome.get_result()  # ty: ignore[unresolved-attribute]
    if call.when == "call" and report.failed:
        try:
            tail = gd.probe("tail", "40")
        except gd.DriverError as exc:
            tail = str(exc)
        item.add_report_section("call", "app log tail", tail)
