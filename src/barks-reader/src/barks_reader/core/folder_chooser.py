"""Where the folder chooser goes: the folder it opens on, and where its keys take it.

The chooser (``ui.settings_fix``) keeps the widgets; which folder it lists, for a
setting's value, a path typed in its box, or a key, is decided here.

Left opens the parent of the folder listed. The top of a Windows drive has none, and
Kivy lists no "../" entry there, so the remote's six keys could not leave the drive
the chooser opened on, with the comics on another. Left there opens the next drive
instead, and from the last the first again.
Kivy-free, and the drives written over pure paths, so Windows' can be tested anywhere.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path, PurePath
from typing import TYPE_CHECKING

from .focus_cursors import clamped

if TYPE_CHECKING:
    from collections.abc import Sequence

_SEPARATORS = "/\\"  # either system's
_SEPARATOR = re.compile(r"[/\\]")

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


def start_folder(value: str, home: Path) -> Path:
    """Return the folder the chooser opens on for a setting holding `value`.

    Args:
        value: The setting's value: a folder, or anything else (the marker of a
            setting not yet set).
        home: Where to open when the value names no real place.

    Returns:
        The parent of the setting's folder, so the folder is listed and can be
        selected; `home` for a value that is no full path (its parent is ".", the
        folder the app was started in) or whose parent is gone.

    """
    chosen = Path(value)
    return chosen.parent if chosen.is_absolute() and chosen.parent.is_dir() else home


def is_parent_entry(entry: str) -> bool:
    """Return whether a listed entry is the "../" row, which stands for the folder above.

    Kivy writes the row as the folder listed, "..", and a separator, either system's.
    """
    return _SEPARATOR.split(entry.rstrip(_SEPARATORS))[-1] == ".."


def folder_and_selection_for_typed(text: str) -> tuple[Path, Path] | None:
    """Return the folder to list and the entry to select for a path typed in the box.

    Args:
        text: What the box holds; "~" is the reader's home.

    Returns:
        A folder that exists is listed and selected; a path that does not, under a
        folder that does (a name half typed), has that folder listed. None when
        neither exists: the list stays where it is.

    """
    path = Path(text).expanduser()
    if path.is_dir():
        return path, path
    if path.parent.is_dir():
        return path.parent, path
    return None


def highlight_after(entries: Sequence[str], current: str | None, delta: int) -> int:
    """Return the index of the entry Up or Down moves the highlight to.

    Args:
        entries: The entries listed, in their order.
        current: The entry highlighted, or None.
        delta: The move: 1 down, -1 up.

    Returns:
        The index `delta` from the highlighted entry, held within the list; the
        first when nothing listed is highlighted.

    """
    index = entries.index(current) + delta if current in entries else 0
    return clamped(index, len(entries))
