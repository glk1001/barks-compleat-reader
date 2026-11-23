"""Where the folder chooser's Left key goes: up a folder, or on to the next drive.

Left opens the parent of the folder listed. The top of a Windows drive has none, and
Kivy lists no "../" entry there, so the remote's six keys could not leave the drive
the chooser opened on, with the comics on another. Left there opens the next drive
instead, and from the last the first again.
Kivy-free, and written over pure paths, so Windows' drives can be tested anywhere.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path, PurePath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# Shown in the chooser where there is more than one drive: nothing else says it.
NEXT_DRIVE_HINT = "Left at the top of a drive opens the next drive."


def drives() -> list[Path]:
    """Return the top folder of each drive Windows has; none on any other system."""
    if sys.platform == "win32":
        return [Path(drive) for drive in os.listdrives()]
    return []


def folders_left_of[P: PurePath](folder: P, all_drives: Sequence[P]) -> list[P]:
    """Return the folders Left may open from `folder`, the first that lists being the one.

    Args:
        folder: The folder the chooser lists.
        all_drives: The top folder of each drive (`drives`), in their order.

    Returns:
        The folder's parent alone; or, from a folder with none (a drive's top, a
        share's), the other drives in turn, those after it first and then round from
        the first, so that a drive that cannot be listed (no disc in it) is passed
        over. With no other drive, the folder itself, as Left has always opened.

    """
    if folder.parent != folder:
        return [folder.parent]
    at = all_drives.index(folder) if folder in all_drives else -1
    in_turn = [*all_drives[at + 1 :], *all_drives[: max(at, 0)]]
    return in_turn or [folder]
