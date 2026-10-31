from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.fanta_comics_info import FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER
from barks_reader.core.user_error_messages import (
    FANTA_VOLUMES_NOT_FOUND_FIX_SETTINGS_MSG,
    FANTA_VOLUMES_NOT_SET_FIX_SETTINGS_MSG,
    WRONG_FANTA_VOLUMES_FIX_AND_RESTART_MSG,
    ErrorDialogKind,
    _format_volume_list,
    build_error_presentation,
)
from barks_reader.core.user_error_types import ErrorInfo, ErrorTypes

_A_TITLE = Titles.LOST_IN_THE_ANDES
_A_TITLE_STR = ENUM_TO_STR_TITLE[_A_TITLE]

# 58 characters with no spaces: longer than a narrow popup's line, so a message that
# broke it (as the dialogs once did, at 50 columns) would show here.
_LONG_PATH = "/mnt/media/comics/fantagraphics_carl_barks_library/volumes"

# Each error's sample, with every field its message reads.
_SAMPLES: dict[ErrorTypes, ErrorInfo | None] = {
    ErrorTypes.FantagraphicsVolumeRootNotSet: None,
    ErrorTypes.FantagraphicsVolumeRootNotFound: None,
    ErrorTypes.DuplicateVolumeArchiveFiles: ErrorInfo(file=_LONG_PATH, duplicate_volumes=[3, 7]),
    ErrorTypes.TooManyVolumeArchiveFiles: ErrorInfo(num_volumes=25, num_archive_files=30),
    ErrorTypes.MissingArchiveVolumes: ErrorInfo(missing_volumes=[5, 9, 14]),
    ErrorTypes.MissingVolumeCannotShowTitle: ErrorInfo(title=_A_TITLE, missing_volumes=[7]),
    ErrorTypes.ArchiveVolumeNotAvailable: ErrorInfo(title=_A_TITLE, file_volume=7),
}


@pytest.fixture
def reader_settings() -> MagicMock:
    settings = MagicMock()
    settings.fantagraphics_volumes_dir = "/some/fanta/dir"
    return settings


class TestGotoSettingsErrors:
    def test_fanta_root_not_set(self, reader_settings: MagicMock) -> None:
        pres = build_error_presentation(
            ErrorTypes.FantagraphicsVolumeRootNotSet, None, reader_settings
        )

        assert pres.kind is ErrorDialogKind.GOTO_SETTINGS
        assert pres.title == "Fantagraphics Directory Not Set"
        assert "has not been set" in pres.text
        assert "browse" in pres.text  # the app stays usable without the library
        assert pres.close_message == FANTA_VOLUMES_NOT_SET_FIX_SETTINGS_MSG

    def test_fanta_root_not_found_includes_configured_dir(self, reader_settings: MagicMock) -> None:
        pres = build_error_presentation(
            ErrorTypes.FantagraphicsVolumeRootNotFound, None, reader_settings
        )

        assert pres.kind is ErrorDialogKind.GOTO_SETTINGS
        assert pres.title == "Fantagraphics Directory Not Found"
        assert '[b]"/some/fanta/dir"[/b]' in pres.text
        assert pres.close_message == FANTA_VOLUMES_NOT_FOUND_FIX_SETTINGS_MSG

    def test_fanta_root_not_found_escapes_kivy_markup(self, reader_settings: MagicMock) -> None:
        reader_settings.fantagraphics_volumes_dir = "/dir/with [markup] & ampersand"

        pres = build_error_presentation(
            ErrorTypes.FantagraphicsVolumeRootNotFound, None, reader_settings
        )

        assert '[b]"/dir/with &bl;markup&br; &amp; ampersand"[/b]' in pres.text

    def test_fanta_root_not_found_leaves_a_long_dir_whole(self, reader_settings: MagicMock) -> None:
        reader_settings.fantagraphics_volumes_dir = _LONG_PATH

        pres = build_error_presentation(
            ErrorTypes.FantagraphicsVolumeRootNotFound, None, reader_settings
        )

        assert f'\n\n[b]"{_LONG_PATH}"[/b]\n\n' in pres.text

    def test_popup_title_override(self, reader_settings: MagicMock) -> None:
        pres = build_error_presentation(
            ErrorTypes.FantagraphicsVolumeRootNotSet,
            None,
            reader_settings,
            popup_title="Custom Title",
        )

        assert pres.title == "Custom Title"


class TestFatalConfigErrors:
    def test_duplicate_archive_files(self, reader_settings: MagicMock) -> None:
        error_info = ErrorInfo(file="/some/fanta/dir", duplicate_volumes=[3, 7])

        pres = build_error_presentation(
            ErrorTypes.DuplicateVolumeArchiveFiles, error_info, reader_settings
        )

        assert pres.kind is ErrorDialogKind.FATAL_CONFIG
        assert pres.title == "Wrong Fantagraphics Archive File"
        assert "The duplicate volumes are 3, 7." in pres.text
        assert pres.close_message == WRONG_FANTA_VOLUMES_FIX_AND_RESTART_MSG

    def test_duplicate_archive_files_full_text(self, reader_settings: MagicMock) -> None:
        # The whole dialog body, so the directory cannot silently go missing (or be
        # broken into lines again) behind a substring check.
        error_info = ErrorInfo(file=_LONG_PATH, duplicate_volumes=[3, 7])

        pres = build_error_presentation(
            ErrorTypes.DuplicateVolumeArchiveFiles, error_info, reader_settings
        )

        assert pres.text == (
            f"There were duplicate Fantagraphics archive files in the directory:\n\n"
            f'[b]"{_LONG_PATH}"[/b]\n\n'
            f"The duplicate volumes are 3, 7. You need to make sure the archives are"
            f" prefixed with the numbers {FIRST_VOLUME_NUMBER:02d} to"
            f" {LAST_VOLUME_NUMBER:02d} inclusive, without duplicates, then restart the app."
        )

    def test_too_many_archive_files(self, reader_settings: MagicMock) -> None:
        error_info = ErrorInfo(num_volumes=25, num_archive_files=30)

        pres = build_error_presentation(
            ErrorTypes.TooManyVolumeArchiveFiles, error_info, reader_settings
        )

        assert pres.kind is ErrorDialogKind.FATAL_CONFIG
        assert pres.title == "Too Many Fantagraphics Archives"
        assert "expected number of files is 25 not 30" in pres.text
        assert pres.close_message == WRONG_FANTA_VOLUMES_FIX_AND_RESTART_MSG


class TestNoticeErrors:
    def test_one_missing_volume_uses_singular(self, reader_settings: MagicMock) -> None:
        error_info = ErrorInfo(missing_volumes=[12])

        pres = build_error_presentation(
            ErrorTypes.MissingArchiveVolumes, error_info, reader_settings
        )

        assert pres.kind is ErrorDialogKind.NOTICE
        assert pres.title == "Fantagraphics Volume Missing"
        assert "volume '12' is missing" in pres.text
        assert pres.close_message == ""

    def test_multiple_missing_volumes_use_plural(self, reader_settings: MagicMock) -> None:
        error_info = ErrorInfo(missing_volumes=[12, 13])

        pres = build_error_presentation(
            ErrorTypes.MissingArchiveVolumes, error_info, reader_settings
        )

        assert pres.title == "Fantagraphics Volumes Missing"
        assert "volumes '12, 13' are missing" in pres.text

    def test_many_missing_volumes_collapse_into_ranges(self, reader_settings: MagicMock) -> None:
        # Runs of 3+ consecutive volumes collapse; a lone pair stays listed.
        error_info = ErrorInfo(missing_volumes=[1, 2, 3, 4, 5, 6, 8, 20, 21])

        pres = build_error_presentation(
            ErrorTypes.MissingArchiveVolumes, error_info, reader_settings
        )

        assert pres.title == "Fantagraphics Volumes Missing"
        assert "volumes '1-6, 8, 20, 21' are missing" in pres.text

    def test_cannot_show_title(self, reader_settings: MagicMock) -> None:
        error_info = ErrorInfo(missing_volumes=[7], title=_A_TITLE)

        pres = build_error_presentation(
            ErrorTypes.MissingVolumeCannotShowTitle, error_info, reader_settings
        )

        assert pres.kind is ErrorDialogKind.NOTICE
        assert pres.title == "Fantagraphics Volume Missing"
        assert f'Cannot show the title "{_A_TITLE_STR}"' in pres.text
        assert "volume '7' is missing" in pres.text

    def test_volume_not_available_yet(self, reader_settings: MagicMock) -> None:
        error_info = ErrorInfo(file_volume=-1, title=_A_TITLE)

        pres = build_error_presentation(
            ErrorTypes.ArchiveVolumeNotAvailable, error_info, reader_settings
        )

        assert pres.kind is ErrorDialogKind.NOTICE
        assert pres.title == "Fantagraphics Volume Not Available"
        assert "not available yet" in pres.text

    def test_volume_not_found(self, reader_settings: MagicMock) -> None:
        error_info = ErrorInfo(file_volume=7, title=_A_TITLE)

        pres = build_error_presentation(
            ErrorTypes.ArchiveVolumeNotAvailable, error_info, reader_settings
        )

        assert pres.title == "Fantagraphics Volume Not Found"
        assert "Fantagraphics Volume 7" in pres.text

    def test_volume_not_available_without_title(self, reader_settings: MagicMock) -> None:
        # 'get_volume_not_available_error_info' produces title=None when the
        # source image has no originating title.
        error_info = ErrorInfo(file_volume=-1, title=None)

        pres = build_error_presentation(
            ErrorTypes.ArchiveVolumeNotAvailable, error_info, reader_settings
        )

        assert pres.kind is ErrorDialogKind.NOTICE
        assert pres.title == "Fantagraphics Volume Not Available"
        assert pres.text == (
            "Cannot show this title.\n\n"
            "The Fantagraphics volume containing this title is not available yet."
        )

    def test_volume_not_found_names_the_title_in_full(self, reader_settings: MagicMock) -> None:
        error_info = ErrorInfo(file_volume=7, title=_A_TITLE)

        pres = build_error_presentation(
            ErrorTypes.ArchiveVolumeNotAvailable, error_info, reader_settings
        )

        assert pres.text == (
            f'Cannot show the title [b]"{_A_TITLE_STR}."[/b]\n\n'
            f"This title is in Fantagraphics Volume 7 which could not be found."
        )


class TestFormatVolumeList:
    """The collapse rule for the missing-volumes notice.

    A run of exactly `_MIN_RUN_TO_COLLAPSE` (3) is the boundary case: it is the
    shortest run that collapses, so it is the only input that can tell `>=` from
    `>` and the run-length arithmetic from an off-by-one.
    """

    @pytest.mark.parametrize(
        ("volumes", "expected"),
        [
            ([], ""),
            ([5], "5"),
            ([1, 2], "1, 2"),
            ([1, 2, 3], "1-3"),
            ([1, 2, 3, 4], "1-4"),
            ([3, 1, 2], "1-3"),
            ([1, 2, 4, 5, 6], "1, 2, 4-6"),
            ([1, 2, 3, 4, 5, 6, 8, 20, 21], "1-6, 8, 20, 21"),
        ],
    )
    def test_collapses_runs(self, volumes: list[int], expected: str) -> None:
        assert _format_volume_list(volumes) == expected


@pytest.mark.parametrize("error_type", list(ErrorTypes))
def test_a_message_is_paragraphs_the_popup_wraps(
    error_type: ErrorTypes, reader_settings: MagicMock
) -> None:
    # A line broken here as well as by the popup's label leaves a word stranded.
    reader_settings.fantagraphics_volumes_dir = _LONG_PATH

    pres = build_error_presentation(error_type, _SAMPLES[error_type], reader_settings)

    paragraphs = pres.text.split("\n\n")
    assert all(paragraph and "\n" not in paragraph for paragraph in paragraphs)
    assert all(paragraph == paragraph.strip() for paragraph in paragraphs)


def test_every_error_type_has_a_sample() -> None:
    assert set(_SAMPLES) == set(ErrorTypes)


def test_unconfigured_error_type_raises(reader_settings: MagicMock) -> None:
    with pytest.raises(ValueError, match="No handler configured"):
        build_error_presentation(MagicMock(), None, reader_settings)
