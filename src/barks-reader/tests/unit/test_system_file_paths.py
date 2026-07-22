from __future__ import annotations

from pathlib import Path

import pytest
from barks_reader.core.system_file_paths import SystemFilePaths


class TestSystemFilePaths:
    @pytest.fixture
    def sys_paths(self) -> SystemFilePaths:
        paths = SystemFilePaths()
        paths.set_barks_reader_files_dir(Path("/dummy"), check_files=False)
        return paths

    def test_get_empty_page_file(self, sys_paths: SystemFilePaths) -> None:
        path = sys_paths.get_empty_page_file()
        assert isinstance(path, Path)
        assert path.suffix == ".jpg"

    def test_get_reader_icon_files_dir(self, sys_paths: SystemFilePaths) -> None:
        path = sys_paths.get_reader_icon_files_dir()
        assert isinstance(path, Path)

    def test_get_barks_reader_indexes_dir(self, sys_paths: SystemFilePaths) -> None:
        path = sys_paths.get_barks_reader_indexes_dir()
        assert isinstance(path, Path)

    def test_get_favourite_titles_path(self, sys_paths: SystemFilePaths) -> None:
        path = sys_paths.get_favourite_titles_path()
        assert isinstance(path, Path)

    def test_get_barks_reader_fantagraphics_overrides_root_dir(
        self, sys_paths: SystemFilePaths
    ) -> None:
        path = sys_paths.get_barks_reader_fantagraphics_overrides_root_dir()
        assert isinstance(path, Path)

    def test_get_app_identity_image_path(self, sys_paths: SystemFilePaths) -> None:
        path = sys_paths.get_app_identity_image_file()
        assert isinstance(path, Path)

    def test_icon_getters(self, sys_paths: SystemFilePaths) -> None:
        """Test all icon getter methods return a Path."""
        methods = [
            sys_paths.get_barks_reader_fullscreen_icon_file,
            sys_paths.get_barks_reader_fullscreen_exit_icon_file,
            sys_paths.get_barks_reader_close_icon_file,
            sys_paths.get_barks_reader_go_back_icon_file,
            sys_paths.get_barks_reader_collapse_icon_file,
            sys_paths.get_barks_reader_refresh_arrow_icon_file,
            sys_paths.get_barks_reader_menu_dots_icon_file,
            sys_paths.get_up_arrow_file,
            sys_paths.get_down_arrow_file,
            sys_paths.get_speech_bubble_icon_file,
        ]

        for method in methods:
            path = method()
            assert isinstance(path, Path)
            assert path.suffix.lower() == ".png"


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
