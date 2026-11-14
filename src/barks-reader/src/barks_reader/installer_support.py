"""What the first-run installer and the data pack installer share: the packs' layout."""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING
from zipfile import ZipFile

from loguru import logger

from barks_reader.core import data_pack
from barks_reader.core.data_pack import DATA_PACK_FILE_NAMES
from barks_reader.core.reader_utils import quote_and_join_with_and

if TYPE_CHECKING:
    from collections.abc import Callable, Collection
    from pathlib import Path

    from barks_reader.core.data_pack import DataPackInfo

# The two top-level folders inside the packs (build-data-zips.sh).
ZIP_CONFIGS_SUBDIR = "Configs/"
ZIP_READER_FILES_SUBDIR = "Reader Files/"

# How much of a file is copied at a time: small enough for a progress bar to move
# through the panels zip, large enough not to slow the copy.
_COPY_CHUNK_BYTES = 1024 * 1024


class InstallerDataError(Exception):
    """What is on disk is not what the installer expects, and it can say what.

    Raised for a problem the installer can name, mostly one a user can fix themselves (a
    re-zipped data pack, a renamed executable, an unreadable config), as opposed to an
    error nobody foresaw. An installer's ``main`` shows ``message`` and ``details`` in
    its error popup instead of a raw traceback.
    """

    def __init__(self, message: str, details: str) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


def subdir_bytes(installer_zip: Path, subdir: str) -> int:
    """Return how many bytes ``extract_subdir`` writes for ``subdir`` in ``installer_zip``."""
    with ZipFile(installer_zip, "r") as installer_files:
        return sum(
            member.file_size
            for member in installer_files.infolist()
            if not member.is_dir() and member.filename.startswith(subdir)
        )


def extract_subdir(
    installer_zip: Path,
    subdir: str,
    extract_to_dir: Path,
    on_bytes: Callable[[int], None] | None = None,
    skip: Collection[str] = (),
) -> int:
    """Extract every file under ``subdir`` in ``installer_zip`` into ``extract_to_dir``.

    Args:
        installer_zip: The data pack.
        subdir: The pack's top-level folder to extract, with its trailing slash.
        extract_to_dir: Where its files go, at their paths under ``subdir``.
        on_bytes: Called with the size of each piece as it is written, for a progress
            bar (``subdir_bytes`` is their total).
        skip: Paths under ``subdir`` to leave in the pack.

    Returns:
        The number of files extracted.

    Raises:
        InstallerDataError: No zip entry starts with ``subdir`` - the usual cause is a
            data pack that was unzipped and re-zipped (e.g. by Safari + Finder), which
            nests the contents one folder deeper. Or an entry's name would put its file
            outside ``extract_to_dir``; nothing is then extracted.

    """
    num_extracted = 0
    # Resolved, so a symlinked folder compares as the folder its files land in.
    destination = extract_to_dir.resolve()
    with ZipFile(installer_zip, "r") as installer_files:
        # Zip member names use "/" on every platform, so the prefix test holds on Windows.
        members = [
            member
            for member in installer_files.infolist()
            if not member.is_dir() and member.filename.startswith(subdir)
        ]
        if not members:
            raise _no_subdir_error(installer_zip, subdir, installer_files)

        # Every name is checked before any file is written. A name is not to be
        # trusted: ".." parts, a leading "/" or a drive letter would each put the file
        # somewhere else (`ZipFile.extract` strips these; writing by hand does not).
        targets = []
        for member in members:
            # Create the new path by stripping the subdir prefix.
            relative_path = member.filename.removeprefix(subdir)
            if relative_path in skip:
                continue
            target_path = extract_to_dir / relative_path
            if not target_path.resolve().is_relative_to(destination):
                raise _outside_destination_error(installer_zip, member.filename)
            targets.append((member, target_path))

        for member, target_path in targets:
            num_extracted += 1

            # Ensure the parent directory exists.
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Stream the member out: the panels zip alone is over a gigabyte, and reading
            # it whole would need that much memory on the user's machine.
            with installer_files.open(member) as source, target_path.open("wb") as target:
                while chunk := source.read(_COPY_CHUNK_BYTES):
                    target.write(chunk)
                    if on_bytes is not None:
                        on_bytes(len(chunk))

    logger.info(f'Extracted {num_extracted} files from "{subdir}" to "{extract_to_dir}".')
    return num_extracted


def require_subdir(installer_zip: Path, subdir: str) -> None:
    """Check that ``installer_zip`` has ``subdir`` at its top level.

    Args:
        installer_zip: The data pack.
        subdir: The top-level folder it should hold, with its trailing slash.

    Raises:
        InstallerDataError: No zip entry starts with ``subdir`` (a re-zipped pack).

    """
    with ZipFile(installer_zip, "r") as installer_files:
        if not any(name.startswith(subdir) for name in installer_files.namelist()):
            raise _no_subdir_error(installer_zip, subdir, installer_files)


def read_member(installer_zip: Path, member: str) -> bytes:
    """Return one file of ``installer_zip``, without extracting it.

    Args:
        installer_zip: The data pack.
        member: The file's path inside the pack.

    Returns:
        The file's bytes.

    Raises:
        InstallerDataError: The pack has no such file.

    """
    with ZipFile(installer_zip, "r") as installer_files:
        try:
            return installer_files.read(member)
        except KeyError:
            msg = f'The installer data pack has no "{member}":\n\n[b]"{installer_zip}".[/b]'
            details = (
                "The file is part of every Barks Reader data pack, so this pack is not a"
                " complete one. Download the original data pack again."
            )
            raise InstallerDataError(msg, details) from None


def _outside_destination_error(installer_zip: Path, member: str) -> Exception:
    msg = (
        f"The installer data pack holds a file that would be written outside the"
        f' folder it is installed in:\n\n[b]"{installer_zip}".[/b]'
    )
    details = (
        f'The file is "{member}". No Barks Reader data pack holds such a name, so this'
        f" pack is not one of ours as it was published. Nothing was extracted from it."
        f" Download the original data pack again."
    )
    return InstallerDataError(msg, details)


def _no_subdir_error(installer_zip: Path, subdir: str, installer_files: ZipFile) -> Exception:
    top_level = sorted({name.split("/")[0] for name in installer_files.namelist()})
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
    return InstallerDataError(msg, details)


def install_reader_files(
    pack: DataPackInfo,
    pack_dir: Path,
    reader_files: Path,
    on_bytes: Callable[[int], None] | None = None,
) -> None:
    """Put the packs' Reader Files in place of ``reader_files``: both installers' one routine.

    Both packs are extracted into the ``.new`` folder beside ``reader_files`` and checked
    against the version they claimed; only then are the folders swapped and the replaced
    one removed. Until the swap, a folder already installed is as it was, and one not yet
    installed does not exist: a failure, or a killed process, leaves no half-made folder
    under the installed name.

    Args:
        pack: The version both packs carry (`data_pack.find_update` checked they agree).
        pack_dir: The folder holding the two packs.
        reader_files: The Reader Files folder to install or replace.
        on_bytes: Called with the size of each piece as it is written, for a progress bar.

    Raises:
        InstallerDataError: What was extracted is not what the packs promised, or the
            folders could not be swapped. The ``.new`` folder has been removed.

    """
    left_alone = "The installed data was left as it was. " if reader_files.exists() else ""
    data_pack.clear_leftovers(reader_files)
    new_dir = data_pack.new_dir_for(reader_files)
    try:
        for pack_name in DATA_PACK_FILE_NAMES:
            extract_subdir(pack_dir / pack_name, ZIP_READER_FILES_SUBDIR, new_dir, on_bytes)
        _verify_and_swap(pack, new_dir, reader_files, left_alone)
    except BaseException:
        shutil.rmtree(new_dir, ignore_errors=True)
        raise


def _verify_and_swap(
    pack: DataPackInfo, new_dir: Path, reader_files: Path, left_alone: str
) -> None:
    problems = data_pack.verify_extracted(new_dir, pack)
    if problems:
        msg = f"The extracted {pack.short()} is not what its packs promised."
        details = (
            "\n".join(problems) + f"\n\n{left_alone}Download both packs again and"
            " check them against the release's SHA256SUMS.txt."
        )
        raise InstallerDataError(msg, details)

    try:
        old_dir = data_pack.swap_reader_files(reader_files)
    except data_pack.ReaderFilesStrandedError as exc:
        msg = (
            f"The new data could not be moved in, and the installed data could not be put"
            f' back: it is in [b]"{exc.old_dir}"[/b].'
        )
        details = (
            f"{exc}\n\nClose the Barks Reader, and any window showing those folders, and"
            f' run the update again: it puts "{exc.old_dir.name}" back first. Or rename'
            f' that folder to "{reader_files.name}" yourself.'
        )
        raise InstallerDataError(msg, details) from exc
    except OSError as exc:
        msg = (
            f'The folder [b]"{reader_files}"[/b] is in use, so the new data could not be moved in.'
        )
        details = (
            f"{exc}\n\nClose the Barks Reader, and any window showing that folder, and"
            f" try again. {left_alone}".rstrip()
        )
        raise InstallerDataError(msg, details) from exc

    if old_dir is not None:
        shutil.rmtree(old_dir, ignore_errors=True)
        if old_dir.exists():
            logger.warning(f'Could not remove "{old_dir}"; the next update will.')
