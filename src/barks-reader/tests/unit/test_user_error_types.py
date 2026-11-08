from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_reader.core.image_selector import ImageInfo
from barks_reader.core.user_error_messages import build_error_presentation
from barks_reader.core.user_error_types import (
    ErrorInfo,
    ErrorTypes,
    get_volume_not_available_error_info,
)

IN_VOLUME_7 = Titles.LOST_IN_THE_ANDES
IN_NO_VOLUME = Titles.ATTIC_ANTICS


class TestGetVolumeNotAvailableErrorInfo:
    def test_a_title_in_a_volume_gives_its_volume(self) -> None:
        info = get_volume_not_available_error_info(
            ImageInfo(filename=Path("a.png"), from_title=IN_VOLUME_7)
        )

        assert info == ErrorInfo(file_volume=7, title=IN_VOLUME_7)

    def test_a_title_in_no_volume_gives_none(self) -> None:
        assert IN_NO_VOLUME not in ALL_FANTA_COMIC_BOOK_INFO

        info = get_volume_not_available_error_info(
            ImageInfo(filename=Path("a.png"), from_title=IN_NO_VOLUME)
        )

        assert info == ErrorInfo(file_volume=-1, title=IN_NO_VOLUME)

    def test_an_image_with_no_title_gives_none(self) -> None:
        info = get_volume_not_available_error_info(ImageInfo(filename=Path("a.png")))

        assert info == ErrorInfo(file_volume=-1, title=None)


def test_an_error_info_with_no_volume_given_says_not_available_yet() -> None:
    """A defaulted volume is no volume, not volume 0."""
    presentation = build_error_presentation(
        ErrorTypes.ArchiveVolumeNotAvailable, ErrorInfo(title=IN_VOLUME_7), MagicMock()
    )

    assert presentation.title == "Fantagraphics Volume Not Available"
    assert "Volume 0" not in presentation.text
