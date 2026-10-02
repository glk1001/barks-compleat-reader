"""Say what a Mac still lacks for the overnight run: the macOS check-overnight-host.

The macOS counterpart of ``check_windows_overnight_host.py``: every one-off step of
``docs/setup.md``'s "A macOS overnight machine", checked, with what to do about each
one missing. It changes nothing. A FAIL fails a stage or the whole run; a WARN is
advice (a calibration, a tool only pushing needs). The exit status is 0 when nothing
FAILs.

Usage (from the repo root, in Terminal on the Mac's own desktop: the GUI probe's
permissions are Terminal's, so over ssh its checks fail):
  uv run python scripts/check_macos_overnight_host.py

``gui_probe.py doctor``'s checks come first (the screen unlocked, both permissions,
``clang``, the repo's secrets, the profile's folders), then the machine's. The data
and repo checks are the Windows check's own.
"""

# cspell:ignore sysadminctl

from __future__ import annotations

import io
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import check_windows_overnight_host as shared

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
# Where docs/setup.md clones it, and coverage_all_platforms.py looks for it by default.
EXPECTED_CLONE = Path.home() / "Developer" / "barks-compleat-reader"
CPI_DB = REPO_ROOT / "src" / "comic-utils" / "src" / "comic_utils" / "cpi.db"
LFS_POINTER_START = b"version https://git-lfs"
# The 4 GB guest's GUI stages fit, but the soak's walk once took the app past 4 GB.
MIN_MEMORY_MB = 8 * 1024

Check = tuple[str, str]


# ------------------------------------------------------------ the pure parts --


def cpi_db_check(path: Path) -> Check:
    """Judge cpi.db: the real database, not the git-lfs pointer a checkout without LFS has."""
    if not path.is_file():
        return ("FAIL", f"{path.name} missing: run 'git lfs pull'")
    with path.open("rb") as db:
        if db.read(len(LFS_POINTER_START)) == LFS_POINTER_START:
            return (
                "FAIL",
                (
                    f"{path.name} is git-lfs's pointer, not the database: run 'git lfs install'"
                    " then 'git lfs pull' (the reader stops on it at a page turn)"
                ),
            )
    return ("OK", f"{path.name} ({path.stat().st_size // (1024 * 1024)} MB)")


def hooks_check(pre_push: str | None) -> Check:
    """Judge the pre-push hook: prek's, which runs the full suite before a push."""
    if pre_push is None:
        return ("WARN", "no pre-push hook: run 'uv run prek install' (after 'git lfs install')")
    if "--hook-type=pre-push" in pre_push:
        return ("OK", "git hooks (prek)")
    return (
        "WARN",
        "the pre-push hook is not prek's (git lfs install took it?): run 'uv run prek install'",
    )


def screen_lock_check(sysadminctl_output: str) -> Check:
    """Judge ``sysadminctl -screenLock status``: off is best; the runner holds the display on."""
    text = sysadminctl_output.strip()
    if "screenLock is off" in text:
        return ("OK", "screen lock: off")
    if not text:
        return ("--", "screen lock: sysadminctl said nothing")
    return (
        "WARN",
        (
            f"screen lock is on ({text.splitlines()[-1].split(']')[-1].strip()}): a run started"
            " on a locked screen fails its GUI stages (System Preferences, Security & Privacy)"
        ),
    )


def total_memory_check(total_mb: int) -> Check:
    """Judge the machine's memory against the 8 GB docs/setup.md asks of the guest."""
    shown = f"{total_mb / 1024:.0f} GB of memory"
    if total_mb >= MIN_MEMORY_MB:
        return ("OK", shown)
    return (
        "WARN",
        f"{shown}: give the Mac 8 GB if it can (the soak's walk has taken the app past 4 GB)",
    )


def clone_check(repo_root: Path, expected: Path = EXPECTED_CLONE) -> Check:
    """Judge where the repo is: elsewhere works, but coverage_all_platforms.py needs telling."""
    if repo_root.resolve() == expected.resolve():
        return ("OK", f"the repo at {expected}")
    return (
        "WARN",
        (
            f"the repo is at {repo_root}, not {expected}: pass it to coverage_all_platforms.py"
            " as HOST:PATH"
        ),
    )


# ------------------------------------------------------- the machine's parts --


def _run(argv: list[str]) -> tuple[int, str]:
    try:
        done = subprocess.run(  # noqa: S603 (fixed tools)
            argv, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
    except OSError as exc:
        return 127, str(exc)
    return done.returncode, done.stdout + done.stderr


def tool_checks() -> list[Check]:
    checks: list[Check] = [
        ("OK", "git")
        if shutil.which("git")
        else ("FAIL", "git not on PATH: xcode-select --install"),
    ]
    status, out = _run(["git", "lfs", "version"])
    checks.append(
        ("OK", out.splitlines()[0])
        if status == 0
        else ("FAIL", "git-lfs missing: docs/setup.md, macOS step 3 (cpi.db needs it)")
    )
    if shutil.which("gh"):
        status, _ = _run(["gh", "auth", "status"])
        checks.append(
            ("OK", "gh logged in")
            if status == 0
            else ("WARN", "gh logged out: 'gh auth login' (only pushing from this Mac needs it)")
        )
    else:
        checks.append(("WARN", "no gh: only pushing from this Mac needs it (macOS step 3)"))
    checks.append(
        ("OK", "bunx")
        if shutil.which("bunx")
        else ("WARN", "no bunx: the cspell commit hooks fail (macOS step 3: ln -s bun bunx)")
    )
    return checks


def _pre_push_hook() -> str | None:
    status, common = _run(["git", "-C", str(REPO_ROOT), "rev-parse", "--git-common-dir"])
    if status != 0:
        return None
    hook = (REPO_ROOT / common.strip()).resolve() / "hooks" / "pre-push"
    try:
        return hook.read_text(encoding="utf-8")
    except OSError:
        return None


def repo_checks() -> list[Check]:
    return [
        *shared.repo_file_checks(),
        cpi_db_check(CPI_DB),
        hooks_check(_pre_push_hook()),
        clone_check(REPO_ROOT),
    ]


def machine_checks() -> list[Check]:
    import run_overnight_desktop as rw  # noqa: PLC0415 (loads the runner only for this)

    _, version = _run(["sw_vers", "-productVersion"])
    _, lock = _run(["sysadminctl", "-screenLock", "status"])
    return [
        ("OK", f"macOS {version.strip()}"),
        total_memory_check(rw.psutil.virtual_memory().total // (1024 * 1024)),
        shared.memory_check(),
        screen_lock_check(lock),
    ]


def gui_checks() -> list[Check]:
    """``gui_probe.py doctor``'s checks: the backend's (screen, permissions) and the repo's."""
    import gui_probe  # noqa: PLC0415
    import gui_probe_darwin  # noqa: PLC0415 (macOS only)

    return [*gui_probe_darwin.DarwinBackend().doctor_checks(), *gui_probe.repo_checks()]


def main() -> int:
    """Print every check; return 0 when nothing FAILs, 2 off macOS."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if sys.platform != "darwin":
        print("check_macos_overnight_host: macOS only", file=sys.stderr)  # noqa: T201
        return 2
    sections: list[tuple[str, Callable[[], list[Check]]]] = [
        ("The GUI probe (doctor)", gui_checks),
        ("Tools", tool_checks),
        ("The repo", repo_checks),
        ("The data", shared.data_checks),
        ("The machine", machine_checks),
    ]
    failed = False
    for title, checks in sections:
        print(f"\n{title}")  # noqa: T201
        for status, text in checks():
            print(f"  {status:4s} {text}")  # noqa: T201
            failed = failed or status == "FAIL"
    verdict = "NOT ready - fix the FAIL items above." if failed else "ready."
    print(f"\ncheck_macos_overnight_host: {verdict}")  # noqa: T201
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
