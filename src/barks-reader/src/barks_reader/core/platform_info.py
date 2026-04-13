import os
import platform as _platform_mod
from enum import Enum
from sys import platform as _sys_platform


class Platform(Enum):
    ANDROID = "android"
    IOS = "ios"
    MACOS_ARM64 = "macos"  # Assume most users have arm64
    MACOS_X64 = "macos-x64"
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
        if _platform_mod.machine() == "arm64":
            platform = Platform.MACOS_ARM64
        else:
            platform = Platform.MACOS_X64
    elif _sys_platform.startswith(("linux", "freebsd")):
        platform = Platform.LINUX
    else:
        platform = Platform.UNKNOWN

    return platform


PLATFORM: Platform = _get_platform()

IS_MACOS: bool = PLATFORM in (Platform.MACOS_ARM64, Platform.MACOS_X64)
