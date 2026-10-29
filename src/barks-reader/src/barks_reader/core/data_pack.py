"""The data pack's version file, and the update an installed reader can take from new packs.

The two data packs (``barks-reader-data-1.barkspack`` and ``-2``) each carry
``Reader Files/data-pack.json``: the pack's version (the ``N`` of its ``data-vN``
release), when and where it was built, and a fingerprint of each Reader Files folder
it holds (``scripts/data_manifest.py`` writes it). The first-run installer extracts the
file with the rest of ``Reader Files``, so an installed reader reads its own version
from there; a reader installed from packs that predate the file is "not versioned".

An update is the same two packs, newer than the installed version, placed beside the
executable as for a first install. `find_update` says whether they are there and
usable; the reader offers to install them, then spawns itself with
`INSTALL_DATA_PACK_ARG` and exits (its open zip and index files must be closed before
the folders move), and that process extracts them into ``Reader Files.new``, swaps the
folders with `swap_reader_files`, and starts the reader again.

Stdlib and loguru only: this is ``core``, shared by the UI, the installers and the
scripts.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zipfile import BadZipFile, ZipFile

from loguru import logger

from .platform_info import PLATFORM, Platform
from .reader_settings import READER_FILES_DIR

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

DATA_PACK_FILE_NAME = "data-pack.json"
# The version file's path inside each pack (and under the installed Reader Files).
PACK_MEMBER = f"{READER_FILES_DIR}/{DATA_PACK_FILE_NAME}"
# The packs are plain zip archives. They deliberately do NOT carry a ".zip"
# extension: Safari auto-expands "safe" downloads (zip among them), which leaves the
# user with a folder instead of the pack the installer expects. An extension no app
# claims is left alone on every platform.
DATA_PACK_FILE_NAMES = ("barks-reader-data-1.barkspack", "barks-reader-data-2.barkspack")
# Names the folder holding the packs, in place of the executable's: a development run
# (nothing beside main.py) can then exercise the update offer with small test packs.
DATA_PACK_DIR_ENV_VAR = "BARKS_READER_DATA_PACK_DIR"
# argv sentinel the reader spawns itself with to run the data pack installer.
INSTALL_DATA_PACK_ARG = "--install-data-pack"
NEW_SUFFIX = ".new"
OLD_SUFFIX = ".old"

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_UNVERSIONED = "an unversioned data pack"


@dataclass(frozen=True)
class DataPackInfo:
    """What a data pack's version file says."""

    version: int
    tag: str
    built_at: datetime
    built_on: str
    entries: dict[str, dict[str, Any]]

    @classmethod
    def from_json(cls, text: str) -> DataPackInfo:
        """Parse a version file.

        Args:
            text: The file's JSON.

        Returns:
            Its contents.

        Raises:
            ValueError: The JSON is not a version file (a field missing or mistyped).

        """
        try:
            body = json.loads(text)
            version = body["version"]
            if not isinstance(version, int) or isinstance(version, bool):
                msg = f"version is not an integer: {version!r}"
                raise TypeError(msg)  # noqa: TRY301
            return cls(
                version=version,
                tag=str(body["tag"]),
                built_at=datetime.fromisoformat(body["built_at"]),
                built_on=str(body["built_on"]),
                entries=dict(body["entries"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            msg = f"not a data pack version file: {exc}"
            raise ValueError(msg) from exc

    def to_json(self) -> str:
        """Return the version file's text."""
        return pack_manifest_json(
            self.version, self.tag, self.built_at, self.built_on, self.entries
        )

    def display(self) -> str:
        """Return the pack as the About box names it: "Data pack 6 (29 Oct 2026)"."""
        built = self.built_at
        return f"Data pack {self.version} ({built.day} {_MONTHS[built.month - 1]} {built.year})"

    def short(self) -> str:
        """Return the pack as a message names it: "data pack 6"."""
        return f"data pack {self.version}"


def pack_manifest_json(
    version: int, tag: str, built_at: datetime, built_on: str, entries: dict[str, dict[str, Any]]
) -> str:
    """Return a version file's text; the one place its shape is written.

    Args:
        version: The pack's number, the N of its data-vN release.
        tag: That release's tag.
        built_at: When the pack was built.
        built_on: The host that built it.
        entries: Each Reader Files folder's fingerprint (files, bytes, md5), by name.

    """
    body = {
        "version": version,
        "tag": tag,
        "built_at": built_at.isoformat(timespec="seconds"),
        "built_on": built_on,
        "entries": entries,
    }
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def installed_version_text(info: DataPackInfo | None) -> str:
    """Return the About box's line for the installed pack."""
    return "Data pack: not versioned" if info is None else info.display()


def read_installed(reader_files_dir: Path) -> DataPackInfo | None:
    """Read the installed Reader Files' version file.

    Args:
        reader_files_dir: The installed Reader Files folder.

    Returns:
        Its version, or None when the folder has no (readable) version file: an
        install from packs that predate it, or a development checkout.

    """
    path = reader_files_dir / DATA_PACK_FILE_NAME
    try:
        return DataPackInfo.from_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning(f'Ignoring the data pack version file "{path}": {exc}')
        return None


def read_from_pack(zip_path: Path) -> DataPackInfo | None:
    """Read a pack's version file without extracting it.

    Only the zip's central directory and the small member are read, so this is cheap
    on a 1 GB pack.

    Args:
        zip_path: The pack.

    Returns:
        Its version, or None when it has no version file (a pack from before the file)
        or is not a zip at all.

    """
    try:
        with ZipFile(zip_path) as pack:
            return DataPackInfo.from_json(pack.read(PACK_MEMBER).decode("utf-8"))
    except (OSError, BadZipFile, KeyError, ValueError) as exc:
        logger.info(f'No data pack version in "{zip_path}": {exc}')
        return None


class UpdateStatus(Enum):
    """What `find_update` found beside the executable."""

    UPDATE_AVAILABLE = "update available"
    NO_PACK_DIR = "no folder to look in"
    PACKS_MISSING = "a pack is missing"
    PACKS_NOT_VERSIONED = "the packs carry no version"
    PACKS_DISAGREE = "the packs are different versions"
    NOT_NEWER = "the packs are not newer than the installed data"


@dataclass(frozen=True)
class UpdateCheck:
    """The result of looking for newer packs beside the executable."""

    status: UpdateStatus
    pack_dir: Path | None
    installed: DataPackInfo | None
    packs: tuple[DataPackInfo | None, ...] = ()
    missing: tuple[str, ...] = ()

    @property
    def available(self) -> DataPackInfo | None:
        """The pack version on offer, when there is one."""
        if self.status is not UpdateStatus.UPDATE_AVAILABLE:
            return None
        return self.packs[0]

    def offer_message(self) -> str:
        """Return the question the reader asks before installing the packs."""
        assert self.available is not None
        return (
            f"{self.available.display()} is beside the Barks Reader. Install it now?"
            f" The reader will close, install it, and start again."
        )

    def no_update_message(self) -> str:
        """Return why there is nothing to install, for the menu's message popup."""
        installed = _UNVERSIONED if self.installed is None else self.installed.short()
        match self.status:
            case UpdateStatus.NO_PACK_DIR:
                return (
                    "No folder to look in for data packs: this is a development run"
                    f" (set {DATA_PACK_DIR_ENV_VAR} to one)."
                )
            case UpdateStatus.PACKS_MISSING:
                names = " and ".join(f'"{name}"' for name in self.missing)
                return (
                    f"No newer data pack beside the Barks Reader (installed: {installed};"
                    f' looked in "{self.pack_dir}" and did not find {names}).'
                )
            case UpdateStatus.PACKS_NOT_VERSIONED:
                return (
                    f'The data packs in "{self.pack_dir}" carry no version: they are older'
                    f" than the first versioned pack. Download the current packs."
                )
            case UpdateStatus.PACKS_DISAGREE:
                versions = " and ".join(
                    _UNVERSIONED if pack is None else pack.short() for pack in self.packs
                )
                return (
                    f'The two data packs in "{self.pack_dir}" are different versions'
                    f" ({versions}): download both packs from the same release."
                )
            case UpdateStatus.NOT_NEWER:
                assert self.packs[0] is not None
                return (
                    f"No newer data pack beside the Barks Reader: the packs in"
                    f' "{self.pack_dir}" are {self.packs[0].short()}, and {installed} is'
                    f" installed."
                )
            case UpdateStatus.UPDATE_AVAILABLE:
                return ""


def pack_dir_for_update(exe_dir: Path, *, is_compiled: bool, env: Mapping[str, str]) -> Path | None:
    """Where to look for newer packs.

    Args:
        exe_dir: The folder beside the executable (`config_info.get_app_exe_dir`).
        is_compiled: Whether this is a standalone build.
        env: The process environment.

    Returns:
        The folder `DATA_PACK_DIR_ENV_VAR` names when it is set; else the executable's
        folder in a standalone build; else None - a development run has no packs
        beside ``main.py`` and never looks.

    """
    named = env.get(DATA_PACK_DIR_ENV_VAR, "")
    if named:
        return Path(named)
    return exe_dir if is_compiled else None


def find_update(pack_dir: Path | None, installed: DataPackInfo | None) -> UpdateCheck:
    """Look for packs newer than the installed data.

    Args:
        pack_dir: Where the packs would be, or None for nowhere.
        installed: The installed version, or None for an unversioned install - which
            any versioned pack is newer than.

    Returns:
        `UpdateStatus.UPDATE_AVAILABLE` when both packs are there, both carry the same
        version and it is newer; otherwise why not.

    """
    if pack_dir is None:
        return UpdateCheck(UpdateStatus.NO_PACK_DIR, None, installed)

    paths = [pack_dir / name for name in DATA_PACK_FILE_NAMES]
    missing = tuple(path.name for path in paths if not path.is_file())
    if missing:
        return UpdateCheck(UpdateStatus.PACKS_MISSING, pack_dir, installed, missing=missing)

    packs = tuple(read_from_pack(path) for path in paths)
    unversioned = tuple(path.name for path, pack in zip(paths, packs, strict=True) if pack is None)
    if unversioned:
        return UpdateCheck(
            UpdateStatus.PACKS_NOT_VERSIONED, pack_dir, installed, packs, missing=unversioned
        )

    versions = {pack.version for pack in packs if pack is not None}
    if len(versions) != 1:
        return UpdateCheck(UpdateStatus.PACKS_DISAGREE, pack_dir, installed, packs)

    installed_version = 0 if installed is None else installed.version
    if versions.pop() <= installed_version:
        return UpdateCheck(UpdateStatus.NOT_NEWER, pack_dir, installed, packs)

    return UpdateCheck(UpdateStatus.UPDATE_AVAILABLE, pack_dir, installed, packs)


def verify_extracted(new_dir: Path, expected: DataPackInfo) -> list[str]:
    """Check an extracted Reader Files folder against the pack's version file.

    Args:
        new_dir: The folder the packs were extracted into.
        expected: The version the packs claimed before extraction.

    Returns:
        What is wrong, one line each; empty when the folder holds the version file
        with that version and every folder it lists (a single file also at its size).
        Nothing is hashed: the panels zip alone is over a gigabyte.

    """
    problems = []
    found = read_installed(new_dir)
    if found is None:
        problems.append(f'no "{DATA_PACK_FILE_NAME}" was extracted')
    elif found.version != expected.version:
        problems.append(
            f'the extracted "{DATA_PACK_FILE_NAME}" is data pack {found.version},'
            f" not {expected.version}"
        )
    for name, fingerprint in expected.entries.items():
        path = new_dir / name
        if not path.exists():
            problems.append(f'"{name}" was not extracted')
        elif path.is_file() and path.stat().st_size != fingerprint.get("bytes"):
            problems.append(
                f'"{name}" is {path.stat().st_size:,} bytes, not the'
                f" {fingerprint.get('bytes'):,} the pack says"
            )
    return problems


def new_dir_for(reader_files_dir: Path) -> Path:
    """Return the folder the packs are extracted into before the swap."""
    return reader_files_dir.with_name(reader_files_dir.name + NEW_SUFFIX)


def old_dir_for(reader_files_dir: Path) -> Path:
    """Return the folder the replaced Reader Files wait in until they are removed."""
    return reader_files_dir.with_name(reader_files_dir.name + OLD_SUFFIX)


def clear_leftovers(reader_files_dir: Path) -> None:
    """Remove a ``.new`` or ``.old`` folder an earlier, interrupted update left behind."""
    for leftover in (new_dir_for(reader_files_dir), old_dir_for(reader_files_dir)):
        if leftover.exists():
            logger.warning(f'Removing the leftover folder "{leftover}".')
            shutil.rmtree(leftover, ignore_errors=True)


def swap_reader_files(
    reader_files_dir: Path,
    *,
    attempts: int = 30,
    delay: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
    rename: Callable[[Path, Path], object] = Path.rename,
) -> Path | None:
    """Put the ``.new`` folder in the installed folder's place.

    The installed folder goes to ``.old`` first and ``.new`` is renamed over its name. On
    Windows a rename fails with ``PermissionError`` while a process holds a file in the
    folder - the reader that spawned the installer, still closing - so each rename is
    retried. If the second rename fails anyway, the installed folder is put back.

    Args:
        reader_files_dir: The installed Reader Files folder.
        attempts: How many times to try each rename.
        delay: Seconds between tries.
        sleep: How to wait (a test passes a no-op).
        rename: How to rename (a test passes one that fails).

    Returns:
        The ``.old`` folder for the caller to remove, or None when there was no
        installed folder to move aside.

    Raises:
        PermissionError: A rename still failed after every attempt.

    """
    new_dir = new_dir_for(reader_files_dir)
    old_dir = old_dir_for(reader_files_dir)

    moved_aside = reader_files_dir.exists()
    if moved_aside:
        _rename_with_retries(reader_files_dir, old_dir, attempts, delay, sleep, rename)
    try:
        _rename_with_retries(new_dir, reader_files_dir, attempts, delay, sleep, rename)
    except PermissionError:
        if moved_aside:
            logger.error(f'Putting "{old_dir}" back as "{reader_files_dir}".')
            rename(old_dir, reader_files_dir)
        raise
    logger.info(f'Installed "{new_dir}" as "{reader_files_dir}".')
    return old_dir if moved_aside else None


def _rename_with_retries(
    source: Path,
    target: Path,
    attempts: int,
    delay: float,
    sleep: Callable[[float], None],
    rename: Callable[[Path, Path], object],
) -> None:
    for attempt in range(1, attempts + 1):
        try:
            rename(source, target)
        except PermissionError as exc:
            if attempt == attempts:
                raise
            logger.warning(
                f'Renaming "{source}" to "{target}" failed ({exc});'
                f" try {attempt} of {attempts}, waiting {delay}s."
            )
            sleep(delay)
        else:
            return


def self_command(*args: str, is_compiled: bool, argv0: str, executable: str) -> list[str]:
    """Return the command that runs this program again, with `args`.

    Args:
        args: Its arguments, such as `INSTALL_DATA_PACK_ARG`.
        is_compiled: Whether this is a standalone build - then ``sys.argv[0]`` is the
            executable; in a development checkout it is ``main.py``, run by the
            interpreter.
        argv0: ``sys.argv[0]``.
        executable: ``sys.executable``.

    """
    command = [argv0] if is_compiled else [executable, argv0]
    return [*command, *args]


def spawn_detached(argv: list[str]) -> None:
    """Start a process that outlives this one.

    Args:
        argv: The command, usually this executable (``sys.argv[0]``) and its arguments.

    """
    logger.info(f"Spawning detached process: {argv}.")
    if PLATFORM == Platform.WIN:
        # Its own console-less process group, so closing the reader's process does not
        # take it down. The flags exist on Windows only.
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        subprocess.Popen(argv, creationflags=flags, close_fds=True)  # noqa: S603
    else:
        subprocess.Popen(argv, start_new_session=True, close_fds=True)  # noqa: S603
