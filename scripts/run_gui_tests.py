"""Run the GUI path tests on Windows, against the real app on the real desktop.

The Windows counterpart of ``run_gui_tests.sh``: the same suite, driven through
``gui_probe.py`` (real keys through SendInput) instead of a nested X server. One
worker, in a visible window: there is no second desktop to run another on, so
the suite takes longer than a headless Linux run. Leave the machine alone while
it runs - a key or a click from you goes to the app and fails the test.

Usage (from the repo root, in PowerShell or cmd):
  uv run python scripts/run_gui_tests.py                  # the suite
  uv run python scripts/run_gui_tests.py -k fullscreen    # extra args go to pytest
  uv run python scripts/run_gui_tests.py --quiet          # failures and the summary only
  uv run python scripts/run_gui_tests.py --soak           # the random walk instead
  uv run python scripts/run_gui_tests.py --app PATH.exe   # against a built executable
  uv run python scripts/run_gui_tests.py --ini key=value  # a Barks Reader setting (repeatable)
  uv run python scripts/run_gui_tests.py --calibrate      # record this machine's timing budgets

Pytest's whole output goes to build/gui-tests/<run>/pytest.log as it runs, beside
the failed tests' artifacts, so a run that hangs or is killed still leaves a record.

The checks, markers and artifacts are the Linux suite's: see run_gui_tests.sh
and docs/plans/gui-test-suite.md.
"""

# cspell:ignore PYTHONUNBUFFERED

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROBE = REPO_ROOT / "scripts" / "gui_probe.py"
GUI_TESTS = "src/barks-reader/tests/gui/"
SUMMARY_PREFIXES = ("FAILED ", "ERROR ", "E  ")


def _parse(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        epilog="Anything else is passed to pytest.",
    )
    parser.add_argument("--quiet", action="store_true", help="print failures and the summary")
    parser.add_argument("--soak", action="store_true", help="run only the random walk")
    parser.add_argument("--calibrate", action="store_true", help="record the timing budgets")
    parser.add_argument("--app", type=Path, help="a built executable to run instead")
    parser.add_argument(
        "--ini", action="append", default=[], metavar="KEY=VALUE", help="a setting for the run"
    )
    return parser.parse_known_args(argv)


def _is_summary(line: str) -> bool:
    """Return whether a -q pytest line is one --quiet keeps: a failure, or the totals."""
    words = ("passed", "failed", "error", "skipped")
    return line.startswith(SUMMARY_PREFIXES) or any(f" {w}" in line for w in words)


def _run_env(options: argparse.Namespace, stamp: str, timings: Path) -> dict[str, str]:
    """Return the environment the suite runs in, as run_gui_tests.sh sets it up."""
    # Unbuffered: pytest's output goes into a pipe, where Python would otherwise
    # hold it in blocks and pytest.log would stay empty until pytest exited.
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    # One worker; the load rule in the timing budgets discounts the run's own.
    env["BARKS_GUI_WORKER_COUNT"] = "1"
    env["BARKS_GUI_RUN_STAMP"] = stamp
    if options.ini:
        env["BARKS_GUI_INI"] = ";".join(options.ini)
        print(f"run_gui_tests: settings for this run: {env['BARKS_GUI_INI']}")  # noqa: T201
    if options.app is not None:
        env["BARKS_PROBE_APP"] = str(options.app.resolve())
        print(f"run_gui_tests: running the built executable {options.app}")  # noqa: T201
    if options.calibrate:
        env["BARKS_GUI_NO_BUDGETS"] = "1"
        env["BARKS_GUI_TIMINGS"] = str(timings)
        timings.parent.mkdir(parents=True, exist_ok=True)
        print(f"run_gui_tests: calibrating the timing budgets (recording to {timings})")  # noqa: T201
    return env


def _run_pytest(cmd: list[str], env: dict[str, str], *, quiet: bool, log: Path) -> int:
    """Run the suite, writing all of pytest's output to `log` as it comes.

    The log is written line by line, not at the end, so a run that hangs or is
    killed part-way still says which tests passed and how the last one failed.
    With `quiet` only failures and the totals are printed, also as they come.
    """
    args = [*cmd, "-q", "--tb=short"] if quiet else [*cmd, "-v", "--durations=0"]
    print("+", " ".join(args))  # noqa: T201
    log.parent.mkdir(parents=True, exist_ok=True)
    with (
        log.open("w", encoding="utf-8") as out,
        subprocess.Popen(  # noqa: S603
            args,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as run,
    ):
        assert run.stdout is not None
        for line in run.stdout:
            out.write(line)
            out.flush()
            if not quiet or _is_summary(line):
                print(line, end="", flush=True)  # noqa: T201
    return run.returncode


def main(argv: list[str]) -> int:
    """Run the suite; return pytest's exit status (or 1 if the machine is not ready)."""
    options, pytest_args = _parse(argv)
    if options.app is not None and not options.app.is_file():
        print(f"run_gui_tests: not an executable: {options.app}", file=sys.stderr)  # noqa: T201
        return 2
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005 (a local folder name)
    timings = REPO_ROOT / "build" / "gui-tests" / stamp / "timings.jsonl"
    env = _run_env(options, stamp, timings)

    doctor = subprocess.run(  # noqa: S603 (fixed argv)
        [sys.executable, str(PROBE), "doctor"], env=env, capture_output=True, text=True, check=False
    )
    if doctor.returncode != 0:
        print(doctor.stdout, file=sys.stderr)  # noqa: T201
        print("run_gui_tests: this machine is not ready (see above)", file=sys.stderr)  # noqa: T201
        return 1

    select = ["-m", "soak" if options.soak else "not soak"]
    cmd = [sys.executable, "-m", "pytest", GUI_TESTS, *select, *pytest_args]
    pytest_log = REPO_ROOT / "build" / "gui-tests" / stamp / "pytest.log"
    status = _run_pytest(cmd, env, quiet=options.quiet, log=pytest_log)
    if status != 0:
        print(f"run_gui_tests: pytest's output and the artifacts are in {pytest_log.parent}")  # noqa: T201

    # A calibration counts only when every test passed: a stuck app's durations
    # would set the baseline wrong.
    if options.calibrate and status == 0:
        gui_path = os.pathsep.join([str(REPO_ROOT / GUI_TESTS), str(PROBE.parent)])
        status = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "barks_gui.timings", "calibrate", str(timings), "1"],
            env=dict(env, PYTHONPATH=gui_path),
            check=False,
        ).returncode
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
