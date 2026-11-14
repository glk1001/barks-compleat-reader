"""What the installers share: the packs' extraction and the Reader Files install."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pytest
from barks_reader.core import config_info as config_info_module
from barks_reader.core import data_pack
from barks_reader.core.config_info import ConfigInfo
from barks_reader.core.data_pack import DATA_PACK_FILE_NAMES, PACK_MEMBER, DataPackInfo
from barks_reader.core.reader_settings import ReaderSettings
from barks_reader.installer_support import (
    InstallerDataError,
    clear_stale_failed_flag,
    extract_subdir,
    install_reader_files,
    read_member,
    require_subdir,
    subdir_bytes,
)

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

        num_extracted = extract_subdir(zip_path, "Configs/", out_dir)

        assert num_extracted == 2  # noqa: PLR2004
        assert (out_dir / "barks-reader.ini").read_text() == _INI_TEXT
        assert (out_dir / "kivy" / "config.ini").read_text() == "[kivy]\n"
        assert not (out_dir / "readme.txt").exists()

    def test_the_bytes_reported_as_written_add_up_to_the_subdirs_size(self, tmp_path: Path) -> None:
        zip_path = _make_zip(
            tmp_path / "pack.zip",
            {"Reader Files/a.txt": "abc", "Reader Files/deep/b.txt": "de", "Configs/c.ini": "x"},
        )
        written: list[int] = []

        extract_subdir(zip_path, "Reader Files/", tmp_path / "out", written.append)

        assert sum(written) == subdir_bytes(zip_path, "Reader Files/") == len("abc") + len("de")
        assert subdir_bytes(zip_path, "Nothing/") == 0

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
            extract_subdir(zip_path, "Configs/", out_dir)

        error = exc_info.value
        assert str(zip_path) in error.message
        assert '"Configs/"' in error.message
        assert "barks-reader-data-1" in error.details
        assert "__MACOSX" in error.details
        assert "re-zipped" in error.details
        assert not out_dir.exists()

    def test_a_skipped_file_stays_in_the_pack(self, tmp_path: Path) -> None:
        zip_path = _make_zip(
            tmp_path / "data.zip",
            {"Configs/barks-reader.ini": _INI_TEXT, "Configs/kivy/config.ini": "[kivy]\n"},
        )
        out_dir = tmp_path / "config"

        num_extracted = extract_subdir(zip_path, "Configs/", out_dir, skip=("barks-reader.ini",))

        assert num_extracted == 1
        assert not (out_dir / "barks-reader.ini").exists()
        assert (out_dir / "kivy" / "config.ini").is_file()

    def test_a_subdir_holding_only_skipped_files_is_not_a_re_zipped_pack(
        self, tmp_path: Path
    ) -> None:
        zip_path = _make_zip(tmp_path / "data.zip", {"Configs/barks-reader.ini": _INI_TEXT})

        assert (
            extract_subdir(zip_path, "Configs/", tmp_path / "out", skip=("barks-reader.ini",)) == 0
        )


class TestExtractSubdirKeepsToItsFolder:
    @pytest.mark.parametrize(
        "name",
        [
            "Reader Files/../escaped.txt",
            "Reader Files/deep/../../escaped.txt",
            "Reader Files//{outside}/escaped.txt",
        ],
    )
    def test_a_name_that_leaves_the_folder_is_refused_and_nothing_is_written(
        self, tmp_path: Path, name: str
    ) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        name = name.format(outside=outside.as_posix().lstrip("/"))
        zip_path = _make_zip(tmp_path / "pack.zip", {"Reader Files/good.txt": "good", name: "bad"})
        out_dir = tmp_path / "data" / "Reader Files"

        with pytest.raises(InstallerDataError) as exc_info:
            extract_subdir(zip_path, "Reader Files/", out_dir)

        assert "outside the folder" in exc_info.value.message
        assert f'"{name}"' in exc_info.value.details
        assert not out_dir.exists()  # not even the good file before it
        assert list(outside.iterdir()) == []
        assert not (tmp_path / "data" / "escaped.txt").exists()

    def test_dots_that_stay_inside_the_folder_are_allowed(self, tmp_path: Path) -> None:
        zip_path = _make_zip(tmp_path / "pack.zip", {"Reader Files/deep/../a.txt": "a"})
        out_dir = tmp_path / "out"

        assert extract_subdir(zip_path, "Reader Files/", out_dir) == 1

        assert (out_dir / "a.txt").read_text() == "a"

    def test_a_symlinked_folder_takes_its_files(self, tmp_path: Path) -> None:
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link = tmp_path / "link"
        try:
            link.symlink_to(real_dir, target_is_directory=True)
        except OSError:
            pytest.skip("this machine cannot make a symbolic link")
        zip_path = _make_zip(tmp_path / "pack.zip", {"Reader Files/a.txt": "a"})

        assert extract_subdir(zip_path, "Reader Files/", link) == 1

        assert (real_dir / "a.txt").read_text() == "a"


class TestRequireSubdir:
    def test_a_pack_with_the_folder_passes(self, tmp_path: Path) -> None:
        zip_path = _make_zip(tmp_path / "data.zip", {"Reader Files/a.txt": "a"})

        require_subdir(zip_path, "Reader Files/")

    def test_a_re_zipped_pack_fails_and_names_what_it_holds(self, tmp_path: Path) -> None:
        zip_path = _make_zip(tmp_path / "data.zip", {"nested/Reader Files/a.txt": "a"})

        with pytest.raises(InstallerDataError) as exc_info:
            require_subdir(zip_path, "Reader Files/")

        assert '"Reader Files/"' in exc_info.value.message
        assert "nested" in exc_info.value.details


class TestReadMember:
    def test_returns_the_files_bytes(self, tmp_path: Path) -> None:
        zip_path = _make_zip(tmp_path / "data.zip", {"Configs/barks-reader.ini": _INI_TEXT})

        assert read_member(zip_path, "Configs/barks-reader.ini") == _INI_TEXT.encode()

    def test_a_missing_file_fails_and_names_it_and_the_pack(self, tmp_path: Path) -> None:
        zip_path = _make_zip(tmp_path / "data.zip", {"Configs/other.ini": "x"})

        with pytest.raises(InstallerDataError) as exc_info:
            read_member(zip_path, "Configs/barks-reader.ini")

        assert '"Configs/barks-reader.ini"' in exc_info.value.message
        assert str(zip_path) in exc_info.value.message
        assert "Download" in exc_info.value.details


class TestInstallReaderFiles:
    """The update's whole runs of it are in test_data_pack_installer.py."""

    @staticmethod
    def _packs(pack_dir: Path, *, two: str = "2") -> DataPackInfo:
        entries = {"one.txt": {"files": 1, "bytes": 1, "md5": "a"}, "two.txt": {"bytes": 1}}
        info = DataPackInfo(6, "data-v6", datetime(2026, 10, 29, tzinfo=UTC), "main-pc", entries)
        version_file = {PACK_MEMBER: info.to_json()}
        _make_zip(pack_dir / DATA_PACK_FILE_NAMES[0], {"Reader Files/one.txt": "1"} | version_file)
        _make_zip(pack_dir / DATA_PACK_FILE_NAMES[1], {"Reader Files/two.txt": two} | version_file)
        return info

    def test_a_first_install_puts_the_folder_in_place_and_counts_its_bytes(
        self, tmp_path: Path
    ) -> None:
        info = self._packs(tmp_path)
        reader_files = tmp_path / "data" / "Reader Files"
        written: list[int] = []

        install_reader_files(info, tmp_path, reader_files, written.append)

        assert (reader_files / "one.txt").read_text() == "1"
        assert (reader_files / "two.txt").read_text() == "2"
        assert data_pack.read_installed(reader_files) == info
        assert sum(written) == sum(
            subdir_bytes(tmp_path / name, "Reader Files/") for name in DATA_PACK_FILE_NAMES
        )
        assert [p.name for p in reader_files.parent.iterdir()] == ["Reader Files"]

    def test_a_first_install_that_fails_says_nothing_of_installed_data(
        self, tmp_path: Path
    ) -> None:
        info = self._packs(tmp_path, two="too long")
        reader_files = tmp_path / "data" / "Reader Files"

        with pytest.raises(InstallerDataError) as exc_info:
            install_reader_files(info, tmp_path, reader_files)

        assert exc_info.value.details.endswith(
            "\n\nDownload both packs again and check them against the release's SHA256SUMS.txt."
        )
        assert list(reader_files.parent.iterdir()) == []

    def test_an_extraction_that_stops_part_way_leaves_no_new_folder(self, tmp_path: Path) -> None:
        info = self._packs(tmp_path)
        (tmp_path / DATA_PACK_FILE_NAMES[1]).write_bytes(b"not a zip")
        reader_files = tmp_path / "data" / "Reader Files"

        with pytest.raises(Exception, match="not a zip"):
            install_reader_files(info, tmp_path, reader_files)

        assert list(reader_files.parent.iterdir()) == []


class TestClearStaleFailedFlag:
    """An install that completed and still has the failed flag (an older installer's)."""

    @pytest.fixture
    def config_info(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConfigInfo:
        """Set up an installed app with whole Reader Files and the failed flag, in tmp_path."""
        monkeypatch.setenv("BARKS_READER_CONFIG_DIR", str(tmp_path / "config"))
        monkeypatch.setenv("BARKS_READER_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setattr(config_info_module, "get_app_exe_dir", lambda: tmp_path)
        config_info = ConfigInfo()
        config_info.app_config_path.write_text("[Barks Reader]\n", encoding="utf-8")
        reader_files = ReaderSettings.get_reader_files_dir(config_info.app_data_dir)
        reader_files.mkdir(parents=True)
        built = datetime(2026, 10, 29, 6, 30, tzinfo=UTC)
        info = DataPackInfo(6, "data-v6", built, "main-pc", {"one.txt": {"bytes": 1}})
        (reader_files / data_pack.DATA_PACK_FILE_NAME).write_text(info.to_json(), encoding="utf-8")
        (reader_files / "one.txt").write_text("1", encoding="utf-8")
        config_info_module.set_barks_reader_installer_failed_flag()
        return config_info

    @staticmethod
    def _flag() -> Path:
        return config_info_module.get_barks_reader_installer_failed_flag_file()

    def test_a_whole_install_loses_its_flag_and_runs(
        self, config_info: ConfigInfo, loguru_sink: list[str]
    ) -> None:
        assert clear_stale_failed_flag(config_info) is True

        assert not self._flag().exists()
        assert any("Removed a stale installer failed flag" in line for line in loguru_sink)

    def test_no_flag_runs_with_nothing_looked_at(self, config_info: ConfigInfo) -> None:
        self._flag().unlink()

        with patch.object(data_pack, "installed_is_whole") as looked:
            assert clear_stale_failed_flag(config_info) is True

        looked.assert_not_called()

    def test_an_app_not_installed_keeps_its_flag(self, config_info: ConfigInfo) -> None:
        config_info.app_config_path.unlink()

        assert clear_stale_failed_flag(config_info) is False
        assert self._flag().exists()

    def test_data_that_is_not_whole_keeps_its_flag(self, config_info: ConfigInfo) -> None:
        reader_files = ReaderSettings.get_reader_files_dir(config_info.app_data_dir)
        (reader_files / "one.txt").write_text("", encoding="utf-8")

        assert clear_stale_failed_flag(config_info) is False
        assert self._flag().exists()

    def test_a_flag_that_cannot_be_removed_still_lets_a_whole_install_run(
        self, config_info: ConfigInfo, loguru_sink: list[str]
    ) -> None:
        with patch.object(Path, "unlink", side_effect=PermissionError(13, "read-only")):
            assert clear_stale_failed_flag(config_info) is True

        assert self._flag().exists()
        assert any("Could not remove the stale installer failed flag" in ln for ln in loguru_sink)
