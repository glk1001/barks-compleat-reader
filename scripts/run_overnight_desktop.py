"""Run the overnight run on Windows or macOS: the stages only a desktop machine can.

The desktop counterpart of ``run_overnight.sh``, which is Linux only (Xvfb,
systemd-inhibit, bash). CI already covers Windows and macOS on every push without
the data pack: the unit suite, the Nuitka build and a smoke test of it. This runs
what CI cannot - the real data pack, the real OpenGL drawing, the built executable
reading comics, and long walks - one stage after another, every stage even after
one fails, except that nothing runs after a failed ``update``. The whole plan, and
what is left to Linux and CI, is docs/plans/windows-overnight.md; the macOS GUI
suite's, docs/plans/macos-gui-tests.md.

Stages (name: what it runs):
  update         git pull --ff-only, then uv sync --locked: the run tests what is
                 on main tonight (pull before starting too: a pull that changes
                 this runner takes effect only on the next run)
  pytest         the unit suite, with the data pack CI's legs do not have, its
                 coverage measured for the coverage stage
  validate       validate-barks-reader-files.py --full-load-check --strict-wiki: the
                 whole library; skipped, saying which, while the prebuilt comics
                 are not on this machine. Before the GUI stages: it warms the file cache
  gui            run_gui_tests.py: the GUI suite on the workspace app, the app's
                 coverage measured where the probe can (BARKS_PROBE_COVERAGE)
  fetch-build    CI's barks-reader-win.exe for this checkout's commit (waiting for
                 its Build Verification run if it is still building: run here,
                 late, CI has almost always finished); skipped with --app, and on
                 macOS, where CI's app has no software OpenGL to draw with on a
                 machine without a GPU driver (the workspace app runs through
                 scripts/macos/with-soft-gl.sh)
  built-app      run_gui_tests.py --app: the suite on that executable, reading real
                 comics; skipped, saying why, when there is none
  soak           run_gui_tests.py --soak: the random walk, SOAK_STEPS keys from each
                 of SOAK_SEEDS
  coverage       the unit suite's and the GUI suite's coverage, each and combined,
                 with an HTML report of what nothing ran: the code only this
                 platform runs, which the Linux run cannot measure. The combined
                 figure is held within COVERAGE_TOLERANCE of this machine's best
                 (coverage_floor.py), on a night pytest and gui both passed

Usage (from the repo root: PowerShell, cmd or Git Bash on Windows; Terminal on the
Mac's own desktop, not over ssh, as its Accessibility and Screen Recording
permissions are Terminal's):
  uv run python scripts/run_overnight_desktop.py [--list] [--only A,B] [--skip A,B]
                                                 [--app PATH]
  --list   print the stages and exit
  --only   run only these stages (comma-separated)
  --skip   run every stage but these
  --app    use this executable for built-app instead of fetching CI's
Env: BARKS_OVERNIGHT_SOAK_STEPS (default 1000) and BARKS_OVERNIGHT_SOAK_SEEDS
(default: one seed from the day of the year, the first of the Linux run's three,
so each night walks a new path); GH_REPO (default glk1001/barks-compleat-reader);
BARKS_OVERNIGHT_MIN_FREE_MB and BARKS_OVERNIGHT_APP_MEMORY_CAP_MB (defaults sized
to the machine, below).

Before the first GUI stage it runs ``gui_probe.py doctor``; on a locked screen, or
with the app's window already open, the GUI stages do not start, and fail, saying
why: injected keys would go nowhere. While the run lasts the machine and its
display are kept awake (Windows' SetThreadExecutionState, macOS's caffeinate).
Leave the machine alone: a key or a click goes to the app.

Graphics: on Windows with no OpenGL driver (the VirtualBox guest's "GDI Generic",
OpenGL 1.1, below Kivy's 2.0) every stage draws through ANGLE, Direct3D in
software, as CI's Windows runner does: KIVY_GL_BACKEND=angle_sdl2, set by the run
itself unless KIVY_GL_BACKEND is already set. Without it Kivy stops on a modal
"OpenGL 2.0 NOT found" box that an unattended run waits on all night.

Memory: a GUI stage starts only with MIN_FREE_MB free, else it fails naming the
biggest apps; and while it runs, the app (its whole process tree) is held to
APP_MEMORY_CAP_MB: over it, the app is stopped and the stage fails, saying so,
rather than the machine running out (a soak's walk through the wiki's big
reference tables once took the app to 4.4 GB). Each GUI stage logs the app's peak.
Both default to 6 GB, or where that is more than the machine can give, half its
memory free and three quarters of it as the cap (the 4 GB macOS guest: 2 and 3 GB).

A stage's output goes to build/overnight/<stamp>/<stage>.log and summary.txt holds
the results so far, in the Linux run's format, rewritten after every stage:
passed, FAILED, WARNED, skipped (the stage says why) or stopped. The exit status
is non-zero if any stage FAILED.
"""

# cspell:ignore PYTHONIOENCODING PYTHONUNBUFFERED taskkill yday pids caffeinate dimsu pmset

from __future__ import annotations

import argparse
import contextlib
import ctypes
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

import gui_probe
import psutil

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
RUNNER = "run_overnight_desktop"
ON_WINDOWS = sys.platform == "win32"
ON_MACOS = sys.platform == "darwin"

# validate before the GUI stages, as on Linux: it reads every volume, so the first app
# the GUI suite boots finds them in the file cache. Run last, it left that app reading
# cold archives (volumes 20 on, 0.4-0.5s each) and over its post tree setup budget.
# fetch-build just before built-app, its one user: a run started soon after a push
# finds CI still building, and third it waited for that build (about 20 minutes)
# with every stage behind it idle; after validate and gui the build is done.
STAGES = ("update", "pytest", "validate", "gui", "fetch-build", "built-app", "soak", "coverage")
GUI_STAGES = frozenset({"gui", "built-app", "soak"})
# How far, in percentage points, the combined coverage may fall below its best (as on Linux).
COVERAGE_TOLERANCE = 1.0

# Status codes a stage returns besides pass (0) and fail (anything else), as the Linux run's.
SKIPPED = 3
WARNED = 4

DEFAULT_GH_REPO = "glk1001/barks-compleat-reader"
# Windows' own OpenGL 1.1, all a machine without a driver has; ANGLE draws instead.
SOFTWARE_OPENGL = "GDI Generic"
ANGLE_BACKEND = "angle_sdl2"
BUILD_WORKFLOW = "build.yml"
WIN_ARTIFACT = "barks-reader-win.exe"
# How long fetch-build waits for this commit's build to finish, and how often it looks.
BUILD_WAIT_SECS = 90 * 60
BUILD_POLL_SECS = 60

DEFAULT_SOAK_STEPS = "1000"

# What a GUI stage needs free to start: the app on the wiki's heaviest page (a
# 1,700-row table) is about 1.5 GB, and a walk can hold more than one such page.
DEFAULT_MIN_FREE_MB = 6144
# The app's ceiling while a GUI stage runs: a guard for the machine, not a leak test
# (the leave_no GUI tests are those). The suite peaks near 2.2 GB; a soak's walk holds
# more, garbage that waits for a rare full collection: 4.9 GB on the Windows laptop,
# through the wiki's big reference tables.
DEFAULT_APP_MEMORY_CAP_MB = 6144
# On a machine too small for those (the 4 GB macOS guest): these shares of its memory.
SMALL_MACHINE_MIN_FREE_SHARE = 0.5
SMALL_MACHINE_CAP_SHARE = 0.75
MEMORY_POLL_SECS = 2.0
_MB = 1024 * 1024

# The prebuilt comics' default home, as ReaderFilePaths has it, when the ini names none.
DEFAULT_PREBUILT_DIR = "${HOME}/Books/Carl Barks/The Comics/Chronological"


def say(*parts: object) -> None:
    """Print a line of the run's own, straight away."""
    print(*parts, flush=True)  # noqa: T201


# ---------------------------------------------------------------- stages --


def list_text(doc: str = __doc__ or "") -> str:
    """Return the stage list from the module docstring, as ``--list`` prints it."""
    found = re.search(r"^Stages.*?(?=^Usage)", doc, re.MULTILINE | re.DOTALL)
    return found[0].rstrip() if found else ""


def parse_names(value: str) -> list[str]:
    """Return the stage names in a comma-separated option value."""
    return [name for name in value.split(",") if name]


def select_stages(only: Sequence[str], skip: Sequence[str]) -> list[str]:
    """Return the stages to run, in run order.

    Raises:
        ValueError: A name in `only` or `skip` is not a stage.

    """
    unknown = [name for name in (*only, *skip) if name not in STAGES]
    if unknown:
        msg = f"no stage called {', '.join(unknown)} (see --list)"
        raise ValueError(msg)
    return [name for name in STAGES if (not only or name in only) and name not in skip]


def result_name(status: int, *, stopped: bool = False) -> str:
    """Return the summary's word for a stage's exit status."""
    if stopped:
        return "stopped"
    if status == 0:
        return "passed"
    if status == SKIPPED:
        return "skipped"
    if status == WARNED:
        return "WARNED"
    return "FAILED"


def soak_seeds(env: Mapping[str, str], today: dt.date) -> list[str]:
    """Return tonight's soak seeds: BARKS_OVERNIGHT_SOAK_SEEDS, else one from the day of year.

    The default is the first of the Linux run's three (day * 10 + 1): one walk a
    night, since one worker runs the walks one after another.
    """
    given = env.get("BARKS_OVERNIGHT_SOAK_SEEDS", "").split()
    return given or [str(today.timetuple().tm_yday * 10 + 1)]


# --------------------------------------------------------------- summary --


@dataclass(frozen=True)
class StageResult:
    name: str
    result: str
    secs: int


def elapsed(secs: float) -> str:
    """Return a run's length as the Linux run writes it: 1h05m."""
    secs = int(secs)
    return f"{secs // 3600}h{secs % 3600 // 60:02d}m"


def summary_text(
    stamp: str, commit: str, state: str, results: Sequence[StageResult], log_dir: str
) -> str:
    """Return summary.txt, line for line in the Linux run's format."""
    lines = [f"==== overnight run, {stamp} ({commit}): {state} ===="]
    lines += [f"{r.name:<14s} {r.result:<8s} {r.secs // 60:4d}m{r.secs % 60:02d}s" for r in results]
    lines.append(f"logs: {log_dir}/")
    return "\n".join(lines) + "\n"


def short_commit() -> str:
    """Return HEAD's short hash, or ? when git cannot say."""
    done = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607 (git from PATH)
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.strip() or "?"


# ------------------------------------------------------------ processes --


SOFT_GL_WRAPPER = SCRIPTS / "macos" / "with-soft-gl.sh"


def venv_command(*args: str) -> list[str]:
    """Return a command that runs `args` in the workspace venv.

    On macOS through with-soft-gl.sh, as the pre-push hook runs the suite there: a
    Mac without a GPU driver (the VirtualBox guest) opens no Kivy window without
    it, and a Mac with one still draws on its GPU.
    """
    if ON_MACOS:
        return ["bash", str(SOFT_GL_WRAPPER), *args]
    return ["uv", "run", *args]


def gl_backend_for(env: Mapping[str, str], renderer: str | None) -> str | None:
    """Return the Kivy graphics backend to set for this run, or None to leave Kivy's choice.

    ANGLE where Windows' OpenGL is its driverless "GDI Generic"; nothing where
    KIVY_GL_BACKEND is already set (the caller chose), or the renderer is a real
    driver's, or it could not be read.
    """
    if "KIVY_GL_BACKEND" in env or renderer != SOFTWARE_OPENGL:
        return None
    return ANGLE_BACKEND


def choose_gl_backend() -> None:
    """On Windows, draw through ANGLE where there is no OpenGL driver, saying so."""
    if not ON_WINDOWS:
        return
    import gui_probe_win32  # noqa: PLC0415 (Windows only)

    renderer = gui_probe_win32.opengl_renderer()
    backend = gl_backend_for(os.environ, renderer)
    if backend is None:
        chosen = os.environ.get("KIVY_GL_BACKEND")
        say(
            f"{RUNNER}: OpenGL: {renderer or 'unread'}"
            + (f"; KIVY_GL_BACKEND={chosen}" if chosen else "")
        )
        return
    os.environ["KIVY_GL_BACKEND"] = backend
    say(
        f"{RUNNER}: OpenGL here is {renderer!r} (1.1, below Kivy's 2.0):"
        f" drawing through ANGLE (KIVY_GL_BACKEND={backend})"
    )


def child_env(base: Mapping[str, str], **extra: str) -> dict[str, str]:
    """Return the environment a stage runs in: UTF-8, unbuffered, plain-text logs.

    Git Bash sets TERM, and loguru colours its output whenever TERM is set, even
    into a log file (see gui_probe.app_env); the console's code page is cp1252,
    which the app log's characters do not fit.
    """
    env = dict(base, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    env["LOGURU_COLORIZE"] = "0"
    env.pop("TERM", None)
    env.update(extra)
    return env


class StageLog:
    """A stage's output: to the console and to its log file, as it comes."""

    def __init__(self, out: TextIO) -> None:
        self._out = out
        # The memory watch writes from its own thread while a stage's output streams.
        self._lock = threading.Lock()

    def line(self, text: str) -> None:
        self._write(text + "\n")

    def _write(self, text: str) -> None:
        with self._lock:
            print(text, end="", flush=True)  # noqa: T201
            self._out.write(text)
            self._out.flush()

    def run(self, argv: Sequence[str], env: Mapping[str, str] | None = None) -> int:
        """Run a command, teeing its output here; return its exit status."""
        self.line("+ " + " ".join(f'"{a}"' if " " in a else a for a in argv))
        with subprocess.Popen(  # noqa: S603 (the stages' own commands)
            argv,
            cwd=REPO_ROOT,
            env=dict(env) if env is not None else child_env(os.environ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as process:
            assert process.stdout is not None
            try:
                for text in process.stdout:
                    self._write(text)
            except KeyboardInterrupt:
                # Before the with's exit waits on it: a child that ignored the
                # Ctrl-C (the app under uv) would hold the run open forever.
                kill_tree(process.pid)
                raise
        return process.returncode

    def capture(self, argv: Sequence[str]) -> tuple[int, str]:
        """Run a command for its output (logged, not echoed); return its status and stdout."""
        done = subprocess.run(  # noqa: S603 (the stages' own commands)
            argv,
            cwd=REPO_ROOT,
            env=child_env(os.environ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self._out.write(f"+ {' '.join(argv)}\n{done.stdout}{done.stderr}")
        self._out.flush()
        return done.returncode, done.stdout


def kill_tree(pid: int) -> None:
    """End a process and every process it started."""
    if ON_WINDOWS:
        subprocess.run(  # noqa: S603 (a pid of our own)
            ["taskkill", "/PID", str(pid), "/T", "/F"],  # noqa: S607 (a Windows tool)
            capture_output=True,
            check=False,
        )
        return
    try:
        root = psutil.Process(pid)
        tree = [*root.children(recursive=True), root]
    except psutil.Error:
        return
    for process in tree:
        with contextlib.suppress(psutil.Error):
            process.kill()


# ----------------------------------------------------------------- memory --


def env_mb(env: Mapping[str, str], name: str, default: int) -> int:
    """Return a size in MB from the environment, or `default` when unset or not a number."""
    try:
        return int(env.get(name, ""))
    except ValueError:
        return default


def available_mb() -> int:
    """Return the physical memory free for a new process, in MB."""
    return psutil.virtual_memory().available // _MB


def memory_defaults(total_mb: int) -> tuple[int, int]:
    """Return the default (MIN_FREE_MB, APP_MEMORY_CAP_MB) for a machine of `total_mb`.

    6 GB each where the machine has room; on a smaller one a share of its memory,
    so a 4 GB machine still runs its GUI stages, held to what it can give.
    """
    return (
        min(DEFAULT_MIN_FREE_MB, int(total_mb * SMALL_MACHINE_MIN_FREE_SHARE)),
        min(DEFAULT_APP_MEMORY_CAP_MB, int(total_mb * SMALL_MACHINE_CAP_SHARE)),
    )


def machine_memory_defaults() -> tuple[int, int]:
    """Return `memory_defaults` for this machine."""
    return memory_defaults(psutil.virtual_memory().total // _MB)


def free_memory_problem(free_mb: int, minimum_mb: int) -> str | None:
    """Return why a GUI stage should not start with `free_mb` free, or None if it may."""
    if free_mb >= minimum_mb:
        return None
    return (
        f"only {free_mb:,} MB of memory free, under the {minimum_mb:,} MB a GUI stage needs"
        " (BARKS_OVERNIGHT_MIN_FREE_MB): close the biggest apps below"
    )


def biggest_apps(count: int = 5) -> list[tuple[str, int]]:
    """Return the apps holding the most memory, as (name, MB), all of an app's processes added."""
    totals: dict[str, int] = {}
    for process in psutil.process_iter(["name", "memory_info"]):
        info = process.info
        if info.get("memory_info") is not None:
            name = str(info.get("name") or "?")
            totals[name] = totals.get(name, 0) + info["memory_info"].rss // _MB
    return sorted(totals.items(), key=lambda item: -item[1])[:count]


# The processes an app launch is made of: uv and the Python it starts, or a build.
_APP_PROCESS_PREFIXES = ("uv", "python", "barks-reader")


def process_tree_mb(pid: int) -> int | None:
    """Return the memory held by `pid` and every process under it, in MB.

    None when there is no such process, or it is not the app's (a pid file left
    behind whose number the system has given to something else).
    """
    try:
        root = psutil.Process(pid)
        if not root.name().lower().startswith(_APP_PROCESS_PREFIXES):
            return None
        tree = [root, *root.children(recursive=True)]
    except psutil.Error:
        return None
    total = 0
    for process in tree:
        try:
            total += process.memory_info().rss
        except psutil.Error:
            continue
    return total // _MB


class AppMemoryWatch(threading.Thread):
    """Hold the app under test to a memory ceiling while a GUI stage runs.

    The app's pid is the probe's (``app.pid``), a new one for every test. Over the
    cap, the app is stopped - its test then fails as a dead app does - and the
    stage is failed for it, with the size logged; the next test boots a new app.
    """

    def __init__(self, log: StageLog, cap_mb: int, pid_file: Path, poll_secs: float) -> None:
        super().__init__(daemon=True)
        self._log = log
        self._cap_mb = cap_mb
        self._pid_file = pid_file
        self._poll_secs = poll_secs
        self._done = threading.Event()
        self._stopped_pids: set[int] = set()
        self.peak_mb = 0
        self.breaches: list[int] = []

    def run(self) -> None:
        while not self._done.wait(self._poll_secs):
            self.check()

    def check(self) -> None:
        """Look at the current app once: note its size, and stop it if over the cap."""
        try:
            pid = int(self._pid_file.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return
        size = process_tree_mb(pid)
        if size is None or pid in self._stopped_pids:
            return
        self.peak_mb = max(self.peak_mb, size)
        if size <= self._cap_mb:
            return
        self._stopped_pids.add(pid)
        self.breaches.append(size)
        self._log.line(
            f"MEMORY: the app reached {size:,} MB, over the {self._cap_mb:,} MB cap"
            " (BARKS_OVERNIGHT_APP_MEMORY_CAP_MB): stopping it; the stage fails"
        )
        kill_tree(pid)

    def finish(self) -> str:
        """Stop watching; return the stage's memory line."""
        self._done.set()
        if self.ident is not None:  # started
            self.join()
        over = f"; over the cap {len(self.breaches)} time(s)" if self.breaches else ""
        return f"memory: the app's peak was {self.peak_mb:,} MB (cap {self._cap_mb:,} MB){over}"


# ------------------------------------------------------ keeping awake --

# Loaded only where there is one, so the pure helpers import (and are tested) anywhere.
_kernel32: Any = ctypes.WinDLL("kernel32") if sys.platform == "win32" else None

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


@contextmanager
def kept_awake() -> Iterator[None]:
    """Keep the machine and its display awake while the block runs: Linux's systemd-inhibit.

    The display too: injected input needs a screen that is on and unlocked.
    """
    with _kept_awake_windows() if ON_WINDOWS else _kept_awake_macos():
        yield


@contextmanager
def _kept_awake_macos() -> Iterator[None]:
    """Hold sleep off with caffeinate, for as long as this process lives.

    ``-w`` ties it to this process, so it lets go even if the run is killed.
    """
    try:
        caffeinate = subprocess.Popen(  # noqa: S603 (fixed argv)
            ["caffeinate", "-dimsu", "-w", str(os.getpid())],  # noqa: S607 (a macOS tool)
        )
    except OSError:
        say(f"{RUNNER}: WARNING - could not hold off sleep; the machine may sleep mid-run")
        yield
        return
    try:
        yield
    finally:
        caffeinate.terminate()


@contextmanager
def _kept_awake_windows() -> Iterator[None]:
    """Hold sleep off with SetThreadExecutionState.

    Cleared on the way out, however the run ends (and by Windows, should the
    process die).
    """
    _kernel32.SetThreadExecutionState.restype = ctypes.c_uint32
    _kernel32.SetThreadExecutionState.argtypes = [ctypes.c_uint32]
    held = _kernel32.SetThreadExecutionState(
        _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
    )
    if not held:
        say(f"{RUNNER}: WARNING - could not hold off sleep; the machine may sleep mid-run")
    try:
        yield
    finally:
        _kernel32.SetThreadExecutionState(_ES_CONTINUOUS)


class _SystemPowerStatus(ctypes.Structure):
    _fields_ = (
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    )


def on_battery() -> bool:
    """Return whether the machine is running on its battery (the AC line is off)."""
    if not ON_WINDOWS:
        done = subprocess.run(
            ["pmset", "-g", "batt"],  # noqa: S607 (a macOS tool)
            capture_output=True,
            text=True,
            check=False,
        )
        return pmset_on_battery(done.stdout)
    status = _SystemPowerStatus()
    if not _kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return False
    return status.ACLineStatus == 0


def pmset_on_battery(pmset_batt: str) -> bool:
    """Return whether `pmset -g batt`'s output says the Mac draws from its battery.

    Its first line names the source: "Now drawing from 'Battery Power'" or
    "... 'AC Power'" (a desktop Mac or a VM says AC).
    """
    return "'Battery Power'" in pmset_batt


# ------------------------------------------------------------ fetch-build --


def pick_build_run(runs: Sequence[Mapping[str, object]]) -> Mapping[str, object] | None:
    """Return the Build Verification run to take the executable from, or None.

    A commit on main has a push run; a commit also on a PR branch has a
    pull_request one too. The push run is preferred, then the newest (gh lists
    newest first).
    """
    for run in runs:
        if run.get("event") == "push":
            return run
    return runs[0] if runs else None


def windows_job(jobs: Sequence[Mapping[str, object]]) -> Mapping[str, object] | None:
    """Return the run's Windows build job, the one that uploads the executable."""
    for job in jobs:
        if "windows" in str(job.get("name", "")).lower():
            return job
    return None


# ---------------------------------------------------------------- validate --


def prebuilt_dir(ini: Path) -> Path:
    """Return where the validator looks for the prebuilt comics: the ini's prebuilt_dir.

    The validator reads the setting whatever its switch says (its Phase 7 is always
    on), and the reader's default when the ini has none.
    """
    try:
        text = ini.read_text(encoding="utf-8")
    except OSError:
        text = ""
    found = re.search(r"^prebuilt_dir\s*=\s*(.*?)\s*$", text, re.MULTILINE)
    return Path(gui_probe.expand_home(found[1] if found else DEFAULT_PREBUILT_DIR))


# ----------------------------------------------------------------- the run --


class Run:
    """One night's run: the stages, their logs and the summary."""

    def __init__(self, stages: Sequence[str], app: Path | None) -> None:
        self.stages = list(stages)
        self.app = app
        self.stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005 (a local folder name)
        self.log_dir_rel = f"build/overnight/{self.stamp}"
        self.log_dir = REPO_ROOT / self.log_dir_rel
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # The pytest and gui stages' coverage data, which the coverage stage combines.
        self.cov_dir = self.log_dir / "coverage"
        # The executable built-app runs: --app's, else the one fetch-build fetched.
        self.exe: Path | None = app
        self.no_exe_why = "fetch-build did not run"
        # None until the first GUI stage asks; then whether the machine can take input.
        self.gui_ready: bool | None = None
        self.results: list[StageResult] = []
        self.started = time.monotonic()

    def write_summary(self, state: str) -> None:
        text = summary_text(self.stamp, short_commit(), state, self.results, self.log_dir_rel)
        (self.log_dir / "summary.txt").write_text(text, encoding="utf-8")

    def gui_tests(self, log: StageLog, *args: str, **env: str) -> int:
        """Run the GUI suite, holding the app to its memory ceiling; over it fails the run."""
        _, default_cap = machine_memory_defaults()
        cap = env_mb(os.environ, "BARKS_OVERNIGHT_APP_MEMORY_CAP_MB", default_cap)
        watch = AppMemoryWatch(log, cap, gui_probe.run_dir() / "app.pid", MEMORY_POLL_SECS)
        watch.start()
        try:
            status = log.run(
                ["uv", "run", "python", str(SCRIPTS / "run_gui_tests.py"), *args],
                child_env(os.environ, **env),
            )
        finally:
            log.line(watch.finish())
        return status or (1 if watch.breaches else 0)

    # --- the stages ---

    def stage_update(self, log: StageLog) -> int:
        status = log.run(["git", "pull", "--ff-only"])
        return status or log.run(["uv", "sync", "--locked"])

    def stage_pytest(self, log: StageLog) -> int:
        self.cov_dir.mkdir(exist_ok=True)
        env = child_env(os.environ, COVERAGE_FILE=str(self.cov_dir / ".coverage.unit"))
        return log.run(venv_command("pytest", "-q", "--cov", "--cov-report=term:skip-covered"), env)

    def stage_fetch_build(self, log: StageLog) -> int:
        if self.app is not None:
            log.line(f"fetch-build: skipped - using --app {self.app}")
            self.no_exe_why = ""
            return SKIPPED
        if not ON_WINDOWS:
            log.line("fetch-build: skipped - CI's macOS app is not tried here yet: it has no")
            log.line("  software OpenGL, which a Mac without a GPU driver needs (the workspace")
            log.line("  app runs through scripts/macos/with-soft-gl.sh); --app tries one")
            self.no_exe_why = "fetch-build fetches none on macOS (see fetch-build.log)"
            return SKIPPED
        self.no_exe_why = "fetch-build did not fetch the executable (see fetch-build.log)"
        repo = os.environ.get("GH_REPO", DEFAULT_GH_REPO)
        _, sha = log.capture(["git", "rev-parse", "HEAD"])
        sha = sha.strip()
        status, out = log.capture(
            [
                "gh",
                "run",
                "list",
                "-R",
                repo,
                "--commit",
                sha,
                "--workflow",
                BUILD_WORKFLOW,
                "--json",
                "databaseId,status,conclusion,event",
                "-L",
                "10",
            ]
        )
        run = pick_build_run(json.loads(out)) if status == 0 and out.strip() else None
        if run is None:
            log.line(f"fetch-build: no Build Verification run for {sha} in {repo}")
            log.line("  (is this commit pushed? gh run list needs 'gh auth login' once)")
            return 1
        run_id = str(run["databaseId"])
        log.line(f"fetch-build: run {run_id} ({run['event']}) for {sha[:8]}")
        job = self._await_windows_job(log, repo, run_id)
        if job is None:
            return 1
        dest = self.log_dir / "build"
        status = log.run(
            ["gh", "run", "download", "-R", repo, run_id, "-n", WIN_ARTIFACT, "-D", str(dest)]
        )
        exe = dest / WIN_ARTIFACT
        if status != 0 or not exe.is_file():
            log.line(f"fetch-build: run {run_id} has no {WIN_ARTIFACT} to download")
            return status or 1
        self.exe = exe
        self.no_exe_why = ""
        log.line(f"fetch-build: {exe}")
        return 0

    @staticmethod
    def _await_windows_job(log: StageLog, repo: str, run_id: str) -> Mapping[str, object] | None:
        """Wait for the run's Windows job to finish; return it if it succeeded, else None.

        Only the Windows job matters here, so a macOS leg that failed does not
        cost the night its built-app stage.
        """
        deadline = time.monotonic() + BUILD_WAIT_SECS
        while True:
            status, out = log.capture(
                ["gh", "run", "view", "-R", repo, run_id, "--json", "status,conclusion,jobs"]
            )
            if status != 0:
                log.line(f"fetch-build: gh run view {run_id} failed (see the lines above)")
                return None
            job = windows_job(json.loads(out).get("jobs", []))
            if job is not None and job.get("status") == "completed":
                if job.get("conclusion") == "success":
                    return job
                log.line(f"fetch-build: the Windows build {job.get('conclusion')}: nothing to test")
                return None
            if time.monotonic() >= deadline:
                log.line(f"fetch-build: run {run_id}'s Windows build still not done; gave up")
                return None
            log.line(f"fetch-build: run {run_id} is still building; looking again in a minute")
            time.sleep(BUILD_POLL_SECS)

    def stage_gui(self, log: StageLog) -> int:
        self.cov_dir.mkdir(exist_ok=True)
        return self.gui_tests(log, BARKS_PROBE_COVERAGE=str(self.cov_dir))

    def stage_built_app(self, log: StageLog) -> int:
        if self.exe is None:
            log.line(f"built-app: skipped - no executable: {self.no_exe_why}")
            return SKIPPED
        return self.gui_tests(log, "--app", str(self.exe))

    def stage_soak(self, log: StageLog) -> int:
        steps = os.environ.get("BARKS_OVERNIGHT_SOAK_STEPS", DEFAULT_SOAK_STEPS)
        status = 0
        for seed in soak_seeds(os.environ, dt.date.today()):  # noqa: DTZ011 (the local day)
            log.line(f"soak: seed {seed}, {steps} keys")
            env = {"BARKS_GUI_WALK_SEED": seed, "BARKS_GUI_WALK_STEPS": steps}
            status = self.gui_tests(log, "--soak", **env) or status
        return status

    @staticmethod
    def stage_validate(log: StageLog) -> int:
        ini = gui_probe.config_dir() / "barks-reader.ini"
        comics = prebuilt_dir(ini)
        if not comics.is_dir():
            log.line(f"validate: skipped - the prebuilt comics are not on this machine: {comics}")
            log.line("  (its Phase 7 would fail every title: windows-overnight.md, step 4)")
            return SKIPPED
        validate = str(SCRIPTS / "validate-barks-reader-files.py")
        return log.run(venv_command("python", validate, "--full-load-check", "--strict-wiki"))

    def stage_coverage(self, log: StageLog) -> int:
        """Report the unit suite's, the GUI suite's and the combined coverage; judge the last."""
        unit, gui = self.cov_dir / ".coverage.unit", self.cov_dir / ".coverage.gui"
        parts = [part for part in (unit, gui) if part.is_file()]
        if not parts:
            log.line("coverage: skipped - neither the pytest nor the gui stage measured any")
            return SKIPPED
        for label, part in (("unit suite", unit), ("GUI tests", gui)):
            if part.is_file():
                log.line(f"coverage: {label:<12}{self._coverage_total(log, part)}%")
        combined = self.cov_dir / ".coverage.all"
        cmd = ["uv", "run", "coverage", "combine", "--keep", "--quiet", f"--data-file={combined}"]
        status = log.run([*cmd, *map(str, parts)])
        if status != 0:
            return status
        total = self._coverage_total(log, combined)
        log.line(f"coverage: combined    {total}%")
        html = self.cov_dir / "html"
        report = ["uv", "run", "coverage", "html", "--fail-under=0", "--quiet", "-d", str(html)]
        log.run([*report, f"--data-file={combined}"])
        log.line(f"coverage: what nothing tests: {html / 'index.html'}")
        if not (self._passed("pytest") and self._passed("gui")):
            log.line("coverage: not judged - the pytest and gui stages did not both pass")
            return 0
        floor = ["uv", "run", "python", str(SCRIPTS / "coverage_floor.py"), total]
        return log.run([*floor, "--tolerance", str(COVERAGE_TOLERANCE)])

    @staticmethod
    def _coverage_total(log: StageLog, data_file: Path) -> str:
        """Return a coverage data file's total, as coverage reports it ("94.7")."""
        cmd = ["uv", "run", "coverage", "report", "--fail-under=0", "--format=total"]
        _, out = log.capture([*cmd, "--precision=1", f"--data-file={data_file}"])
        return out.strip()

    def _passed(self, stage: str) -> bool:
        return any(r.name == stage and r.result == "passed" for r in self.results)

    def _gui_ready(self) -> bool:
        """Return whether the machine can take injected input; ask doctor once, logging it."""
        if self.gui_ready is None:
            with (self.log_dir / "gui-doctor.log").open("w", encoding="utf-8") as out:
                doctor = ["uv", "run", "python", str(SCRIPTS / "gui_probe.py"), "doctor"]
                status = StageLog(out).run(doctor)
            self.gui_ready = status == 0
        return self.gui_ready

    def run_stage(self, name: str, log: StageLog) -> int:
        if name in GUI_STAGES and not self._gui_ready():
            log.line(f"{name}: not run - this machine cannot take injected input tonight;")
            log.line(f"  doctor says why in {self.log_dir_rel}/gui-doctor.log")
            return 1
        if name in GUI_STAGES:
            default_minimum, _ = machine_memory_defaults()
            minimum = env_mb(os.environ, "BARKS_OVERNIGHT_MIN_FREE_MB", default_minimum)
            problem = free_memory_problem(available_mb(), minimum)
            if problem is not None:
                log.line(f"{name}: not run - {problem}:")
                for app, size in biggest_apps():
                    log.line(f"  {size:>7,} MB  {app}")
                return 1
        stage: Callable[[StageLog], int] = getattr(self, "stage_" + name.replace("-", "_"))
        return stage(log)

    # --- the loop ---

    def run(self) -> int:
        """Run every stage; return 1 if any failed, 0 if none did, 130 if stopped."""
        say(f"{RUNNER}: {len(self.stages)} stages: {' '.join(self.stages)}")
        say(f"{RUNNER}: to stop it and everything it started: Ctrl-C")
        say(f"{RUNNER}: results so far in {self.log_dir_rel}/summary.txt")
        failed = False
        for n, name in enumerate(self.stages, 1):
            into = elapsed(time.monotonic() - self.started)
            at = time.strftime("%H:%M")
            say(f"\n==== [{n}/{len(self.stages)}] {name}, started {at} ({into} into the run) ====")
            began = time.monotonic()
            with (self.log_dir / f"{name}.log").open("w", encoding="utf-8") as out:
                log = StageLog(out)
                try:
                    status = self.run_stage(name, log)
                except KeyboardInterrupt:
                    return self._stopped(name, began)
                except Exception as exc:  # noqa: BLE001 (one stage's crash is its failure alone)
                    log.line(f"{name}: {type(exc).__name__}: {exc}")
                    status = 1
            self._record(name, result_name(status), began)
            failed = failed or self.results[-1].result == "FAILED"
            if name == "update" and status != 0:
                say(f"{RUNNER}: update failed, so nothing else runs: it would test the wrong code")
                return self._finish("stopped after a failed update", 1)
            self.write_summary(f"{n} of {len(self.stages)} stages done")
        return self._finish(f"finished in {elapsed(time.monotonic() - self.started)}", int(failed))

    def _record(self, name: str, result: str, began: float) -> None:
        secs = int(time.monotonic() - began)
        self.results.append(StageResult(name, result, secs))
        say(f"==== {name}: {result} in {secs // 60}m{secs % 60}s ====")

    def _stopped(self, name: str, began: float) -> int:
        self._record(name, "stopped", began)
        if name in GUI_STAGES:
            # Close the app and put the profile back, as a GUI runner does on its way out.
            subprocess.run(  # noqa: S603
                [sys.executable, str(SCRIPTS / "gui_probe.py"), "stop"], check=False
            )
        return self._finish(
            f"stopped during {name}, {elapsed(time.monotonic() - self.started)} in", 130
        )

    def _finish(self, state: str, status: int) -> int:
        self.write_summary(state)
        say("\n" + (self.log_dir / "summary.txt").read_text(encoding="utf-8").rstrip())
        return status


def _parse(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--list", action="store_true", help="print the stages and exit")
    parser.add_argument("--only", default="", help="run only these stages (comma-separated)")
    parser.add_argument("--skip", default="", help="run every stage but these")
    parser.add_argument("--app", type=Path, help="the executable built-app runs")
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    """Run the night's stages; return 0 if none failed, 2 for a bad command line."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
    options = _parse(argv)
    if options.list:
        say(list_text())
        return 0
    try:
        stages = select_stages(parse_names(options.only), parse_names(options.skip))
    except ValueError as exc:
        print(f"{RUNNER}: {exc}", file=sys.stderr)  # noqa: T201
        return 2
    if options.app is not None and not options.app.is_file():
        print(f"{RUNNER}: not an executable: {options.app}", file=sys.stderr)  # noqa: T201
        return 2
    if not (ON_WINDOWS or ON_MACOS):
        print(f"{RUNNER}: Windows and macOS only; on Linux use run_overnight.sh", file=sys.stderr)  # noqa: T201
        return 2
    if on_battery():
        say(f"{RUNNER}: WARNING - on battery: a throttled CPU can fail the timing budgets; plug in")
    app = options.app.resolve() if options.app is not None else None
    choose_gl_backend()
    with kept_awake():
        return Run(stages, app).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
