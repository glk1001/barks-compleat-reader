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
    LINUX_FANTA_VOLUMES_SEARCH_PATH,
    MACOS_FANTA_VOLUMES_SEARCH_PATH,
    RANDOM_SEED_ENV_VAR,
    WINDOWS_FANTA_VOLUMES_SEARCH_PATH,
    ConfigInfo,
    _assert_kivy_not_yet_imported,
    _find_dir_on_search_path,
    _find_dir_under_directory,
    _find_fanta_volumes,
    _run_loguru_config,
    barks_reader_installer_failed,
    find_fanta_volumes_dirpath,
    get_app_exe_dir,
    get_barks_reader_installer_failed_flag_file,
    get_log_level,
    get_log_path,
    remove_barks_reader_installer_failed_flag,
    seed_random_from_env,
    set_barks_reader_installer_failed_flag,
    setup_loguru,
)
from barks_reader.core.platform_info import Platform

_NOT_UNDER_PYTEST = patch.object(config_info, "_running_under_pytest", return_value=False)


class TestAssertKivyNotYetImported:
    def test_raises_when_kivy_in_sys_modules(self) -> None:
        # The package alone: none of the kivy.* submodules this test process has loaded.
        clean = {k: v for k, v in sys.modules.items() if k != "kivy" and not k.startswith("kivy.")}
        clean["kivy"] = ModuleType("kivy")
        with (
            _NOT_UNDER_PYTEST,
            patch.dict(sys.modules, clean, clear=True),
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

    def test_same_seed_gives_the_same_sequence(
        self, monkeypatch: pytest.MonkeyPatch, loguru_sink: list[str]
    ) -> None:
        monkeypatch.setenv(RANDOM_SEED_ENV_VAR, "1234")
        assert seed_random_from_env() == 1234  # noqa: PLR2004
        assert f"Random seed pinned to 1234 by {RANDOM_SEED_ENV_VAR}." in loguru_sink
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
        self, monkeypatch: pytest.MonkeyPatch, loguru_sink: list[str]
    ) -> None:
        """A typo in the variable must not stop the app starting, and says why it was ignored."""
        monkeypatch.setenv(RANDOM_SEED_ENV_VAR, "banana")
        assert seed_random_from_env() is None
        assert f'Ignoring {RANDOM_SEED_ENV_VAR}="banana": expected a whole number.' in loguru_sink


# ---------------------------------------------------------------------------
# get_app_exe_dir, is_app_installed, _setup_app_config_dir
# ---------------------------------------------------------------------------


class TestGetAppExeDir:
    def test_a_compiled_build_anchors_beside_its_executable(self, tmp_path: Path) -> None:
        exe = tmp_path / "bin" / "barks-reader-linux"
        with patch.object(config_info, "IS_COMPILED", True), patch.object(sys, "argv", [str(exe)]):  # noqa: FBT003
            assert get_app_exe_dir() == tmp_path.resolve() / "bin"

    def test_a_macos_build_anchors_beside_its_app_bundle(self, tmp_path: Path) -> None:
        """Inside the bundle is read-only and replaced on update; the data lives beside it."""
        exe = tmp_path / "Barks Reader.app" / "Contents" / "MacOS" / "barks-reader"
        with patch.object(config_info, "IS_COMPILED", True), patch.object(sys, "argv", [str(exe)]):  # noqa: FBT003
            assert get_app_exe_dir() == tmp_path.resolve()

    def test_a_checkout_anchors_beside_the_repository(self) -> None:
        anchor = get_app_exe_dir()
        assert any((child / "main.py").is_file() for child in anchor.iterdir())


class TestAppConfigDir:
    def test_installed_once_the_config_file_exists(self, tmp_path: Path) -> None:
        cfg = _bare_config_info(tmp_path)
        cfg.app_config_path = tmp_path / "barks-reader.ini"
        assert not cfg.is_app_installed()

        cfg.app_config_path.touch()
        assert cfg.is_app_installed()

    def test_the_config_dir_is_laid_out_and_kivy_is_pointed_at_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nested folders made as needed, twice over without complaint; KIVY_HOME set."""
        monkeypatch.setenv("KIVY_HOME", "-")  # put back after the test, whatever it sets
        config = tmp_path / "not" / "yet" / "config"
        cfg = _bare_config_info(tmp_path)
        with (
            patch.object(cfg, "_get_app_config_dir", return_value=config),
            patch.object(cfg, "_get_app_data_dir", return_value=tmp_path / "data"),
            patch.object(config_info, "_assert_kivy_not_yet_imported") as kivy_check,
        ):
            cfg._setup_app_config_dir()  # noqa: SLF001
            cfg._setup_app_config_dir()  # noqa: SLF001  (a second launch: all there already)

        assert cfg.app_config_dir == config
        assert cfg.app_config_path == config / "barks-reader.ini"
        assert cfg.app_data_dir == tmp_path / "data"
        assert cfg.kivy_config_dir == config / "kivy"
        assert cfg.app_log_path == config / "kivy" / "logs" / "barks-reader.log"
        assert (config / "kivy" / "logs").is_dir()
        assert config_info.os.environ["KIVY_HOME"] == str(config / "kivy")
        assert kivy_check.call_count == 2  # noqa: PLR2004

    def test_a_config_dir_that_cannot_be_made_is_an_error(self, tmp_path: Path) -> None:
        cfg = _bare_config_info(tmp_path)
        with (
            patch.object(cfg, "_get_app_config_dir", return_value=tmp_path / "never-made"),
            patch.object(Path, "mkdir"),
            pytest.raises(RuntimeError, match="Could not create app config directory"),
        ):
            cfg._setup_app_config_dir()  # noqa: SLF001


# ---------------------------------------------------------------------------
# setup_loguru, _run_loguru_config
# ---------------------------------------------------------------------------


class TestLoguruSetup:
    @pytest.fixture(autouse=True)
    def _keep_the_module_globals(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(config_info, "log_level", config_info.log_level)
        monkeypatch.setattr(config_info, "log_path", config_info.log_path)

    @pytest.fixture
    def cfg(self, tmp_path: Path) -> ConfigInfo:
        cfg = _bare_config_info(tmp_path)
        cfg.app_config_dir = tmp_path
        cfg.app_log_path = tmp_path / "kivy" / "logs" / "barks-reader.log"
        return cfg

    def test_setup_records_the_level_and_the_log_path(self, cfg: ConfigInfo) -> None:
        with patch.object(config_info, "_run_loguru_config") as run:
            setup_loguru(cfg, "INFO")

        assert get_log_level() == "INFO"
        assert get_log_path() == cfg.app_config_dir / "kivy" / "logs" / "barks-reader.log"
        run.assert_called_once_with(cfg)

    def test_a_good_config_is_loaded_once(self, cfg: ConfigInfo) -> None:
        with (
            patch.object(config_info.LoguruConfig, "load") as load,
            patch.object(config_info.logger, "add") as add,
        ):
            _run_loguru_config(cfg)

        load.assert_called_once_with(cfg.app_config_dir / "log-config.yaml")
        add.assert_not_called()

    def test_a_bad_config_falls_back_to_the_console_and_the_log_file(self, cfg: ConfigInfo) -> None:
        """At the app's level, with full tracebacks, then the config is tried once more."""
        config_info.log_level = "WARNING"  # put back by _keep_the_module_globals
        with (
            patch.object(
                config_info.LoguruConfig, "load", side_effect=[ValueError("bad"), None]
            ) as load,
            patch.object(config_info.logger, "add") as add,
        ):
            _run_loguru_config(cfg)

        assert [(c.args, c.kwargs) for c in add.call_args_list] == [
            ((sink,), {"level": "WARNING", "backtrace": True, "diagnose": True})
            for sink in (sys.stderr, str(cfg.app_log_path))
        ]
        assert [c.args for c in load.call_args_list] == [
            (cfg.app_config_dir / "log-config.yaml",)
        ] * 2

    def test_a_config_that_fails_twice_is_logged_and_exits(self, cfg: ConfigInfo) -> None:
        with (
            patch.object(config_info.LoguruConfig, "load", side_effect=ValueError("bad")),
            patch.object(config_info.logger, "add"),
            patch.object(config_info.logger, "exception") as logged,
            pytest.raises(SystemExit) as exited,
        ):
            _run_loguru_config(cfg)

        assert exited.value.code == 1
        logged.assert_called_once_with("LoguruConfig failed: ")


# ---------------------------------------------------------------------------
# find_fanta_volumes_dirpath and its search
# ---------------------------------------------------------------------------


class TestFindFantaVolumes:
    @pytest.mark.parametrize(
        ("platform", "is_macos", "search_path"),
        [
            (Platform.WIN, False, WINDOWS_FANTA_VOLUMES_SEARCH_PATH),
            (Platform.MACOS_ARM64, True, MACOS_FANTA_VOLUMES_SEARCH_PATH),
            (Platform.LINUX, False, LINUX_FANTA_VOLUMES_SEARCH_PATH),
        ],
    )
    def test_each_platform_searches_its_own_path(
        self, platform: Platform, is_macos: bool, search_path: list[str], tmp_path: Path
    ) -> None:
        cfg = _bare_config_info(tmp_path)
        with (
            patch.object(config_info, "PLATFORM", platform),
            patch.object(config_info, "IS_MACOS", is_macos),
            patch.object(config_info, "_find_fanta_volumes", return_value=tmp_path) as find,
        ):
            assert find_fanta_volumes_dirpath(cfg, "Fanta") == tmp_path

        find.assert_called_once_with(cfg, "Fanta", search_path)

    def test_not_found_is_logged_and_none(self, tmp_path: Path, loguru_sink: list[str]) -> None:
        cfg = _bare_config_info(tmp_path)
        with patch.object(config_info, "_find_fanta_volumes", return_value=None):
            assert find_fanta_volumes_dirpath(cfg, "Fanta") is None

        assert any(
            'Could not find Fantagraphics Barks Library directory "Fanta".' in line
            for line in loguru_sink
        )

    def test_the_data_dir_is_searched_first(self, tmp_path: Path) -> None:
        cfg = _bare_config_info(tmp_path)
        cfg.app_data_dir = tmp_path / "data"
        (cfg.app_data_dir / "Fanta").mkdir(parents=True)
        (tmp_path / "elsewhere" / "Fanta").mkdir(parents=True)

        found = _find_fanta_volumes(cfg, "Fanta", [str(tmp_path / "elsewhere")])

        assert found == cfg.app_data_dir / "Fanta"

    def test_the_search_passes_over_missing_and_empty_dirs(
        self, tmp_path: Path, loguru_sink: list[str]
    ) -> None:
        (tmp_path / "empty").mkdir()
        (tmp_path / "has-it" / "Fanta").mkdir(parents=True)
        search_path = [str(tmp_path / "missing"), str(tmp_path / "empty"), str(tmp_path / "has-it")]

        assert _find_dir_on_search_path(search_path, "Fanta") == tmp_path / "has-it" / "Fanta"
        assert _find_dir_on_search_path(search_path[:2], "Fanta") is None
        assert f'Searching: "{tmp_path / "missing"}" is not a directory.' in loguru_sink
        assert f'Searching: "Fanta" not found under "{tmp_path / "empty"}".' in loguru_sink
