"""The settings screen's side of `ReaderSettings`: defaults, change handling, panel refresh."""

# ruff: noqa: SLF001

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import reader_settings as reader_settings_module
from barks_reader.core.reader_file_paths import BarksPanelsExtType, ReaderFilePaths
from barks_reader.core.reader_settings import (
    _FIELDS,
    BARKS_READER_SECTION,
    JPG_BARKS_PANELS_ZIP,
    PNG_BARKS_PANELS_DIR,
    USE_PNG_IMAGES,
    WIKI_BUNDLE_DIR,
)
from barks_reader.core.system_file_paths import SystemFilePaths
from barks_reader.ui.reader_settings_buildable import BuildableReaderSettings
from kivy.uix import settings as kivy_settings

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def config() -> MagicMock:
    config = MagicMock()
    config.getboolean.return_value = False
    return config


@pytest.fixture
def file_paths() -> MagicMock:
    return MagicMock(spec=ReaderFilePaths)


@pytest.fixture
def settings(config: MagicMock, file_paths: MagicMock, tmp_path: Path) -> BuildableReaderSettings:
    with (
        patch.object(reader_settings_module, ReaderFilePaths.__name__, return_value=file_paths),
        patch.object(reader_settings_module, SystemFilePaths.__name__),
    ):
        settings = BuildableReaderSettings()
    settings.set_config(config, tmp_path / "barks-reader.ini", tmp_path)
    return settings


@pytest.fixture
def jpg_zip(settings: BuildableReaderSettings) -> Path:
    zip_path = settings.reader_files_dir / JPG_BARKS_PANELS_ZIP
    zip_path.parent.mkdir(parents=True)
    zip_path.write_bytes(b"")
    return zip_path


def test_every_field_gets_its_default(config: MagicMock) -> None:
    BuildableReaderSettings.build_config(config)

    section, defaults = config.setdefaults.call_args.args
    assert section == BARKS_READER_SECTION
    assert set(defaults) == {spec.key for spec in _FIELDS}


class TestOnChangedSetting:
    def test_another_sections_change_is_accepted_untouched(
        self, settings: BuildableReaderSettings, file_paths: MagicMock
    ) -> None:
        assert settings.on_changed_setting("Kivy", "keyboard_mode", "dock") is True
        file_paths.set_barks_panels_source.assert_not_called()

    def test_png_images_are_refused_without_a_png_panels_dir(
        self, settings: BuildableReaderSettings, config: MagicMock, file_paths: MagicMock
    ) -> None:
        config.getboolean.return_value = True
        config.get.return_value = "/no/such/png/panels"

        assert settings.on_changed_setting(BARKS_READER_SECTION, USE_PNG_IMAGES, True) is False  # noqa: FBT003
        file_paths.set_barks_panels_source.assert_not_called()

    def test_png_images_on_reads_the_png_panels_dir(
        self,
        settings: BuildableReaderSettings,
        config: MagicMock,
        file_paths: MagicMock,
        tmp_path: Path,
    ) -> None:
        config.getboolean.return_value = True
        config.get.return_value = str(tmp_path)

        assert settings.on_changed_setting(BARKS_READER_SECTION, USE_PNG_IMAGES, True) is True  # noqa: FBT003
        file_paths.set_barks_panels_source.assert_called_once_with(
            tmp_path, BarksPanelsExtType.MOSTLY_PNG
        )

    def test_png_images_off_goes_back_to_the_jpg_zip(
        self, settings: BuildableReaderSettings, file_paths: MagicMock, jpg_zip: Path
    ) -> None:
        assert settings.on_changed_setting(BARKS_READER_SECTION, USE_PNG_IMAGES, False) is True  # noqa: FBT003
        file_paths.set_barks_panels_source.assert_called_once_with(jpg_zip, BarksPanelsExtType.JPG)

    def test_a_new_png_panels_dir_is_read_in_png_mode(
        self,
        settings: BuildableReaderSettings,
        config: MagicMock,
        file_paths: MagicMock,
        tmp_path: Path,
    ) -> None:
        config.getboolean.return_value = True

        assert (
            settings.on_changed_setting(BARKS_READER_SECTION, PNG_BARKS_PANELS_DIR, tmp_path)
            is True
        )
        file_paths.set_barks_panels_source.assert_called_once_with(
            tmp_path, BarksPanelsExtType.MOSTLY_PNG
        )

    def test_a_new_png_panels_dir_waits_in_jpg_mode(
        self, settings: BuildableReaderSettings, file_paths: MagicMock
    ) -> None:
        """The JPG zip stays the source, even for a dir that does not exist yet."""
        assert (
            settings.on_changed_setting(BARKS_READER_SECTION, PNG_BARKS_PANELS_DIR, "/not/made")
            is True
        )
        file_paths.set_barks_panels_source.assert_not_called()


class TestOnChangedSettingTakesThePanelsText:
    """Kivy's panel sends the text it wrote: "0"/"1" for a switch, a str for a path."""

    def test_a_switch_turned_off_is_off(
        self, settings: BuildableReaderSettings, file_paths: MagicMock, jpg_zip: Path
    ) -> None:
        assert settings.on_changed_setting(BARKS_READER_SECTION, USE_PNG_IMAGES, "0") is True
        file_paths.set_barks_panels_source.assert_called_once_with(jpg_zip, BarksPanelsExtType.JPG)

    def test_a_new_png_panels_dir_is_a_path(
        self,
        settings: BuildableReaderSettings,
        config: MagicMock,
        file_paths: MagicMock,
        tmp_path: Path,
    ) -> None:
        config.getboolean.return_value = True

        assert settings.on_changed_setting(
            BARKS_READER_SECTION, PNG_BARKS_PANELS_DIR, str(tmp_path)
        )
        file_paths.set_barks_panels_source.assert_called_once_with(
            tmp_path, BarksPanelsExtType.MOSTLY_PNG
        )

    def test_a_wiki_dir_that_is_no_bundle_is_refused_not_a_crash(
        self, settings: BuildableReaderSettings, config: MagicMock, tmp_path: Path
    ) -> None:
        """The soak's crash: the wiki dir's check joined a str with "/"."""
        config.getboolean.return_value = True  # the live wiki bundle is on

        assert not settings.on_changed_setting(BARKS_READER_SECTION, WIKI_BUNDLE_DIR, str(tmp_path))

    def test_a_wiki_dir_with_its_index_is_taken(
        self, settings: BuildableReaderSettings, config: MagicMock, tmp_path: Path
    ) -> None:
        config.getboolean.return_value = True
        (tmp_path / "index.md").write_text("")

        assert settings.on_changed_setting(BARKS_READER_SECTION, WIKI_BUNDLE_DIR, str(tmp_path))


class _FakeSettingItem:
    def __init__(self, section: str, key: str) -> None:
        self.section = section
        self.key = key
        self.value = "old"


class TestSettingsPanelRefresh:
    def test_saving_with_no_panel_only_writes_the_config(
        self, settings: BuildableReaderSettings, config: MagicMock
    ) -> None:
        settings._save_settings()

        config.write.assert_called_once_with()

    def test_saving_refreshes_every_item_on_the_panel(
        self, settings: BuildableReaderSettings, config: MagicMock
    ) -> None:
        item = _FakeSettingItem(BARKS_READER_SECTION, USE_PNG_IMAGES)
        panel = MagicMock()
        panel.children = [item, MagicMock()]
        panel.get_value.return_value = "new"
        kivy_panel = MagicMock()
        kivy_panel.interface.content.panels = {1: panel}
        settings._settings = kivy_panel

        with patch.object(kivy_settings, "SettingItem", _FakeSettingItem):
            settings._save_settings()

        config.write.assert_called_once_with()
        panel.get_value.assert_called_once_with(BARKS_READER_SECTION, USE_PNG_IMAGES)
        assert item.value == "new"

    def test_an_interface_without_a_menu_is_its_own_content_panel(
        self, settings: BuildableReaderSettings
    ) -> None:
        item = _FakeSettingItem(BARKS_READER_SECTION, USE_PNG_IMAGES)
        panel = MagicMock()
        panel.children = [item]
        panel.get_value.return_value = "new"
        kivy_panel = MagicMock()
        kivy_panel.interface.content = None
        kivy_panel.interface.panels = {1: panel}
        settings._settings = kivy_panel

        with patch.object(kivy_settings, "SettingItem", _FakeSettingItem):
            settings._save_settings()

        assert item.value == "new"
