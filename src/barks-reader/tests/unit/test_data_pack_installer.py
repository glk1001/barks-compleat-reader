"""The data pack installer: newer packs beside the executable replace the installed data."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

import pytest
from barks_reader import data_pack_installer
from barks_reader.core import data_pack
from barks_reader.core import minimal_config_info as minimal_config_info_module
from barks_reader.core.data_pack import DATA_PACK_FILE_NAMES, PACK_MEMBER, DataPackInfo
from barks_reader.ui import kivy_standalone_error_popup, kivy_standalone_show_message
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_INI_TEXT = "[Barks Reader]\nfanta_dir = Fantagraphics Volumes\n"
_BUILT = datetime(2026, 10, 29, tzinfo=UTC)


def _info(version: int, entries: dict[str, dict] | None = None) -> DataPackInfo:
    if entries is None:
        entries = {
            "Indexes": {"files": 1, "bytes": 1, "md5": "a"},
            "Barks Panels.zip": {"files": 1, "bytes": 3, "md5": "b"},
        }
    return DataPackInfo(version, f"data-v{version}", _BUILT, "main-pc", entries)


@dataclass
class _Update:
    exe_dir: Path
    config_info: data_pack_installer.ConfigInfo
    error_popup: MagicMock
    success: MagicMock
    spawn: MagicMock

    @property
    def reader_files(self) -> Path:
        return self.config_info.app_data_dir / "Reader Files"

    def install_old_data(self, version: int | None = 5) -> None:
        (self.reader_files / "Indexes").mkdir(parents=True)
        (self.reader_files / "Indexes" / "old.seg").write_text("old")
        (self.reader_files / "stale.txt").write_text("stale")
        if version is not None:
            (self.reader_files / "data-pack.json").write_text(_info(version).to_json())
        self.config_info.app_config_dir.mkdir(parents=True, exist_ok=True)
        self.config_info.app_config_path.write_text(_INI_TEXT)

    def write_packs(self, version: int = 6, *, panels: bytes = b"zip") -> None:
        info = _info(version)
        with ZipFile(self.exe_dir / DATA_PACK_FILE_NAMES[0], "w") as pack:
            pack.writestr("Configs/barks-reader.ini", "[Barks Reader]\nfanta_dir = X\n")
            pack.writestr("Reader Files/Indexes/new.seg", "new")
            pack.writestr(PACK_MEMBER, info.to_json())
        with ZipFile(self.exe_dir / DATA_PACK_FILE_NAMES[1], "w") as pack:
            pack.writestr("Reader Files/Barks Panels.zip", panels)
            pack.writestr(PACK_MEMBER, info.to_json())

    def error_message(self) -> str:
        return self.error_popup.call_args.kwargs["message"]

    def error_details(self) -> str:
        return self.error_popup.call_args.kwargs["details"]


@pytest.fixture
def update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_Update]:
    """Set up an installed reader beside a scratch executable, packs beside it, popups caught."""
    exe_dir = tmp_path / "exe"
    exe_dir.mkdir()
    monkeypatch.setenv("BARKS_READER_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("BARKS_READER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv(data_pack.DATA_PACK_DIR_ENV_VAR, str(exe_dir))
    monkeypatch.setattr(data_pack_installer, "get_app_exe_dir", lambda: exe_dir)
    monkeypatch.setattr(sys, "argv", [str(exe_dir / "barks-reader")])

    sinks: list[int] = []
    real_add = logger.add

    def add_sink(*args: Any, **kwargs: Any) -> int:  # noqa: ANN401
        sinks.append(real_add(*args, **kwargs))
        return sinks[-1]

    with (
        patch.object(logger, "add", side_effect=add_sink),
        patch.object(kivy_standalone_error_popup, "show_error_popup") as error_popup,
        patch.object(data_pack_installer, "_show_success_message") as success,
        patch.object(data_pack, "spawn_detached") as spawn,
    ):
        yield _Update(exe_dir, data_pack_installer.ConfigInfo(), error_popup, success, spawn)
    for sink in sinks:
        logger.remove(sink)


class TestMain:
    def test_newer_packs_replace_the_installed_data_and_leave_the_config(
        self, update: _Update
    ) -> None:
        update.install_old_data()
        update.write_packs()

        assert data_pack_installer.main() == 0

        assert (update.reader_files / "Indexes" / "new.seg").read_text() == "new"
        assert not (update.reader_files / "Indexes" / "old.seg").exists()
        assert not (update.reader_files / "stale.txt").exists()
        assert (update.reader_files / "Barks Panels.zip").read_bytes() == b"zip"
        assert data_pack.read_installed(update.reader_files) == _info(6)
        assert update.config_info.app_config_path.read_text() == _INI_TEXT
        assert not update.reader_files.with_name("Reader Files.new").exists()
        assert not update.reader_files.with_name("Reader Files.old").exists()
        update.error_popup.assert_not_called()
        assert update.success.call_args.args[1] == _info(6)
        assert not (update.exe_dir / "barks-reader-installer-failed.flag").exists()
        logs = list(update.exe_dir.glob("barks-reader-data-pack-update-*.log"))
        assert len(logs) == 1
        assert "Installed Data pack 6 (29 Oct 2026)." in logs[0].read_text()

    def test_an_unversioned_install_takes_the_packs(self, update: _Update) -> None:
        update.install_old_data(version=None)
        update.write_packs()

        assert data_pack_installer.main() == 0

        assert data_pack.read_installed(update.reader_files) == _info(6)

    def test_packs_no_newer_than_the_install_change_nothing(self, update: _Update) -> None:
        update.install_old_data(version=6)
        update.write_packs(version=6)

        with pytest.raises(SystemExit):
            data_pack_installer.main()

        assert "no newer data pack" in update.error_message()
        assert "data pack 6 is installed" in update.error_details()
        assert (update.reader_files / "stale.txt").exists()
        update.success.assert_not_called()

    def test_an_extraction_that_does_not_match_the_packs_leaves_the_data_alone(
        self, update: _Update
    ) -> None:
        update.install_old_data()
        update.write_packs(panels=b"truncated!")

        with pytest.raises(SystemExit):
            data_pack_installer.main()

        assert "not what its packs promised" in update.error_message()
        assert '"Barks Panels.zip" is 10 bytes, not the 3' in update.error_details()
        assert (update.reader_files / "Indexes" / "old.seg").exists()
        assert not update.reader_files.with_name("Reader Files.new").exists()
        update.success.assert_not_called()

    @staticmethod
    def _swap_with(rename: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN401
        """Run the real swap, with `rename` in place of the OS's and no waiting."""
        monkeypatch.setattr(
            data_pack_installer.data_pack,
            "swap_reader_files",
            partial(data_pack.swap_reader_files, attempts=2, sleep=lambda _s: None, rename=rename),
        )

    def test_a_folder_in_use_is_reported_and_the_data_put_back(
        self, update: _Update, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        update.install_old_data()
        update.write_packs()

        def rename(source: Path, target: Path) -> None:
            if source.name.endswith(".new"):
                raise PermissionError(13, "in use")
            source.rename(target)

        self._swap_with(rename, monkeypatch)

        with pytest.raises(SystemExit):
            data_pack_installer.main()

        assert "is in use" in update.error_message()
        assert "left as it was" in update.error_details()
        assert (update.reader_files / "Indexes" / "old.seg").exists()
        assert not update.reader_files.with_name("Reader Files.new").exists()
        assert not update.reader_files.with_name("Reader Files.old").exists()
        update.success.assert_not_called()

    def test_data_that_cannot_be_put_back_is_reported_where_it_is(
        self, update: _Update, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        update.install_old_data()
        update.write_packs()
        old = update.reader_files.with_name("Reader Files.old")

        def rename(source: Path, target: Path) -> None:
            if target == update.reader_files:
                raise PermissionError(13, "in use")
            source.rename(target)

        self._swap_with(rename, monkeypatch)

        with pytest.raises(SystemExit):
            data_pack_installer.main()

        assert "could not be put back" in update.error_message()
        assert f'"{old}"' in update.error_message()
        assert 'run the update again: it puts "Reader Files.old" back first' in (
            update.error_details()
        )
        assert not update.reader_files.exists()
        assert (old / "Indexes" / "old.seg").exists()
        assert not update.reader_files.with_name("Reader Files.new").exists()
        update.success.assert_not_called()

    def test_data_stranded_by_a_failed_update_is_put_back_before_the_next(
        self, update: _Update
    ) -> None:
        update.install_old_data()
        update.write_packs(panels=b"truncated!")
        old = update.reader_files.with_name("Reader Files.old")
        update.reader_files.rename(old)

        with pytest.raises(SystemExit):
            data_pack_installer.main()

        # The packs were bad, and the stranded data is back where the reader looks.
        assert "not what its packs promised" in update.error_message()
        assert (update.reader_files / "Indexes" / "old.seg").exists()
        assert not old.exists()

    def test_leftovers_of_an_interrupted_update_are_cleared_first(self, update: _Update) -> None:
        update.install_old_data()
        update.write_packs()
        leftover = update.reader_files.with_name("Reader Files.new")
        leftover.mkdir()
        (leftover / "half.txt").write_text("half")

        assert data_pack_installer.main() == 0

        assert not (update.reader_files / "half.txt").exists()

    def test_an_unexpected_error_shows_the_traceback_popup(
        self, update: _Update, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        update.install_old_data()
        update.write_packs()
        monkeypatch.setattr(
            data_pack_installer, "extract_subdir", MagicMock(side_effect=RuntimeError("boom"))
        )

        with pytest.raises(SystemExit):
            data_pack_installer.main()

        assert "boom" in update.error_popup.call_args.kwargs["details"]


class TestSuccessMessage:
    @pytest.fixture
    def spawn(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
        monkeypatch.setenv("BARKS_READER_CONFIG_DIR", str(tmp_path / "config"))
        monkeypatch.setenv("BARKS_READER_DATA_DIR", str(tmp_path / "data"))
        with patch.object(data_pack, "spawn_detached") as spawn:
            yield spawn

    def test_the_popup_names_the_pack_and_its_close_starts_the_reader(
        self, tmp_path: Path, spawn: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["/exe/barks-reader"])
        with (
            patch.object(kivy_standalone_show_message, "show_standalone_popup") as popup,
            patch.object(
                data_pack_installer, "get_centred_position_on_primary_monitor", return_value=(1, 2)
            ),
            patch.object(minimal_config_info_module, "get_minimal_config_options") as options,
            patch.object(data_pack_installer, "IS_COMPILED", new=True),
        ):
            options.return_value.success_background_path = tmp_path / "ok.png"
            data_pack_installer._show_success_message(  # noqa: SLF001
                data_pack_installer.ConfigInfo(), _info(6)
            )

            title, content = popup.call_args.args
            assert title == "Data Pack Updated"
            assert "Data pack 6 (29 Oct 2026)" in content.label.text
            assert popup.call_args.kwargs["background_image_file"] == tmp_path / "ok.png"
            assert popup.call_args.kwargs["size_hint"] == (1, 1)
            assert popup.call_args.kwargs["add_close_button"] is False
            popup.call_args.kwargs["on_dismiss"]()

        spawn.assert_called_once_with(["/exe/barks-reader"])

    def test_the_ok_button_dismisses_the_popup(self) -> None:
        content = data_pack_installer._success_content("done")  # noqa: SLF001

        content.ok_button.trigger_action()  # before the popup exists: nothing to dismiss
        content.popup_ref = MagicMock()
        content.ok_button.trigger_action()

        content.popup_ref.dismiss.assert_called_once()
        assert content.ok_button.text == "OK"

    def test_without_the_background_art_the_popup_still_shows(
        self, spawn: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["/exe/barks-reader"])
        with (
            patch.object(kivy_standalone_show_message, "show_standalone_popup") as popup,
            patch.object(
                data_pack_installer, "get_centred_position_on_primary_monitor", return_value=(1, 2)
            ),
            patch.object(
                minimal_config_info_module,
                "get_minimal_config_options",
                side_effect=FileNotFoundError("no art"),
            ),
        ):
            data_pack_installer._show_success_message(  # noqa: SLF001
                data_pack_installer.ConfigInfo(), _info(6)
            )

        assert popup.call_args.kwargs["background_image_file"] is None
        spawn.assert_not_called()

    def test_the_preview_shows_a_made_up_pack_and_its_close_starts_nothing(
        self, spawn: MagicMock
    ) -> None:
        with (
            patch.object(kivy_standalone_show_message, "show_standalone_popup") as popup,
            patch.object(
                data_pack_installer, "get_centred_position_on_primary_monitor", return_value=(1, 2)
            ),
            patch.object(minimal_config_info_module, "get_minimal_config_options"),
        ):
            data_pack_installer.preview_success_message()

            title, content = popup.call_args.args
            assert title == "Data Pack Updated"
            assert "Data pack 6 (" in content.label.text
            popup.call_args.kwargs["on_dismiss"]()

        spawn.assert_not_called()

    def test_a_development_run_starts_the_reader_through_the_interpreter(
        self, spawn: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["main.py"])
        with patch.object(data_pack_installer, "IS_COMPILED", new=False):
            data_pack_installer._restart_reader()  # noqa: SLF001

        spawn.assert_called_once_with([sys.executable, "main.py"])
