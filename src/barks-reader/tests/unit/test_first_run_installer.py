# cspell:ignore José Ávila Größe
"""The first-run installer: its config checks, and a whole run."""

from __future__ import annotations

import sys
from configparser import ConfigParser
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pytest
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_saved_excepthook = sys.excepthook
from barks_reader import (  # noqa: E402
    first_run_installer,
    first_run_installer_show_message,
    installer_progress,
)
from barks_reader.core import config_info as config_info_module  # noqa: E402
from barks_reader.core import data_pack, reader_utils  # noqa: E402
from barks_reader.core.data_pack import (  # noqa: E402
    DATA_PACK_FILE_NAMES,
    PACK_MEMBER,
    DataPackInfo,
)
from barks_reader.installer_support import InstallerDataError  # noqa: E402
from barks_reader.ui import kivy_standalone_error_popup  # noqa: E402

# Importing the installer module installs its own excepthook; keep pytest's.
sys.excepthook = _saved_excepthook

_INI_TEXT = "[Barks Reader]\nfanta_dir = Fantagraphics Volumes\n"
_KIVY_INI_TEXT = "[kivy]\n"


def _info(version: int) -> DataPackInfo:
    entries = {
        "one.txt": {"files": 1, "bytes": 1, "md5": "a"},
        "two.txt": {"files": 1, "bytes": 1, "md5": "b"},
    }
    built = datetime(2026, 10, 29, tzinfo=UTC)
    return DataPackInfo(version, f"data-v{version}", built, "main-pc", entries)


def _make_zip(zip_path: Path, entries: dict[str, str]) -> Path:
    with ZipFile(zip_path, "w") as zf:
        for name, text in entries.items():
            zf.writestr(name, text)
    return zip_path


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
            config_info, config_info.app_config_path
        )

        assert result == fanta_dir
        parser = ConfigParser()
        parser.read(config_info.app_config_path)
        assert parser.get("Barks Reader", "fanta_dir") == str(fanta_dir)

    def test_a_library_path_kivy_could_not_read_back_is_written_so_it_can(
        self,
        config_info: first_run_installer.ConfigInfo,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Letters outside ASCII (the file is UTF-8 on every machine) and a "%"."""
        fanta_dir = tmp_path / "José Ávila" / "100% Barks"
        monkeypatch.setattr(
            config_info_module, "find_fanta_volumes_dirpath", lambda *_args: fanta_dir
        )
        config_info.app_config_path.write_text(
            "[Barks Reader]\nfanta_dir = unset\nnote = Größe\n", encoding="utf-8"
        )

        first_run_installer._configure_fanta_volumes_for_platform(  # noqa: SLF001
            config_info, config_info.app_config_path
        )

        # As kivy.config.ConfigParser reads it: this encoding, "%" an interpolation.
        text = config_info.app_config_path.read_bytes().decode("utf-8")
        assert "José Ávila" in text
        assert "100%% Barks" in text
        parser = ConfigParser()
        parser.read(config_info.app_config_path, encoding="utf-8-sig")
        assert parser.get("Barks Reader", "fanta_dir") == str(fanta_dir)
        assert parser.get("Barks Reader", "note") == "Größe"

    def test_the_config_is_written_as_utf_8_whatever_the_machines_encoding(
        self, config_info: first_run_installer.ConfigInfo, fanta_dir: Path
    ) -> None:
        """Linux's default is UTF-8 already, so the round trip alone proves nothing here."""
        config_info.app_config_path.write_text(_INI_TEXT)
        path_type = type(config_info.app_config_path)

        with patch.object(path_type, "open", autospec=True, side_effect=path_type.open) as opened:
            first_run_installer._configure_fanta_volumes_for_platform(  # noqa: SLF001
                config_info, config_info.app_config_path
            )

        writes = [call for call in opened.call_args_list if call.args[1:2] == ("w",)]
        assert [call.kwargs.get("encoding") for call in writes] == ["utf-8"]
        assert fanta_dir.name in config_info.app_config_path.read_text(encoding="utf-8")

    @pytest.mark.usefixtures("fanta_dir")
    def test_missing_config_file_fails_loudly(
        self, config_info: first_run_installer.ConfigInfo
    ) -> None:
        assert not config_info.app_config_path.exists()

        with pytest.raises(InstallerDataError, match="Could not read") as exc_info:
            first_run_installer._configure_fanta_volumes_for_platform(  # noqa: SLF001
                config_info, config_info.app_config_path
            )

        assert str(config_info.app_config_path) in exc_info.value.message

    @pytest.mark.usefixtures("fanta_dir")
    def test_config_without_barks_reader_section_fails_loudly(
        self, config_info: first_run_installer.ConfigInfo
    ) -> None:
        config_info.app_config_path.write_text("[Other Section]\nkey = value\n")

        with pytest.raises(InstallerDataError, match=r"no .*section"):
            first_run_installer._configure_fanta_volumes_for_platform(  # noqa: SLF001
                config_info, config_info.app_config_path
            )


@dataclass
class _Install:
    exe_dir: Path
    config_info: first_run_installer.ConfigInfo
    fanta_dir: Path | None
    error_popup: MagicMock
    success_message: MagicMock
    progress: MagicMock

    @property
    def failed_flag(self) -> Path:
        return self.exe_dir / config_info_module.BARKS_READER_INSTALLER_FAILED_FLAG_FILE

    @property
    def reader_files(self) -> Path:
        return self.config_info.app_data_dir / "Reader Files"

    @property
    def installed(self) -> bool:
        """Whether the next launch would take the app as installed."""
        return self.config_info.is_app_installed()

    def write_packs(
        self,
        first: dict[str, str] | None = None,
        *,
        versions: tuple[int | None, int | None] = (6, 6),
        two: str = "2",
    ) -> None:
        """Write both packs; `first` replaces the whole of pack 1, version file and all."""
        packs: list[dict[str, str]] = [
            {
                "Configs/barks-reader.ini": _INI_TEXT,
                "Configs/kivy/config.ini": _KIVY_INI_TEXT,
                "Reader Files/one.txt": "1",
            },
            {"Reader Files/two.txt": two},
        ]
        for pack, version in zip(packs, versions, strict=True):
            if version is not None:
                pack[PACK_MEMBER] = _info(version).to_json()
        if first is not None:
            packs[0] = first
        for name, pack in zip(DATA_PACK_FILE_NAMES, packs, strict=True):
            _make_zip(self.exe_dir / name, pack)

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
        # No window: the work runs where it is called, as on a machine with none.
        patch.object(
            installer_progress,
            "run_showing_progress",
            side_effect=lambda work, *_args, **_kwargs: (work(), False),
        ) as progress,
    ):
        yield _Install(exe_dir, config_info, fanta_dir, error_popup, success, progress)
    for sink in sinks:
        logger.remove(sink)


class TestMain:
    def test_a_first_run_installs_both_packs_and_says_so(self, install: _Install) -> None:
        install.write_packs()
        install.failed_flag.write_text("")

        first_run_installer.main()

        assert (install.reader_files / "one.txt").read_text() == "1"
        assert (install.reader_files / "two.txt").read_text() == "2"
        assert data_pack.read_installed(install.reader_files) == _info(6)
        assert not install.reader_files.with_name("Reader Files.new").exists()
        kivy_ini = install.config_info.app_config_dir / "kivy" / "config.ini"
        assert kivy_ini.read_text() == _KIVY_INI_TEXT
        assert list(install.config_info.app_config_dir.glob("*.new")) == []
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

    def test_the_data_is_unpacked_behind_a_window_that_follows_its_bytes(
        self, install: _Install
    ) -> None:
        install.write_packs()

        first_run_installer.main()

        _work, progress = install.progress.call_args.args
        assert progress.total > len("1") + len("2")  # and each pack's version file
        assert progress.fraction == 1.0
        assert install.progress.call_args.kwargs["title"] == "Installing the Barks Reader"

    def test_the_success_message_is_shown_in_the_progress_windows_loop(
        self, install: _Install
    ) -> None:
        """With the window up, the report follows in it, and is not shown a second time."""
        install.write_packs()
        end_loop = MagicMock()

        def with_a_window(work: Any, *_args: Any, show_next: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
            result = work()
            show_next(result, end_loop)
            return result, True

        install.progress.side_effect = with_a_window

        first_run_installer.main()

        install.success_message.assert_called_once()
        kwargs = install.success_message.call_args.kwargs
        assert kwargs["in_running_loop"] is True
        assert kwargs["on_dismiss"] is end_loop
        assert install.success_message.call_args.args[1] == install.fanta_dir

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
        # The line scripts/smoke-test-build.sh looks for in a build's first run, which
        # has no packs beside it: reword one and the other must follow.
        log = (install.exe_dir / "installer.log").read_text()
        assert "Checking the installer zips in" in log

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
        kwargs = install.error_popup.call_args.kwargs
        assert "contact The Barks Reader developer" in kwargs["details"]
        assert kwargs["show_details"] is True
        # Said once, by main: the popup is not asked to log it again.
        log = (install.exe_dir / "installer.log").read_text(encoding="utf-8")
        assert log.count("The compiled panel module failed to load.") == 1

    def test_a_re_zipped_pack_fails_with_its_details_shown(self, install: _Install) -> None:
        install.write_packs({"barks-reader-data-1/Reader Files/one.txt": "1"})

        with pytest.raises(SystemExit):
            first_run_installer.main()

        assert install.failed_flag.exists()
        kwargs = install.error_popup.call_args.kwargs
        assert '"Reader Files/"' in kwargs["message"]
        assert "re-zipped" in kwargs["details"]
        assert kwargs["show_details"] is True
        assert not install.installed

    def test_a_pack_that_is_no_zip_is_reported_as_a_bad_download(self, install: _Install) -> None:
        install.write_packs()
        (install.exe_dir / DATA_PACK_FILE_NAMES[1]).write_bytes(b"not a zip")

        with pytest.raises(SystemExit):
            first_run_installer.main()

        assert install.failed_flag.exists()
        assert install.error_message() == "The Barks Reader data packs cannot be installed."
        details = install.error_popup.call_args.kwargs["details"]
        assert DATA_PACK_FILE_NAMES[1] in details
        assert "download it again" in details
        install.progress.assert_not_called()

    def test_packs_from_different_releases_are_refused(self, install: _Install) -> None:
        install.write_packs(versions=(5, 6))

        with pytest.raises(SystemExit):
            first_run_installer.main()

        details = install.error_popup.call_args.kwargs["details"]
        assert "different versions (data pack 5 and data pack 6)" in details
        assert not install.reader_files.exists()
        assert not install.installed

    @pytest.mark.parametrize("versions", [(None, 6), (None, None)])
    def test_packs_with_no_version_are_refused(
        self, install: _Install, versions: tuple[int | None, int | None]
    ) -> None:
        install.write_packs(versions=versions)

        with pytest.raises(SystemExit):
            first_run_installer.main()

        details = install.error_popup.call_args.kwargs["details"]
        assert "older than the first versioned pack" in details
        assert not install.reader_files.exists()
        assert not install.installed

    def test_data_that_is_not_what_the_packs_promised_is_not_installed(
        self, install: _Install
    ) -> None:
        install.write_packs(two="too long")

        with pytest.raises(SystemExit):
            first_run_installer.main()

        assert install.failed_flag.exists()
        assert "not what its packs promised" in install.error_message()
        details = install.error_popup.call_args.kwargs["details"]
        assert '"two.txt" is 8 bytes, not the 1' in details
        assert "left as it was" not in details  # nothing was installed before
        assert not install.reader_files.exists()
        assert not install.reader_files.with_name("Reader Files.new").exists()
        assert not install.installed

    def test_anything_unexpected_fails_with_its_traceback(self, install: _Install) -> None:
        install.write_packs()

        with (
            patch.object(
                first_run_installer, "install_reader_files", side_effect=RuntimeError("boom")
            ),
            pytest.raises(SystemExit),
        ):
            first_run_installer.main()

        assert install.failed_flag.exists()
        assert install.error_message() == "RuntimeError: boom"
        assert "Traceback" in install.error_popup.call_args.kwargs["details"]
        assert not install.installed

    def test_the_apps_config_is_written_only_once_the_data_is_in_place(
        self, install: _Install
    ) -> None:
        """The config says "installed", so it must not exist while the data is unpacked."""
        install.write_packs()
        seen: list[tuple[bool, bool]] = []

        def before_the_work(work: Any, *_args: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
            kivy_ini = install.config_info.app_config_dir / "kivy" / "config.ini"
            seen.append((kivy_ini.is_file(), install.installed))
            return work(), False

        install.progress.side_effect = before_the_work

        first_run_installer.main()

        assert seen == [(True, False)]  # Kivy's config for the window, not yet the app's
        assert install.installed

    def test_a_config_the_pack_lacks_fails_with_nothing_left_pending(
        self, install: _Install
    ) -> None:
        install.write_packs(
            {"Configs/kivy/config.ini": _KIVY_INI_TEXT, "Reader Files/one.txt": "1"},
            versions=(None, 6),
        )
        with ZipFile(install.exe_dir / DATA_PACK_FILE_NAMES[0], "a") as pack:
            pack.writestr(PACK_MEMBER, _info(6).to_json())

        with pytest.raises(SystemExit):
            first_run_installer.main()

        assert 'has no "Configs/barks-reader.ini"' in install.error_message()
        assert not install.installed

    def test_a_config_with_no_section_fails_with_nothing_left_pending(
        self, install: _Install
    ) -> None:
        install.write_packs(
            {"Configs/barks-reader.ini": "[Other]\nkey = value\n", "Reader Files/one.txt": "1"},
            versions=(None, 6),
        )
        with ZipFile(install.exe_dir / DATA_PACK_FILE_NAMES[0], "a") as pack:
            pack.writestr(PACK_MEMBER, _info(6).to_json())

        with pytest.raises(SystemExit):
            first_run_installer.main()

        assert "section" in install.error_message()
        assert not install.installed
        assert list(install.config_info.app_config_dir.glob("*.new")) == []

    def test_a_failed_install_runs_again_and_succeeds(self, install: _Install) -> None:
        """A failure leaves the app not installed, so the next launch installs it afresh."""
        install.write_packs(two="too long")
        with pytest.raises(SystemExit):
            first_run_installer.main()
        assert install.failed_flag.exists()
        assert not install.installed  # so main.py runs the installer again

        install.write_packs()
        first_run_installer.main()

        assert install.installed
        assert not install.failed_flag.exists()
        assert (install.reader_files / "two.txt").read_text() == "2"
        install.success_message.assert_called_once()

    def test_what_an_interrupted_install_left_is_replaced(self, install: _Install) -> None:
        """A killed install's folders, and a Reader Files with no config, are not kept."""
        install.write_packs()
        for folder in (install.reader_files, install.reader_files.with_name("Reader Files.new")):
            folder.mkdir(parents=True)
            (folder / "half.txt").write_text("half")

        first_run_installer.main()

        assert not (install.reader_files / "half.txt").exists()
        assert (install.reader_files / "one.txt").read_text() == "1"
        assert not install.reader_files.with_name("Reader Files.old").exists()
        assert install.installed

    def test_a_report_that_cannot_be_shown_does_not_fail_the_install(
        self, install: _Install
    ) -> None:
        install.write_packs()
        install.success_message.side_effect = RuntimeError("no font")

        first_run_installer.main()  # and no SystemExit

        assert install.installed
        assert not install.failed_flag.exists()
        install.error_popup.assert_not_called()
        log = (install.exe_dir / "installer.log").read_text()
        assert "The install is complete, but its report could not be shown:" in log

    def test_a_report_that_fails_in_the_progress_window_does_not_fail_the_install(
        self, install: _Install
    ) -> None:
        """As `run_showing_progress` does: the work done, it raises what `show_next` raised."""
        install.write_packs()
        install.success_message.side_effect = RuntimeError("no font")

        def with_a_window(work: Any, *_args: Any, show_next: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
            show_next(work(), MagicMock())

        install.progress.side_effect = with_a_window

        first_run_installer.main()

        assert install.installed
        assert not install.failed_flag.exists()
        install.error_popup.assert_not_called()
        install.success_message.assert_called_once()  # not tried again with no window


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
