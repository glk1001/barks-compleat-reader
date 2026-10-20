"""Whether the Fantagraphics library is there to read from, and what to tell the user. Kivy-free.

The app stays browsable without the library (the bundled override and extra pages
still read); a misconfigured one blocks reading until it is fixed and the app restarted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from barks_fantagraphics.fanta_comics_info import NUM_VOLUMES

from .fantagraphics_volumes import (
    DuplicateArchiveFilesError,
    MissingArchiveFilesError,
    TooManyArchiveFilesError,
)
from .reader_settings import UNSET_FANTA_DIR_MARKER
from .user_error_types import ErrorInfo, ErrorTypes

if TYPE_CHECKING:
    from pathlib import Path


class FantaVolumesState(Enum):
    """What was found of the Fantagraphics volumes."""

    VOLUMES_EXIST = auto()
    ALL_VOLUMES_MISSING = auto()
    SOME_VOLUMES_MISSING = auto()
    VOLUMES_NOT_SET = auto()
    VOLUMES_TOO_MANY = auto()
    DUPLICATE_VOLUMES = auto()
    VOLUMES_NOT_NEEDED = auto()


# No usable library, but the app stays fully browsable: show a single startup notice and
# still build the bundled override/extra pages, so the restored censored stories read.
# (VOLUMES_EXIST / SOME_VOLUMES_MISSING / VOLUMES_NOT_NEEDED are the ordinary ready states.)
NO_LIBRARY_STATES = frozenset(
    {
        FantaVolumesState.VOLUMES_NOT_SET,
        FantaVolumesState.ALL_VOLUMES_MISSING,
    }
)
# Misconfiguration the user must fix and restart; reading is blocked with a popup.
BAD_STATES = frozenset(
    {
        FantaVolumesState.VOLUMES_TOO_MANY,
        FantaVolumesState.DUPLICATE_VOLUMES,
    }
)

# Why a state is bad or has no library, and the error to tell the user with.
STATE_ERRORS: dict[FantaVolumesState, tuple[str, ErrorTypes]] = {
    FantaVolumesState.VOLUMES_NOT_SET: (
        "Fantagraphics Directory Not Set",
        ErrorTypes.FantagraphicsVolumeRootNotSet,
    ),
    FantaVolumesState.ALL_VOLUMES_MISSING: (
        "Fantagraphics Directory Not Found",
        ErrorTypes.FantagraphicsVolumeRootNotFound,
    ),
    FantaVolumesState.VOLUMES_TOO_MANY: (
        "Too Many Archive Files in Fantagraphics Directory",
        ErrorTypes.TooManyVolumeArchiveFiles,
    ),
    FantaVolumesState.DUPLICATE_VOLUMES: (
        "Duplicate Archive Files in Fantagraphics Directory",
        ErrorTypes.DuplicateVolumeArchiveFiles,
    ),
}


def post_build_state(*, use_prebuilt_archives: bool, volumes_dir: Path) -> FantaVolumesState:
    """Return what the settings say of the volumes before any archive is opened.

    Args:
        use_prebuilt_archives: Whether the reader reads prebuilt comics, needing no volumes.
        volumes_dir: The Fantagraphics volumes folder setting.

    Returns:
        Not needed, not set, a folder that is not there, or volumes to look in.

    """
    if use_prebuilt_archives:
        return FantaVolumesState.VOLUMES_NOT_NEEDED
    if str(volumes_dir) == UNSET_FANTA_DIR_MARKER:
        return FantaVolumesState.VOLUMES_NOT_SET
    if not volumes_dir.is_dir():
        return FantaVolumesState.ALL_VOLUMES_MISSING
    return FantaVolumesState.VOLUMES_EXIST


def no_library_error_type(state: FantaVolumesState) -> ErrorTypes:
    """Return the notice for a missing library: the unset setting, or a folder with no volumes."""
    return STATE_ERRORS[state][1]


class LibraryNotice(Enum):
    """What the user is told when the volumes cannot all be opened."""

    NONE = auto()  # a notice was already shown
    NO_LIBRARY = auto()  # one browsable notice: the folder holds no volumes at all
    ERROR = auto()  # the error's own popup, which sets the "files not loaded" overlay


@dataclass(frozen=True, slots=True)
class LibraryCheck:
    """The outcome of opening the volumes: the state, what to say, and whether to go on.

    Attributes:
        state: What was found.
        error_info: The error's details for its popup.
        notice: What to tell the user.
        error_type: The error the notice is about; None when there is no notice.
        readable: Whether the app goes on to read: a partial library does, a
            misconfigured one does not.

    """

    state: FantaVolumesState
    error_info: ErrorInfo
    notice: LibraryNotice
    error_type: ErrorTypes | None
    readable: bool


def check_library_error(
    error: TooManyArchiveFilesError | DuplicateArchiveFilesError | MissingArchiveFilesError,
    *,
    library_notice_shown: bool,
) -> LibraryCheck:
    """Return what to do about an error opening the volumes.

    Args:
        error: The error the volumes raised.
        library_notice_shown: Whether the one-time no-library notice was shown up front
            (an unset or non-existent folder), so missing volumes get no second one.

    Returns:
        The check: too many or duplicate archives block reading with their popup; missing
        volumes let reading go on, with one no-library notice when none is there, the
        per-volume popup when some are, and nothing when a notice was already shown.

    """
    if isinstance(error, TooManyArchiveFilesError):
        return LibraryCheck(
            FantaVolumesState.VOLUMES_TOO_MANY,
            ErrorInfo(num_volumes=error.num_volumes, num_archive_files=error.num_archive_files),
            LibraryNotice.ERROR,
            ErrorTypes.TooManyVolumeArchiveFiles,
            readable=False,
        )
    if isinstance(error, DuplicateArchiveFilesError):
        return LibraryCheck(
            FantaVolumesState.DUPLICATE_VOLUMES,
            ErrorInfo(file=str(error.archive_root), duplicate_volumes=error.duplicates),
            LibraryNotice.ERROR,
            ErrorTypes.DuplicateVolumeArchiveFiles,
            readable=False,
        )
    error_info = ErrorInfo(missing_volumes=error.missing_file_vols)
    if library_notice_shown:
        notice, error_type = LibraryNotice.NONE, None
    elif len(error.missing_file_vols) >= NUM_VOLUMES:
        notice, error_type = LibraryNotice.NO_LIBRARY, ErrorTypes.FantagraphicsVolumeRootNotFound
    else:
        notice, error_type = LibraryNotice.ERROR, ErrorTypes.MissingArchiveVolumes
    return LibraryCheck(
        FantaVolumesState.SOME_VOLUMES_MISSING, error_info, notice, error_type, readable=True
    )
