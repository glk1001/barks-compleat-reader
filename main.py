# ruff: noqa: PLC0415, EXE002

# -------------------------------------------------------------------- #
# --- We need to change the KIVY_HOME directory to be under this   --- #
# --- app's settings directory. The 'barks_reader.config_info'     --- #
# --- module handles this, and for this to work, we need to import --- #
# --- it before any kivy imports.                                  --- #

import logging
import os
import sys
from configparser import ConfigParser

from barks_fantagraphics.comics_cmd_args import CmdArgs, ExtraArg
from barks_reader.config_info import (  # IMPORT THIS BEFORE Kivy!!
    KIVY_LOGGING_NAME,
    ConfigInfo,
    barks_reader_installer_failed,
    get_barks_reader_installer_failed_flag_file,
    get_log_level,
    get_log_path,
    log_level,
    setup_loguru,
)
from barks_reader.minimal_config_info import MinimalConfigOptions, get_minimal_config_options
from barks_reader.platform_info import PLATFORM, Platform
from barks_reader.reader_consts_and_types import RAW_ACTION_BAR_SIZE_Y
from barks_reader.reader_settings import (
    BARKS_READER_SECTION,
    MAIN_WINDOW_HEIGHT,
    MAIN_WINDOW_LEFT,
    MAIN_WINDOW_TOP,
)
from barks_reader.reader_utils import get_best_window_height_fit, get_win_width_from_height
from barks_reader.screen_metrics import SCREEN_METRICS
from loguru import logger

# ------------------------------------------------------------------ #


def start_logging(cfg_info: ConfigInfo, _args: CmdArgs, min_options: MinimalConfigOptions) -> None:
    # 'kivy.Config' is defined under an 'if'.
    from kivy import Config, kivy_home_dir  # ty: ignore[possibly-missing-import]

    setup_loguru(cfg_info, min_options.log_level)

    Config.set("kivy", "log_level", log_level.lower())  # ty: ignore[possibly-missing-attribute]
    redirect_kivy_logs()

    logger.info("*** Starting barks reader ***")
    logger.info(f"running_under_pycrucible = {cfg_info.is_running_under_pycrucible}")
    logger.info(f'app dir = "{cfg_info.app_dir}".')
    logger.info(f'app config path = "{cfg_info.app_config_path}".')
    logger.info(f'app_data_dir = "{cfg_info.app_data_dir}".')
    logger.info(f'app log path = "{get_log_path()}".')
    logger.info(f'app log level = "{get_log_level()}".')
    logger.info(f'kivy config dir = "{cfg_info.kivy_config_dir}".')
    logger.info(f'KIVY_HOME = "{os.environ["KIVY_HOME"]}".')
    logger.info(f'kivy_home_dir = "{kivy_home_dir}".')

    if kivy_home_dir != str(cfg_info.kivy_config_dir):
        msg = (
            f'Config problem: Kivy home directory: "{kivy_home_dir}"'
            f' != app config directory: "{cfg_info.kivy_config_dir}".'
        )
        raise RuntimeError(msg)


def redirect_kivy_logs() -> None:
    from kivy import Logger as KivyLogger

    # Redirect Kivy's log messages to our main loguru setup.
    class LoguruKivyHandler(logging.Handler):
        # noinspection Annotator
        def __init__(self, logr) -> None:  # noqa: ANN001
            self.logr = logr
            super().__init__()

        def emit(self, log_record: logging.LogRecord) -> None:
            # noinspection Annotator
            def patch_loguru_rec(record) -> None:  # noqa: ANN001
                record.update(exception=log_record.exc_info)
                record.update(file=log_record.filename)
                record.update(function=log_record.funcName)
                record.update(line=log_record.lineno)
                record.update(module=log_record.module)
                record.update(name=log_record.name)
                record.update(process=log_record.process)
                record.update(thread=log_record.thread)

            # noinspection PyBroadException
            try:
                patched_logger = self.logr.patch(patch_loguru_rec)
                level = logging.getLevelName(log_record.levelno).lower()

                # Kivy emits this message: "kivy: Modules: Start <inspector> with config {}"
                # which we need to be careful with.
                message = log_record.getMessage().replace("{", "{{").replace("}", "}}")

                # Now log the kivy information using Loguru.
                # Use getattr to call the appropriate logging method based on level.
                # And fallback to 'info'.
                log_method = getattr(patched_logger, level, patched_logger.info)
                log_method(message, sys_name=KIVY_LOGGING_NAME)
            except Exception:
                self.logr.exception("Error in LoguruKivyHandler.emit: ")

    KivyLogger.addHandler(LoguruKivyHandler(logger))


def update_window_size(args: CmdArgs, min_options: MinimalConfigOptions) -> None:
    ini_win_height, ini_win_left, ini_win_top = (
        min_options.win_height,
        min_options.win_left,
        min_options.win_top,
    )
    cmd_arg_win_height, cmd_arg_win_left, cmd_arg_win_top = get_main_win_info_from_cmd_args(args)
    best_win_height, best_win_left, best_win_top = get_main_win_from_screen_metrics()

    win_height = cmd_arg_win_height
    win_left = cmd_arg_win_left
    win_top = cmd_arg_win_top

    if win_height == 0:
        win_height = ini_win_height if ini_win_height > 0 else best_win_height
    if win_left == -1:
        win_left = ini_win_left if ini_win_left != -1 else best_win_left
    if win_top == -1:
        if win_height == best_win_height:
            win_top = best_win_top
        else:
            win_top = (
                ini_win_top if ini_win_top != -1 else max(0, ((best_win_height - win_height) // 2))
            )

    logger.debug(f"Main win dimensions: {win_height}, ({win_left}, {win_top}).")

    set_window_size(win_height, win_left, win_top)

    if min_options.reader_app_icon_path:
        from kivy import Config  # ty: ignore[possibly-missing-import]

        logger.debug(f'App icon file: "{min_options.reader_app_icon_path}".')
        Config.set("kivy", "window_icon", str(min_options.reader_app_icon_path))  # ty: ignore[possibly-missing-attribute]


def get_main_win_info_from_cmd_args(args: CmdArgs) -> tuple[int, int, int]:
    win_height = args.get_extra_arg("--win_height")
    win_left = args.get_extra_arg("--win_left")
    win_top = args.get_extra_arg("--win_top")

    logger.debug(f"Cmd arg main win dimensions: {win_height}, ({win_left}, {win_top}).")

    return win_height, win_left, win_top


def get_main_win_info_from_ini_file(cfg_info: ConfigInfo) -> tuple[int, int, int]:
    barks_config = ConfigParser()
    barks_config.read(cfg_info.app_config_path)

    try:
        win_height = int(barks_config.get(BARKS_READER_SECTION, MAIN_WINDOW_HEIGHT))
        win_left = int(barks_config.get(BARKS_READER_SECTION, MAIN_WINDOW_LEFT))
        win_top = int(barks_config.get(BARKS_READER_SECTION, MAIN_WINDOW_TOP))

        logger.debug(f"Ini main win dimensions: {win_height}, ({win_left}, {win_top}).")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Ini error: {e}.")
        logger.debug("Ini main win dimensions: 0, (-1, -1).")
        return 0, 0, 0
    else:
        return win_height, win_left, win_top


def get_main_win_from_screen_metrics() -> tuple[int, int, int]:
    primary_screen_info = SCREEN_METRICS.get_primary_screen_info()

    win_centre = primary_screen_info.monitor_x + round(primary_screen_info.width_pixels / 2)

    win_height_margin = 20
    win_height = get_best_window_height_fit(primary_screen_info.height_pixels) - win_height_margin
    win_left = win_centre - round(get_win_width_from_height(win_height) / 2)
    win_top = win_height_margin // 2

    logger.debug(f"Best fit main win dimensions: {win_height}, ({win_left}, {win_top}).")

    return win_height, win_left, win_top


def set_window_size(win_height: int, win_left: int, win_top: int) -> None:
    from kivy import Config  # ty: ignore[possibly-missing-import]

    # noinspection LongLine
    if PLATFORM != Platform.WIN:
        # For some reason, kivy on Windows does not like window_state = 'hidden'.
        # It trashes fonts, and crashes with
        #      File "C:\Users\User\source\repos\barks-compleat-reader\.venv\Lib\site-packages\kivy\input\providers\mouse.py", line 312, in create_hover  # noqa: E501
        #      nx /= win._density  # noqa: ERA001
        #      |     |   -> <NumericProperty name=_density>
        #      |     -> <kivy.core.window.window_sdl2.WindowSDL object at 0x000001E400937380>
        #      -> 0.0
        #
        # ZeroDivisionError: float division by zero

        # Don't show anything until the app decides to.
        Config.set("graphics", "window_state", "hidden")  # ty: ignore[possibly-missing-attribute]

    # Note: Can't use dp(RAW_ACTION_BAR_SIZE_Y) here because importing 'dp'
    #       initializes the Window with wrong dimensions.
    win_width = get_win_width_from_height(win_height - RAW_ACTION_BAR_SIZE_Y)
    logger.debug(f"Main win width: {win_width}.")

    Config.set("graphics", "left", win_left)  # ty: ignore[possibly-missing-attribute]
    Config.set("graphics", "top", win_top)  # ty: ignore[possibly-missing-attribute]
    Config.set("graphics", "width", win_width)  # ty: ignore[possibly-missing-attribute]
    Config.set("graphics", "height", win_height)  # ty: ignore[possibly-missing-attribute]

    logger.info(
        f"Set window position and size: ({win_left}, {win_top}), ({win_width}, {win_height})."
    )


def call_reader_main(cfg_info: ConfigInfo, args: CmdArgs) -> None:
    from barks_reader.barks_reader_app import main

    main(cfg_info, args)


def ok_to_run() -> bool:
    if not barks_reader_installer_failed():
        return True

    logger.critical("Cannot run the Barks Reader. It looks like the Barks Reader installer failed.")
    logger.info(
        f"This is based on finding the Barks Reader FAILED flag"
        f' file at "{get_barks_reader_installer_failed_flag_file()}".'
    )
    return False


if __name__ == "__main__":
    if not ok_to_run():
        sys.exit(1)

    config_info = ConfigInfo()

    EXTRA_ARGS: list[ExtraArg] = [
        ExtraArg("--win-height", action="store", type=int, default=0),
        ExtraArg("--win-left", action="store", type=int, default=-1),
        ExtraArg("--win-top", action="store", type=int, default=-1),
    ]
    cmd_args = CmdArgs("Compleat Barks Reader", extra_args=EXTRA_ARGS)
    args_ok, error_msg = cmd_args.args_are_valid()
    if not args_ok:
        sys.exit(1)

    minimal_options = get_minimal_config_options(config_info)

    assert minimal_options.error_background_path
    config_info.error_background_path = minimal_options.error_background_path

    start_logging(config_info, cmd_args, minimal_options)

    update_window_size(cmd_args, minimal_options)

    call_reader_main(config_info, cmd_args)
