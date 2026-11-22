"""The popup gallery's sample content, free of Kivy: what each popup is shown with.

Beside ``core.popup_gallery`` rather than in it: that module is the names and requests
``scripts/popup_gallery.py`` imports, and stays as light as that needs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.search_results import PageInfo, SpeechInfo, TitleInfo

from .data_pack import DataPackInfo, UpdateCheck, UpdateStatus
from .user_error_types import ErrorInfo, ErrorTypes


def _sample_pack(version: int, built_at: datetime) -> DataPackInfo:
    return DataPackInfo(version, f"data-v{version}", built_at, "gallery", {})


def sample_update_check(status: UpdateStatus) -> UpdateCheck:
    """Return a data pack check to show its popup with: pack 7 offered over pack 6.

    Args:
        status: What the check found, which picks the popup.

    Returns:
        The check, with one pack file missing for the popup that lists them.

    """
    installed = _sample_pack(6, datetime(2026, 10, 29, tzinfo=UTC))
    offered = _sample_pack(7, datetime(2026, 11, 14, tzinfo=UTC))
    return UpdateCheck(
        status,
        Path.home() / "Downloads",
        installed,
        packs=(offered, offered),
        missing=("barks-reader-data-2.barkspack",),
    )


def sample_title_speech() -> TitleInfo:
    """Return a story's speech found on three pages, to show the speech bubbles popup with."""

    def page(comic_page: str, *lines: str) -> PageInfo:
        speech = [
            SpeechInfo(str(group), group, text, text, speaker="donald")
            for group, text in enumerate(lines, start=1)
        ]
        return PageInfo(comic_page, speech)

    return TitleInfo(
        fanta_vol=7,
        fanta_pages={
            "3": page("3", "Square eggs! Who ever heard of square eggs?"),
            "7": page(
                "7",
                "These square eggs will make us rich, boys!",
                "If we can get them home without breaking.",
            ),
            "21": page("21", "Square chickens lay square eggs, of course!"),
        },
    )


# What each user error's popup is shown with: the fields its message reads.
ERROR_SAMPLES: dict[ErrorTypes, ErrorInfo | None] = {
    ErrorTypes.FantagraphicsVolumeRootNotSet: None,
    ErrorTypes.FantagraphicsVolumeRootNotFound: ErrorInfo(
        file="/media/greg/Barks/Fantagraphics Carl Barks Library"
    ),
    ErrorTypes.DuplicateVolumeArchiveFiles: ErrorInfo(
        file="/media/greg/Barks/Fantagraphics Carl Barks Library", duplicate_volumes=[7, 12]
    ),
    ErrorTypes.MissingArchiveVolumes: ErrorInfo(missing_volumes=[5, 9, 14]),
    ErrorTypes.MissingVolumeCannotShowTitle: ErrorInfo(
        missing_volumes=[7], title=Titles.LOST_IN_THE_ANDES
    ),
    ErrorTypes.ArchiveVolumeNotAvailable: ErrorInfo(file_volume=7, title=Titles.LOST_IN_THE_ANDES),
    ErrorTypes.ComicLoadFailed: ErrorInfo(title=Titles.LOST_IN_THE_ANDES),
}
