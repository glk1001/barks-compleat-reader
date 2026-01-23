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

    def test_get_about_background_path(self, sys_paths: SystemFilePaths) -> None:
        path = sys_paths.get_about_background_path()
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
