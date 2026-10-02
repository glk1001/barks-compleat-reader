"""Say what a Windows machine still lacks for the overnight run: the Windows check-overnight-host.

The counterpart of ``check-overnight-host.sh``: every one-off step of
``docs/setup.md``'s "A Windows overnight machine", checked, with what to do about
each one missing. It changes nothing. A FAIL fails a stage or the whole run; a
WARN is advice (a calibration, a copy gone stale) or a condition only the night
will show (the task registered, wake timers on). The exit status is 0 when
nothing FAILs.

Usage (from the repo root, in PowerShell or cmd):
  uv run python scripts/check_windows_overnight_host.py

``gui_probe.py doctor``'s checks come first (the screen unlocked, the repo's
secrets, the profile's folders), then the machine's.
"""

# cspell:ignore NSENINPUTPRETIME RTCWAKE STANDBYIDLE VIDEOIDLE SCRNSAVE schtasks winreg
# cspell:ignore Mirametrix HKEY tasklist

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import gui_probe

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
TASK_NAME = "Barks Reader overnight"
BARKS_ROOT = Path.home() / "Books" / "Carl Barks"
WIKI_SUBPATH = Path("Reader Files") / "Carl Barks Wiki"
GENERATED_MODULES = (
    ("src/barks-reader/src/barks_reader/_version.py", "bash scripts/build.sh"),
    ("src/comic-utils/src/comic_utils/get_panel_bytes.py", "bash scripts/generate-panel-module.sh"),
)
# A run is about 65 minutes; a timeout shorter than this blanks or sleeps the machine
# before the task starts (the runner holds the display only once it runs).
MIN_IDLE_SECS = 2 * 3600
# "If you've been away, when should Windows require you to sign in again?": Never.
SIGN_IN_NEVER = 0xFFFFFFFF
# Apps that lock the session when a webcam sees no one, whatever Windows says.
PRESENCE_LOCK_APPS = {"Glance.exe": "LG Glance by Mirametrix (Walk Away Lock)"}

# (what, powercfg subgroup, setting): each an idle timeout in seconds, 0 for never.
IDLE_SETTINGS = (
    ("turn off the display", "SUB_VIDEO", "VIDEOIDLE"),
    ("sleep", "SUB_SLEEP", "STANDBYIDLE"),
    (
        "the non-sensor presence timeout",
        "8619b916-e004-4dd8-9b66-dae86f806698",
        "5adbbfbc-074e-4da1-ba38-db8b36b2c8f3",
    ),
)

Check = tuple[str, str]


# ------------------------------------------------------------ the pure parts --


def ac_index(powercfg_output: str) -> int | None:
    """Return a setting's value on AC from ``powercfg /qh`` output, or None if it has none."""
    found = re.search(r"Current AC Power Setting Index:\s*0x([0-9a-fA-F]+)", powercfg_output)
    return int(found[1], 16) if found else None


def idle_check(what: str, secs: int | None) -> Check:
    """Judge an idle timeout on AC: never, or longer than a run, is OK."""
    if secs is None:
        return ("--", f"{what}: not a setting on this machine")
    if secs == 0 or secs >= MIN_IDLE_SECS:
        shown = "never" if secs == 0 else f"{secs // 60} min"
        return ("OK", f"{what} on AC: {shown}")
    return (
        "WARN",
        (
            f"{what} on AC after {secs // 60} min: make it 0 (never) or {MIN_IDLE_SECS // 60}+"
            " (docs/setup.md, Windows)"
        ),
    )


def sign_in_check(delay: int | None) -> Check:
    """Judge "require sign-in again after being away" (DelayLockInterval)."""
    if delay == SIGN_IN_NEVER:
        return ("OK", "sign-in when away: Never")
    shown = "not set" if delay is None else f"after {delay // 60} min"
    return (
        "FAIL",
        (
            f"sign-in when away: {shown} - set it to Never (Settings, Accounts, Sign-in options),"
            " or the machine wakes to a lock screen"
        ),
    )


def screen_saver_check(saver: str, secure: str) -> Check:
    """Judge the screen saver: none, or one without a password, is OK."""
    if not saver.strip():
        return ("OK", "no screen saver")
    if secure.strip() == "1":
        return ("FAIL", f"a screen saver with a password ({saver}): it locks the screen")
    return ("OK", f"screen saver without a password ({saver})")


def presence_lock_checks(running: set[str]) -> list[Check]:
    """Return a FAIL for each webcam presence-lock app among the running process names."""
    lowered = {name.lower() for name in running}
    found = [(exe, app) for exe, app in PRESENCE_LOCK_APPS.items() if exe.lower() in lowered]
    if not found:
        return [("OK", "no webcam presence-lock app running")]
    return [
        ("FAIL", f"{app} is running ({exe}): it locks an unattended session; remove it")
        for exe, app in found
    ]


def has_crlf(root: Path, limit: int = 50) -> bool:
    """Return whether any of the first `limit` pages under `root` has CRLF line endings."""
    pages = sorted(root.rglob("*.md"))[:limit]
    return any(b"\r\n" in page.read_bytes() for page in pages)


def wiki_copy_checks(data_dir: Path | None) -> list[Check]:
    """Check the wiki copy in Reader Files: there, and in LF as the export writes it on Linux."""
    if data_dir is None:
        return [("FAIL", "no app data directory (BARKS_READER_DATA_DIR) to find the wiki in")]
    wiki = data_dir / WIKI_SUBPATH
    if not (wiki / "index.md").is_file():
        return [("FAIL", f"no wiki copy at {wiki} (barks-wiki's scripts/export_reader_wiki.py)")]
    if has_crlf(wiki):
        return [
            (
                "WARN",
                (
                    f"the wiki copy at {wiki} has CRLF line endings, from a barks-wiki"
                    " before e75af9d4: re-export it as docs/setup.md says"
                ),
            )
        ]
    return [("OK", f"wiki copy: {wiki}")]


# ------------------------------------------------------- the machine's parts --


def _run(argv: list[str]) -> tuple[int, str]:
    try:
        done = subprocess.run(  # noqa: S603 (fixed tools)
            argv, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
    except OSError as exc:
        return 127, str(exc)
    return done.returncode, done.stdout + done.stderr


def _registry(path: str, name: str, *, machine: bool = False) -> object | None:
    """Return a registry value, or None where there is none (or no registry)."""
    if sys.platform != "win32":
        return None
    import winreg  # noqa: PLC0415 (Windows only)

    root = winreg.HKEY_LOCAL_MACHINE if machine else winreg.HKEY_CURRENT_USER
    try:
        with winreg.OpenKey(root, path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _as_int(value: object) -> int | None:
    try:
        return int(str(value))
    except ValueError:
        return None


def tool_checks() -> list[Check]:
    checks: list[Check] = []
    for tool, why in (
        ("git", "Git for Windows"),
        ("gh", "winget install GitHub.cli, for fetch-build"),
    ):
        checks.append(
            ("OK", tool) if shutil.which(tool) else ("FAIL", f"{tool} not on PATH ({why})")
        )
    if shutil.which("gh"):
        status, _ = _run(["gh", "auth", "status"])
        checks.append(
            ("OK", "gh logged in") if status == 0 else ("FAIL", "gh: run 'gh auth login'")
        )
    checks.append(
        ("OK", "bunx")
        if shutil.which("bunx")
        else ("WARN", "no bunx: the cspell commit hook fails (docs/setup.md, Windows: bunx.cmd)")
    )
    return checks


def repo_file_checks() -> list[Check]:
    checks: list[Check] = [
        ("OK", module)
        if (REPO_ROOT / module).is_file()
        else ("FAIL", f"{module} missing - run '{fix}'")
        for module, fix in GENERATED_MODULES
    ]
    calibration = REPO_ROOT / ".benchmarks" / "gui-timings.json"
    checks.append(
        ("OK", "GUI timings calibrated")
        if calibration.is_file()
        else ("WARN", "not calibrated: uv run python scripts/run_gui_tests.py --calibrate")
    )
    return checks


def data_checks() -> list[Check]:
    checks: list[Check] = []
    reader_files = BARKS_ROOT / "Compleat Barks Disney Reader" / "Reader Files"
    checks.append(
        ("OK", f"{reader_files}")
        if reader_files.is_dir()
        else (
            "FAIL",
            (
                f"{reader_files} missing - the junction (Windows) or link (macOS) in"
                " docs/setup.md (pytest needs it)"
            ),
        )
    )
    ini = gui_probe.config_dir() / "barks-reader.ini"
    prebuilt = _prebuilt_dir(ini)
    checks.append(
        ("OK", f"prebuilt comics: {prebuilt}")
        if prebuilt.is_dir()
        else ("WARN", f"no prebuilt comics at {prebuilt}: the validate stage skips itself")
    )
    return [*checks, *wiki_copy_checks(gui_probe.data_dir())]


def _prebuilt_dir(ini: Path) -> Path:
    # As the runner's validate stage reads it.
    import run_overnight_desktop  # noqa: PLC0415 (loads the runner only for this)

    return run_overnight_desktop.prebuilt_dir(ini)


def memory_check() -> Check:
    """Judge free memory as a GUI stage will, but only warn: tonight's may differ from now's."""
    import run_overnight_desktop as rw  # noqa: PLC0415 (loads the runner only for this)

    free = rw.available_mb()
    default_minimum, _ = rw.machine_memory_defaults()  # as the runner sizes it to the machine
    minimum = rw.env_mb(os.environ, "BARKS_OVERNIGHT_MIN_FREE_MB", default_minimum)
    problem = rw.free_memory_problem(free, minimum)
    if problem is None:
        return ("OK", f"{free:,} MB of memory free (a GUI stage needs {minimum:,})")
    biggest = ", ".join(f"{name} {size:,} MB" for name, size in rw.biggest_apps(3))
    return ("WARN", f"{problem}: {biggest}")


def machine_checks() -> list[Check]:
    checks: list[Check] = [memory_check()]
    dev_mode = _registry(
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock",
        "AllowDevelopmentWithoutDevLicense",
        machine=True,
    )
    checks.append(
        ("OK", "Developer Mode")
        if dev_mode == 1
        else (
            "FAIL",
            "Developer Mode off: four GUI tests cannot make symlinks (ms-settings:developers)",
        )
    )
    checks.append(sign_in_check(_as_int(_registry(r"Control Panel\Desktop", "DelayLockInterval"))))
    saver = _registry(r"Control Panel\Desktop", "SCRNSAVE.EXE") or ""
    secure = _registry(r"Control Panel\Desktop", "ScreenSaverIsSecure") or ""
    checks.append(screen_saver_check(str(saver), str(secure)))
    for what, subgroup, setting in IDLE_SETTINGS:
        _, out = _run(["powercfg", "/qh", "SCHEME_CURRENT", subgroup, setting])
        checks.append(idle_check(what, ac_index(out)))
    _, out = _run(["powercfg", "/qh", "SCHEME_CURRENT", "SUB_SLEEP", "RTCWAKE"])
    wake = ac_index(out)
    checks.append(
        ("OK", "wake timers allowed on AC")
        if wake in (1, 2)
        else ("WARN", "wake timers off on AC: the task cannot wake the machine at night")
    )
    _, out = _run(["tasklist", "/FO", "CSV", "/NH"])
    running = {line.split('","')[0].strip('"') for line in out.splitlines() if line}
    checks.extend(presence_lock_checks(running))
    status, _ = _run(["schtasks", "/Query", "/TN", TASK_NAME])
    checks.append(
        ("OK", f"the '{TASK_NAME}' task is registered")
        if status == 0
        else ("WARN", f"no '{TASK_NAME}' task: scripts\\windows\\register-overnight-task.ps1")
    )
    return checks


def gui_checks() -> list[Check]:
    """``gui_probe.py doctor``'s checks: the backend's (the screen) and the repo's."""
    import gui_probe_win32  # noqa: PLC0415 (Windows only)

    return [*gui_probe_win32.Win32Backend().doctor_checks(), *gui_probe.repo_checks()]


def main() -> int:
    """Print every check; return 0 when nothing FAILs, 2 off Windows."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if sys.platform != "win32":
        print("check_windows_overnight_host: Windows only", file=sys.stderr)  # noqa: T201
        return 2
    sections: list[tuple[str, Callable[[], list[Check]]]] = [
        ("The GUI probe (doctor)", gui_checks),
        ("Tools", tool_checks),
        ("The repo", repo_file_checks),
        ("The data", data_checks),
        ("The machine", machine_checks),
    ]
    failed = False
    for title, checks in sections:
        print(f"\n{title}")  # noqa: T201
        for status, text in checks():
            print(f"  {status:4s} {text}")  # noqa: T201
            failed = failed or status == "FAIL"
    verdict = "NOT ready - fix the FAIL items above." if failed else "ready."
    print(f"\ncheck_windows_overnight_host: {verdict}")  # noqa: T201
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
