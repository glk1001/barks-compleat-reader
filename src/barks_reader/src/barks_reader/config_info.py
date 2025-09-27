import os
from pathlib import Path
from sys import platform as _sys_platform

APP_NAME = "barks-reader"

# This app will hook into kivy logging, so there is no kivy console
# logging required.
os.environ["KIVY_NO_ARGS"] = "1"
os.environ["KIVY_NO_CONSOLELOG"] = "1"


class ConfigInfo:
    def __init__(self) -> None:
        self._app_name = APP_NAME
        self.app_config_dir: Path | None = None
        self.app_config_path: Path | None = None
        self.kivy_config_dir: Path | None = None
        self.app_log_path: Path | None = None

        self.platform = _get_platform()

        self._setup_app_config_dir()

    def _setup_app_config_dir(self) -> None:
        self.app_config_dir = self._get_app_config_dir()

        self.app_config_dir.mkdir(parents=True, exist_ok=True)
        if not self.app_config_dir.is_dir():
            msg = f'Could not create app config directory "{self.app_config_dir}".'
            raise RuntimeError(msg)

        self.app_config_path = self.app_config_dir / (self._app_name + ".ini")

        self.kivy_config_dir = self.app_config_dir / "kivy"
        os.environ["KIVY_HOME"] = str(self.kivy_config_dir)

        log_dir = self.kivy_config_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.app_log_path = log_dir / (self._app_name + ".log")

    def _get_app_config_dir(self) -> Path:
        app_env_var = f"{self._app_name.upper()}_HOME"
        if app_env_var in os.environ:
            return Path(os.environ[app_env_var])

        return self._get_user_data_dir()

    def _get_user_data_dir(self) -> Path:
        # Determine and return the user_data_dir.
        if self.platform == "ios":
            data_dir = Path("~/Documents").expanduser() / self._app_name
        elif self.platform == "android":
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
        elif self.platform == "win":
            data_dir = Path(os.environ["APPDATA"]) / self._app_name
        elif self.platform == "macosx":
            data_dir = Path("~/Library/Application Support").expanduser()
            data_dir /= self._app_name
        else:  # _platform == 'linux' or anything else...:
            data_dir = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
            data_dir /= self._app_name

        if not data_dir.is_dir():
            data_dir.mkdir(parents=True, exist_ok=True)

        return data_dir


def _get_platform() -> str:
    # On Android sys.platform returns 'linux2', so prefer to check the
    # existence of environ variables set during Python initialization
    kivy_build = os.environ.get("KIVY_BUILD", "")

    if kivy_build in {"android", "ios"}:
        platform = kivy_build
    elif "P4A_BOOTSTRAP" in os.environ:
        platform = "android"
    elif "ANDROID_ARGUMENT" in os.environ:
        # We used to use this method to detect android platform,
        # leaving it here to be backwards compatible with `pydroid3`
        # and similar tools outside kivy's ecosystem
        platform = "android"
    elif _sys_platform in ("win32", "cygwin"):
        platform = "win"
    elif _sys_platform == "darwin":
        platform = "macosx"
    elif _sys_platform.startswith(("linux", "freebsd")):
        platform = "linux"
    else:
        platform = "unknown"

    return platform
