import os
from sys import platform as _sys_platform


class ConfigInfo:
    def __init__(self, app_name: str):
        self.app_name = app_name
        self.app_config_dir = ""
        self.app_config_path = ""
        self.kivy_config_dir = ""
        self.app_log_path = ""

        self.platform = _get_platform()

    def setup_app_config_dir(self) -> None:
        self.app_config_dir = self._get_app_config_dir()

        os.makedirs(self.app_config_dir, exist_ok=True)
        if not os.path.isdir(self.app_config_dir):
            raise RuntimeError(f'Could not create app config directory "{self.app_config_dir}".')

        self.app_config_path = os.path.join(self.app_config_dir, self.app_name + ".ini")

        self.kivy_config_dir = os.path.join(self.app_config_dir, "kivy")
        os.environ["KIVY_HOME"] = self.kivy_config_dir

        log_dir = os.path.join(self.kivy_config_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        self.app_log_path = os.path.join(log_dir, self.app_name + ".log")

    def _get_app_config_dir(self):
        app_env_var = f"{self.app_name.upper()}_HOME"
        if app_env_var in os.environ:
            return os.environ[app_env_var]

        return self._get_user_data_dir()

    def _get_user_data_dir(self):
        # Determine and return the user_data_dir.
        if self.platform == "ios":
            data_dir = os.path.expanduser(os.path.join("~/Documents", self.app_name))
        elif self.platform == "android":
            from jnius import autoclass, cast

            # noinspection PyPep8Naming
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            context = cast("android.content.Context", PythonActivity.mActivity)
            file_p = cast("java.io.File", context.getFilesDir())
            data_dir = file_p.getAbsolutePath()
        elif self.platform == "win":
            data_dir = os.path.join(os.environ["APPDATA"], self.app_name)
        elif self.platform == "macosx":
            data_dir = "~/Library/Application Support/{}".format(self.app_name)
            data_dir = os.path.expanduser(data_dir)
        else:  # _platform == 'linux' or anything else...:
            data_dir = os.environ.get("XDG_CONFIG_HOME", "~/.config")
            data_dir = os.path.expanduser(os.path.join(data_dir, self.app_name))
        if not os.path.exists(data_dir):
            os.mkdir(data_dir)
        return data_dir


def _get_platform():
    # On Android sys.platform returns 'linux2', so prefer to check the
    # existence of environ variables set during Python initialization
    kivy_build = os.environ.get("KIVY_BUILD", "")
    if kivy_build in {"android", "ios"}:
        return kivy_build
    elif "P4A_BOOTSTRAP" in os.environ:
        return "android"
    elif "ANDROID_ARGUMENT" in os.environ:
        # We used to use this method to detect android platform,
        # leaving it here to be backwards compatible with `pydroid3`
        # and similar tools outside kivy's ecosystem
        return "android"
    elif _sys_platform in ("win32", "cygwin"):
        return "win"
    elif _sys_platform == "darwin":
        return "macosx"
    elif _sys_platform.startswith("linux"):
        return "linux"
    elif _sys_platform.startswith("freebsd"):
        return "linux"
    return "unknown"
