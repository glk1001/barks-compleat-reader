"""Drive the Barks Reader GUI on the desktop it runs on: the probe for Windows.

The same commands, arguments, output and exit codes as ``gui-probe.sh``, the
Linux probe, so ``gui_driver.py`` and the GUI test suite run unchanged on top of
either. What differs is only how a platform finds the app's window, injects
input and takes a screenshot; that lives in a backend module
(``gui_probe_win32.py``). Everything else is here: the run directory, the app
and input logs, the pid file, the config backup, and the waits on the app log.

There is no nested display to hide behind, so the app runs on the real desktop
and keys go to the foreground window. The probe brings the app to the front
before it sends anything and refuses to send when it cannot, so a key never goes
to some other window. Do not use the machine while a run is going.

Usage (the same as gui-probe.sh; see there):
  python scripts/gui_probe.py doctor | start | stop | stop-xserver | geometry
  python scripts/gui_probe.py shot OUT.png | click X Y | key NAME... | type TEXT
  python scripts/gui_probe.py wait REGEX [SECS] | settle [QUIET_MS [MAX_SECS]]
  python scripts/gui_probe.py log | config | tail [N]

Env: BARKS_PROBE_DISPLAY (":2"; only names the run directory here),
BARKS_PROBE_KEY_GAP (seconds after each injected key, default 0.4),
BARKS_READER_CONFIG_DIR, BARKS_PROBE_NO_RESTORE=1 and BARKS_PROBE_APP, all as
for gui-probe.sh.

Only the standard library is used, plus Pillow for ``shot``, as the driver
runs this with the interpreter it runs under.
"""

# cspell:ignore PYTHONIOENCODING creationflags

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, Protocol

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
WINDOW_NAME = "Compleat Barks Disney Reader"
# The app is interactive once its window is shown: a key sent earlier goes nowhere.
READY_MARKER = "Main window shown."
DEFAULT_KEY_GAP = 0.4
# How long `start` waits for the app's window to appear once the ready line is logged.
WINDOW_WAIT_SECS = 10
# A directory setting the app reads only while its switch is on (reader_settings.py's
# keys): doctor does not warn about one whose switch is off.
DIR_SWITCHES = {
    "png_barks_panels_dir": "use_png_images",
    "prebuilt_dir": "use_prebuilt_comics",
    "wiki_bundle_dir": "use_live_wiki_bundle",
}


class ProbeError(RuntimeError):
    """A command could not do what it was asked; the message says why."""


class Backend(Protocol):
    """What a platform supplies: the window, input, screenshots and processes."""

    creation_flags: int

    def find_window(self, title: str) -> int | None:
        """Return the handle of a visible top-level window whose title contains `title`."""
        ...

    def client_geometry(self, window: int) -> tuple[int, int, int, int]:
        """Return the window's drawable area as (width, height, x, y) in screen pixels."""
        ...

    def bring_to_front(self, window: int) -> bool:
        """Make the window the foreground one; return whether it now is."""
        ...

    def move_pointer(self, x: int, y: int) -> None:
        """Put the pointer at screen pixel (x, y)."""
        ...

    def click(self, x: int, y: int) -> None:
        """Left-click at screen pixel (x, y)."""
        ...

    def send_key(self, name: str) -> None:
        """Press and release the key an X11 keysym name stands for (``Return``, ``Down``)."""
        ...

    def send_char(self, char: str) -> None:
        """Type one character."""
        ...

    def capture(self, rect: tuple[int, int, int, int], out: Path) -> None:
        """Save the screen area (width, height, x, y) to a PNG."""
        ...

    def process_alive(self, pid: int) -> bool:
        """Return whether a process is still running."""
        ...

    def kill_tree(self, pid: int, max_secs: float) -> None:
        """End a process and its children, waiting up to `max_secs` for it to go."""
        ...

    def doctor_checks(self) -> list[tuple[str, str]]:
        """Return (status, text) lines for `doctor`: status is OK, WARN or FAIL."""
        ...


# ------------------------------------------------------------------ paths --


def display_number() -> str:
    """Return the display number the run directory is named after (":3" -> "3")."""
    return os.environ.get("BARKS_PROBE_DISPLAY", ":2").lstrip(":") or "2"


def run_dir() -> Path:
    """Return this display's run directory: its logs, pid file and backups."""
    return Path(tempfile.gettempdir()) / f"barks-gui-probe-{display_number()}"


def app_log() -> Path:
    return run_dir() / "app.log"


def input_log() -> Path:
    return run_dir() / "input.log"


def _pid_file() -> Path:
    return run_dir() / "app.pid"


def env_runtime_value(name: str, env_file: Path | None = None) -> str:
    """Return a variable's value from the repo's ``.env.runtime``, or "" if it is not there.

    Args:
        name: The variable, e.g. ``BARKS_READER_CONFIG_DIR``.
        env_file: The file to read; the repo's by default.

    """
    path = env_file or REPO_ROOT / ".env.runtime"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    found = re.search(rf'^{re.escape(name)}="?(.*?)"?\s*$', text, re.MULTILINE)
    return found[1] if found else ""


def expand_home(value: str) -> str:
    """Expand ``${HOME}`` (as ``.env.runtime`` writes it) and any other env var in a path."""
    return os.path.expandvars(value.replace("${HOME}", str(Path.home())))


def _dir_setting(name: str, default: Path) -> Path:
    """Return a directory setting: an exported env var wins, as for the app; then .env.runtime."""
    value = os.environ.get(name) or env_runtime_value(name)
    return Path(expand_home(value)) if value else default


def config_dir() -> Path:
    return _dir_setting("BARKS_READER_CONFIG_DIR", Path.home() / "opt" / "barks-reader" / "config")


def data_dir() -> Path:
    return _dir_setting("BARKS_READER_DATA_DIR", Path.home() / "opt" / "barks-reader")


def config_file() -> Path:
    return config_dir() / "barks-reader.json"


def app_env(base: Mapping[str, str]) -> dict[str, str]:
    """Return the environment the app is launched with: `base`, with a plain-text log.

    The app log is the suite's oracle, read as plain text. On Windows loguru colours
    its output whenever TERM is set - as Git Bash sets it - even when that output
    is a file, and the colour codes land in the middle of the lines a test parses.
    LOGURU_COLORIZE is loguru's own switch for every handler that does not choose.
    """
    return dict(base, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", LOGURU_COLORIZE="0")


def _profile_backups() -> list[tuple[Path, Path]]:
    """Return each live profile file the app rewrites, with where `start` backs it up."""
    return [
        (config_file(), run_dir() / "barks-reader.json.bak"),
        (config_dir() / "barks-reader-history.json", run_dir() / "barks-reader-history.json.bak"),
    ]


# -------------------------------------------------------------- the log --


def log_has(pattern: str, text: str) -> bool:
    """Return whether the log text has a line matching `pattern`, as ``grep -E`` would."""
    return re.search(pattern, text, re.MULTILINE) is not None


def _read_log() -> str:
    try:
        return app_log().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def wait_for(pattern: str, timeout: float) -> bool:
    """Poll the app log for `pattern` until it appears or `timeout` seconds pass."""
    deadline = time.monotonic() + timeout
    while not log_has(pattern, _read_log()):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.5)
    return True


def settle(quiet_ms: int = 1000, max_secs: float = 30) -> None:
    """Block until the app log has not grown for `quiet_ms`: the app has stopped drawing."""
    deadline = time.monotonic() + max_secs
    quiet = 0
    prev = -1
    while time.monotonic() < deadline:
        try:
            size = app_log().stat().st_size
        except OSError:
            size = 0
        quiet = quiet + 250 if size == prev else 0
        if quiet >= quiet_ms:
            return
        prev = size
        time.sleep(0.25)


def note_input(kind: str, detail: str) -> None:
    """Log an injected input with its time, as gui-probe.sh does (the harness reads it)."""
    stamp = dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]  # noqa: DTZ005 (local, as the app logs)
    with input_log().open("a", encoding="utf-8") as out:
        out.write(f"{stamp} {kind} {detail}\n")


# ------------------------------------------------------------ the probe --


class Probe:
    """The commands, over a platform backend."""

    def __init__(self, backend: Backend) -> None:
        self._backend = backend

    # --- process state ---

    @staticmethod
    def _pid() -> int | None:
        try:
            return int(_pid_file().read_text().strip())
        except (OSError, ValueError):
            return None

    def app_alive(self) -> bool:
        pid = self._pid()
        return pid is not None and self._backend.process_alive(pid)

    def _window(self) -> int:
        if self._pid() is None:
            msg = "not started - run 'gui_probe.py start' first"
            raise ProbeError(msg)
        window = self._backend.find_window(WINDOW_NAME)
        if window is None:
            msg = f"app window ({WINDOW_NAME}) not found"
            raise ProbeError(msg)
        return window

    def _front_window(self) -> int:
        """Return the app's window once it is in front, so input can only go to it."""
        window = self._window()
        if not self._backend.bring_to_front(window):
            msg = (
                "the app window would not come to the front, so input would go elsewhere"
                " (is the screen locked, or is another window holding the foreground?)"
            )
            raise ProbeError(msg)
        return window

    # --- commands ---

    def start(self) -> None:
        if self.app_alive():
            msg = "already running (stop it first)"
            raise ProbeError(msg)
        if self._backend.find_window(WINDOW_NAME) is not None:
            msg = f"a {WINDOW_NAME} window is already open - close it first, or keys would go to it"
            raise ProbeError(msg)
        run_dir().mkdir(parents=True, exist_ok=True)
        app_log().write_text("")
        input_log().write_text("")
        # The app rewrites its config as it runs; keep the user's copy intact. A
        # harness booting from a throwaway profile sets BARKS_PROBE_NO_RESTORE=1.
        if not os.environ.get("BARKS_PROBE_NO_RESTORE"):
            for source, backup in _profile_backups():
                if source.is_file():
                    shutil.copy2(source, backup)
        self._launch()

        print("gui-probe: waiting for the app to become interactive...")  # noqa: T201
        if not wait_for(READY_MARKER, 120):
            self._abort_start(f"app never became ready; see {app_log()}")
        settle(1000, 30)
        window = self._await_window()
        if not self._backend.bring_to_front(window):
            self._abort_start("the app window would not come to the front (is the screen locked?)")
        # Mid-height on the far left: inside the window but clear of the action
        # bar and the goto arrows, so no hover state is triggered.
        _, height, x, y = self._backend.client_geometry(window)
        self._backend.move_pointer(x + 5, y + height // 2)
        print(f"gui-probe: ready. Log: {app_log()}")  # noqa: T201

    def _launch(self) -> None:
        """Start the app (the workspace's, or a build) with its output going to the app log."""
        env = app_env(os.environ)
        app = os.environ.get("BARKS_PROBE_APP")
        if app:
            # A build reads no .env.runtime: hand it the data dir a workspace run would read.
            argv = [app]
            env["BARKS_READER_DATA_DIR"] = str(data_dir())
        else:
            argv = ["uv", "run", "--directory", str(REPO_ROOT), "main.py"]
        with app_log().open("ab") as log:
            process = subprocess.Popen(  # noqa: S603 (fixed argv)
                argv,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                creationflags=self._backend.creation_flags,
            )
        _pid_file().write_text(str(process.pid))

    def _await_window(self) -> int:
        """Return the app's window once it shows, or abort the start."""
        deadline = time.monotonic() + WINDOW_WAIT_SECS
        while time.monotonic() < deadline:
            window = self._backend.find_window(WINDOW_NAME)
            if window is not None:
                return window
            time.sleep(0.25)
        return self._abort_start(f"the app logged its ready line but no {WINDOW_NAME} showed")

    def _abort_start(self, why: str) -> NoReturn:
        """Stop a failed start, so no half-booted app is left for the next one to trip on."""
        self.stop(quiet=True)
        raise ProbeError(why)

    def stop(self, *, quiet: bool = False) -> None:
        pid = self._pid()
        if pid is not None:
            self._backend.kill_tree(pid, max_secs=10)
        for target, backup in _profile_backups():
            if backup.is_file():
                shutil.copy2(backup, target)
                if not quiet:
                    print(f"gui-probe: restored {target}")  # noqa: T201
            # Spent once applied: `start` takes a fresh pair.
            backup.unlink(missing_ok=True)
        _pid_file().unlink(missing_ok=True)
        if not quiet:
            print("gui-probe: stopped")  # noqa: T201

    def stop_xserver(self) -> None:
        # No X server here; kept so the suite's session teardown runs unchanged.
        if self.app_alive():
            msg = "the app is still running - stop it first"
            raise ProbeError(msg)
        print("gui-probe: no X server on this platform")  # noqa: T201

    def geometry(self) -> str:
        width, height, x, y = self._backend.client_geometry(self._window())
        return f"{width}x{height}+{x}+{y}"

    def shot(self, out: Path) -> None:
        window = self._window()
        # Settle first: a still-growing log means a half-painted frame.
        settle(500, 5)
        self._backend.capture(self._backend.client_geometry(window), out)

    def click(self, x: int, y: int) -> None:
        """Click at a pixel of the window's drawable area, as `shot` captures it."""
        window = self._front_window()
        _, _, left, top = self._backend.client_geometry(window)
        note_input("click", f"{x} {y}")
        self._backend.move_pointer(left + x, top + y)
        time.sleep(0.3)
        self._backend.click(left + x, top + y)

    def key(self, names: Sequence[str]) -> None:
        gap = float(os.environ.get("BARKS_PROBE_KEY_GAP", DEFAULT_KEY_GAP))
        for name in names:
            self._front_window()
            note_input("key", name)
            self._backend.send_key(name)
            time.sleep(gap)

    def type(self, text: str) -> None:
        self._front_window()
        # Logged like keys are: the harness counts one key press per character.
        note_input("type", text)
        for char in text:
            self._backend.send_char(char)

    def doctor(self) -> bool:
        """Print what this machine has and lacks; return whether it is ready."""
        lines = [*self._backend.doctor_checks(), *repo_checks()]
        for status, text in lines:
            print(f"  {status:4s} {text}")  # noqa: T201
        failed = any(status == "FAIL" for status, _ in lines)
        verdict = "NOT ready - fix the FAIL items above." if failed else "ready."
        print(f"\ndoctor: {verdict}")  # noqa: T201
        return not failed


def repo_checks() -> list[tuple[str, str]]:
    """Return the doctor checks that are the same on every platform: repo, tools, app data."""
    checks: list[tuple[str, str]] = [
        ("OK", "uv") if shutil.which("uv") else ("FAIL", "uv not on PATH")
    ]
    env_file = REPO_ROOT / ".env.runtime"
    if env_file.is_file():
        checks.append(("OK", ".env.runtime"))
        for var in ("BARKS_ZIPS_KEY", "BARKS_READER_CONFIG_DIR", "BARKS_READER_DATA_DIR"):
            present = env_runtime_value(var, env_file) != ""
            checks.append(("OK", var) if present else ("FAIL", f"{var} not set in .env.runtime"))
    else:
        why = "gitignored (it holds BARKS_ZIPS_KEY), copy it from a working machine"
        checks.append(("FAIL", f".env.runtime - {why}"))
    venv = REPO_ROOT / ".venv"
    checks.append(("OK", ".venv") if venv.is_dir() else ("FAIL", ".venv - run 'uv sync'"))
    ini = config_dir() / "barks-reader.ini"
    if not ini.is_file():
        # The GUI suite copies each test's profile from here: without one it skips every test.
        why = "the GUI suite skips every test (point BARKS_READER_CONFIG_DIR at a profile)"
        checks.append(("WARN", f"{ini} not found - {why}"))
        return checks
    checks.append(("OK", str(ini)))
    return checks + dir_setting_checks(ini)


_TRUE_VALUES = ("1", "true", "yes", "on")


def dir_setting_checks(ini: Path) -> list[tuple[str, str]]:
    """Check every *_dir setting in the app's ini: absolute paths, written on some machine.

    A directory whose switch is off is never read, so it is reported, not warned about.
    """
    settings = dict(re.findall(r"^([a-z_]+)\s*=\s*(.*?)\s*$", ini.read_text(), re.MULTILINE))
    checks: list[tuple[str, str]] = []
    for key, value in settings.items():
        if not key.endswith("_dir"):
            continue
        switch = DIR_SWITCHES.get(key)
        if switch is not None and settings.get(switch, "0").lower() not in _TRUE_VALUES:
            checks.append(("--", f"{key} not used ({switch} is off)"))
            continue
        path = Path(expand_home(value))
        missing = f"{key} -> {path} (missing; edit {ini})"
        checks.append(("OK", key) if path.is_dir() else ("WARN", missing))
    return checks


def _backend() -> Backend:
    if sys.platform == "win32":
        import gui_probe_win32  # noqa: PLC0415 (a platform's module, loaded on that platform)

        return gui_probe_win32.Win32Backend()
    msg = f"no gui_probe.py backend for {sys.platform}; on Linux use scripts/gui-probe.sh"
    raise ProbeError(msg)


def run_log_command(command: str, args: list[str]) -> int | None:
    """Run a command that needs only the paths and the log; None if `command` is not one."""
    match command:
        case "log":
            print(app_log())  # noqa: T201
        case "config":
            print(config_file())  # noqa: T201
        case "tail":
            print("\n".join(_read_log().splitlines()[-int(args[0] if args else 20) :]))  # noqa: T201
        case "wait":
            timeout = float(args[1]) if len(args) > 1 else 15
            if not wait_for(args[0], timeout):
                why = f"timed out after {timeout:g}s waiting for: {args[0]}"
                print(f"gui-probe: {why}", file=sys.stderr)  # noqa: T201
                return 1
        case "settle":
            settle(int(args[0]) if args else 1000, float(args[1]) if len(args) > 1 else 30)
        case _:
            return None
    return 0


def run_backend_command(probe: Probe, command: str, args: list[str]) -> int:
    """Run a command that drives the app's window; 1 (with the usage) for an unknown one."""
    match command:
        case "doctor":
            return 0 if probe.doctor() else 1
        case "start":
            probe.start()  # a start position (X,Y) is accepted and ignored: no nested display
        case "stop":
            probe.stop()
        case "stop-xserver":
            probe.stop_xserver()
        case "geometry":
            print(probe.geometry())  # noqa: T201
        case "shot":
            probe.shot(Path(args[0]))
            print(args[0])  # noqa: T201
        case "click":
            probe.click(int(args[0]), int(args[1]))
        case "key":
            probe.key(args)
        case "type":
            probe.type(args[0])
        case _:
            print(__doc__)  # noqa: T201
            return 1
    return 0


def main(argv: Sequence[str]) -> int:
    """Run one probe command; return its exit status."""
    if not argv:
        print(__doc__)  # noqa: T201
        return 1
    command, args = argv[0], list(argv[1:])
    try:
        status = run_log_command(command, args)
        if status is None:
            status = run_backend_command(Probe(_backend()), command, args)
    except ProbeError as exc:
        print(f"gui-probe: {exc}", file=sys.stderr)  # noqa: T201
        return 1
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
