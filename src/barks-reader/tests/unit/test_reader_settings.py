# ruff: noqa: SLF001

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import reader_settings as reader_settings_module
from barks_reader.core.reader_file_paths import BarksPanelsExtType, ReaderFilePaths
from barks_reader.core.reader_settings import (
    BARKS_READER_SECTION,
    FANTA_DIR,
    ReaderSettings,
)
from barks_reader.core.system_file_paths import SystemFilePaths


@pytest.fixture
def mock_config() -> MagicMock:
    """Mock the ConfigParser."""
    config = MagicMock()
    config.get.return_value = "/mock/path"
    config.getboolean.return_value = False
    config.getint.return_value = 0
    return config


@pytest.fixture
def mock_reader_file_paths() -> MagicMock:
    """Mock ReaderFilePaths."""
    return MagicMock(spec=ReaderFilePaths)


@pytest.fixture
def mock_sys_file_paths() -> MagicMock:
    """Mock SystemFilePaths."""
    return MagicMock(spec=SystemFilePaths)


@pytest.fixture
def reader_settings(
    mock_config: MagicMock,
    mock_reader_file_paths: MagicMock,
    mock_sys_file_paths: MagicMock,
) -> ReaderSettings:
    """Create a ReaderSettings instance with mocked dependencies."""
    with (
        patch.object(
            reader_settings_module,
            ReaderFilePaths.__name__,
            return_value=mock_reader_file_paths,
        ),
        patch.object(
            reader_settings_module,
            SystemFilePaths.__name__,
            return_value=mock_sys_file_paths,
        ),
    ):
        settings = ReaderSettings()
        app_settings_path = Path("/app/settings.ini")
        app_data_dir = Path("/app/data")
        # noinspection PyTypeChecker
        settings.set_config(mock_config, app_settings_path, app_data_dir)
        return settings


class TestReaderSettings:
    def test_init(self) -> None:
        """Test initialization of ReaderSettings."""
        with (
            patch.object(reader_settings_module, ReaderFilePaths.__name__) as mock_rfp,
            patch.object(reader_settings_module, SystemFilePaths.__name__) as mock_sfp,
        ):
            settings = ReaderSettings()
            assert settings._reader_file_paths == mock_rfp.return_value
            assert settings._reader_sys_file_paths == mock_sfp.return_value

    def test_set_config(self, reader_settings: ReaderSettings, mock_config: MagicMock) -> None:
        """Test setting the configuration."""
        assert reader_settings._config == mock_config
        assert reader_settings.get_app_settings_path() == Path("/app/settings.ini")
        assert reader_settings.get_user_data_path() == Path("/app/barks-reader.json")

    def test_get_fantagraphics_volumes_dir(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        """Test retrieving the Fantagraphics volumes directory."""
        mock_config.get.return_value = "/fanta/volumes"
        path = reader_settings.fantagraphics_volumes_dir

        mock_config.get.assert_called_with(BARKS_READER_SECTION, FANTA_DIR)
        assert path == Path("/fanta/volumes")

    def test_force_barks_panels_dir_png(
        self,
        reader_settings: ReaderSettings,
        mock_config: MagicMock,
        mock_reader_file_paths: MagicMock,
    ) -> None:
        """Test forcing Barks panels directory to PNG."""
        mock_config.get.return_value = "$VAR/panels"

        # Patch os.path.expandvars in the module
        with patch.object(
            reader_settings_module.os.path,
            os.path.expandvars.__name__,
            return_value="/expanded/panels",
        ) as mock_expand:
            reader_settings.force_barks_panels_dir(use_png_images=True)

            mock_expand.assert_called_with("$VAR/panels")
            mock_reader_file_paths.set_barks_panels_source.assert_called_with(
                Path("/expanded/panels"), BarksPanelsExtType.MOSTLY_PNG
            )

    def test_force_barks_panels_dir_jpg(
        self, reader_settings: ReaderSettings, mock_reader_file_paths: MagicMock
    ) -> None:
        """Test forcing Barks panels directory to JPG."""
        expected_path = Path("/app/data/Reader Files/Barks Panels.zip")

        reader_settings.force_barks_panels_dir(use_png_images=False)

        mock_reader_file_paths.set_barks_panels_source.assert_called_with(
            expected_path, BarksPanelsExtType.JPG
        )

    def test_is_first_use_of_reader_setter(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        """Test setting the 'is_first_use_of_reader' property."""
        with patch.object(reader_settings, ReaderSettings._save_settings.__name__) as mock_save:
            reader_settings.is_first_use_of_reader = False
            mock_config.set.assert_called_with(BARKS_READER_SECTION, "is_first_use_of_reader", 0)
            mock_save.assert_called_once()

            mock_save.reset_mock()
            reader_settings.is_first_use_of_reader = True
            mock_config.set.assert_called_with(BARKS_READER_SECTION, "is_first_use_of_reader", 1)
            mock_save.assert_called_once()

    def test_is_valid_fantagraphics_volumes_dir(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        """Test validation of Fantagraphics volumes directory."""
        # Case 1: use_prebuilt_archives is True
        mock_config.getboolean.side_effect = lambda _section, key: key == "use_prebuilt_comics"
        assert reader_settings.is_valid_fantagraphics_volumes_dir(Path("/any/path")) is True

        # Case 2: use_prebuilt_archives is False, dir exists
        mock_config.getboolean.side_effect = None
        mock_config.getboolean.return_value = False
        with patch.object(Path, Path.is_dir.__name__, return_value=True):
            assert reader_settings.is_valid_fantagraphics_volumes_dir(Path("/valid/path")) is True

        # Case 3: use_prebuilt_archives is False, dir does not exist
        with patch.object(Path, Path.is_dir.__name__, return_value=False):
            assert (
                reader_settings.is_valid_fantagraphics_volumes_dir(Path("/invalid/path")) is False
            )

    def test_is_valid_use_png_images(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        """Test validation of PNG images setting."""
        # Case 1: use_png_images = True
        mock_config.getboolean.return_value = True
        mock_config.get.return_value = "/png/dir"
        with (
            patch.object(
                reader_settings_module.os.path, os.path.expandvars.__name__, return_value="/png/dir"
            ),
            patch.object(Path, Path.is_dir.__name__, return_value=True),
        ):
            assert reader_settings._is_valid_use_png_images(use_png_images=True) is True

        with (
            patch.object(
                reader_settings_module.os.path, os.path.expandvars.__name__, return_value="/png/dir"
            ),
            patch.object(Path, Path.is_dir.__name__, return_value=False),
        ):
            assert reader_settings._is_valid_use_png_images(use_png_images=True) is False

        # Case 2: use_png_images = False
        mock_config.getboolean.return_value = False
        with patch.object(Path, Path.is_file.__name__, return_value=True):
            assert reader_settings._is_valid_use_png_images(use_png_images=False) is True

        with patch.object(Path, Path.is_file.__name__, return_value=False):
            assert reader_settings._is_valid_use_png_images(use_png_images=False) is False

    def test_get_reader_settings_json(self) -> None:
        """Test generation of reader settings JSON."""
        json_str = reader_settings_module._get_reader_settings_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_properties(self, reader_settings: ReaderSettings, mock_config: MagicMock) -> None:
        """Test various simple property getters."""
        mock_config.getboolean.return_value = True
        assert reader_settings.goto_saved_node_on_start is True

        mock_config.getint.return_value = 100
        assert reader_settings._get_main_window_height() == 100  # noqa: PLR2004

        mock_config.get.return_value = "INFO"
        assert reader_settings.log_level == "INFO"
