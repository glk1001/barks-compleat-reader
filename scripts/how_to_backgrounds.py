"""The art behind each of the how-to's pages, and where it is on this machine.

The backgrounds are not in the repo: each is a page of extra art already in a
volume's directory of fixes (``Fantagraphics-fixes-and-additions``), named here by
its volume and file. ``generate_how_to_pages.py`` lays the text over them and
``generated_files.py`` records their hashes, so the pages are reported stale when one
changes. Kept apart from the generator so that the record's check need not import
WeasyPrint, which only a Linux machine is sure to have.

To use other art, or to give a longer how-to another page, edit ``HOW_TO_BACKGROUNDS``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_fantagraphics.comics_consts import BARKS_ROOT_DIR
from barks_fantagraphics.comics_database import ComicsDatabase

if TYPE_CHECKING:
    from pathlib import Path

# One per page, in page order: the Fantagraphics volume and the file in its fixes'
# images directory. Each is stretched to the stylesheet's page size.
HOW_TO_BACKGROUNDS: tuple[tuple[int, str], ...] = (
    (7, "244.jpg"),
    (7, "242.jpg"),
    (9, "217.jpg"),
    (7, "243.jpg"),
    (8, "224.jpg"),
    (9, "216.jpg"),
    (7, "247.jpg"),
)


def fixes_root_dir() -> Path:
    """Return the directory holding every volume's fixes, which a machine may lack."""
    return ComicsDatabase(for_building_comics=False).get_fantagraphics_fixes_root_dir()


def how_to_background_paths() -> list[Path]:
    """Return the how-to's backgrounds on this machine, in page order."""
    database = ComicsDatabase(for_building_comics=False)
    return [
        database.get_fantagraphics_fixes_volume_image_dir(volume) / file_name
        for volume, file_name in HOW_TO_BACKGROUNDS
    ]


def how_to_backgrounds_by_name() -> dict[str, Path]:
    """Return the how-to's backgrounds under the names the record gives them.

    A name is the file's path from the Barks root, with forward slashes: the same on
    every machine, wherever its home directory is.
    """
    return {path.relative_to(BARKS_ROOT_DIR).as_posix(): path for path in how_to_background_paths()}
