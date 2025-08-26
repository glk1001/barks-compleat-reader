# ------------------------------------------------------------------ #
# --- We need to change the KIVY_HOME directory to be under this --- #
# --- app's settings directory. The 'config_info' module handles --- #
# --- this, and for this to work, we need to import it before    --- #
# --- any kivy imports.                                          --- #

import logging
import sys

from barks_fantagraphics.comics_cmd_args import CmdArgs, ExtraArg
from loguru import logger
from loguru_config import LoguruConfig

from barks_reader.config_info import ConfigInfo

# ------------------------------------------------------------------ #

APP_LOGGING_NAME = "app"  # For use by 'loguru-config'
KIVY_LOGGING_NAME = "kivy"


def start_logging(cfg_info: ConfigInfo, args: CmdArgs) -> None:
    from kivy import Config  # noqa: PLC0415

    setup_loguru(cfg_info, args)

    Config.set("kivy", "log_level", logging.getLevelName(log_level).lower())
    redirect_kivy_logs()

    logger.info("*** Starting barks reader ***")
    logger.info(f'app config path = "{cfg_info.app_config_path}".')
    logger.info(f'app log path = "{log_path}".')
    logger.info(f'kivy config dir = "{cfg_info.kivy_config_dir}".')


def redirect_kivy_logs() -> None:
    from kivy import Logger as KivyLogger  # noqa: PLC0415

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
    from barks_reader.reader_file_paths import HOME_DIR  # noqa: PLC0415

    global log_path  # noqa: PLW0603
    log_path = HOME_DIR / cfg_info.app_config_dir / "kivy" / "logs" / "barks-reader.log"

    global log_level  # noqa: PLW0603
    log_level = logging.DEBUG
    # log_level = cmd_args.get_log_level()

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


def update_window_size(args: CmdArgs) -> None:
    win_height = args.get_extra_arg("--win_height")
    if win_height == 0:
        return

    win_left = args.get_extra_arg("--win_left")

    set_window_size(win_left, win_height)


def set_window_size(win_left: int, win_height: int) -> None:
    from kivy import Config  # noqa: PLC0415

    Config.set("graphics", "left", win_left)
    comic_page_aspect_ratio = 3200.0 / 2120.0
    Config.set("graphics", "width", round(win_height / comic_page_aspect_ratio))
    Config.set("graphics", "height", round(win_height + 45.0))


def call_reader_main(cfg_info: ConfigInfo, args: CmdArgs) -> None:
    from barks_reader.barks_reader_app import main  # noqa: PLC0415

    main(cfg_info, args)


if __name__ == "__main__":
    config_info = ConfigInfo()

    EXTRA_ARGS: list[ExtraArg] = [
        ExtraArg("--win-left", action="store", type=int, default=0),
        ExtraArg("--win-height", action="store", type=int, default=0),
    ]
    cmd_args = CmdArgs("Compleat Barks Reader", extra_args=EXTRA_ARGS)
    args_ok, error_msg = cmd_args.args_are_valid()
    if not args_ok:
        sys.exit(1)

    update_window_size(cmd_args)

    start_logging(config_info, cmd_args)

    call_reader_main(config_info, cmd_args)
