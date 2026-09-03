"""Tests for the first-run installer's data-pack extraction and config re-read checks."""

from __future__ import annotations

import sys
from configparser import ConfigParser
from typing import TYPE_CHECKING
from zipfile import ZipFile

import pytest

if TYPE_CHECKING:
    from pathlib import Path

_saved_excepthook = sys.excepthook
from barks_reader import first_run_installer  # noqa: E402
from barks_reader.core import config_info as config_info_module  # noqa: E402
from barks_reader.first_run_installer import InstallerDataError, _extract_subdir  # noqa: E402

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
