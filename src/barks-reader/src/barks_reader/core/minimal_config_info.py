import logging
from configparser import RawConfigParser
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from .config_info import ConfigInfo
from .main_layout import MATCH_THE_SCREEN


@dataclass(frozen=True, slots=True)
class MinimalConfigOptions:
    """The few settings read before the app is up: the window, the log level, the layout.

    The defaults are what a boot gets when the ini cannot be read.

    Attributes:
        error_background_path: The background of the boot error screen.
        success_background_path: The background shown once the boot succeeds.
        win_height: The saved window height; 0 for none.
        win_left: The saved window's left edge; -1 for none.
        win_top: The saved window's top edge; -1 for none.
        log_level: The log level name.
        main_screen_layout: The "Layout" setting: single page, spread, or match the screen.

    """

    error_background_path: Path | None = None
    success_background_path: Path | None = None
    win_height: int = 0
    win_left: int = -1
    win_top: int = -1
    log_level: str = logging.getLevelName(logging.INFO)
    main_screen_layout: str = MATCH_THE_SCREEN


def get_minimal_config_options(cfg_info: ConfigInfo) -> MinimalConfigOptions:
    """Read the settings the boot needs before the app is up, from the app's ini.

    Any error reading them (a bad ini, a missing background) is logged, and the boot
    goes on with the defaults.

    Args:
        cfg_info: Where the app's ini and data are.

    Returns:
        The settings read, or the defaults on any error.

    """
    from .reader_settings import (  # noqa: PLC0415
        BARKS_READER_SECTION,
        LOG_LEVEL,
        MAIN_SCREEN_LAYOUT,
        MAIN_WINDOW_HEIGHT,
        MAIN_WINDOW_LEFT,
        MAIN_WINDOW_TOP,
        ReaderSettings,
        read_setting_from_config,
    )
    from .system_file_paths import SystemFilePaths  # noqa: PLC0415

    barks_config = RawConfigParser()

    try:
        # As Kivy, which writes the file, reads it: UTF-8, not the machine's encoding,
        # and with no interpolation (a "%" in a value is only itself).
        barks_config.read(cfg_info.app_config_path, encoding="utf-8-sig")
        reader_files_dir = ReaderSettings.get_reader_files_dir(cfg_info.app_data_dir)
        win_height = read_setting_from_config(barks_config, MAIN_WINDOW_HEIGHT)
        win_left = read_setting_from_config(barks_config, MAIN_WINDOW_LEFT)
        win_top = read_setting_from_config(barks_config, MAIN_WINDOW_TOP)
        log_lvl = read_setting_from_config(barks_config, LOG_LEVEL)
        # A setting newer than the ini (the first run after an update) is its default;
        # it must not cost the saved window geometry.
        main_screen_layout = (
            read_setting_from_config(barks_config, MAIN_SCREEN_LAYOUT)
            if barks_config.has_option(BARKS_READER_SECTION, MAIN_SCREEN_LAYOUT)
            else MATCH_THE_SCREEN
        )

        sys_paths = SystemFilePaths()
        sys_paths.set_barks_reader_files_dir(reader_files_dir, check_files=False)
        error_background_path = sys_paths.get_error_background_path()
        success_background_path = sys_paths.get_success_background_path()
        sys_paths.check_files([error_background_path, success_background_path])

        min_options = MinimalConfigOptions(
            error_background_path,
            success_background_path,
            win_height,
            win_left,
            win_top,
            log_lvl,
            main_screen_layout,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Ini error: {e}.")
        min_options = MinimalConfigOptions()

    # One line for both outcomes, so a fallback boot logs every option a read one does.
    logger.debug(
        f"Minimal config options: "
        f'"{min_options.error_background_path}",'
        f'"{min_options.success_background_path}",'
        f" {min_options.win_height},"
        f" ({min_options.win_left}, {min_options.win_top}),"
        f" '{min_options.log_level}',"
        f" '{min_options.main_screen_layout}'."
    )
    return min_options
