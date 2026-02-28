# Need to sort out Android packages and how to handle installer.
# ruff: noqa: ERA001

import os
import sys
from pathlib import Path

from loguru import logger
from loguru_config import LoguruConfig

from barks_reader.core.platform_info import PLATFORM, Platform

APP_NAME = "barks-reader"

BARKS_READER_INSTALLER_FAILED_FLAG_FILE = "barks-reader-installer-failed.flag"
IOS_CONFIG_DIR = "~/Documents"

LINUX_FANTA_VOLUMES_SEARCH_PATH = ["~/opt/barks-reader", "~/Documents", "~/Books"]
WINDOWS_FANTA_VOLUMES_SEARCH_PATH = ["~/BarksReader", "~/Documents", "~/Books"]
MACOS_FANTA_VOLUMES_SEARCH_PATH = [
    "~/Applications/BarksReader",
    "~/Documents",
    "~/Books",
]

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
        main_script_dir = Path(__file__).parent.parent.parent.parent.parent.parent
        assert (main_script_dir / "main.py").is_file()
        self.is_running_under_pycrucible = main_script_dir.name == "pycrucible_payload"

        self.app_dir = main_script_dir.parent

        self._app_name = APP_NAME
        self.app_config_dir: Path = None  # ty: ignore[invalid-assignment]
        self.app_config_path: Path = None  # ty: ignore[invalid-assignment]
        self.app_data_dir: Path = None  # ty: ignore[invalid-assignment]
        self.kivy_config_dir: Path = None  # ty: ignore[invalid-assignment]
        self.app_log_path: Path = None  # ty: ignore[invalid-assignment]
        self.error_background_path: Path = None  # ty: ignore[invalid-assignment]

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
        if not self.is_running_under_pycrucible:
            app_env_var = f"{self._app_name.upper().replace('-', '_')}_CONFIG_DIR"
            if app_env_var not in os.environ:
                msg = f'Not running under pycrucible. Expected config env var "{app_env_var}".'
                raise RuntimeError(msg)
            return Path(os.environ[app_env_var])

        return self._get_user_app_config_dir()

    def _get_user_app_config_dir(self) -> Path:
        # Determine and return the user_data_dir.
        if PLATFORM == Platform.IOS:
            config_dir = Path(IOS_CONFIG_DIR).expanduser() / self._app_name
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
            # config_dir = Path(file_p.getAbsolutePath())
        else:  # anything else...:
            config_dir = self.app_dir
            config_dir /= "config"

        # Need to sort out Android and installer requirements.
        # noinspection PyUnboundLocalVariable
        return config_dir

    def _get_app_data_dir(self) -> Path:
        if not self.is_running_under_pycrucible:
            app_env_var = f"{self._app_name.upper().replace('-', '_')}_DATA_DIR"
            if app_env_var not in os.environ:
                msg = f'Not running under pycrucible. Expected data env var "{app_env_var}".'
                raise RuntimeError(msg)
            return Path(os.environ[app_env_var])

        return self.app_dir


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


def find_fanta_volumes_dirpath(config_info: ConfigInfo, fanta_volumes_dirname: str) -> Path | None:
    if PLATFORM == Platform.WIN:
        search_path = WINDOWS_FANTA_VOLUMES_SEARCH_PATH
    elif PLATFORM == Platform.MACOSX:
        search_path = MACOS_FANTA_VOLUMES_SEARCH_PATH
    else:
        search_path = LINUX_FANTA_VOLUMES_SEARCH_PATH

    vol_path = _find_fanta_volumes(config_info, fanta_volumes_dirname, search_path)
    if not vol_path:
        logger.warning(
            f"Could not find Fantagraphics Barks Library"
            f' directory "{fanta_volumes_dirname}".'
            f' Looked in search path "{search_path}".'
        )

    return vol_path


def _find_fanta_volumes(
    config_info: ConfigInfo, fanta_volumes_dirname: str, search_path: list[str]
) -> Path | None:
    search_path = [str(config_info.app_data_dir), *search_path]
    return _find_dir_on_search_path(search_path, fanta_volumes_dirname)


def _find_dir_on_search_path(search_path: list[str], target_dirname: str) -> Path | None:
    for path in search_path:
        dirpath = Path(path).expanduser()
        if not dirpath.is_dir():
            logger.debug(f'Searching: "{dirpath}" is not a directory.')
            continue

        candidates = _find_dir_under_directory(dirpath, target_dirname)
        if candidates:
            return candidates[0]
        logger.debug(f'Searching: "{target_dirname}" not found under "{dirpath}".')

    return None


def _find_dir_under_directory(start_path: Path, target_dirname: str) -> list[Path]:
    return [path for path in start_path.iterdir() if path.is_dir() and path.name == target_dirname]
