"""scripts/popup_gallery.py: the scratch profile, the requests, the window finder, the sheet."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

import popup_gallery
import pytest
from barks_reader.core.popup_gallery import POPUP_NAMES, parse_request
from gui_driver import CONFIG_DIR_ENV_VAR

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
