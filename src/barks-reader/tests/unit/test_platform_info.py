from __future__ import annotations

import os
import platform as platform_mod
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import patch

from barks_reader.core import platform_info as platform_info_module
from barks_reader.core.platform_info import Platform, _get_platform

if TYPE_CHECKING:
    from collections.abc import Iterator

# The only environment variables `_get_platform` reads. Tests strip exactly these
# and leave the rest of the environment alone.
_PLATFORM_ENV_KEYS = ("KIVY_BUILD", "P4A_BOOTSTRAP", "ANDROID_ARGUMENT")


@contextmanager
def platform_env(**overrides: str) -> Iterator[None]:
    """Run with only ``overrides`` of the platform-detection variables set.

    Deliberately *not* ``patch.dict(os.environ, ..., clear=True)``: clearing the
    whole environment also drops mutmut's ``MUTANT_UNDER_TEST``, which its
    trampoline reads on every call — so the mutated body never runs and every
    mutant here is reported as a false survivor (it aborted the run entirely).
    Copying the real environment minus the three keys under test keeps the
    isolation without the collateral damage.
    """
    env = {k: v for k, v in os.environ.items() if k not in _PLATFORM_ENV_KEYS}
    env.update(overrides)
    with patch.dict(platform_info_module.os.environ, env, clear=True):
        yield


class TestPlatformEnum:
    def test_values(self) -> None:
        # PLATFORM.value is baked into the packaged executable name
        # (config_info: f"{app_name}-{PLATFORM.value}"), so these strings are
        # part of the build contract, not free-form labels.
        assert {p.name: p.value for p in Platform} == {
            "ANDROID": "android",
            "IOS": "ios",
            "MACOS_ARM64": "macos",
            "MACOS_X64": "macos-x64",
            "LINUX": "linux",
            "WIN": "win",
            "UNKNOWN": "unknown",
        }


class TestGetPlatform:
    def test_ios_via_kivy_build(self) -> None:
        with platform_env(KIVY_BUILD="ios"):
            assert _get_platform() == Platform.IOS

    def test_android_via_kivy_build(self) -> None:
        with platform_env(KIVY_BUILD="android"):
            assert _get_platform() == Platform.ANDROID

    def test_android_via_p4a_bootstrap(self) -> None:
        with platform_env(KIVY_BUILD="", P4A_BOOTSTRAP="sdl2"):
            assert _get_platform() == Platform.ANDROID

    def test_android_via_android_argument(self) -> None:
        with platform_env(KIVY_BUILD="", ANDROID_ARGUMENT=""):
            assert _get_platform() == Platform.ANDROID

    def test_kivy_build_is_matched_exactly(self) -> None:
        # A near-miss value must not be taken for either mobile platform: the
        # checks are equality against "ios"/"android", not a prefix or a
        # truthiness test.
        for near_miss in ("ios-simulator", "android-arm64", "IOS", "Android"):
            with (
                platform_env(KIVY_BUILD=near_miss),
                patch.object(platform_info_module, "_sys_platform", "linux"),
            ):
                assert _get_platform() == Platform.LINUX

    def test_p4a_bootstrap_and_android_argument_are_presence_checks(self) -> None:
        # Both are `in os.environ` tests, so an empty value still means Android.
        with platform_env(P4A_BOOTSTRAP=""):
            assert _get_platform() == Platform.ANDROID
        with platform_env(ANDROID_ARGUMENT=""):
            assert _get_platform() == Platform.ANDROID

    def test_windows(self) -> None:
        with platform_env(), patch.object(platform_info_module, "_sys_platform", "win32"):
            assert _get_platform() == Platform.WIN

    def test_cygwin(self) -> None:
        with platform_env(), patch.object(platform_info_module, "_sys_platform", "cygwin"):
            assert _get_platform() == Platform.WIN

    def test_macos_arm64(self) -> None:
        with (
            platform_env(),
            patch.object(platform_info_module, "_sys_platform", "darwin"),
            patch.object(platform_mod, "machine", return_value="arm64"),
        ):
            assert _get_platform() == Platform.MACOS_ARM64

    def test_macos_x64(self) -> None:
        # Anything that is not exactly "arm64" is the Intel build — including
        # Apple's other arm spellings, which never reach `platform.machine()`.
        for machine in ("x86_64", "i386", "arm", "ARM64"):
            with (
                platform_env(),
                patch.object(platform_info_module, "_sys_platform", "darwin"),
                patch.object(platform_mod, "machine", return_value=machine),
            ):
                assert _get_platform() == Platform.MACOS_X64

    def test_linux(self) -> None:
        with platform_env(), patch.object(platform_info_module, "_sys_platform", "linux"):
            assert _get_platform() == Platform.LINUX

    def test_freebsd(self) -> None:
        with platform_env(), patch.object(platform_info_module, "_sys_platform", "freebsd12"):
            assert _get_platform() == Platform.LINUX

    def test_unknown_platform(self) -> None:
        for other in ("sunos5", "aix"):
            with platform_env(), patch.object(platform_info_module, "_sys_platform", other):
                assert _get_platform() == Platform.UNKNOWN

    def test_windows_is_matched_exactly(self) -> None:
        # "win32"/"cygwin" are exact members of a tuple, not prefixes: sys.platform
        # on 64-bit Windows is still "win32", and "windows" is not a value Python
        # reports.
        with platform_env(), patch.object(platform_info_module, "_sys_platform", "windows"):
            assert _get_platform() == Platform.UNKNOWN

    def test_darwin_is_matched_exactly(self) -> None:
        with platform_env(), patch.object(platform_info_module, "_sys_platform", "darwin-x"):
            assert _get_platform() == Platform.UNKNOWN

    def test_env_wins_over_sys_platform(self) -> None:
        # The whole reason the environment is checked first: on Android
        # sys.platform reads "linux".
        with (
            platform_env(KIVY_BUILD="android"),
            patch.object(platform_info_module, "_sys_platform", "linux"),
        ):
            assert _get_platform() == Platform.ANDROID
        with (
            platform_env(KIVY_BUILD="ios"),
            patch.object(platform_info_module, "_sys_platform", "darwin"),
        ):
            assert _get_platform() == Platform.IOS


class TestModuleConstants:
    def test_platform_is_the_detected_one(self) -> None:
        # PLATFORM is `_get_platform()` evaluated at import, not a hardcoded value.
        assert _get_platform() == platform_info_module.PLATFORM

    def test_is_macos_agrees_with_platform(self) -> None:
        # Deliberately no importlib.reload() dance to see the mac branches: a
        # reload rebuilds the Platform enum class, whose members then compare
        # unequal to the ones every other test module already imported.
        assert (
            platform_info_module.PLATFORM in (Platform.MACOS_ARM64, Platform.MACOS_X64)
        ) == platform_info_module.IS_MACOS
