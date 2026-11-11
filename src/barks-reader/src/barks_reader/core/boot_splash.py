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


def close_boot_splash() -> None:
    """Take the splash down, if one is up. Safe to call again, and anywhere.

    A splash that cannot be taken down is logged and left: it goes when the app ends.
    """
    splash_file = boot_splash_file()
    if splash_file is None:
        return

    try:
        splash_file.unlink()
    except FileNotFoundError:
        return
    except OSError as e:
        logger.warning(f'Could not take down the boot splash "{splash_file}": {e}')
        return

    logger.info("Took down the boot splash.")
