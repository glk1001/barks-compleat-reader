from __future__ import annotations

import platform as platform_mod
from unittest.mock import patch

from barks_reader.core import platform_info as platform_info_module
from barks_reader.core.platform_info import Platform, _get_platform


class TestGetPlatform:
    def test_ios_via_kivy_build(self) -> None:
        with patch.dict(platform_info_module.os.environ, {"KIVY_BUILD": "ios"}, clear=True):
            assert _get_platform() == Platform.IOS

    def test_android_via_kivy_build(self) -> None:
        with patch.dict(platform_info_module.os.environ, {"KIVY_BUILD": "android"}, clear=True):
            assert _get_platform() == Platform.ANDROID

    def test_android_via_p4a_bootstrap(self) -> None:
        with patch.dict(
            platform_info_module.os.environ,
            {"KIVY_BUILD": "", "P4A_BOOTSTRAP": "sdl2"},
            clear=True,
        ):
            assert _get_platform() == Platform.ANDROID

    def test_android_via_android_argument(self) -> None:
        with patch.dict(
            platform_info_module.os.environ,
            {"KIVY_BUILD": "", "ANDROID_ARGUMENT": ""},
            clear=True,
        ):
            assert _get_platform() == Platform.ANDROID

    def test_windows(self) -> None:
        with (
            patch.dict(platform_info_module.os.environ, {"KIVY_BUILD": ""}, clear=True),
            patch.object(platform_info_module, "_sys_platform", "win32"),
        ):
            assert _get_platform() == Platform.WIN

    def test_cygwin(self) -> None:
        with (
            patch.dict(platform_info_module.os.environ, {"KIVY_BUILD": ""}, clear=True),
            patch.object(platform_info_module, "_sys_platform", "cygwin"),
        ):
            assert _get_platform() == Platform.WIN

    def test_macos_arm64(self) -> None:
        with (
            patch.dict(platform_info_module.os.environ, {"KIVY_BUILD": ""}, clear=True),
            patch.object(platform_info_module, "_sys_platform", "darwin"),
            patch.object(platform_mod, "machine", return_value="arm64"),
        ):
            assert _get_platform() == Platform.MACOS_ARM64

    def test_macos_x64(self) -> None:
        with (
            patch.dict(platform_info_module.os.environ, {"KIVY_BUILD": ""}, clear=True),
            patch.object(platform_info_module, "_sys_platform", "darwin"),
            patch.object(platform_mod, "machine", return_value="x86_64"),
        ):
            assert _get_platform() == Platform.MACOS_X64

    def test_linux(self) -> None:
        with (
            patch.dict(platform_info_module.os.environ, {"KIVY_BUILD": ""}, clear=True),
            patch.object(platform_info_module, "_sys_platform", "linux"),
        ):
            assert _get_platform() == Platform.LINUX

    def test_freebsd(self) -> None:
        with (
            patch.dict(platform_info_module.os.environ, {"KIVY_BUILD": ""}, clear=True),
            patch.object(platform_info_module, "_sys_platform", "freebsd12"),
        ):
            assert _get_platform() == Platform.LINUX

    def test_unknown_platform(self) -> None:
        with (
            patch.dict(platform_info_module.os.environ, {"KIVY_BUILD": ""}, clear=True),
            patch.object(platform_info_module, "_sys_platform", "sunos5"),
        ):
            assert _get_platform() == Platform.UNKNOWN
