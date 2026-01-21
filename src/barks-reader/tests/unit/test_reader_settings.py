# ruff: noqa: SLF001

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.reader_file_paths import BarksPanelsExtType
from barks_reader.reader_settings import (
    BARKS_READER_SECTION,
    FANTA_DIR,
    IS_FIRST_USE_OF_READER,
    PNG_BARKS_PANELS_DIR,
    PREBUILT_COMICS_DIR,
    USE_PREBUILT_COMICS,
    BuildableReaderSettings,
    ReaderSettings,
)


@pytest.fixture
def mock_config() -> MagicMock:
    return MagicMock()


@pytest.fixture
def reader_settings(mock_config: MagicMock) -> ReaderSettings:
    with (
        patch("barks_reader.reader_settings.ReaderFilePaths"),
        patch("barks_reader.reader_settings.SystemFilePaths"),
    ):
        settings = ReaderSettings()
        # noinspection PyTypeChecker
        settings.set_config(mock_config, Path("/app/settings.ini"), Path("/app/data"))

        # Ensure mocks are attached
        # settings._reader_file_paths is set in __init__
        return settings


@pytest.fixture
def buildable_settings(mock_config: MagicMock) -> BuildableReaderSettings:
    with (
        patch("barks_reader.reader_settings.ReaderFilePaths"),
        patch("barks_reader.reader_settings.SystemFilePaths"),
    ):
        settings = BuildableReaderSettings()
        # noinspection PyTypeChecker
        settings.set_config(mock_config, Path("/app/settings.ini"), Path("/app/data"))
        return settings


class TestReaderSettings:
    def test_init(self, reader_settings: ReaderSettings) -> None:
        assert reader_settings.get_app_settings_path() == Path("/app/settings.ini")
        assert reader_settings.get_user_data_path() == Path("/app/barks-reader.json")
        # Check derived path
        assert reader_settings.reader_files_dir == Path("/app/data/Reader Files")

    def test_get_fantagraphics_volumes_dir(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        mock_config.get.return_value = "/fanta/dir"
        assert reader_settings.fantagraphics_volumes_dir == Path("/fanta/dir")
        mock_config.get.assert_called_with(BARKS_READER_SECTION, FANTA_DIR)

    def test_get_prebuilt_comics_dir(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        with patch("os.path.expandvars", side_effect=lambda x: x.replace("$HOME", "/home/user")):
            mock_config.get.return_value = "$HOME/prebuilt"
            assert reader_settings.prebuilt_comics_dir == Path("/home/user/prebuilt")
            mock_config.get.assert_called_with(BARKS_READER_SECTION, PREBUILT_COMICS_DIR)

    def test_use_prebuilt_archives(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        mock_config.getboolean.return_value = True
        assert reader_settings.use_prebuilt_archives is True
        mock_config.getboolean.assert_called_with(BARKS_READER_SECTION, USE_PREBUILT_COMICS)

    def test_force_barks_panels_dir_png(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        # Setup for PNG
        mock_config.getboolean.return_value = True  # USE_PNG_IMAGES
        mock_config.get.return_value = "/png/dir"

        with patch("os.path.expandvars", return_value="/png/dir"):
            reader_settings.set_barks_panels_dir()

        # noinspection PyProtectedMember, PyUnresolvedReferences,LongLine
        reader_settings._reader_file_paths.set_barks_panels_source.assert_called_with(  # ty:ignore[unresolved-attribute]
            Path("/png/dir"), BarksPanelsExtType.MOSTLY_PNG
        )

    def test_force_barks_panels_dir_jpg(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        # Setup for JPG
        mock_config.getboolean.return_value = False  # USE_PNG_IMAGES

        reader_settings.set_barks_panels_dir()

        expected_path = Path("/app/data/Reader Files/Barks Panels.zip")
        # noinspection PyProtectedMember, PyUnresolvedReferences,LongLine
        reader_settings._reader_file_paths.set_barks_panels_source.assert_called_with(  # ty:ignore[unresolved-attribute]
            expected_path, BarksPanelsExtType.JPG
        )

    def test_is_first_use_of_reader_setter(
        self, reader_settings: ReaderSettings, mock_config: MagicMock
    ) -> None:
        # We need to patch _save_settings because it calls write() and _update_settings_panel
        with patch.object(reader_settings, "_save_settings") as mock_save:
            reader_settings.is_first_use_of_reader = False

            mock_config.set.assert_called_with(BARKS_READER_SECTION, IS_FIRST_USE_OF_READER, 0)
            mock_save.assert_called_once()

    def test_is_valid_dir(self) -> None:
        # Static method test
        with patch("pathlib.Path.is_dir", return_value=True):
            # noinspection PyProtectedMember
            assert ReaderSettings._is_valid_dir("/valid/path") is True

        with patch("pathlib.Path.is_dir", return_value=False):
            # noinspection PyProtectedMember
            assert ReaderSettings._is_valid_dir("/invalid/path") is False


class TestBuildableReaderSettings:
    def test_build_config(self, mock_config: MagicMock) -> None:
        BuildableReaderSettings.build_config(mock_config)
        mock_config.setdefaults.assert_called_once()
        args, _ = mock_config.setdefaults.call_args
        assert args[0] == BARKS_READER_SECTION
        assert FANTA_DIR in args[1]

    def test_build_settings(
        self, buildable_settings: BuildableReaderSettings, mock_config: MagicMock
    ) -> None:
        mock_settings_panel = MagicMock()
        # noinspection PyTypeChecker
        buildable_settings.build_settings(mock_settings_panel)
        mock_settings_panel.add_json_panel.assert_called_once()
        args, _ = mock_settings_panel.add_json_panel.call_args
        assert args[0] == BARKS_READER_SECTION
        assert args[1] == mock_config

    def test_on_changed_setting_other_section(
        self, buildable_settings: BuildableReaderSettings
    ) -> None:
        assert buildable_settings.on_changed_setting("OTHER", "key", "val") is True

    def test_on_changed_setting_valid_png(
        self, buildable_settings: BuildableReaderSettings, mock_config: MagicMock
    ) -> None:
        # Mock validation to pass
        # noinspection PyProtectedMember
        buildable_settings._VALIDATION_METHODS[PNG_BARKS_PANELS_DIR] = MagicMock(return_value=True)

        # Mock _get_use_png_images to return True so _get_barks_panels_ext_type returns MOSTLY_PNG
        mock_config.getboolean.return_value = True

        with patch("os.path.expandvars", return_value="/new/png"):
            res = buildable_settings.on_changed_setting(
                BARKS_READER_SECTION, PNG_BARKS_PANELS_DIR, "/new/png"
            )

        assert res is True
        # noinspection PyProtectedMember, PyUnresolvedReferences,LongLine
        buildable_settings._reader_file_paths.set_barks_panels_source.assert_called_with(  # ty:ignore[unresolved-attribute]
            "/new/png", BarksPanelsExtType.MOSTLY_PNG
        )

    def test_on_changed_setting_invalid(self, buildable_settings: BuildableReaderSettings) -> None:
        # noinspection PyProtectedMember
        buildable_settings._VALIDATION_METHODS[PREBUILT_COMICS_DIR] = MagicMock(return_value=False)

        res = buildable_settings.on_changed_setting(
            BARKS_READER_SECTION, PREBUILT_COMICS_DIR, "/bad"
        )
        assert res is False

    def test_save_settings(
        self, buildable_settings: BuildableReaderSettings, mock_config: MagicMock
    ) -> None:
        # Mock _update_settings_panel to avoid Kivy imports
        with patch.object(buildable_settings, "_update_settings_panel") as mock_update:
            # noinspection PyProtectedMember
            buildable_settings._save_settings()

            mock_config.write.assert_called_once()
            mock_update.assert_called_once()

    def test_update_settings_panel(self, buildable_settings: BuildableReaderSettings) -> None:
        # 1. Test with no settings panel
        # noinspection PyProtectedMember
        buildable_settings._update_settings_panel()  # Should return early

        # 2. Test with settings panel
        mock_settings = MagicMock()
        # noinspection PyProtectedMember
        buildable_settings._settings = mock_settings

        mock_panel = MagicMock()
        mock_settings.interface.content.panels = {"panel1": mock_panel}

        # Create a dummy class to simulate SettingItem
        class MockSettingItem:
            def __init__(self) -> None:
                self.section = "sec"
                self.key = "key"
                self.value = None

        mock_module = MagicMock()
        mock_module.SettingItem = MockSettingItem

        with patch.dict("sys.modules", {"kivy.uix.settings": mock_module}):
            child = MockSettingItem()
            mock_panel.children = [child]

            # noinspection PyProtectedMember
            buildable_settings._update_settings_panel()

            mock_panel.get_value.assert_called()
            # Verify value assignment
            assert child.value == mock_panel.get_value.return_value
