import logging
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from barks_reader.core.config_info import ConfigInfo


@dataclass
class MinimalConfigOptions:
    error_background_path: Path | None = None
    success_background_path: Path | None = None
    win_height: int = 0
    win_left: int = -1
    win_top: int = -1
    log_level: str = logging.getLevelName(logging.INFO)


def get_minimal_config_options(cfg_info: ConfigInfo) -> MinimalConfigOptions:
    from barks_reader.core.reader_settings import (  # noqa: PLC0415
        BARKS_READER_SECTION,
        LOG_LEVEL,
        MAIN_WINDOW_HEIGHT,
        MAIN_WINDOW_LEFT,
        MAIN_WINDOW_TOP,
        ReaderSettings,
    )
    from barks_reader.core.system_file_paths import SystemFilePaths  # noqa: PLC0415

    barks_config = ConfigParser()
    barks_config.read(cfg_info.app_config_path)

    try:
        reader_files_dir = ReaderSettings.get_reader_files_dir(cfg_info.app_data_dir)
        win_height = int(barks_config.get(BARKS_READER_SECTION, MAIN_WINDOW_HEIGHT))
        win_left = int(barks_config.get(BARKS_READER_SECTION, MAIN_WINDOW_LEFT))
        win_top = int(barks_config.get(BARKS_READER_SECTION, MAIN_WINDOW_TOP))
        log_lvl = barks_config.get(BARKS_READER_SECTION, LOG_LEVEL)

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
        )

        logger.debug(
            f"Minimal config options: "
            f'"{min_options.error_background_path}",'
            f'"{min_options.success_background_path}",'
            f" {min_options.win_height},"
            f" ({min_options.win_left}, {min_options.win_top}),"
            f" '{min_options.log_level}'."
        )

    except Exception as e:  # noqa: BLE001
        logger.warning(f"Ini error: {e}.")
        min_options = MinimalConfigOptions()
        logger.debug(
            f"Minimal config options: "
            f'"{min_options.error_background_path}",'
            f'"{min_options.success_background_path}",'
            f" {min_options.win_height},"
            f" ({min_options.win_left}, {min_options.win_top}),"
            f" '{min_options.log_level}'."
        )
        return min_options
    else:
        return min_options
