"""scripts/popup_gallery.py: the scratch profile, the requests, the window finder, the sheet."""

# cspell:ignore killpg

from __future__ import annotations

import os
import re
import subprocess
import sys
from contextlib import nullcontext
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import popup_gallery
import pytest
from barks_reader.core import log_markers
from barks_reader.core.popup_gallery import POPUP_NAMES, parse_request
from gui_driver import CONFIG_DIR_ENV_VAR, DriverError

if TYPE_CHECKING:
    from pathlib import Path


class TestLiveProfileDir:
    def test_the_environment_wins(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv(CONFIG_DIR_ENV_VAR, str(tmp_path))
        assert popup_gallery.live_profile_dir() == tmp_path

    def test_else_the_env_file_with_home_filled_in(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv(CONFIG_DIR_ENV_VAR, raising=False)
        monkeypatch.setattr(popup_gallery, "REPO_ROOT", tmp_path)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))  # Path.home() on Windows
        (tmp_path / ".env.runtime").write_text(
            f'{CONFIG_DIR_ENV_VAR}="${{HOME}}/opt/barks-reader/config"\n', encoding="utf-8"
        )
        assert popup_gallery.live_profile_dir() == tmp_path / "home/opt/barks-reader/config"

    def test_else_the_default(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv(CONFIG_DIR_ENV_VAR, raising=False)
        monkeypatch.setattr(popup_gallery, "REPO_ROOT", tmp_path)
        assert popup_gallery.live_profile_dir() == popup_gallery.LIVE_PROFILE_DEFAULT


class TestScratchProfile:
    def _live(self, root: Path) -> Path:
        live = root / "live"
        (live / "kivy" / "logs").mkdir(parents=True)
        (live / "barks-reader.ini").write_text(
            "[Barks Reader]\nconfirm_quit = 1\nlog_level = INFO\n"
            "main_screen_layout = Single page\nuse_deah = 1\n",
            encoding="utf-8",
        )
        (live / "barks-reader.json").write_text("{}", encoding="utf-8")
        (live / "kivy" / "config.ini").write_text("[kivy]\n", encoding="utf-8")
        (live / "kivy" / "logs" / "big.log").write_text("x" * 100, encoding="utf-8")
        return live

    def test_the_top_files_and_the_kivy_ini_are_copied_not_the_logs(self, tmp_path: Path) -> None:
        scratch = popup_gallery.make_scratch_profile(self._live(tmp_path), tmp_path / "scratch")
        assert sorted(p.name for p in scratch.iterdir()) == [
            "barks-reader.ini",
            "barks-reader.json",
            "kivy",
        ]
        assert [p.name for p in (scratch / "kivy").iterdir()] == ["config.ini"]

    def test_the_copy_logs_at_debug_matches_the_screen_and_the_live_ini_is_untouched(
        self, tmp_path: Path
    ) -> None:
        live = self._live(tmp_path)
        scratch = popup_gallery.make_scratch_profile(live, tmp_path / "scratch")
        assert (scratch / "barks-reader.ini").read_text(encoding="utf-8") == (
            "[Barks Reader]\nconfirm_quit = 1\nlog_level = DEBUG\n"
            "main_screen_layout = Match the screen\nuse_deah = 1\n"
        )
        assert "log_level = INFO" in (live / "barks-reader.ini").read_text(encoding="utf-8")

    def test_live_mode_keeps_the_profiles_settings(self, tmp_path: Path) -> None:
        live = self._live(tmp_path)
        scratch = popup_gallery.make_scratch_profile(live, tmp_path / "scratch", for_capture=False)
        assert (scratch / "barks-reader.ini").read_text(encoding="utf-8") == (
            live / "barks-reader.ini"
        ).read_text(encoding="utf-8")

    def test_a_second_run_starts_from_a_fresh_copy(self, tmp_path: Path) -> None:
        live = self._live(tmp_path)
        scratch = popup_gallery.make_scratch_profile(live, tmp_path / "scratch")
        (scratch / "left-over.json").write_text("{}", encoding="utf-8")
        popup_gallery.make_scratch_profile(live, scratch)
        assert not (scratch / "left-over.json").exists()


def test_a_request_is_written_whole_for_the_app_to_read(tmp_path: Path) -> None:
    request_file = tmp_path / "popup-request"
    popup_gallery.write_request(request_file, "spread-3", "quit")
    assert parse_request(request_file.read_text(encoding="utf-8")) == ("spread-3", "quit")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["popup-request"]


def test_captures_are_numbered_to_list_in_gallery_order() -> None:
    assert popup_gallery.shot_name(3, "clear-history") == "03-clear-history.png"


def test_the_sheet_labels_every_capture_by_its_name(tmp_path: Path) -> None:
    shots = [tmp_path / "01-quit.png", tmp_path / "02-about.png"]
    command = popup_gallery.montage_command(shots, tmp_path / "sheet.png", "spread")
    assert command[:3] == ["montage", "-label", "%t"]
    assert command[3:5] == [str(shot) for shot in shots]
    assert command[-1] == str(tmp_path / "sheet.png")


class TestFindTopWindow:
    LISTING = """
xwininfo: Window id: 0x3a8 (the root window) (has no name)

  Root window id: 0x3a8 (the root window) (has no name)
  Parent window id: 0x0 (none)
     2 children:
     0x200001 "SDL helper": ()  10x10+-100+-100  +-100+-100
     0x200002 "Barks Reader Installer": ("python" "python")  800x1000+400+100  +400+100
"""

    def test_the_first_window_big_enough_for_a_popup(self) -> None:
        assert popup_gallery.find_top_window(self.LISTING) == (800, 1000, 400, 100)

    def test_none_before_the_popup_has_a_window(self) -> None:
        assert popup_gallery.find_top_window("  Root window id: 0x3a8\n") is None


class TestPreviewCommand:
    def test_the_preview_runs_its_module_after_the_launcher(self) -> None:
        command = popup_gallery.preview_command("data-pack-success")
        assert command[:5] == ["uv", "run", "--env-file", ".env.runtime", "python"]
        assert command[-2:] == ["barks_reader.data_pack_installer", "--preview"]

    def test_config_info_is_in_before_the_module_runs_as_main(self, tmp_path: Path) -> None:
        (tmp_path / "fake_preview.py").write_text(
            "import sys\n"
            "assert __name__ == '__main__'\n"
            "print('barks_reader.core.config_info' in sys.modules, sys.argv[1:])\n",
            encoding="utf-8",
        )
        command = popup_gallery.preview_command("data-pack-success")
        launcher = command[command.index("-c") + 1]
        env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(tmp_path), *sys.path])}
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", launcher, "fake_preview", "--preview"],
            capture_output=True,
            text=True,
            env=env,
            check=True,
            encoding="utf-8",
        )
        assert result.stdout == "True ['--preview']\n"


def test_an_own_window_failing_leaves_the_rest_to_capture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def capture(name: str, out: Path, _profile: Path) -> Path:
        if name == "error-popup":
            msg = f"{name}: no window appeared"
            raise popup_gallery.DriverError(msg)
        return out / f"{name}.png"

    sheets: list[list[Path]] = []
    monkeypatch.setattr(popup_gallery, "capture_own_window", capture)
    monkeypatch.setattr(popup_gallery, "_montage", lambda shots, *_: sheets.append(shots))
    failed = popup_gallery.capture_own_windows(list(popup_gallery.OWN_WINDOW), tmp_path, tmp_path)
    assert failed == ["error-popup"]
    assert sheets == [[tmp_path / "first-run-installer.png", tmp_path / "data-pack-success.png"]]


class TestStopGroup:
    """A preview or display gone before it is stopped is no error."""

    @staticmethod
    def _process(*, wait_raises: Exception | None = None) -> MagicMock:
        process = MagicMock(pid=4321)
        process.poll.return_value = None
        process.wait.side_effect = wait_raises
        return process

    def test_a_group_gone_before_the_signal_is_left(self, monkeypatch: pytest.MonkeyPatch) -> None:
        killpg = MagicMock(side_effect=ProcessLookupError)
        monkeypatch.setattr(popup_gallery.os, "killpg", killpg, raising=False)
        popup_gallery._stop_group(self._process())  # noqa: SLF001
        assert killpg.call_count == 1  # no SIGKILL sent after it

    def test_a_group_that_will_not_go_is_killed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        killpg = MagicMock()
        monkeypatch.setattr(popup_gallery.os, "killpg", killpg, raising=False)
        monkeypatch.setattr(popup_gallery.signal, "SIGKILL", 9, raising=False)
        popup_gallery._stop_group(  # noqa: SLF001
            self._process(wait_raises=subprocess.TimeoutExpired("preview", 10))
        )
        assert [c.args for c in killpg.call_args_list] == [
            (4321, popup_gallery.signal.SIGTERM),
            (4321, 9),
        ]

    def test_a_group_gone_before_the_kill_is_left(self, monkeypatch: pytest.MonkeyPatch) -> None:
        killpg = MagicMock(side_effect=[None, ProcessLookupError])
        monkeypatch.setattr(popup_gallery.os, "killpg", killpg, raising=False)
        monkeypatch.setattr(popup_gallery.signal, "SIGKILL", 9, raising=False)
        popup_gallery._stop_group(  # noqa: SLF001
            self._process(wait_raises=subprocess.TimeoutExpired("preview", 10))
        )
        assert killpg.call_count == 2  # noqa: PLR2004

    def test_a_finished_process_is_not_signalled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        killpg = MagicMock()
        monkeypatch.setattr(popup_gallery.os, "killpg", killpg, raising=False)
        process = self._process()
        process.poll.return_value = 0
        popup_gallery._stop_group(process)  # noqa: SLF001
        killpg.assert_not_called()


class TestSelect:
    def test_nothing_named_is_everything(self) -> None:
        assert popup_gallery.select("", ["a", "b"]) == ["a", "b"]

    def test_the_names_come_back_in_the_lists_order(self) -> None:
        assert popup_gallery.select("b, a", ["a", "b", "c"]) == ["a", "b"]

    def test_an_unknown_name_stops_the_run(self) -> None:
        with pytest.raises(SystemExit, match="no such popup or size: z"):
            popup_gallery.select("a,z", ["a", "b"])


def test_list_names_every_popup(capsys: pytest.CaptureFixture[str]) -> None:
    assert popup_gallery.main(["--list"]) == 0
    printed = capsys.readouterr().out
    for name in (*POPUP_NAMES, *popup_gallery.OWN_WINDOW):
        assert f"  {name}\n" in printed


class TestMontage:
    def test_no_captures_make_no_sheet(self, tmp_path: Path) -> None:
        with patch.object(popup_gallery.subprocess, "run") as run:
            popup_gallery._montage([], tmp_path / "sheet.png", "single")  # noqa: SLF001

        run.assert_not_called()

    def test_the_captures_are_laid_out_on_one_sheet(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        shots, sheet = [tmp_path / "01-about.png"], tmp_path / "sheet.png"
        with patch.object(popup_gallery.subprocess, "run") as run:
            popup_gallery._montage(shots, sheet, "single")  # noqa: SLF001

        run.assert_called_once_with(
            popup_gallery.montage_command(shots, sheet, "single"), check=True
        )
        assert f"sheet: {sheet}" in capsys.readouterr().out


class TestCaptureSize:
    """One headless boot per screen size: each popup asked for, waited on, then captured."""

    @staticmethod
    def _capture(tmp_path: Path, driver: MagicMock) -> tuple[list[Path], MagicMock]:
        driver.frame_capture.side_effect = lambda path, _request: path
        with (
            patch.object(popup_gallery, "probe") as probe,
            patch.object(popup_gallery, "Driver", return_value=driver) as made,
        ):
            try:
                names = list(POPUP_NAMES[:2])
                return popup_gallery.capture_size("spread", names, tmp_path, tmp_path / "p"), probe
            finally:
                made.assert_called_once_with(paced=False)
                assert [c.args for c in probe.call_args_list] == [("start",), ("stop",)]

    def test_each_popup_is_asked_for_waited_on_and_captured_in_order(self, tmp_path: Path) -> None:
        driver = MagicMock()
        asked: list[str] = []
        driver.expect.side_effect = lambda _pattern, _timeout: nullcontext(
            asked.append((tmp_path / "popup-request").read_text(encoding="utf-8"))
            if (tmp_path / "popup-request").exists()
            else None
        )

        shots, _ = self._capture(tmp_path, driver)

        first, second = POPUP_NAMES[:2]
        assert shots == [
            tmp_path / "spread" / popup_gallery.shot_name(1, first),
            tmp_path / "spread" / popup_gallery.shot_name(2, second),
        ]
        waited_on = [c.args[0] for c in driver.expect.call_args_list]
        assert waited_on == [
            log_markers.pattern(log_markers.POPUP_GALLERY_SHOWN, request="spread-1", name=first),
            log_markers.pattern(log_markers.POPUP_GALLERY_SHOWN, request="spread-2", name=second),
        ]
        assert [c.args[1] for c in driver.frame_capture.call_args_list] == [
            "spread-1-frame",
            "spread-2-frame",
        ]
        # The last request written is the second popup's, in the app's own format.
        last = (tmp_path / "popup-request").read_text(encoding="utf-8")
        assert parse_request(last) == ("spread-2", second)
        assert driver.settle.call_count == 2  # noqa: PLR2004

    def test_the_app_is_booted_headless_at_the_size_from_the_scratch_profile(
        self, tmp_path: Path
    ) -> None:
        self._capture(tmp_path, MagicMock())

        assert os.environ[CONFIG_DIR_ENV_VAR] == str(tmp_path / "p")
        assert os.environ["BARKS_PROBE_SCREEN"] == popup_gallery.SIZES["spread"]
        assert os.environ["BARKS_PROBE_HEADLESS"] == "1"
        assert os.environ[popup_gallery.POPUP_GALLERY_ENV_VAR] == str(tmp_path / "popup-request")

    def test_a_popup_that_never_shows_still_stops_the_app(self, tmp_path: Path) -> None:
        driver = MagicMock()
        driver.expect.side_effect = DriverError("beat stalled")

        with pytest.raises(DriverError, match="beat stalled"):
            self._capture(tmp_path, driver)  # its finally checks the stop


class TestWaitForXServer:
    def test_it_waits_until_the_server_s_socket_is_there(self) -> None:
        with (
            patch.object(popup_gallery.Path, "exists", side_effect=[False, False, True]),
            patch.object(popup_gallery.time, "sleep") as sleep,
        ):
            popup_gallery._wait_for_x_server(":12")  # noqa: SLF001

        assert sleep.call_count == 2  # noqa: PLR2004

    def test_a_server_that_never_comes_up_is_said(self) -> None:
        with (
            patch.object(popup_gallery.Path, "exists", return_value=False),
            patch.object(popup_gallery.time, "monotonic", side_effect=[0.0, 11.0]),
            pytest.raises(DriverError, match="Xvfb never came up on :12"),
        ):
            popup_gallery._wait_for_x_server(":12")  # noqa: SLF001


class TestCaptureOwnWindow:
    """A popup that runs before the app, or without it: its preview on a private display."""

    NAME = "error-popup"

    def _capture(
        self, tmp_path: Path, windows: list[tuple[int, int, int, int] | None], *, exits: bool
    ) -> tuple[Path, MagicMock, MagicMock]:
        xvfb, popup = MagicMock(name="xvfb"), MagicMock(name="popup")
        popup.poll.return_value = 1 if exits else None
        with (
            patch.object(popup_gallery.subprocess, "Popen", side_effect=[xvfb, popup]) as popen,
            patch.object(popup_gallery.subprocess, "run") as run,
            patch.object(popup_gallery, "_wait_for_x_server"),
            patch.object(popup_gallery, "find_top_window", side_effect=windows),
            patch.object(popup_gallery, "_stop_group") as stop,
            patch.object(popup_gallery.time, "sleep"),
        ):
            try:
                shot = popup_gallery.capture_own_window(self.NAME, tmp_path, tmp_path / "p")
            finally:
                # However it ends, the preview and then its display are stopped.
                assert [c.args[0] for c in stop.call_args_list] == [popup, xvfb]
        return shot, popen, run

    def test_the_preview_s_window_is_cropped_out_of_its_private_display(
        self, tmp_path: Path
    ) -> None:
        shot, popen, run = self._capture(tmp_path, [None, (800, 600, 10, 20)], exits=False)

        assert shot == tmp_path / "own-window" / f"{self.NAME}.png"
        display = popup_gallery.OWN_WINDOW_DISPLAY
        assert popen.call_args_list[0].args[0][:2] == ["Xvfb", display]
        preview = popen.call_args_list[1]
        assert preview.args[0] == popup_gallery.preview_command(self.NAME)
        assert preview.kwargs["env"]["DISPLAY"] == display
        assert preview.kwargs["env"][CONFIG_DIR_ENV_VAR] == str(tmp_path / "p")
        grab = run.call_args.args[0]
        assert grab[0] == "import"
        assert grab[grab.index("-crop") + 1] == "800x600+10+20"
        assert grab[-1] == str(shot)

    def test_a_preview_that_exits_with_no_window_names_its_log(self, tmp_path: Path) -> None:
        log = tmp_path / "own-window" / f"{self.NAME}.log"

        with pytest.raises(DriverError, match=re.escape(f"no window appeared; see {log}")):
            self._capture(tmp_path, [], exits=True)

        assert log.is_file()


class TestRunLive:
    def test_the_real_app_runs_from_a_copy_of_the_profile_in_live_mode(
        self, tmp_path: Path
    ) -> None:
        with (
            patch.object(popup_gallery, "live_profile_dir", return_value=tmp_path / "live"),
            patch.object(
                popup_gallery, "make_scratch_profile", return_value=tmp_path / "profile"
            ) as copy,
            patch.object(
                popup_gallery.subprocess, "run", return_value=MagicMock(returncode=3)
            ) as run,
        ):
            assert popup_gallery.run_live(tmp_path) == 3  # noqa: PLR2004

        copy.assert_called_once_with(tmp_path / "live", tmp_path / "profile", for_capture=False)
        assert run.call_args.args[0][-1] == "main.py"
        env = run.call_args.kwargs["env"]
        assert env[CONFIG_DIR_ENV_VAR] == str(tmp_path / "profile")
        assert env[popup_gallery.POPUP_GALLERY_ENV_VAR] == popup_gallery.LIVE_MODE


# A capture run hooks SIGHUP, which Windows does not have; the gallery captures on Linux.
captures_on_posix = pytest.mark.skipif(sys.platform == "win32", reason="hooks SIGHUP")


class TestMain:
    @staticmethod
    def _main(argv: list[str], failed: list[str]) -> tuple[int, MagicMock, MagicMock, MagicMock]:
        with (
            patch.object(popup_gallery.signal, "signal"),  # never the test run's own handlers
            patch.object(popup_gallery, "live_profile_dir"),
            patch.object(popup_gallery, "make_scratch_profile") as profile,
            patch.object(popup_gallery, "capture_size", return_value=["a.png"]) as capture,
            patch.object(popup_gallery, "_montage") as montage,
            patch.object(popup_gallery, "capture_own_windows", return_value=failed) as own,
        ):
            status = popup_gallery.main(argv)
            assert all(c.args[3] is profile.return_value for c in capture.call_args_list)
        return status, capture, montage, own

    @captures_on_posix
    def test_every_popup_is_captured_at_every_size_and_a_sheet_made_of_each(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        status, capture, montage, own = self._main(["--out", str(tmp_path)], [])

        assert status == 0
        assert [c.args[0] for c in capture.call_args_list] == list(popup_gallery.SIZES)
        assert all(c.args[1] == list(POPUP_NAMES) for c in capture.call_args_list)
        sheets = [c.args[1].name for c in montage.call_args_list]
        assert sheets == [f"{size}-sheet.png" for size in popup_gallery.SIZES]
        assert own.call_args.args[0] == list(popup_gallery.OWN_WINDOW)
        assert capsys.readouterr().out.rstrip().endswith(f"Done: {tmp_path}")

    @captures_on_posix
    def test_only_and_sizes_narrow_the_run_and_the_own_windows_can_be_left_out(
        self, tmp_path: Path
    ) -> None:
        only = f"{POPUP_NAMES[1]},error-popup"
        argv = ["--out", str(tmp_path), "--only", only, "--sizes", "spread", "--no-own-window"]

        status, capture, _, own = self._main(argv, [])

        assert status == 0
        assert [c.args[:2] for c in capture.call_args_list] == [("spread", [POPUP_NAMES[1]])]
        own.assert_not_called()

    @captures_on_posix
    def test_an_own_window_not_captured_fails_the_run_and_is_named(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        argv = ["--out", str(tmp_path), "--only", "error-popup"]

        status, capture, _, _ = self._main(argv, ["error-popup"])

        assert status == 1
        capture.assert_not_called()
        assert "Done, 1 not captured (error-popup)" in capsys.readouterr().out

    def test_live_steps_through_them_in_the_real_app_instead(self, tmp_path: Path) -> None:
        with patch.object(popup_gallery, "run_live", return_value=0) as live:
            assert popup_gallery.main(["--live", "--out", str(tmp_path / "run")]) == 0

        live.assert_called_once_with(tmp_path / "run")
        assert (tmp_path / "run").is_dir()
