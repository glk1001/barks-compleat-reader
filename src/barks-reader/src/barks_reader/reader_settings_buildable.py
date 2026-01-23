from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from loguru import logger

from barks_reader.core.reader_file_paths import BarksPanelsExtType, ReaderFilePaths

# noinspection PyProtectedMember
from barks_reader.core.reader_settings import (
    BARKS_READER_SECTION,
    FANTA_DIR,
    GOTO_FULLSCREEN_ON_APP_START,
    GOTO_FULLSCREEN_ON_COMIC_READ,
    GOTO_SAVED_NODE_ON_START,
    IS_FIRST_USE_OF_READER,
    LOG_LEVEL,
    MAIN_WINDOW_HEIGHT,
    MAIN_WINDOW_LEFT,
    MAIN_WINDOW_TOP,
    PNG_BARKS_PANELS_DIR,
    PREBUILT_COMICS_DIR,
    SHOW_FUN_VIEW_TITLE_INFO,
    SHOW_TOP_VIEW_TITLE_INFO,
    UNSET_FANTA_DIR_MARKER,
    USE_BLANK_EYEBALLS_FOR_BOMBIE,
    USE_DERE_INSTEAD_OF_THEAH,
    USE_GLK_FIREBUG_ENDING,
    USE_HARPIES_INSTEAD_OF_LARKIES,
    USE_PNG_IMAGES,
    USE_PREBUILT_COMICS,
    BuildableConfigParser,
    ReaderSettings,
    Settings,
    _get_reader_settings_json,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class BuildableReaderSettings(ReaderSettings):
    def __init__(self) -> None:
        super().__init__()

        self._settings: Settings | None = None

        self._GETTER_METHODS = {
            FANTA_DIR: self._get_fantagraphics_volumes_dir,
            PNG_BARKS_PANELS_DIR: self._get_png_barks_panels_dir,
            USE_PNG_IMAGES: self._get_use_png_images,
            PREBUILT_COMICS_DIR: self._get_prebuilt_comics_dir,
            USE_PREBUILT_COMICS: self._get_use_prebuilt_archives,
            SHOW_TOP_VIEW_TITLE_INFO: self._get_show_top_view_title_info,
            SHOW_FUN_VIEW_TITLE_INFO: self._get_show_fun_view_title_info,
            IS_FIRST_USE_OF_READER: self._get_is_first_use_of_reader,
            LOG_LEVEL: self._get_log_level,
            MAIN_WINDOW_HEIGHT: self._get_main_window_height,
            MAIN_WINDOW_LEFT: self._get_main_window_left,
            MAIN_WINDOW_TOP: self._get_main_window_top,
            GOTO_SAVED_NODE_ON_START: self._get_goto_saved_node_on_start,
            GOTO_FULLSCREEN_ON_APP_START: self._get_goto_fullscreen_on_app_start,
            GOTO_FULLSCREEN_ON_COMIC_READ: self._get_goto_fullscreen_on_comic_read,
            USE_HARPIES_INSTEAD_OF_LARKIES: self.get_use_harpies_instead_of_larkies,
            USE_DERE_INSTEAD_OF_THEAH: self.get_use_dere_instead_of_theah,
            USE_BLANK_EYEBALLS_FOR_BOMBIE: self.get_use_blank_eyeballs_for_bombie,
            USE_GLK_FIREBUG_ENDING: self.get_use_glk_firebug_ending,
        }

        self._VALIDATION_METHODS: dict[str, Callable[[Path | bool | int | str], bool]] = {
            FANTA_DIR: self.is_valid_fantagraphics_volumes_dir,
            PNG_BARKS_PANELS_DIR: self._is_valid_png_barks_panels_dir,
            USE_PNG_IMAGES: self._is_valid_use_png_images,
            PREBUILT_COMICS_DIR: self._is_valid_prebuilt_comics_dir,
            USE_PREBUILT_COMICS: self._is_valid_use_prebuilt_archives,
            GOTO_SAVED_NODE_ON_START: self._is_valid_goto_saved_node_on_start,
            GOTO_FULLSCREEN_ON_APP_START: self._is_valid_goto_fullscreen_on_app_start,
            GOTO_FULLSCREEN_ON_COMIC_READ: self._is_valid_goto_fullscreen_on_comic_read,
            SHOW_TOP_VIEW_TITLE_INFO: self._is_valid_show_top_view_title_info,
            SHOW_FUN_VIEW_TITLE_INFO: self._is_valid_show_fun_view_title_info,
            IS_FIRST_USE_OF_READER: self._is_valid_is_first_use_of_reader,
            LOG_LEVEL: self._is_valid_log_level,
            MAIN_WINDOW_HEIGHT: self._is_valid_main_window_height,
            MAIN_WINDOW_LEFT: self._is_valid_main_window_left,
            MAIN_WINDOW_TOP: self._is_valid_main_window_top,
            USE_HARPIES_INSTEAD_OF_LARKIES: self._is_valid_use_harpies_instead_of_larkies,
            USE_DERE_INSTEAD_OF_THEAH: self._is_valid_use_dere_instead_of_theah,
            USE_BLANK_EYEBALLS_FOR_BOMBIE: self._is_valid_use_blank_eyeballs_for_bombie,
            USE_GLK_FIREBUG_ENDING: self._is_valid_use_glk_firebug_ending,
        }

    @staticmethod
    def build_config(config: BuildableConfigParser) -> None:
        # NOTE: For some reason we need to use 0/1 instead of False/True.
        #       Not sure why.
        config.setdefaults(
            BARKS_READER_SECTION,
            {
                FANTA_DIR: UNSET_FANTA_DIR_MARKER,
                PNG_BARKS_PANELS_DIR: ReaderFilePaths.get_default_png_barks_panels_source(),
                USE_PNG_IMAGES: 1,
                PREBUILT_COMICS_DIR: ReaderFilePaths.get_default_prebuilt_comic_zips_dir(),
                USE_PREBUILT_COMICS: 0,
                GOTO_SAVED_NODE_ON_START: 1,
                GOTO_FULLSCREEN_ON_APP_START: 0,
                GOTO_FULLSCREEN_ON_COMIC_READ: 0,
                USE_HARPIES_INSTEAD_OF_LARKIES: 1,
                USE_DERE_INSTEAD_OF_THEAH: 1,
                USE_BLANK_EYEBALLS_FOR_BOMBIE: 1,
                USE_GLK_FIREBUG_ENDING: 1,
                SHOW_TOP_VIEW_TITLE_INFO: 1,
                SHOW_FUN_VIEW_TITLE_INFO: 1,
                IS_FIRST_USE_OF_READER: 1,
                LOG_LEVEL: "INFO",
                MAIN_WINDOW_HEIGHT: 0,
                MAIN_WINDOW_LEFT: -1,
                MAIN_WINDOW_TOP: -1,
            },
        )

    def build_settings(self, settings: Settings) -> None:
        assert self._config
        settings.add_json_panel(
            BARKS_READER_SECTION, self._config, data=_get_reader_settings_json()
        )
        self._settings = settings

    def validate_settings(self) -> None:
        for key in self._VALIDATION_METHODS:
            self._VALIDATION_METHODS[key](self._GETTER_METHODS[key]())

    def on_changed_setting(self, section: str, key: str, value: Any) -> bool:  # noqa: ANN401
        if section != BARKS_READER_SECTION:
            return True

        assert key in self._VALIDATION_METHODS
        if not self._VALIDATION_METHODS[key](value):
            return False

        if key == PNG_BARKS_PANELS_DIR:
            self._reader_file_paths.set_barks_panels_source(
                value, self._get_barks_panels_ext_type()
            )
        elif key == USE_PNG_IMAGES:
            if value:
                self._reader_file_paths.set_barks_panels_source(
                    self._get_png_barks_panels_dir(), BarksPanelsExtType.MOSTLY_PNG
                )
            else:
                self._reader_file_paths.set_barks_panels_source(
                    self._get_jpg_barks_panels_source(), BarksPanelsExtType.JPG
                )

        return True

    @override
    def _save_settings(self) -> None:
        assert self._config
        self._config.write()
        self._update_settings_panel()

    def _update_settings_panel(self) -> None:
        if not self._settings:
            logger.debug("Panel settings not set. Skipping update.")
            return

        logger.info("Updating panel reader settings.")

        panels = self._settings.interface.content.panels

        # This module is used by non-GUI scripts but this import pops up a window.
        from kivy.uix.settings import SettingItem  # noqa: PLC0415

        for panel in panels.values():
            children = panel.children

            for child in children:
                if isinstance(child, SettingItem):
                    child.value = panel.get_value(child.section, child.key)
