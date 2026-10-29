"""What the first-run installer and the data pack installer share: the packs' layout."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING
from zipfile import ZipFile

from loguru import logger

from barks_reader.core.reader_utils import quote_and_join_with_and

if TYPE_CHECKING:
    from pathlib import Path

# The two top-level folders inside the packs (build-data-zips.sh).
ZIP_CONFIGS_SUBDIR = "Configs/"
ZIP_READER_FILES_SUBDIR = "Reader Files/"


class InstallerDataError(Exception):
    """The installer data on disk is not what the installer expects.

    Raised for problems a user can fix themselves (a re-zipped data pack, an unreadable
    config), as opposed to programming errors. An installer's ``main`` shows ``message``
    and ``details`` in its error popup instead of a raw traceback.
    """

    def __init__(self, message: str, details: str) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


def extract_subdir(installer_zip: Path, subdir: str, extract_to_dir: Path) -> int:
    """Extract every file under ``subdir`` in ``installer_zip`` into ``extract_to_dir``.

    Returns the number of files extracted. Raises ``InstallerDataError`` if no zip entry
    starts with ``subdir`` - the usual cause is a data pack that was unzipped and
    re-zipped (e.g. by Safari + Finder), which nests the contents one folder deeper.
    """
    num_extracted = 0
    with ZipFile(installer_zip, "r") as installer_files:
        for member in installer_files.infolist():
            # TODO: Does this work with Windows????
            if member.is_dir() or not member.filename.startswith(subdir):
                continue
            num_extracted += 1

            # Create the new path by stripping the subdir prefix.
            relative_path = member.filename.removeprefix(subdir)
            target_path = extract_to_dir / relative_path

            # Ensure the parent directory exists.
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Stream the member out: the panels zip alone is over a gigabyte, and reading
            # it whole would need that much memory on the user's machine.
            with installer_files.open(member) as source, target_path.open("wb") as target:
                shutil.copyfileobj(source, target)

        if num_extracted == 0:
            top_level = sorted({m.filename.split("/")[0] for m in installer_files.infolist()})
            msg = (
                f'The installer data pack has no "{subdir}" folder at its top level:'
                f'\n\n[b]"{installer_zip}".[/b]'
            )
            details = (
                f'Expected a top-level "{subdir}" folder but the data pack contains'
                f" {quote_and_join_with_and(top_level)}.\n\nThis usually means the data"
                f" pack was unzipped and then re-zipped, which puts everything inside an"
                f" extra folder. Download the original data pack again, or re-zip from"
                f' inside the unzipped folder so that "{subdir}" is at the top level.'
            )
            raise InstallerDataError(msg, details)

    logger.info(f'Extracted {num_extracted} files from "{subdir}" to "{extract_to_dir}".')
    return num_extracted
