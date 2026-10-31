#!/usr/bin/env python3
"""Show every popup the Barks Reader owns, to check they look alike: a contact sheet, or live.

The popups were written one at a time and do not look alike; the plan that sets them
right is ``docs/plans/popup-consistency.md``, and this is how each step is checked.

Contact sheets (the default)
    For each screen size in ``SIZES`` this boots the real app headless through
    ``gui-probe.sh``, from a scratch copy of the profile, and has it open each popup in
    turn (``barks_reader.ui.popup_gallery``, which opens each through the function its
    screen calls, with sample content). Each is captured with the probe's frame
    request, the window drawn again off screen. The popups that run in their own
    window before the app does (``OWN_WINDOW``: the first-run installer, the error
    popup, the data pack success) are each run by their own preview on a private
    Xvfb display and captured from it. Every PNG lands in ``--out``, with one
    contact sheet per size and one for the own-window popups.

Live (``--live``)
    Runs the real app on this screen from a scratch copy of the profile, Page Down and
    Page Up stepping through the popups. Every popup's buttons do nothing there.

The profile
    The app writes its config on exit and its history on every read, so it is only
    ever run from a copy: the top-level files of the live profile's folder (its
    ``kivy`` folder of logs is left behind), with ``log_level`` set to DEBUG, since the
    lines waited on are logged at DEBUG. The live profile is never written.

Assumes
    - ``scripts/gui-probe.sh doctor`` passes, and nothing else is on its display
      (``BARKS_PROBE_DISPLAY``, ``:2``).
    - Xvfb, xwininfo and ImageMagick (``import``, ``montage``) on the PATH, and the
      own-window display (``BARKS_POPUP_GALLERY_DISPLAY``, ``:12``) free.
    - ``.env.runtime`` names the reader's folders, as for any workspace run.

Usage:
    uv run scripts/popup_gallery.py                   # every popup, every size
    uv run scripts/popup_gallery.py --list
    uv run scripts/popup_gallery.py --only quit,about --sizes spread
    uv run scripts/popup_gallery.py --no-own-window
    uv run scripts/popup_gallery.py --out /tmp/popups
    uv run scripts/popup_gallery.py --live
"""

# cspell:ignore pointsize nolisten killpg

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from barks_reader.core import log_markers
from barks_reader.core.popup_gallery import (
    LIVE_MODE,
    POPUP_GALLERY_ENV_VAR,
    POPUP_NAMES,
    request_text,
)
from gui_driver import CONFIG_DIR_ENV_VAR, REPO_ROOT, Driver, DriverError, probe

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import FrameType

# The screen sizes the app is booted on: the single page (a portrait screen), the
# two-page spread (a landscape one) and a common 1080p monitor.
SIZES: dict[str, str] = {"single": "900x1300", "spread": "1760x1300", "1080p": "1920x1080"}

# The popups that run in their own window, before the app or without it: a name and
# the module run, with its arguments, to show it (each module's own preview).
OWN_WINDOW: dict[str, tuple[str, ...]] = {
    "first-run-installer": ("barks_reader.first_run_installer_show_message",),
    "error-popup": ("barks_reader.ui.kivy_standalone_error_popup",),
    "data-pack-success": ("barks_reader.data_pack_installer", "--preview"),
}
# Each preview runs as `__main__` after config_info, as main.py would import it: a
# preview that reaches kivy first would fail config_info's import-order guard.
_PREVIEW_LAUNCHER = (
    "import runpy, sys; import barks_reader.core.config_info; "
    "sys.argv = sys.argv[1:]; "
    "runpy.run_module(sys.argv[0], run_name='__main__', alter_sys=True)"
)
OWN_WINDOW_DISPLAY = os.environ.get("BARKS_POPUP_GALLERY_DISPLAY", ":12")
OWN_WINDOW_SCREEN = "1600x1200"

# The probe already ran gui-probe.sh's `settle`; a popup opens over a short animation.
SHOWN_TIMEOUT = 20
# An own-window popup: how long to wait for its window, then for it to draw.
OWN_WINDOW_TIMEOUT = 60
OWN_WINDOW_SETTLE_SECS = 2.0

DEFAULT_OUT = REPO_ROOT / "build" / "popup-gallery"
LIVE_PROFILE_DEFAULT = Path.home() / "opt" / "barks-reader" / "config"
_LOG_LEVEL_RE = re.compile(r"^log_level\s*=.*$", re.MULTILINE)
# A top-level window in `xwininfo -root -children`: its size and position.
_WINDOW_RE = re.compile(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)")
_MIN_WINDOW_SIDE = 200


def _say(message: str) -> None:
    """Say how the run is going, on stdout."""
    print(message)  # noqa: T201


def live_profile_dir() -> Path:
    """Return the live profile's folder: the env var's, else ``.env.runtime``'s, else the default.

    The same order gui-probe.sh and the app use, so the copy is of the profile the app
    would boot from.
    """
    configured = os.environ.get(CONFIG_DIR_ENV_VAR, "")
    if not configured:
        env_file = REPO_ROOT / ".env.runtime"
        text = env_file.read_text(encoding="utf-8") if env_file.is_file() else ""
        found = re.search(rf'^{CONFIG_DIR_ENV_VAR}="([^"]*)"', text, re.MULTILINE)
        configured = found[1] if found else ""
    configured = configured.replace("${HOME}", str(Path.home()))
    return Path(configured) if configured else LIVE_PROFILE_DEFAULT


def make_scratch_profile(live: Path, scratch: Path, *, debug: bool = True) -> Path:
    """Copy the live profile's top-level files to `scratch`, logging at DEBUG if asked.

    Args:
        live: The live profile's folder; only read.
        scratch: The folder to make (emptied first if it is there).
        debug: Set the ini's ``log_level`` to DEBUG, for the lines waited on.

    Returns:
        `scratch`.

    """
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    for path in live.iterdir():
        if path.is_file():
            shutil.copy2(path, scratch / path.name)
    kivy_ini = live / "kivy" / "config.ini"
    if kivy_ini.is_file():
        (scratch / "kivy").mkdir()
        shutil.copy2(kivy_ini, scratch / "kivy" / "config.ini")
    ini = scratch / "barks-reader.ini"
    if debug and ini.is_file():
        text = ini.read_text(encoding="utf-8")
        ini.write_text(_LOG_LEVEL_RE.sub("log_level = DEBUG", text), encoding="utf-8")
    return scratch


def write_request(request_file: Path, request: str, name: str) -> None:
    """Write a request whole, then rename it into place, so the app never reads half."""
    partial = request_file.with_suffix(".tmp")
    partial.write_text(request_text(request, name), encoding="utf-8")
    partial.replace(request_file)


def shot_name(index: int, name: str) -> str:
    """Return a capture's file name, numbered so a folder lists in the gallery's order."""
    return f"{index:02d}-{name}.png"


def montage_command(shots: Sequence[Path], sheet: Path, title: str) -> list[str]:
    """Return the ImageMagick command that lays `shots` out on one labelled sheet."""
    # -label names each image after it, by its file name's stem ("03-quit").
    return [
        "montage",
        "-label",
        "%t",
        *(str(shot) for shot in shots),
        "-title",
        title,
        "-pointsize",
        "18",
        "-fill",
        "white",
        "-background",
        "#202020",
        "-geometry",
        "x600+14+14",
        "-tile",
        "4x",
        str(sheet),
    ]


def _montage(shots: Sequence[Path], sheet: Path, title: str) -> None:
    if not shots:
        return
    subprocess.run(montage_command(shots, sheet, title), check=True)  # noqa: S603  (fixed argv)
    _say(f"  sheet: {sheet}")


def capture_size(size_name: str, names: Sequence[str], out: Path, profile: Path) -> list[Path]:
    """Boot the app headless at one size and capture each popup named.

    Args:
        size_name: A key of `SIZES`.
        names: The popups to capture, in order.
        out: The run's folder; the captures go in ``out/<size_name>/``.
        profile: The scratch profile to boot from.

    Returns:
        The captures, in order.

    Raises:
        DriverError: If the app does not boot, or does not answer a request in time.

    """
    shots_dir = out / size_name
    shots_dir.mkdir(parents=True, exist_ok=True)
    request_file = out / "popup-request"
    os.environ.update(
        {
            CONFIG_DIR_ENV_VAR: str(profile),
            POPUP_GALLERY_ENV_VAR: str(request_file),
            "BARKS_PROBE_HEADLESS": "1",
            "BARKS_PROBE_SCREEN": SIZES[size_name],
        }
    )
    _say(f"{size_name} ({SIZES[size_name]}): booting the app...")
    probe("start")
    shots: list[Path] = []
    try:
        driver = Driver(paced=False)
        for index, name in enumerate(names, start=1):
            request = f"{size_name}-{index}"
            shown = log_markers.pattern(log_markers.POPUP_GALLERY_SHOWN, request=request, name=name)
            with driver.expect(shown, SHOWN_TIMEOUT):
                write_request(request_file, request, name)
            driver.settle()
            shot = driver.frame_capture(shots_dir / shot_name(index, name), f"{request}-frame")
            shots.append(shot)
            _say(f"  {shot.name}")
    finally:
        probe("stop")
    return shots


def _wait_for_x_server(display: str, timeout: float = 10) -> None:
    socket = Path("/tmp/.X11-unix") / f"X{display.lstrip(':')}"  # noqa: S108  (X's own path)
    deadline = time.monotonic() + timeout
    while not socket.exists():
        if time.monotonic() > deadline:
            msg = f"Xvfb never came up on {display}"
            raise DriverError(msg)
        time.sleep(0.1)


def find_top_window(xwininfo_children: str) -> tuple[int, int, int, int] | None:
    """Return the first top-level window big enough to be a popup, as (w, h, x, y).

    Args:
        xwininfo_children: What ``xwininfo -root -children`` printed.

    Returns:
        The window's size and position, or None if there is none yet.

    """
    for line in xwininfo_children.splitlines():
        found = _WINDOW_RE.search(line)
        if not found:
            continue
        width, height, x, y = (int(g) for g in found.groups())
        if width >= _MIN_WINDOW_SIDE and height >= _MIN_WINDOW_SIDE:
            return width, height, x, y
    return None


def preview_command(name: str) -> list[str]:
    """Return the command that runs own-window popup `name`'s preview.

    Args:
        name: A key of `OWN_WINDOW`.

    Returns:
        The command, run from the repo's root.

    """
    return [
        "uv",
        "run",
        "--env-file",
        ".env.runtime",
        "python",
        "-c",
        _PREVIEW_LAUNCHER,
        *OWN_WINDOW[name],
    ]


def capture_own_window(name: str, out: Path, profile: Path) -> Path:
    """Run one own-window popup's preview on a private Xvfb and capture its window.

    Args:
        name: A key of `OWN_WINDOW`.
        out: The run's folder; the capture goes in ``out/own-window/``.
        profile: The scratch profile, so nothing the preview writes reaches the live one.

    Returns:
        The capture.

    Raises:
        DriverError: If the window never appears.

    """
    shots_dir = out / "own-window"
    shots_dir.mkdir(parents=True, exist_ok=True)
    display = OWN_WINDOW_DISPLAY
    env = {**os.environ, "DISPLAY": display, CONFIG_DIR_ENV_VAR: str(profile)}
    xvfb = subprocess.Popen(  # noqa: S603
        ["Xvfb", display, "-screen", "0", f"{OWN_WINDOW_SCREEN}x24", "-nolisten", "tcp"],  # noqa: S607
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    log = shots_dir / f"{name}.log"
    try:
        _wait_for_x_server(display)
        with log.open("w", encoding="utf-8") as log_file:
            popup = subprocess.Popen(  # noqa: S603
                preview_command(name),
                cwd=REPO_ROOT,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        try:
            geometry = None
            deadline = time.monotonic() + OWN_WINDOW_TIMEOUT
            while geometry is None:
                if popup.poll() is not None or time.monotonic() > deadline:
                    msg = f"{name}: no window appeared; see {log}"
                    raise DriverError(msg)
                time.sleep(0.5)
                listing = subprocess.run(  # noqa: S603
                    ["xwininfo", "-display", display, "-root", "-children"],  # noqa: S607
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout
                geometry = find_top_window(listing)
            time.sleep(OWN_WINDOW_SETTLE_SECS)
            width, height, x, y = geometry
            shot = shots_dir / f"{name}.png"
            subprocess.run(  # noqa: S603
                [  # noqa: S607
                    "import",
                    "-display",
                    display,
                    "-window",
                    "root",
                    "-crop",
                    f"{width}x{height}+{x}+{y}",
                    "+repage",
                    str(shot),
                ],
                check=True,
            )
            _say(f"  {shot.name}")
            return shot
        finally:
            _stop_group(popup)
    finally:
        _stop_group(xvfb)


def capture_own_windows(names: Sequence[str], out: Path, profile: Path) -> list[str]:
    """Capture each own-window popup and make their sheet; one failing leaves the rest.

    Args:
        names: Keys of `OWN_WINDOW`.
        out: The run's folder.
        profile: The scratch profile.

    Returns:
        The names not captured.

    """
    _say("Own-window popups:")
    shots: list[Path] = []
    failed: list[str] = []
    for name in names:
        try:
            shots.append(capture_own_window(name, out, profile))
        except DriverError as error:
            _say(f"  FAILED {error}")
            failed.append(name)
    if shots:
        _montage(shots, out / "own-window-sheet.png", "own window")
    return failed


def _stop_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        os.killpg(process.pid, signal.SIGKILL)


def run_live(out: Path) -> int:
    """Run the real app on this screen with the live gallery, from a scratch profile."""
    profile = make_scratch_profile(live_profile_dir(), out / "profile", debug=False)
    env = {
        **os.environ,
        CONFIG_DIR_ENV_VAR: str(profile),
        POPUP_GALLERY_ENV_VAR: LIVE_MODE,
        "BARKS_READER_NO_SCREEN_WARNING": "1",
    }
    _say(f"Live popup gallery, {len(POPUP_NAMES)} popups: Page Down and Page Up step.")
    _say(f"Profile: {profile} (a copy; the live one is not touched).")
    return subprocess.run(  # noqa: S603
        ["uv", "run", "--directory", str(REPO_ROOT), "main.py"],  # noqa: S607
        env=env,
        check=False,
    ).returncode


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="list the popups and exit")
    parser.add_argument("--only", default="", help="comma-separated popup names to capture")
    parser.add_argument(
        "--sizes",
        default=",".join(SIZES),
        help=f"comma-separated screen sizes ({', '.join(SIZES)})",
    )
    parser.add_argument("--no-own-window", action="store_true", help="skip the own-window popups")
    parser.add_argument("--live", action="store_true", help="step through them in the real app")
    parser.add_argument("--out", type=Path, default=None, help="the run's folder")
    return parser.parse_args(argv)


def select(only: str, available: Sequence[str]) -> list[str]:
    """Return the names `only` picks out of `available`, in `available`'s order.

    Args:
        only: Comma-separated names, or "" for every one.
        available: Every name there is.

    Returns:
        The names picked.

    Raises:
        SystemExit: If `only` names one that is not there.

    """
    if not only:
        return list(available)
    wanted = [name.strip() for name in only.split(",") if name.strip()]
    unknown = [name for name in wanted if name not in available]
    if unknown:
        msg = f"no such popup or size: {', '.join(unknown)} (see --list)"
        raise SystemExit(msg)
    return [name for name in available if name in wanted]


def main(argv: Sequence[str] | None = None) -> int:
    """Capture the popups (or run the live gallery) and say where the results are."""
    args = _parse_args(argv)
    if args.list:
        _say("In the app:")
        _say("\n".join(f"  {name}" for name in POPUP_NAMES))
        _say("In their own window:")
        _say("\n".join(f"  {name}" for name in OWN_WINDOW))
        return 0
    out: Path = args.out or DEFAULT_OUT / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")  # noqa: DTZ005
    out.mkdir(parents=True, exist_ok=True)
    if args.live:
        return run_live(out)

    picked = select(args.only, [*POPUP_NAMES, *OWN_WINDOW])
    in_app = [name for name in picked if name in POPUP_NAMES]
    own = [name for name in picked if name in OWN_WINDOW and not args.no_own_window]
    sizes = select(args.sizes, list(SIZES))

    # A terminal closing or a kill still stops the app and the X servers (the finally
    # blocks run on SystemExit).
    def _exit_on_signal(sig: int, _frame: FrameType | None) -> None:
        raise SystemExit(128 + sig)

    signal.signal(signal.SIGTERM, _exit_on_signal)
    signal.signal(signal.SIGHUP, _exit_on_signal)

    profile = make_scratch_profile(live_profile_dir(), out / "profile")
    _say(f"Popup gallery into {out}")
    if in_app:
        for size_name in sizes:
            shots = capture_size(size_name, in_app, out, profile)
            _montage(shots, out / f"{size_name}-sheet.png", f"{size_name} {SIZES[size_name]}")
    failed = capture_own_windows(own, out, profile) if own else []
    if failed:
        _say(f"Done, {len(failed)} not captured ({', '.join(failed)}): {out}")
        return 1
    _say(f"Done: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
