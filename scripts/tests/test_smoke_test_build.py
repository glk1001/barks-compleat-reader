"""smoke-test-build.sh tells the stop it sends a build from a crash in the build.

The smoke test stops a build left at its popup with a SIGTERM to the processes under
the launch, and Nuitka's onefile bootstrap passes that on to the program as a SIGINT:
the KeyboardInterrupt traceback that can follow is the stop, not a crash. A fake
build stands in for the real one. Like the onefile bootstrap, the launched process
starts a child and waits for it, and the child is what the smoke test signals: it
leaves the installer's log and flag, logs the popup, and on SIGTERM prints the
traceback it was given.
"""

# cspell:ignore pytestmark

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SMOKE_TEST = Path(__file__).resolve().parent.parent / "smoke-test-build.sh"

# A bare "bash" on the Windows runner is WSL with no distro installed.
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="needs a real bash")

# The launched process starts itself again as the child and waits, as the onefile
# bootstrap waits on the program it unpacked; the child prints TRACEBACK_FILE when
# stopped. The smoke test runs the build from its own folder, so the installer's
# files land where it looks.
FAKE_BUILD = """#!/usr/bin/env bash
if [[ "${1:-}" != child ]]; then
    echo "Checking existence of installer zip" > barks-reader-installer-fake.log
    : > barks-reader-installer-failed.flag
    "$0" child &
    wait "$!"
    exit $?
fi
trap 'cat "TRACEBACK_FILE"; exit 1' TERM
echo "Standalone popup opened"
while :; do sleep 0.1; done
"""

INTERRUPT = """Traceback (most recent call last):
  File "main.py", line 394, in <module>
  File "kivy/base.py", line 616, in stopTouchApp
KeyboardInterrupt
"""

ERROR_THEN_INTERRUPT = """Traceback (most recent call last):
  File "main.py", line 394, in <module>
ValueError: the build is broken
During handling of the above exception, another exception occurred:
Traceback (most recent call last):
  File "kivy/base.py", line 616, in stopTouchApp
KeyboardInterrupt
"""


def _smoke_test(tmp_path: Path, traceback: str) -> subprocess.CompletedProcess[str]:
    traceback_file = tmp_path / "traceback.txt"
    traceback_file.write_text(traceback, encoding="utf-8")
    build = tmp_path / "build" / "barks-reader-linux"
    build.parent.mkdir()
    build.write_text(FAKE_BUILD.replace("TRACEBACK_FILE", str(traceback_file)), encoding="utf-8")
    build.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in ("KIVY_GL_BACKEND", "WAYLAND_DISPLAY")}
    env["DISPLAY"] = ":0"  # a display is set, so no xvfb-run: the fake draws nothing
    return subprocess.run(  # noqa: S603
        ["bash", str(SMOKE_TEST), str(build), "1"],  # noqa: S607
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
        check=False,
    )


def test_a_keyboard_interrupt_from_the_stop_is_not_a_crash(tmp_path: Path) -> None:
    result = _smoke_test(tmp_path, INTERRUPT)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "stopped at the popup" in result.stdout
    assert "not a crash" in result.stdout


def test_an_error_chained_to_the_interrupt_still_fails(tmp_path: Path) -> None:
    result = _smoke_test(tmp_path, ERROR_THEN_INTERRUPT)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "FAIL - a traceback" in result.stderr
    assert "ValueError: the build is broken" in result.stderr
