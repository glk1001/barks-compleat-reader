# Need to sort out Android packages and how to handle pyinstaller.
# ruff: noqa: ERA001

import os
import sys
from pathlib import Path

from loguru import logger
from loguru_config import LoguruConfig

from barks_reader.platform_info import PLATFORM, Platform

APP_NAME = "barks-reader"

BARKS_READER_INSTALLER_FAILED_FLAG_FILE = "barks-reader-installer-failed.flag"
IOS_CONFIG_DIR = "~/Documents"
LINUX_CONFIG_DIR = os.environ.get("XDG_CONFIG_HOME", "~/.config")
LINUX_APP_DIR = "~/.local/share"
MACOS_CONFIG_DIR = "~/Library/Application Support"
WINDOWS_CONFIG_DIR = os.environ.get("APPDATA", "")

# This app will hook into kivy logging, so there is no kivy console
# logging required.
os.environ["KIVY_NO_ARGS"] = "1"
os.environ["KIVY_NO_CONSOLELOG"] = "1"


class ConfigInfo:
    """Configure the apps config directory and force Kivy to use it.

    To do this, we make the KIVY_HOME directory to be under the apps config dir.
    For this to work, this module must be imported before any kivy imports.
    """

    # noinspection PyTypeChecker
    def __init__(self) -> None:
        self._app_name = APP_NAME
        self.app_config_dir: Path = None
        self.app_config_path: Path = None
        self.app_data_dir: Path = None
        self.kivy_config_dir: Path = None
        self.app_log_path: Path = None

        self._setup_app_config_dir()

        assert self.app_config_dir
        assert self.app_config_path
        assert self.app_data_dir
        assert self.kivy_config_dir
        assert self.app_log_path

    def _setup_app_config_dir(self) -> None:
        self.app_config_dir = self._get_app_config_dir()
        assert self.app_config_dir

        self.app_config_dir.mkdir(parents=True, exist_ok=True)
        if not self.app_config_dir.is_dir():
            msg = f'Could not create app config directory "{self.app_config_dir}".'
            raise RuntimeError(msg)

        self.app_config_path = self.app_config_dir / (self._app_name + ".ini")

        self.app_data_dir = self._get_app_data_dir()
        assert self.app_data_dir

        self.kivy_config_dir = self.app_config_dir / "kivy"
        os.environ["KIVY_HOME"] = str(self.kivy_config_dir)

        log_dir = self.kivy_config_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.app_log_path = log_dir / (self._app_name + ".log")

    def get_executable_name(self) -> str:
        executable_name = self._app_name + "-" + PLATFORM.value

        if PLATFORM == Platform.WIN:
            executable_name += ".exe"

        return executable_name

    def _get_app_config_dir(self) -> Path:
        app_env_var = f"{self._app_name.upper()}_CONFIG_DIR"
        if app_env_var in os.environ:
            return Path(os.environ[app_env_var])

        return self._get_user_app_config_dir()

    def _get_user_app_config_dir(self) -> Path:
        # Determine and return the user_data_dir.
        if PLATFORM == Platform.IOS:
            data_dir = Path(IOS_CONFIG_DIR).expanduser() / self._app_name
        elif PLATFORM == Platform.ANDROID:
            pass
            # from jnius import autoclass
            #
            # # noinspection PyPep8Naming
            # PythonActivity = autoclass("org.kivy.android.PythonActivity")
            # # noinspection PyTypeHints
            # context = cast("android.content.Context", PythonActivity.mActivity)
            # # noinspection PyTypeHints
            # file_p = cast("java.io.File", context.getFilesDir())
            # data_dir = Path(file_p.getAbsolutePath())
        elif PLATFORM == Platform.WIN:
            data_dir = Path(WINDOWS_CONFIG_DIR) / self._app_name
        elif PLATFORM == Platform.MACOSX:
            data_dir = Path(MACOS_CONFIG_DIR).expanduser()
            data_dir /= self._app_name
        else:  # _platform == 'linux' or anything else...:
            data_dir = Path(LINUX_CONFIG_DIR).expanduser()
            data_dir /= self._app_name

        # Need to sort out Android and pyinstaller requirements.
        # noinspection PyUnboundLocalVariable
        if not data_dir.is_dir():
            data_dir.mkdir(parents=True, exist_ok=True)

        return data_dir

    def _get_app_data_dir(self) -> Path:
        app_env_var = f"{self._app_name.upper()}_DATA_DIR"
        if app_env_var in os.environ:
            return Path(os.environ[app_env_var])

        if PLATFORM in [Platform.IOS, Platform.ANDROID, Platform.WIN, Platform.MACOSX]:
            return self._get_user_app_config_dir()

        return Path(LINUX_APP_DIR).expanduser() / self._app_name


def barks_reader_installer_failed() -> bool:
    return get_barks_reader_installer_failed_flag_file().is_file()


def set_barks_reader_installer_failed_flag() -> None:
    with get_barks_reader_installer_failed_flag_file().open("w"):
        pass


def remove_barks_reader_installer_failed_flag() -> None:
    get_barks_reader_installer_failed_flag_file().unlink(missing_ok=True)


def get_barks_reader_installer_failed_flag_file() -> Path:
    # Put the flag file on the same level as the pycrucible executable.
    return Path.cwd().parent / BARKS_READER_INSTALLER_FAILED_FLAG_FILE


# Make these log variables global so loguru-config can access them.
APP_LOGGING_NAME = "app"  # For use by 'loguru-config'
KIVY_LOGGING_NAME = "kivy"
log_level = "DEBUG"
log_path = None


def get_log_level() -> str:
    return log_level


def get_log_path() -> Path | None:
    return log_path


def setup_loguru(cfg_info: ConfigInfo, log_lvl: str) -> None:
    global log_path  # noqa: PLW0603
    log_path = cfg_info.app_config_dir / "kivy" / "logs" / "barks-reader.log"

    global log_level  # noqa: PLW0603
    log_level = log_lvl

    _run_loguru_config(cfg_info)


def _run_loguru_config(cfg_info: ConfigInfo) -> None:
    # noinspection PyBroadException
    try:
        LoguruConfig.load(cfg_info.app_config_dir / "log-config.yaml")
    except Exception:  # noqa: BLE001
        logger.add(sys.stderr, level=log_level, backtrace=True, diagnose=True)
        logger.add(str(cfg_info.app_log_path), level=log_level, backtrace=True, diagnose=True)
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
