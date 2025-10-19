import os
from enum import Enum
from sys import platform as _sys_platform


class Platform(Enum):
    ANDROID = "android"
    IOS = "ios"
    MACOSX = "macosx"
    LINUX = "linux"
    WIN = "win"
    UNKNOWN = "unknown"


def _get_platform() -> Platform:
    # On Android sys.platform returns 'linux2', so prefer checking the
    # existence of environ variables set during Python initialization.
    kivy_build = os.environ.get("KIVY_BUILD", "")

    if kivy_build == "ios":
        platform = Platform.IOS
    elif kivy_build == "android" or "P4A_BOOTSTRAP" in os.environ:
        platform = Platform.ANDROID
    elif "ANDROID_ARGUMENT" in os.environ:
        # We used to use this method to detect android platform,
        # leaving it here to be backwards compatible with `pydroid3`
        # and similar tools outside kivy's ecosystem
        platform = Platform.ANDROID
    elif _sys_platform in ("win32", "cygwin"):
        platform = Platform.WIN
    elif _sys_platform == "darwin":
        platform = Platform.MACOSX
    elif _sys_platform.startswith(("linux", "freebsd")):
        platform = Platform.LINUX
    else:
        platform = Platform.UNKNOWN

    return platform


PLATFORM = _get_platform()
