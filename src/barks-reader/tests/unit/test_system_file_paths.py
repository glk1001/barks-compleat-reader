from __future__ import annotations

from pathlib import Path

import pytest
from barks_reader.core.system_file_paths import SystemFilePaths

_ASSETS_ROOT = Path("/dummy")

# The reader's asset-layout contract: every path `SystemFilePaths` resolves under the
# assets root, as (getter name, path relative to that root).
#
# These are asserted exactly rather than by type/suffix. The whole class is a table of
# string literals, so a typo in one is invisible to a `isinstance(path, Path)` check but
# is a missing asset — and a hard startup failure — in the real app.
_EXPECTED_PATHS: tuple[tuple[str, str], ...] = (
    # Top-level directories.
    ("get_reader_icon_files_dir", "Reader Icons"),
    ("get_barks_reader_indexes_dir", "Indexes"),
    ("get_statistics_dir", "Statistics"),
    (
        "get_barks_reader_fantagraphics_overrides_root_dir",
        "Fantagraphics Volumes Overrides",
    ),
    (
        "get_barks_reader_fantagraphics_panel_segments_root_dir",
        "Fantagraphics-panel-segments",
    ),
    # Document directories.
    ("get_intro_doc_dir", "Various/documents/intro-to-barks-reader"),
    ("get_censorship_fixes_doc_dir", "Various/documents/censorship-fixes"),
    ("get_how_to_doc_dir", "Various/documents/how-to"),
    # 'Various' files.
    ("get_barks_reader_app_window_icon_path", "Various/app-icon.png"),
    ("get_error_background_path", "Various/error-background.png"),
    ("get_success_background_path", "Various/success-background.png"),
    ("get_app_identity_image_file", "Various/app-identity-image.png"),
    ("get_speech_bubble_icon_file", "Various/speech-bubble-icon.png"),
    ("get_eye_open_icon_file", "Various/icon-eye-open.png"),
    ("get_eye_off_icon_file", "Various/icon-eye-off.png"),
    ("get_up_arrow_file", "Various/up-arrow.png"),
    ("get_down_arrow_file", "Various/down-arrow.png"),
    ("get_transparent_blank_file", "Various/transparent-blank.png"),
    ("get_empty_page_file", "Various/empty-page.jpg"),
    ("get_favourite_titles_path", "Various/favourite-titles.txt"),
    # Action-bar icons.
    ("get_barks_reader_close_icon_file", "Reader Icons/ActionBar Icons/icon-close.png"),
    (
        "get_barks_reader_go_back_icon_file",
        "Reader Icons/ActionBar Icons/icon-back-arrow.png",
    ),
    (
        "get_barks_reader_collapse_icon_file",
        "Reader Icons/ActionBar Icons/icon-collapse.png",
    ),
    (
        "get_barks_reader_refresh_arrow_icon_file",
        "Reader Icons/ActionBar Icons/icon-refresh-arrow.png",
    ),
    (
        "get_barks_reader_settings_icon_file",
        "Reader Icons/ActionBar Icons/icon-settings.png",
    ),
    (
        "get_barks_reader_menu_dots_icon_file",
        "Reader Icons/ActionBar Icons/icon-menu-dots.png",
    ),
    (
        "get_barks_reader_fullscreen_icon_file",
        "Reader Icons/ActionBar Icons/icon-fullscreen.png",
    ),
    (
        "get_barks_reader_fullscreen_exit_icon_file",
        "Reader Icons/ActionBar Icons/icon-fullscreen-exit.png",
    ),
    (
        "get_barks_reader_single_page_icon_file",
        "Reader Icons/ActionBar Icons/icon-single-page.png",
    ),
    (
        "get_barks_reader_double_page_icon_file",
        "Reader Icons/ActionBar Icons/icon-double-page.png",
    ),
    ("get_barks_reader_goto_icon_file", "Reader Icons/ActionBar Icons/icon-goto.png"),
    (
        "get_barks_reader_goto_start_icon_file",
        "Reader Icons/ActionBar Icons/icon-goto-start.png",
    ),
    (
        "get_barks_reader_goto_end_icon_file",
        "Reader Icons/ActionBar Icons/icon-goto-end.png",
    ),
    (
        "get_barks_reader_contrast_on_icon_file",
        "Reader Icons/ActionBar Icons/icon-contrast-on.png",
    ),
    (
        "get_barks_reader_contrast_off_icon_file",
        "Reader Icons/ActionBar Icons/icon-contrast-off.png",
    ),
    (
        "get_barks_reader_goto_title_icon_file",
        "Reader Icons/ActionBar Icons/icon-goto-title.png",
    ),
    (
        "get_hamburger_menu_icon_path",
        "Reader Icons/ActionBar Icons/menu-hamburger-icon.png",
    ),
)


def _build_asset_tree(root: Path) -> None:
    """Materialise every path in `_EXPECTED_PATHS` under `root`.

    Entries with a suffix become files, the rest directories — so the tree is built from
    the test's own expectations, not from the class under test.
    """
    for _getter, relative in _EXPECTED_PATHS:
        path = root / relative
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"")
        else:
            path.mkdir(parents=True, exist_ok=True)


class TestSystemFilePaths:
    @pytest.fixture
    def sys_paths(self) -> SystemFilePaths:
        paths = SystemFilePaths()
        paths.set_barks_reader_files_dir(_ASSETS_ROOT, check_files=False)
        return paths

    @pytest.mark.parametrize(
        ("getter", "relative"),
        _EXPECTED_PATHS,
        ids=[getter for getter, _ in _EXPECTED_PATHS],
    )
    def test_resolved_path(self, sys_paths: SystemFilePaths, getter: str, relative: str) -> None:
        assert getattr(sys_paths, getter)() == _ASSETS_ROOT / relative

    def test_get_stat_image_path_joins_onto_the_statistics_dir(
        self, sys_paths: SystemFilePaths
    ) -> None:
        assert sys_paths.get_stat_image_path("titles-per-year.png") == (
            _ASSETS_ROOT / "Statistics" / "titles-per-year.png"
        )

    def test_every_getter_is_covered_by_the_expected_paths_table(self) -> None:
        """Guard against a new getter landing without an entry in `_EXPECTED_PATHS`."""
        # `get_stat_image_path` takes an argument, so it is asserted separately above.
        getters = {
            name
            for name in dir(SystemFilePaths)
            if name.startswith("get_") and name != "get_stat_image_path"
        }
        assert getters == {getter for getter, _ in _EXPECTED_PATHS}


class TestCheckDirs:
    def test_passes_for_existing_dirs(self, tmp_path: Path) -> None:
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()

        # No exception expected.
        SystemFilePaths._check_dirs([a, b])  # noqa: SLF001

    def test_raises_when_dir_missing(self, tmp_path: Path) -> None:
        a = tmp_path / "exists"
        a.mkdir()
        missing = tmp_path / "missing"

        with pytest.raises(FileNotFoundError, match="Required directory not found"):
            SystemFilePaths._check_dirs([a, missing])  # noqa: SLF001

    def test_raises_when_a_file_is_given_instead_of_a_dir(self, tmp_path: Path) -> None:
        not_a_dir = tmp_path / "file.txt"
        not_a_dir.write_text("x")

        with pytest.raises(FileNotFoundError, match="Required directory not found"):
            SystemFilePaths._check_dirs([not_a_dir])  # noqa: SLF001


class TestCheckFiles:
    def test_passes_for_existing_files(self, tmp_path: Path) -> None:
        f = tmp_path / "f.txt"
        f.write_text("x")

        # No exception expected.
        SystemFilePaths.check_files([f])

    def test_raises_when_file_missing(self, tmp_path: Path) -> None:
        existing = tmp_path / "exists.txt"
        existing.write_text("x")
        missing = tmp_path / "missing.txt"

        with pytest.raises(FileNotFoundError, match="Required file not found"):
            SystemFilePaths.check_files([existing, missing])

    def test_raises_when_a_dir_is_given_instead_of_a_file(self, tmp_path: Path) -> None:
        not_a_file = tmp_path / "subdir"
        not_a_file.mkdir()

        with pytest.raises(FileNotFoundError, match="Required file not found"):
            SystemFilePaths.check_files([not_a_file])


class TestSetBarksReaderFilesDirValidation:
    def test_check_files_false_skips_validation_on_missing_path(self, tmp_path: Path) -> None:
        # The whole tree doesn't exist — but check_files=False short-circuits validation.
        paths = SystemFilePaths()
        paths.set_barks_reader_files_dir(tmp_path / "does_not_exist", check_files=False)

    def test_check_files_true_raises_on_missing_subdir(self, tmp_path: Path) -> None:
        paths = SystemFilePaths()
        # tmp_path exists but none of the required subdirs do.
        with pytest.raises(FileNotFoundError, match="Required directory not found"):
            paths.set_barks_reader_files_dir(tmp_path, check_files=True)

    def test_validation_is_on_by_default(self, tmp_path: Path) -> None:
        """Callers that omit `check_files` get the required-files check, not a silent skip."""
        paths = SystemFilePaths()
        with pytest.raises(FileNotFoundError, match="Required directory not found"):
            paths.set_barks_reader_files_dir(tmp_path)

    def test_passes_against_a_complete_asset_tree(self, tmp_path: Path) -> None:
        """A tree built from `_EXPECTED_PATHS` satisfies every required dir and file.

        This pins the required-files check to the same layout table as the getters: if a
        checked path is spelled differently from the one the getters resolve, the check
        looks for a file this tree never created and the test fails.
        """
        _build_asset_tree(tmp_path)

        paths = SystemFilePaths()
        # No exception expected.
        paths.set_barks_reader_files_dir(tmp_path, check_files=True)

    @pytest.mark.parametrize(
        "missing",
        [
            pytest.param("Indexes", id="dir"),
            pytest.param("Various/app-icon.png", id="various_file"),
            pytest.param("Reader Icons/ActionBar Icons/icon-close.png", id="action_bar_icon"),
            pytest.param("Various/favourite-titles.txt", id="favourite_titles"),
        ],
    )
    def test_raises_when_a_required_entry_is_absent(self, tmp_path: Path, missing: str) -> None:
        _build_asset_tree(tmp_path)
        target = tmp_path / missing
        if target.is_dir():
            target.rmdir()
        else:
            target.unlink()

        paths = SystemFilePaths()
        with pytest.raises(FileNotFoundError, match=r"Required (directory|file) not found"):
            paths.set_barks_reader_files_dir(tmp_path, check_files=True)
