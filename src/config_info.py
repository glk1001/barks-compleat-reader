import os
from pathlib import Path
from sys import platform as _sys_platform


class ConfigInfo:
    def __init__(self, app_name: str) -> None:
        self._app_name = app_name
        self._app_config_dir: Path = Path()
        self.app_config_path: Path = Path()
        self.kivy_config_dir: Path = Path()
        self.app_log_path: Path = Path()

        self.platform = _get_platform()

    def setup_app_config_dir(self) -> None:
        self._app_config_dir = self._get_app_config_dir()

        self._app_config_dir.mkdir(parents=True, exist_ok=True)
        if not self._app_config_dir.is_dir():
            msg = f'Could not create app config directory "{self._app_config_dir}".'
            raise RuntimeError(msg)

        self.app_config_path = self._app_config_dir / (self._app_name + ".ini")

        self.kivy_config_dir = self._app_config_dir / "kivy"
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
            from jnius import autoclass, cast  # noqa: PLC0415

            # noinspection PyPep8Naming
            PythonActivity = autoclass("org.kivy.android.PythonActivity")  # noqa: N806
            context = cast("android.content.Context", PythonActivity.mActivity)
            file_p = cast("java.io.File", context.getFilesDir())
            data_dir = Path(file_p.getAbsolutePath())
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
