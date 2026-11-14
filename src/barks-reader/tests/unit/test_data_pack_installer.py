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
from barks_reader import data_pack_installer, installer_progress, installer_support
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
    progress: MagicMock

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

    def log_text(self) -> str:
        (log,) = self.exe_dir.glob("barks-reader-data-pack-update-*.log")
        return log.read_text(encoding="utf-8")

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
        # No window: the work runs where it is called, as on a machine with none.
        patch.object(
            installer_progress,
            "run_showing_progress",
            side_effect=lambda work, *_args, **_kwargs: (work(), False),
        ) as progress,
    ):
        yield _Update(
            exe_dir, data_pack_installer.ConfigInfo(), error_popup, success, spawn, progress
        )
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
        update.spawn.assert_called_once_with([sys.executable, str(update.exe_dir / "barks-reader")])
        assert not (update.exe_dir / "barks-reader-installer-failed.flag").exists()
        logs = list(update.exe_dir.glob("barks-reader-data-pack-update-*.log"))
        assert len(logs) == 1
        assert "Installed Data pack 6 (29 Oct 2026)." in logs[0].read_text()

    def test_the_packs_are_unpacked_behind_a_window_that_follows_their_bytes(
        self, update: _Update
    ) -> None:
        update.install_old_data()
        update.write_packs()

        assert data_pack_installer.main() == 0

        _work, progress = update.progress.call_args.args
        assert progress.total > len("new") + len(b"zip")  # and each pack's version file
        assert progress.fraction == 1.0  # every byte promised was written
        kwargs = update.progress.call_args.kwargs
        assert kwargs["title"] == "Updating the Barks Reader's Data"
        assert kwargs["borderless"] is True  # as the success popup that follows in it is

    def test_the_success_message_is_shown_in_the_progress_windows_loop(
        self, update: _Update
    ) -> None:
        """With the window up, the message follows in it; its close only ends the loop."""
        update.install_old_data()
        update.write_packs()
        end_loop = MagicMock()

        def with_a_window(work: Any, *_args: Any, show_next: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
            result = work()
            show_next(result, end_loop)
            update.spawn.assert_not_called()  # not while the popup is up
            return result, True

        update.progress.side_effect = with_a_window

        assert data_pack_installer.main() == 0

        update.success.assert_called_once()
        assert update.success.call_args.args[1] == _info(6)
        kwargs = update.success.call_args.kwargs
        assert kwargs["in_running_loop"] is True
        assert kwargs["on_dismiss"] is end_loop
        update.spawn.assert_called_once()

    def test_a_window_closed_some_other_way_still_starts_the_reader(self, update: _Update) -> None:
        """The desktop's own close ends the loop with the popup's `on_dismiss` never called."""
        update.install_old_data()
        update.write_packs()

        def closed_by_the_desktop(work: Any, *_args: Any, show_next: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
            result = work()
            show_next(result, MagicMock())
            return result, True

        update.progress.side_effect = closed_by_the_desktop

        assert data_pack_installer.main() == 0

        update.success.call_args.kwargs["on_dismiss"].assert_not_called()
        update.spawn.assert_called_once()

    def test_a_success_popup_that_fails_in_the_window_is_not_a_failed_update(
        self, update: _Update
    ) -> None:
        """As `run_showing_progress` does: the work done, it raises what `show_next` raised."""
        update.install_old_data()
        update.write_packs()
        update.success.side_effect = RuntimeError("no font")

        def with_a_window(work: Any, *_args: Any, show_next: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
            show_next(work(), MagicMock())

        update.progress.side_effect = with_a_window

        assert data_pack_installer.main() == 0

        update.error_popup.assert_not_called()
        update.success.assert_called_once()  # not tried again with no window
        update.spawn.assert_called_once()
        assert data_pack.read_installed(update.reader_files) == _info(6)
        assert "the popup saying so could not be shown" in update.log_text()

    def test_a_success_popup_that_fails_with_no_window_is_not_a_failed_update(
        self, update: _Update
    ) -> None:
        update.install_old_data()
        update.write_packs()
        update.success.side_effect = RuntimeError("no font")

        assert data_pack_installer.main() == 0

        update.error_popup.assert_not_called()
        update.spawn.assert_called_once()
        assert "the popup saying so could not be shown" in update.log_text()

    def test_a_log_file_that_cannot_be_made_does_not_stop_the_update(self, update: _Update) -> None:
        update.install_old_data()
        update.write_packs()

        with patch.object(logger, "add", side_effect=PermissionError(13, "read-only")):
            assert data_pack_installer.main() == 0

        assert data_pack.read_installed(update.reader_files) == _info(6)
        update.spawn.assert_called_once()

    def test_a_config_that_cannot_be_set_up_is_reported_and_no_reader_started(
        self, update: _Update
    ) -> None:
        update.install_old_data()
        update.write_packs()

        with (
            patch.object(data_pack_installer, "ConfigInfo", side_effect=RuntimeError("no dir")),
            pytest.raises(SystemExit),
        ):
            data_pack_installer.main()

        assert update.error_message() == "RuntimeError: no dir"
        update.spawn.assert_not_called()
        assert "its config could not be set up" in update.log_text()

    def test_an_error_popup_that_cannot_be_shown_still_starts_the_reader(
        self, update: _Update
    ) -> None:
        update.install_old_data()
        update.write_packs(panels=b"truncated!")
        update.error_popup.side_effect = RuntimeError("no window")

        with pytest.raises(RuntimeError, match="no window"):
            data_pack_installer.main()

        update.spawn.assert_called_once()

    def test_a_reader_that_cannot_be_started_after_a_failure_is_logged(
        self, update: _Update
    ) -> None:
        update.install_old_data()
        update.write_packs(panels=b"truncated!")
        update.spawn.side_effect = OSError("no such file")
        handling: list[object] = []
        update.error_popup.side_effect = lambda *_a, **_k: handling.append(sys.exc_info()[1])

        with pytest.raises(SystemExit):  # the popup's exit, not the spawn's error
            data_pack_installer.main()

        # No error is being handled while the popup is up: an interrupt there is then
        # printed as itself, not chained to the error the popup is reporting.
        assert handling == [None]

        assert "not what its packs promised" in update.error_message()
        assert "Could not start the Barks Reader again:" in update.log_text()

    def test_no_newer_pack_is_reported_before_any_window_opens(self, update: _Update) -> None:
        update.install_old_data(version=6)
        update.write_packs(version=6)

        with pytest.raises(SystemExit):
            data_pack_installer.main()

        update.progress.assert_not_called()

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
        update.spawn.assert_called_once()  # the reader closed for this: it runs again

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
        update.spawn.assert_called_once()  # on the data it had
        assert not (update.exe_dir / "barks-reader-installer-failed.flag").exists()

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
        update.spawn.assert_called_once()

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
        update.spawn.assert_not_called()  # a reader with no data would only fail
        assert "Not starting the Barks Reader again" in update.log_text()

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
            installer_support, "extract_subdir", MagicMock(side_effect=RuntimeError("boom"))
        )
        handling: list[object] = []
        update.error_popup.side_effect = lambda *_a, **_k: handling.append(sys.exc_info()[1])

        with pytest.raises(SystemExit):
            data_pack_installer.main()

        assert handling == [None]  # the popup is shown outside the error's handler
        assert "boom" in update.error_popup.call_args.kwargs["details"]
        update.spawn.assert_called_once()


class TestSuccessMessage:
    @pytest.fixture
    def spawn(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
        monkeypatch.setenv("BARKS_READER_CONFIG_DIR", str(tmp_path / "config"))
        monkeypatch.setenv("BARKS_READER_DATA_DIR", str(tmp_path / "data"))
        with patch.object(data_pack, "spawn_detached") as spawn:
            yield spawn

    def test_the_popup_names_the_pack_and_its_close_starts_nothing_itself(
        self, tmp_path: Path, spawn: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["/exe/barks-reader"])
        with (
            patch.object(kivy_standalone_show_message, "show_standalone_popup") as popup,
            patch.object(kivy_standalone_show_message, "place_window") as place_window,
            patch.object(minimal_config_info_module, "get_minimal_config_options") as options,
            patch.object(data_pack_installer, "IS_COMPILED", new=True),
        ):
            options.return_value.success_background_path = tmp_path / "ok.png"
            data_pack_installer._show_success_message(  # noqa: SLF001
                data_pack_installer.ConfigInfo(), _info(6)
            )

            title, content = popup.call_args.args
            assert title == "Data Pack Updated"
            assert "Data pack 6 (29 Oct 2026)" in content.text
            assert popup.call_args.kwargs["background_image_file"] == tmp_path / "ok.png"
            assert popup.call_args.kwargs["fill_window"] is True
            (ok,) = popup.call_args.kwargs["buttons"]
            assert (ok.text, ok.closes) == ("OK", True)
            # No frame of the desktop's: the popup's own title bar is the window's top.
            place_window.assert_called_once_with((900, 720), borderless=True)
            ok.on_press()  # the frame closes it; main starts the reader once it has
            assert popup.call_args.kwargs["on_dismiss"] is None

        spawn.assert_not_called()

    def test_the_body_is_the_message_alone_its_ok_the_frames(self) -> None:
        content = data_pack_installer._success_content("done")  # noqa: SLF001
        assert content.text == "done"
        assert not content.children

    def test_without_the_background_art_the_popup_still_shows(
        self, spawn: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["/exe/barks-reader"])
        with (
            patch.object(kivy_standalone_show_message, "show_standalone_popup") as popup,
            patch.object(kivy_standalone_show_message, "place_window"),
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
            patch.object(kivy_standalone_show_message, "place_window"),
            patch.object(minimal_config_info_module, "get_minimal_config_options"),
        ):
            data_pack_installer.preview_success_message()

            title, content = popup.call_args.args
            assert title == "Data Pack Updated"
            assert "Data pack 6 (" in content.text
            assert popup.call_args.kwargs["on_dismiss"] is None

        spawn.assert_not_called()

    def test_a_standalone_build_starts_its_own_executable(
        self, spawn: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["/exe/barks-reader"])
        with patch.object(data_pack_installer, "IS_COMPILED", new=True):
            data_pack_installer._restart_reader()  # noqa: SLF001

        spawn.assert_called_once_with(["/exe/barks-reader"])

    def test_a_development_run_starts_the_reader_through_the_interpreter(
        self, spawn: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["main.py"])
        with patch.object(data_pack_installer, "IS_COMPILED", new=False):
            data_pack_installer._restart_reader()  # noqa: SLF001

        spawn.assert_called_once_with([sys.executable, "main.py"])

    def test_a_run_by_hand_has_no_reader_to_start_again(
        self, spawn: MagicMock, monkeypatch: pytest.MonkeyPatch, loguru_sink: list[str]
    ) -> None:
        # As ``python -m barks_reader.data_pack_installer`` leaves it: the module itself.
        monkeypatch.setattr(sys, "argv", [data_pack_installer.__file__])
        with patch.object(data_pack_installer, "IS_COMPILED", new=False):
            data_pack_installer._restart_reader()  # noqa: SLF001

        spawn.assert_not_called()
        assert any("the reader did not start this update" in line for line in loguru_sink)

    def test_a_standalone_build_is_never_taken_for_a_run_by_hand(
        self, spawn: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", [data_pack_installer.__file__])
        with patch.object(data_pack_installer, "IS_COMPILED", new=True):
            data_pack_installer._restart_reader()  # noqa: SLF001

        spawn.assert_called_once_with([data_pack_installer.__file__])
