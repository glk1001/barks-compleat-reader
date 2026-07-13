"""Tests for the Kivy import ordering guard in config_info."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from barks_reader.core import config_info
from barks_reader.core.config_info import (
    ConfigInfo,
    _assert_kivy_not_yet_imported,
    _find_dir_under_directory,
    barks_reader_installer_failed,
    get_barks_reader_installer_failed_flag_file,
    remove_barks_reader_installer_failed_flag,
    set_barks_reader_installer_failed_flag,
)
from barks_reader.core.platform_info import Platform

_NOT_UNDER_PYTEST = patch.object(config_info, "_running_under_pytest", return_value=False)


class TestAssertKivyNotYetImported:
    def test_raises_when_kivy_in_sys_modules(self) -> None:
        fake_modules = {**sys.modules, "kivy": ModuleType("kivy")}
        with (
            _NOT_UNDER_PYTEST,
            patch.dict(sys.modules, fake_modules),
            pytest.raises(ImportError, match="Kivy was imported before"),
        ):
            _assert_kivy_not_yet_imported()

    def test_raises_when_kivy_submodule_in_sys_modules(self) -> None:
        clean = {k: v for k, v in sys.modules.items() if k != "kivy" and not k.startswith("kivy.")}
        clean["kivy.app"] = ModuleType("kivy.app")
        with (
            _NOT_UNDER_PYTEST,
            patch.dict(sys.modules, clean, clear=True),
            pytest.raises(ImportError, match=r"kivy\.app"),
        ):
            _assert_kivy_not_yet_imported()

    def test_passes_when_kivy_not_loaded(self) -> None:
        clean_modules = {
            k: v for k, v in sys.modules.items() if k != "kivy" and not k.startswith("kivy.")
        }
        with _NOT_UNDER_PYTEST, patch.dict(sys.modules, clean_modules, clear=True):
            _assert_kivy_not_yet_imported()  # Should not raise.

    def test_error_message_includes_fix_hint(self) -> None:
        fake_modules = {**sys.modules, "kivy": ModuleType("kivy")}
        with (
            _NOT_UNDER_PYTEST,
            patch.dict(sys.modules, fake_modules),
            pytest.raises(ImportError, match="ensure config_info is imported before"),
        ):
            _assert_kivy_not_yet_imported()

    def test_skipped_under_pytest(self) -> None:
        """Guard should be a no-op when running under pytest."""
        fake_modules = {**sys.modules, "kivy": ModuleType("kivy")}
        with patch.dict(sys.modules, fake_modules):
            _assert_kivy_not_yet_imported()  # Should not raise (pytest skip active).


# ---------------------------------------------------------------------------
# get_executable_name + _get_user_app_config_dir (platform branches)
# ---------------------------------------------------------------------------


def _bare_config_info(app_dir: Path) -> ConfigInfo:
    """Build a ConfigInfo without running __init__ (which requires real dirs)."""
    instance = object.__new__(ConfigInfo)
    instance._app_name = "barks-reader"  # noqa: SLF001
    instance.app_dir = app_dir
    return instance


class TestGetExecutableName:
    def test_linux_no_exe_suffix(self) -> None:
        with patch.object(config_info, "PLATFORM", Platform.LINUX):
            cfg = _bare_config_info(Path("/dev/null"))
            assert cfg.get_executable_name() == "barks-reader-linux"

    def test_windows_adds_exe_suffix(self) -> None:
        with patch.object(config_info, "PLATFORM", Platform.WIN):
            cfg = _bare_config_info(Path("/dev/null"))
            assert cfg.get_executable_name() == "barks-reader-win.exe"


class TestGetUserAppConfigDir:
    def test_ios_returns_documents_subdir(self, tmp_path: Path) -> None:
        with patch.object(config_info, "PLATFORM", Platform.IOS):
            cfg = _bare_config_info(tmp_path)
            result = cfg._get_user_app_config_dir()  # noqa: SLF001

        # IOS_CONFIG_DIR is "~/Documents" — expanduser must have been applied.
        assert result == Path(config_info.IOS_CONFIG_DIR).expanduser() / "barks-reader"

    def test_android_returns_app_dir(self, tmp_path: Path) -> None:
        with patch.object(config_info, "PLATFORM", Platform.ANDROID):
            cfg = _bare_config_info(tmp_path)
            result = cfg._get_user_app_config_dir()  # noqa: SLF001

        assert result == tmp_path

    def test_desktop_returns_app_dir_config(self, tmp_path: Path) -> None:
        with patch.object(config_info, "PLATFORM", Platform.LINUX):
            cfg = _bare_config_info(tmp_path)
            result = cfg._get_user_app_config_dir()  # noqa: SLF001

        assert result == tmp_path / "config"


# ---------------------------------------------------------------------------
# Installer-failed flag lifecycle
# ---------------------------------------------------------------------------


class TestInstallerFailedFlag:
    def test_full_lifecycle(self, tmp_path: Path) -> None:
        # The flag file lives at `get_app_exe_dir() / FLAG_FILE_NAME`.
        with patch.object(config_info, "get_app_exe_dir", lambda: tmp_path):
            # Initially absent → False.
            assert barks_reader_installer_failed() is False

            set_barks_reader_installer_failed_flag()
            assert barks_reader_installer_failed() is True
            assert get_barks_reader_installer_failed_flag_file().is_file()

            remove_barks_reader_installer_failed_flag()
            assert barks_reader_installer_failed() is False

            # Idempotent — second remove on missing file must not raise.
            remove_barks_reader_installer_failed_flag()
            assert barks_reader_installer_failed() is False


# ---------------------------------------------------------------------------
# _find_dir_under_directory
# ---------------------------------------------------------------------------


class TestFindDirUnderDirectory:
    def test_returns_matching_directory(self, tmp_path: Path) -> None:
        (tmp_path / "alpha").mkdir()
        (tmp_path / "match").mkdir()
        (tmp_path / "zulu").mkdir()
        (tmp_path / "not_a_dir.txt").touch()  # File with the same name should be skipped.

        result = _find_dir_under_directory(tmp_path, "match")

        assert result == [tmp_path / "match"]

    def test_returns_empty_when_no_match(self, tmp_path: Path) -> None:
        (tmp_path / "alpha").mkdir()
        (tmp_path / "beta").mkdir()

        assert _find_dir_under_directory(tmp_path, "nope") == []
