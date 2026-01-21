from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from barks_reader.image_file_getter import TitleImageFileGetter
from barks_reader.reader_file_paths import FileTypes


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.file_paths = MagicMock()
    settings.file_paths.get_file_ext.return_value = ".png"
    return settings


class TestTitleImageFileGetter:
    def test_initialization(self, mock_settings: MagicMock) -> None:
        getter = TitleImageFileGetter(mock_settings)
        assert getter is not None

    def test_get_all_title_image_files_empty(self, mock_settings: MagicMock) -> None:
        """Test that it returns an empty dict structure when no files are found."""
        getter = TitleImageFileGetter(mock_settings)

        # Mock ReaderFilePaths to return a dummy path for any directory request
        mock_dir = MagicMock(spec=Path)
        mock_dir.glob.return_value = []  # No files found
        mock_settings.file_paths.get_barks_panels_dir_for_type.return_value = mock_dir

        # Also mock get_edited_version_if_possible to return the input path
        mock_settings.file_paths.get_edited_version_if_possible.side_effect = lambda p: (p, False)

        result = getter.get_all_title_image_files("Some Title")

        assert isinstance(result, dict)
        # It should return a dict where keys are FileTypes and values are sets
        for file_type in FileTypes:
            if file_type in result:
                assert isinstance(result[file_type], set)
                assert len(result[file_type]) == 0

    def test_get_all_title_image_files_found(self, mock_settings: MagicMock) -> None:
        """Test that it correctly categorizes found files."""
        getter = TitleImageFileGetter(mock_settings)

        # Set up a mock directory that returns a file when globbed.
        mock_dir = MagicMock(spec=Path)
        mock_file = Path("path/to/Title - Cover.png")
        mock_dir.glob.return_value = [mock_file]

        # Configure settings to return this mock dir for COVER type
        def get_dir_side_effect(file_type: FileTypes) -> MagicMock:
            if file_type == FileTypes.COVER:
                return mock_dir
            empty_dir = MagicMock(spec=Path)
            empty_dir.glob.return_value = []
            return empty_dir

        mock_settings.file_paths.get_barks_panels_dir_for_type.side_effect = get_dir_side_effect

        # Mock edited version check
        mock_settings.file_paths.get_edited_version_if_possible.return_value = (mock_file, False)

        # Mock the FILE_TYPE_FILE_GETTERS dictionary
        # It maps FileTypes to a callable that takes (title_str, use_only_edited)
        mock_getter_func = MagicMock()

        def getter_side_effect(_title: str, use_only_edited: bool) -> Path | None:
            if use_only_edited:
                return None
            return mock_file

        mock_getter_func.side_effect = getter_side_effect
        mock_settings.file_paths.FILE_TYPE_FILE_GETTERS = {FileTypes.COVER: mock_getter_func}

        result = getter.get_all_title_image_files("Title")

        assert FileTypes.COVER in result
        assert len(result[FileTypes.COVER]) == 1

        # Check the content of the set: (Path, is_edited)
        item = next(iter(result[FileTypes.COVER]))
        assert item[0] == mock_file
        assert item[1] is False
