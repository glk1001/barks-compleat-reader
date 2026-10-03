"""The first-run installer: its data-pack extraction, its config checks, and a whole run."""

from __future__ import annotations

import sys
from configparser import ConfigParser
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pytest
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_saved_excepthook = sys.excepthook
from barks_reader import first_run_installer, first_run_installer_show_message  # noqa: E402
from barks_reader.core import config_info as config_info_module  # noqa: E402
from barks_reader.core import reader_utils  # noqa: E402
from barks_reader.first_run_installer import InstallerDataError, _extract_subdir  # noqa: E402
from barks_reader.ui import kivy_standalone_error_popup  # noqa: E402

# Importing the installer module installs its own excepthook; keep pytest's.
sys.excepthook = _saved_excepthook

_INI_TEXT = "[Barks Reader]\nfanta_dir = Fantagraphics Volumes\n"


def _make_zip(zip_path: Path, entries: dict[str, str]) -> Path:
    with ZipFile(zip_path, "w") as zf:
        for name, text in entries.items():
            zf.writestr(name, text)
    return zip_path


class TestExtractSubdir:
    def test_extracts_files_under_subdir_and_returns_count(self, tmp_path: Path) -> None:
        zip_path = _make_zip(
            tmp_path / "data.zip",
            {
                "Configs/": "",
                "Configs/barks-reader.ini": _INI_TEXT,
                "Configs/kivy/config.ini": "[kivy]\n",
                "Reader Files/readme.txt": "not a config",
            },
        )
        out_dir = tmp_path / "config"

        num_extracted = _extract_subdir(zip_path, "Configs/", out_dir)

        assert num_extracted == 2  # noqa: PLR2004
        assert (out_dir / "barks-reader.ini").read_text() == _INI_TEXT
        assert (out_dir / "kivy" / "config.ini").read_text() == "[kivy]\n"
        assert not (out_dir / "readme.txt").exists()

    def test_re_zipped_pack_with_nested_top_level_folder_fails_loudly(self, tmp_path: Path) -> None:
        # What Safari + Finder produce: the real contents one folder deeper, plus __MACOSX.
        zip_path = _make_zip(
            tmp_path / "data.zip",
            {
                "barks-reader-data-1/Configs/barks-reader.ini": _INI_TEXT,
                "barks-reader-data-1/Reader Files/readme.txt": "x",
                "__MACOSX/barks-reader-data-1/._Configs": "",
            },
        )
        out_dir = tmp_path / "config"

        with pytest.raises(InstallerDataError) as exc_info:
            _extract_subdir(zip_path, "Configs/", out_dir)

        error = exc_info.value
        assert str(zip_path) in error.message
        assert '"Configs/"' in error.message
        assert "barks-reader-data-1" in error.details
        assert "__MACOSX" in error.details
        assert "re-zipped" in error.details
        assert not out_dir.exists()


class TestConfigureFantaVolumes:
    @pytest.fixture
    def config_info(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> first_run_installer.ConfigInfo:
        monkeypatch.setenv("BARKS_READER_CONFIG_DIR", str(tmp_path / "config"))
        monkeypatch.setenv("BARKS_READER_DATA_DIR", str(tmp_path / "data"))
        return first_run_installer.ConfigInfo()

    @pytest.fixture
    def fanta_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        fanta_dir = tmp_path / "fanta"
        fanta_dir.mkdir()
        monkeypatch.setattr(
            config_info_module, "find_fanta_volumes_dirpath", lambda *_args: fanta_dir
        )
        return fanta_dir

    def test_rewrites_fanta_dir_when_config_is_valid(
        self, config_info: first_run_installer.ConfigInfo, fanta_dir: Path
    ) -> None:
        config_info.app_config_path.write_text(_INI_TEXT)

        result = first_run_installer._configure_fanta_volumes_for_platform(  # noqa: SLF001
            config_info
        )

        assert result == fanta_dir
        parser = ConfigParser()
        parser.read(config_info.app_config_path)
        assert parser.get("Barks Reader", "fanta_dir") == str(fanta_dir)

    @pytest.mark.usefixtures("fanta_dir")
    def test_missing_config_file_fails_loudly(
        self, config_info: first_run_installer.ConfigInfo
    ) -> None:
        assert not config_info.app_config_path.exists()

        with pytest.raises(InstallerDataError, match="Could not read") as exc_info:
            first_run_installer._configure_fanta_volumes_for_platform(  # noqa: SLF001
                config_info
            )

        assert str(config_info.app_config_path) in exc_info.value.message

    @pytest.mark.usefixtures("fanta_dir")
    def test_config_without_barks_reader_section_fails_loudly(
        self, config_info: first_run_installer.ConfigInfo
    ) -> None:
        config_info.app_config_path.write_text("[Other Section]\nkey = value\n")

        with pytest.raises(InstallerDataError, match=r"no .*section"):
            first_run_installer._configure_fanta_volumes_for_platform(  # noqa: SLF001
                config_info
            )


@dataclass
class _Install:
    exe_dir: Path
    config_info: first_run_installer.ConfigInfo
    fanta_dir: Path | None
    error_popup: MagicMock
    success_message: MagicMock

    @property
    def failed_flag(self) -> Path:
        return self.exe_dir / config_info_module.BARKS_READER_INSTALLER_FAILED_FLAG_FILE

    def write_packs(self, first: dict[str, str] | None = None) -> None:
        _make_zip(
            self.exe_dir / "barks-reader-data-1.barkspack",
            first
            if first is not None
            else {"Configs/barks-reader.ini": _INI_TEXT, "Reader Files/one.txt": "1"},
        )
        _make_zip(self.exe_dir / "barks-reader-data-2.barkspack", {"Reader Files/two.txt": "2"})

    def error_message(self) -> str:
        return self.error_popup.call_args.kwargs["message"]


@pytest.fixture
def install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_Install]:
    """Set up a first run beside a scratch executable, its popups caught, all in tmp_path.

    The installer's own log file is a loguru sink it never removes, so this does.
    """
    exe_dir = tmp_path / "exe"
    exe_dir.mkdir()
    fanta_dir = tmp_path / "fanta"
    fanta_dir.mkdir()
    monkeypatch.setenv("BARKS_READER_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("BARKS_READER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(first_run_installer, "_barks_reader_exe_dir", exe_dir)
    monkeypatch.setattr(first_run_installer, "_log_file", exe_dir / "installer.log")
    monkeypatch.setattr(config_info_module, "get_app_exe_dir", lambda: exe_dir)
    monkeypatch.setattr(config_info_module, "find_fanta_volumes_dirpath", lambda *_: fanta_dir)
    config_info = first_run_installer.ConfigInfo()
    monkeypatch.setattr(sys, "argv", [str(exe_dir / config_info.get_executable_name())])

    sinks: list[int] = []
    real_add = logger.add

    def add_sink(*args: Any, **kwargs: Any) -> int:  # noqa: ANN401
        sinks.append(real_add(*args, **kwargs))
        return sinks[-1]

    with (
        patch.object(logger, "add", side_effect=add_sink),
        patch.object(reader_utils, "safe_import_check", return_value=True),
        patch.object(kivy_standalone_error_popup, "show_error_popup") as error_popup,
        patch.object(first_run_installer_show_message, "show_installer_message") as success,
    ):
        yield _Install(exe_dir, config_info, fanta_dir, error_popup, success)
    for sink in sinks:
        logger.remove(sink)


class TestMain:
    def test_a_first_run_installs_both_packs_and_says_so(self, install: _Install) -> None:
        install.write_packs()
        install.failed_flag.write_text("")

        first_run_installer.main()

        data_dir = install.config_info.app_data_dir / "Reader Files"
        assert (data_dir / "one.txt").read_text() == "1"
        assert (data_dir / "two.txt").read_text() == "2"
        parser = ConfigParser()
        parser.read(install.config_info.app_config_path)
        assert parser.get("Barks Reader", "fanta_dir") == str(install.fanta_dir)
        assert not install.failed_flag.exists()
        install.error_popup.assert_not_called()
        title, fanta_dir, data_zips, config_dir, log_path = install.success_message.call_args.args
        assert (title, fanta_dir) == ("Installation Complete", install.fanta_dir)
        assert [p.name for p in data_zips] == [
            "barks-reader-data-1.barkspack",
            "barks-reader-data-2.barkspack",
        ]
        assert (config_dir, log_path) == (
            install.config_info.app_config_dir,
            install.config_info.app_log_path,
        )
        log = (install.exe_dir / "installer.log").read_text()
        assert "Finished installing config and data files." in log

    def test_without_the_library_it_still_installs(
        self, install: _Install, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(config_info_module, "find_fanta_volumes_dirpath", lambda *_: None)
        install.write_packs()

        first_run_installer.main()

        assert install.success_message.call_args.args[1] is None
        assert install.config_info.app_config_path.read_text() == _INI_TEXT

    def test_an_installed_app_is_left_alone(self, install: _Install) -> None:
        install.config_info.app_config_path.write_text(_INI_TEXT)

        first_run_installer.main()

        install.success_message.assert_not_called()
        install.error_popup.assert_not_called()

    def test_a_missing_pack_fails_and_says_where_it_should_be(self, install: _Install) -> None:
        with pytest.raises(SystemExit) as exited:
            first_run_installer.main()

        assert exited.value.code == 1
        assert install.failed_flag.exists()
        assert "barks-reader-data-1.barkspack" in install.error_message()
        assert str(install.exe_dir) in install.error_popup.call_args.kwargs["details"]

    def test_a_renamed_executable_fails(
        self, install: _Install, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", [str(install.exe_dir / "renamed")])

        with pytest.raises(SystemExit):
            first_run_installer.main()

        assert install.failed_flag.exists()
        assert "Unexpected Barks Reader executable" in install.error_message()
        assert (
            install.config_info.get_executable_name()
            in (install.error_popup.call_args.kwargs["details"])
        )

    def test_a_broken_panel_module_fails(self, install: _Install) -> None:
        with (
            patch.object(reader_utils, "safe_import_check", return_value=False),
            pytest.raises(SystemExit),
        ):
            first_run_installer.main()

        assert install.failed_flag.exists()
        assert install.error_message() == "The compiled panel module failed to load."

    def test_a_re_zipped_pack_fails_with_its_details_shown(self, install: _Install) -> None:
        install.write_packs({"barks-reader-data-1/Configs/barks-reader.ini": _INI_TEXT})

        with pytest.raises(SystemExit):
            first_run_installer.main()

        assert install.failed_flag.exists()
        kwargs = install.error_popup.call_args.kwargs
        assert '"Configs/"' in kwargs["message"]
        assert "re-zipped" in kwargs["details"]
        assert kwargs["show_details"] is True

    def test_anything_unexpected_fails_with_its_traceback(self, install: _Install) -> None:
        install.write_packs()
        (install.exe_dir / "barks-reader-data-2.barkspack").write_bytes(b"not a zip")

        with pytest.raises(SystemExit):
            first_run_installer.main()

        assert install.failed_flag.exists()
        assert install.error_message().startswith("BadZipFile: ")
        assert "Traceback" in install.error_popup.call_args.kwargs["details"]


def test_an_uncaught_exception_gets_the_installers_popup() -> None:
    try:
        msg = "boom"
        raise ValueError(msg)  # noqa: TRY301
    except ValueError:
        exc_info = sys.exc_info()

    with (
        patch.object(kivy_standalone_error_popup, "show_error_popup") as error_popup,
        pytest.raises(SystemExit),
    ):
        first_run_installer._handle_uncaught_exception(*exc_info)  # noqa: SLF001

    kwargs = error_popup.call_args.kwargs
    assert (kwargs["title_bar_text"], kwargs["title"]) == ("Installer", "Barks Reader Installation")
    assert kwargs["message"] == "ValueError: boom"
