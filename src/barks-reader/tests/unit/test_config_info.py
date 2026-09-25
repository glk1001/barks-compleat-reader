"""Tests for the Kivy import ordering guard in config_info."""

from __future__ import annotations

import random
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from barks_reader.core import config_info
from barks_reader.core.config_info import (
    RANDOM_SEED_ENV_VAR,
    ConfigInfo,
    _assert_kivy_not_yet_imported,
    _find_dir_under_directory,
    barks_reader_installer_failed,
    get_barks_reader_installer_failed_flag_file,
    remove_barks_reader_installer_failed_flag,
    seed_random_from_env,
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

    def test_error_lists_the_first_five_loaded_kivy_modules_alphabetically(self) -> None:
        # The listing is capped so the message stays readable when the whole of
        # kivy is already loaded; six modules is the smallest input that shows
        # both the cap and the separator.
        clean = {k: v for k, v in sys.modules.items() if k != "kivy" and not k.startswith("kivy.")}
        for name in ("uix", "core", "graphics", "app", "clock", "base"):
            clean[f"kivy.{name}"] = ModuleType(f"kivy.{name}")

        with (
            _NOT_UNDER_PYTEST,
            patch.dict(sys.modules, clean, clear=True),
            pytest.raises(ImportError) as exc_info,
        ):
            _assert_kivy_not_yet_imported()

        assert (
            "Already-loaded kivy modules: "
            "kivy.app, kivy.base, kivy.clock, kivy.core, kivy.graphics. "
        ) in str(exc_info.value)
        assert "kivy.uix" not in str(exc_info.value)

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


class TestDirectoryEnvOverrides:
    """The config and data dir env vars win whenever set, in a build as in a checkout.

    A development run has nothing else to go on; a test harness points a built
    executable at a scratch profile the same way. A user's build has them unset
    and falls back to the directory beside the executable.
    """

    @pytest.fixture
    def compiled(self, tmp_path: Path) -> ConfigInfo:
        cfg = _bare_config_info(tmp_path)
        cfg.is_running_compiled = True
        return cfg

    def test_a_compiled_build_takes_the_config_dir_from_the_env_var(
        self, compiled: ConfigInfo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BARKS_READER_CONFIG_DIR", str(tmp_path / "scratch"))
        with patch.object(config_info, "PLATFORM", Platform.LINUX):
            assert compiled._get_app_config_dir() == tmp_path / "scratch"  # noqa: SLF001

    def test_a_compiled_build_takes_the_data_dir_from_the_env_var(
        self, compiled: ConfigInfo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BARKS_READER_DATA_DIR", str(tmp_path / "data"))
        assert compiled._get_app_data_dir() == tmp_path / "data"  # noqa: SLF001

    def test_a_compiled_build_without_the_env_vars_uses_its_own_directory(
        self, compiled: ConfigInfo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("BARKS_READER_CONFIG_DIR", raising=False)
        monkeypatch.delenv("BARKS_READER_DATA_DIR", raising=False)
        with patch.object(config_info, "PLATFORM", Platform.LINUX):
            assert compiled._get_app_config_dir() == tmp_path / "config"  # noqa: SLF001
        assert compiled._get_app_data_dir() == tmp_path  # noqa: SLF001

    def test_a_checkout_without_the_env_vars_refuses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = _bare_config_info(tmp_path)
        cfg.is_running_compiled = False
        monkeypatch.delenv("BARKS_READER_CONFIG_DIR", raising=False)
        monkeypatch.delenv("BARKS_READER_DATA_DIR", raising=False)
        with pytest.raises(RuntimeError, match="BARKS_READER_CONFIG_DIR"):
            cfg._get_app_config_dir()  # noqa: SLF001
        with pytest.raises(RuntimeError, match="BARKS_READER_DATA_DIR"):
            cfg._get_app_data_dir()  # noqa: SLF001


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


# ---------------------------------------------------------------------------
# seed_random_from_env
# ---------------------------------------------------------------------------


class TestSeedRandomFromEnv:
    """Opt-in determinism: unset, the app keeps picking different art each run."""

    @staticmethod
    def _sample() -> list[float]:
        return [random.random() for _ in range(5)]

    def test_unset_does_not_seed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(RANDOM_SEED_ENV_VAR, raising=False)
        assert seed_random_from_env() is None

    def test_same_seed_gives_the_same_sequence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(RANDOM_SEED_ENV_VAR, "1234")
        assert seed_random_from_env() == 1234  # noqa: PLR2004
        first = self._sample()
        seed_random_from_env()
        assert self._sample() == first

    def test_different_seeds_give_different_sequences(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(RANDOM_SEED_ENV_VAR, "1")
        seed_random_from_env()
        first = self._sample()
        monkeypatch.setenv(RANDOM_SEED_ENV_VAR, "2")
        seed_random_from_env()
        assert self._sample() != first

    def test_a_non_number_is_ignored_rather_than_fatal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A typo in the variable must not stop the app starting."""
        monkeypatch.setenv(RANDOM_SEED_ENV_VAR, "banana")
        assert seed_random_from_env() is None
