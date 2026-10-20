"""The library's state and what to tell the user (barks_reader.core.fanta_volumes_state)."""

from __future__ import annotations

from pathlib import Path

import pytest
from barks_fantagraphics.fanta_comics_info import NUM_VOLUMES
from barks_reader.core.fanta_volumes_state import (
    BAD_STATES,
    NO_LIBRARY_STATES,
    STATE_ERRORS,
    FantaVolumesState,
    LibraryNotice,
    check_library_error,
    no_library_error_type,
    post_build_state,
)
from barks_reader.core.fantagraphics_volumes import (
    DuplicateArchiveFilesError,
    MissingArchiveFilesError,
    TooManyArchiveFilesError,
)
from barks_reader.core.reader_settings import UNSET_FANTA_DIR_MARKER
from barks_reader.core.user_error_types import ErrorTypes


class TestPostBuildState:
    def test_prebuilt_comics_need_no_volumes(self) -> None:
        state = post_build_state(use_prebuilt_archives=True, volumes_dir=Path("/nowhere"))
        assert state is FantaVolumesState.VOLUMES_NOT_NEEDED

    def test_the_unset_marker_is_not_set(self) -> None:
        state = post_build_state(
            use_prebuilt_archives=False, volumes_dir=Path(UNSET_FANTA_DIR_MARKER)
        )
        assert state is FantaVolumesState.VOLUMES_NOT_SET
        assert state in NO_LIBRARY_STATES

    def test_a_folder_that_is_not_there_has_every_volume_missing(self, tmp_path: Path) -> None:
        state = post_build_state(use_prebuilt_archives=False, volumes_dir=tmp_path / "gone")
        assert state is FantaVolumesState.ALL_VOLUMES_MISSING
        assert post_build_state(use_prebuilt_archives=False, volumes_dir=tmp_path) is (
            FantaVolumesState.VOLUMES_EXIST
        )


def test_the_no_library_notice_names_the_unset_setting_or_the_missing_folder() -> None:
    assert no_library_error_type(FantaVolumesState.VOLUMES_NOT_SET) is (
        ErrorTypes.FantagraphicsVolumeRootNotSet
    )
    assert no_library_error_type(FantaVolumesState.ALL_VOLUMES_MISSING) is (
        ErrorTypes.FantagraphicsVolumeRootNotFound
    )


def test_every_bad_or_no_library_state_has_a_reason() -> None:
    for state in BAD_STATES | NO_LIBRARY_STATES:
        reason, error_type = STATE_ERRORS[state]
        assert reason
        assert isinstance(error_type, ErrorTypes)


class TestCheckLibraryError:
    def test_too_many_archives_block_reading_with_their_popup(self) -> None:
        check = check_library_error(
            TooManyArchiveFilesError(14, 12, Path("/root")), library_notice_shown=False
        )
        assert (check.state, check.notice, check.readable) == (
            FantaVolumesState.VOLUMES_TOO_MANY,
            LibraryNotice.ERROR,
            False,
        )
        assert check.error_type is ErrorTypes.TooManyVolumeArchiveFiles
        assert check.state in BAD_STATES
        # The popup says how many archives there are and how many there should be.
        assert (check.error_info.num_archive_files, check.error_info.num_volumes) == (14, 12)

    def test_duplicate_archives_block_reading_with_their_popup(self) -> None:
        root = Path("/root")
        check = check_library_error(
            DuplicateArchiveFilesError([3], root), library_notice_shown=False
        )
        assert check.state is FantaVolumesState.DUPLICATE_VOLUMES
        assert check.notice is LibraryNotice.ERROR
        assert check.error_type is ErrorTypes.DuplicateVolumeArchiveFiles
        assert check.readable is False
        assert (check.error_info.file, check.error_info.duplicate_volumes) == (str(root), [3])

    def test_a_partial_library_reads_on_after_the_per_volume_popup(self) -> None:
        check = check_library_error(
            MissingArchiveFilesError([2, 5], Path("/dir")), library_notice_shown=False
        )
        assert check.state is FantaVolumesState.SOME_VOLUMES_MISSING
        assert (check.notice, check.error_type) == (
            LibraryNotice.ERROR,
            ErrorTypes.MissingArchiveVolumes,
        )
        assert check.readable is True
        assert check.error_info.missing_volumes == [2, 5]  # the popup lists them

    def test_a_folder_with_no_volume_at_all_gets_the_one_no_library_notice(self) -> None:
        check = check_library_error(
            MissingArchiveFilesError(list(range(1, NUM_VOLUMES + 1)), Path("/dir")),
            library_notice_shown=False,
        )
        assert (check.notice, check.error_type, check.readable) == (
            LibraryNotice.NO_LIBRARY,
            ErrorTypes.FantagraphicsVolumeRootNotFound,
            True,
        )

    @pytest.mark.parametrize("missing", [[2, 5], list(range(1, NUM_VOLUMES + 1))])
    def test_a_notice_already_shown_is_not_shown_again(self, missing: list[int]) -> None:
        check = check_library_error(
            MissingArchiveFilesError(missing, Path("/dir")), library_notice_shown=True
        )
        assert (check.notice, check.readable) == (LibraryNotice.NONE, True)
