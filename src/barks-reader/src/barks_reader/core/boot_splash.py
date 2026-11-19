"""The picture the Windows build shows while it unpacks itself, and how it is taken down.

The Windows executable is one file that unpacks itself before any Python runs
(`--onefile-windows-splash-screen-image` in `scripts/build.sh`). The small program
that does the unpacking puts the picture up, and takes it down when a file it made
in the temp folder is deleted, or when the app it started ends. The app deletes
that file when its own first window is about to show.

Nothing here is true of a development checkout, or of the Linux and macOS builds:
there is no such file, and closing the splash does nothing.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from loguru import logger

# The process id of the program that unpacked the app, set by it for the app.
_ONEFILE_PARENT_ENV = "NUITKA_ONEFILE_PARENT"

# Where Windows looks for the temp folder, in its order. The unpacking program asks
# Windows (GetTempPathW); Python's own lookup puts TMPDIR first, then TEMP, then TMP.
_WINDOWS_TEMP_ENVS = ("TMP", "TEMP")

# The unpacking programs (by process id) whose splash is down, or was looked for and
# not found: neither is looked into again in the log.
_settled: set[str] = set()


def boot_splash_file() -> Path | None:
    """Return the file whose deletion takes the splash down, or None when there is none.

    Returns:
        The path the unpacking program watches (it may already be gone), or None
        when this process was not started by one.

    """
    parent_pid = os.environ.get(_ONEFILE_PARENT_ENV, "")
    if not parent_pid.isdecimal():
        return None

    return Path(tempfile.gettempdir()) / f"onefile_{parent_pid}_splash_feedback.tmp"


def _boot_splash_files() -> list[Path]:
    """Return every place the unpacking program may have made the file, likeliest first.

    Python's temp folder, then the ones Windows would choose: they differ when TMP and
    TEMP do, or when TMPDIR is set, and the splash then
    stayed up over the reader for the whole session, with nothing in the log.
    """
    splash_file = boot_splash_file()
    if splash_file is None:
        return []

    files = [splash_file]
    for name in _WINDOWS_TEMP_ENVS:
        folder = os.environ.get(name)
        if folder and Path(folder) / splash_file.name not in files:
            files.append(Path(folder) / splash_file.name)
    return files


def close_boot_splash() -> None:
    """Take the splash down, if one is up. Safe to call again, and anywhere.

    A splash that cannot be taken down is logged and left: it goes when the app ends.
    So is the first look that finds no file: no splash was up (the Linux and macOS
    builds have none), or the file is somewhere this does not look.
    """
    splash_files = _boot_splash_files()
    if not splash_files:
        return
    parent_pid = os.environ.get(_ONEFILE_PARENT_ENV, "")

    for splash_file in splash_files:
        try:
            splash_file.unlink()
        except FileNotFoundError:
            continue
        except OSError as e:
            logger.warning(f'Could not take down the boot splash "{splash_file}": {e}')
            return

        logger.info("Took down the boot splash.")
        _settled.add(parent_pid)
        return

    if parent_pid not in _settled:
        _settled.add(parent_pid)
        folders = ", ".join(f'"{splash_file.parent}"' for splash_file in splash_files)
        logger.debug(
            f"No boot splash file to delete in {folders}:"
            " no splash is up, or its file was made somewhere else."
        )
