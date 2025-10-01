# ruff: noqa: PLC0415, EXE002

# -------------------------------------------------------------------- #
# --- We need to change the KIVY_HOME directory to be under this   --- #
# --- app's settings directory. The 'barks_reader.config_info'     --- #
# --- module handles this, and for this to work, we need to import --- #
# --- it before any kivy imports                                   --- #

import logging
import os
import platform
import sys
from configparser import ConfigParser

from barks_fantagraphics.comics_cmd_args import CmdArgs, ExtraArg
from barks_reader.config_info import ConfigInfo  # IMPORT THIS BEFORE Kivy!!
from barks_reader.reader_settings import (
    BARKS_READER_SECTION,
    MAIN_WINDOW_HEIGHT,
    MAIN_WINDOW_LEFT,
    MAIN_WINDOW_TOP,
)
from barks_reader.screen_metrics import get_approximate_taskbar_height, get_primary_screen_info
from comic_utils.comic_consts import IS_PYINSTALLER_BUNDLE, PYINSTALLER_BUNDLED_MAIN_DIR
from loguru import logger
from loguru_config import LoguruConfig

# ------------------------------------------------------------------ #

APP_LOGGING_NAME = "app"  # For use by 'loguru-config'
KIVY_LOGGING_NAME = "kivy"


# noinspection PyPep8Naming
def set_project_paths() -> None:
    if not IS_PYINSTALLER_BUNDLE:
        return

    from barks_reader.bottom_title_view_screen import BOTTOM_TITLE_VIEW_SCREEN_KV_FILE
    from barks_reader.comic_book_reader import COMIC_BOOK_READER_KV_FILE
    from barks_reader.fun_image_view_screen import FUN_IMAGE_VIEW_SCREEN_KV_FILE
    from barks_reader.intro_compleat_barks_reader import INTRO_COMPLEAT_BARKS_READER_KV_FILE
    from barks_reader.main_screen import MAIN_SCREEN_KV_FILE
    from barks_reader.reader_ui_classes import READER_TREE_VIEW_KV_FILE
    from barks_reader.tree_view_screen import TREE_VIEW_SCREEN_KV_FILE

    barks_reader_srce_dir = PYINSTALLER_BUNDLED_MAIN_DIR / "barks_reader"

    COMIC_BOOK_READER_KV_FILE = barks_reader_srce_dir / COMIC_BOOK_READER_KV_FILE.name  # noqa: N806
    READER_TREE_VIEW_KV_FILE = barks_reader_srce_dir / READER_TREE_VIEW_KV_FILE.name  # noqa: N806
    BOTTOM_TITLE_VIEW_SCREEN_KV_FILE = barks_reader_srce_dir / BOTTOM_TITLE_VIEW_SCREEN_KV_FILE.name  # noqa: N806
    FUN_IMAGE_VIEW_SCREEN_KV_FILE = barks_reader_srce_dir / FUN_IMAGE_VIEW_SCREEN_KV_FILE.name  # noqa: N806
    TREE_VIEW_SCREEN_KV_FILE = barks_reader_srce_dir / TREE_VIEW_SCREEN_KV_FILE.name  # noqa: N806
    INTRO_COMPLEAT_BARKS_READER_KV_FILE = (  # noqa: N806
        barks_reader_srce_dir / INTRO_COMPLEAT_BARKS_READER_KV_FILE.name
    )
    MAIN_SCREEN_KV_FILE = barks_reader_srce_dir / MAIN_SCREEN_KV_FILE.name  # noqa: N806

    logger.debug(f'Pyinstaller reset: COMIC_BOOK_READER_KV_FILE = "{COMIC_BOOK_READER_KV_FILE}".')
    logger.debug(f'Pyinstaller reset: READER_TREE_VIEW_KV_FILE = "{READER_TREE_VIEW_KV_FILE}".')
    logger.debug(
        f"Pyinstaller reset: BOTTOM_TITLE_VIEW_SCREEN_KV_FILE"
        f' = "{BOTTOM_TITLE_VIEW_SCREEN_KV_FILE}".'
    )
    logger.debug(
        f'Pyinstaller reset: FUN_IMAGE_VIEW_SCREEN_KV_FILE = "{FUN_IMAGE_VIEW_SCREEN_KV_FILE}".'
    )
    logger.debug(f'Pyinstaller reset: TREE_VIEW_SCREEN_KV_FILE = "{TREE_VIEW_SCREEN_KV_FILE}".')
    logger.debug(
        f"Pyinstaller reset: INTRO_COMPLEAT_BARKS_READER_KV_FILE"
        f' = "{INTRO_COMPLEAT_BARKS_READER_KV_FILE}".'
    )
    logger.debug(f'Pyinstaller reset: MAIN_SCREEN_KV_FILE = "{MAIN_SCREEN_KV_FILE}".')


def start_logging(cfg_info: ConfigInfo, args: CmdArgs) -> None:
    from kivy import Config, kivy_home_dir

    setup_loguru(cfg_info, args)

    Config.set("kivy", "log_level", logging.getLevelName(log_level).lower())
    redirect_kivy_logs()

    logger.info("*** Starting barks reader ***")
    logger.info(f'app config path = "{cfg_info.app_config_path}".')
    logger.info(f'app log path = "{log_path}".')
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
                message = log_record.getMessage().replace("{}", "{{}}")

                # Now log the kivy information using Loguru.
                # Use getattr to call the appropriate logging method based on level.
                # And fallback to 'info'.
                log_method = getattr(patched_logger, level, patched_logger.info)
                log_method(message, sys_name=KIVY_LOGGING_NAME)
            except Exception:
                self.logr.exception("Error in LoguruKivyHandler.emit: ")

    KivyLogger.addHandler(LoguruKivyHandler(logger))


# Make these log variables global so loguru-config can access them.
log_level = logging.DEBUG
log_path = None


def setup_loguru(cfg_info: ConfigInfo, _args: CmdArgs) -> None:
    from barks_reader.reader_file_paths import HOME_DIR

    global log_path  # noqa: PLW0603
    log_path = HOME_DIR / cfg_info.app_config_dir / "kivy" / "logs" / "barks-reader.log"

    global log_level  # noqa: PLW0603
    log_level = logging.DEBUG
    # log_level = cmd_args.get_log_level()  # noqa: ERA001

    run_loguru_config(cfg_info)


def run_loguru_config(cfg_info: ConfigInfo) -> None:
    # noinspection PyBroadException
    try:
        LoguruConfig.load(cfg_info.app_config_dir / "log-config.yaml")
    except Exception:  # noqa: BLE001
        logger.add(sys.stderr, level=log_level, backtrace=True, diagnose=True)
        logger.add(str(config_info.app_log_path), level=log_level, backtrace=True, diagnose=True)
    else:
        return  # all is well!

    # Failed but try again. Should fail again but at least the exception will be properly
    # logged with the above emergency config.
    # noinspection PyBroadException
    try:
        LoguruConfig.load(cfg_info.app_config_dir / "log-config.yaml")
    except:  # noqa: E722
        logger.exception("LoguruConfig failed: ")
        sys.exit(1)


def update_window_size(args: CmdArgs, cfg_info: ConfigInfo) -> None:
    cmd_arg_win_height, cmd_arg_win_left, cmd_arg_win_top = get_main_win_info_from_cmd_args(args)
    ini_win_height, ini_win_left, ini_win_top = get_main_win_info_from_ini_file(cfg_info)
    best_win_height, best_win_left, best_win_top = get_best_main_window_fit()

    win_height = cmd_arg_win_height
    win_left = cmd_arg_win_left
    win_top = cmd_arg_win_top

    if win_height == 0:
        win_height = ini_win_height if ini_win_height > 0 else best_win_height
    if win_left == -1:
        win_left = ini_win_left if ini_win_left != -1 else best_win_left
    if win_top == -1:
        win_top = ini_win_top if ini_win_top != -1 else best_win_top

    logger.debug(f"Main win dimensions: {win_height}, ({win_left}, {win_top}).")

    set_window_size(win_height, win_left, win_top)


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


def get_best_main_window_fit() -> tuple[int, int, int]:
    primary_screen_info = get_primary_screen_info()

    win_centre = primary_screen_info.monitor_x + round(primary_screen_info.width_pixels / 2)

    win_height = primary_screen_info.height_pixels - get_approximate_taskbar_height()
    win_left = win_centre - round(get_win_width_from_height(win_height) / 2)
    win_top = 0

    logger.debug(f"Best fit main win dimensions: {win_height}, ({win_left}, {win_top}).")

    return win_height, win_left, win_top


def get_win_width_from_height(win_height: int) -> int:
    comic_page_aspect_ratio = 3200.0 / 2120.0
    return round(win_height / comic_page_aspect_ratio)


def set_window_size(win_height: int, win_left: int, win_top: int) -> None:
    from kivy import Config

    if platform.system() != "Windows":
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
        Config.set("graphics", "window_state", "hidden")

    win_width = get_win_width_from_height(win_height)
    logger.debug(f"Main win width: {win_width}.")

    Config.set("graphics", "left", win_left)
    Config.set("graphics", "top", win_top)
    Config.set("graphics", "width", win_width)
    Config.set("graphics", "height", round(win_height + 45.0))

    logger.info(
        f'Set window position and size: ({win_left}, {win_top}), ({win_width}, {win_height})".'
    )


def call_reader_main(cfg_info: ConfigInfo, args: CmdArgs) -> None:
    from barks_reader.barks_reader_app import main

    main(cfg_info, args)


if __name__ == "__main__":
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

    start_logging(config_info, cmd_args)

    update_window_size(cmd_args, config_info)

    # Careful! Because of kivy import issues, we need to do this
    # just before calling app main.
    set_project_paths()

    call_reader_main(config_info, cmd_args)
