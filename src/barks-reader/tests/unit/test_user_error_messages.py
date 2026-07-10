from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_reader.core.user_error_messages import (
    FANTA_VOLUMES_NOT_FOUND_FIX_SETTINGS_MSG,
    FANTA_VOLUMES_NOT_SET_FIX_SETTINGS_MSG,
    WRONG_FANTA_VOLUMES_FIX_AND_RESTART_MSG,
    ErrorDialogKind,
    build_error_presentation,
)
from barks_reader.core.user_error_types import ErrorInfo, ErrorTypes

_A_TITLE = Titles.LOST_IN_THE_ANDES
_A_TITLE_STR = ENUM_TO_STR_TITLE[_A_TITLE]


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
        assert "has\nnot been set" in pres.text
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
        assert "Cannot show this title." in pres.text
        assert "not available yet" in pres.text


def test_unconfigured_error_type_raises(reader_settings: MagicMock) -> None:
    with pytest.raises(ValueError, match="No handler configured"):
        build_error_presentation(MagicMock(), None, reader_settings)
