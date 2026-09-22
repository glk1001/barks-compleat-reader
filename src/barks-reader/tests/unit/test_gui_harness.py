"""The GUI suite's harness helpers: pure functions, so they run here without an app.

The harness lives beside the GUI tests (``tests/gui/barks_gui``), outside the
unit tree and not installed, so the paths go in by hand the way the GUI
conftest does. ``gui_driver`` is stdlib-only, so nothing here touches Kivy.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

_TESTS_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _TESTS_DIR.parents[2]
for _path in (_REPO_ROOT / "scripts", _TESTS_DIR / "gui"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import gui_driver as gd  # noqa: E402
from barks_gui import harness  # noqa: E402
from barks_reader.core import log_markers as markers  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Iterator

LIVE_INI = """[Barks Reader]
confirm_quit = 0
Fanta_Dir = /library
goto_fullscreen_on_app_start = 1

[kivy]
log_level = info
"""


class TestDisplayForWorker:
    @pytest.mark.parametrize(
        ("worker", "base", "want"),
        [
            ("master", ":2", ":2"),
            ("gw0", ":2", ":2"),
            ("gw3", ":2", ":5"),
            ("gw1", ":7", ":8"),
            ("gw1", ":", ":3"),  # a bare colon falls back to the probe's default base
            ("gwX", ":2", ":2"),  # not a numbered worker
        ],
    )
    def test_each_worker_gets_its_own_display(self, worker: str, base: str, want: str) -> None:
        assert harness.display_for_worker(worker, base) == want


class TestArtifactName:
    def test_drops_the_module_path_and_makes_the_rest_a_file_name(self) -> None:
        nodeid = "src/barks-reader/tests/gui/test_x.py::test_a[b c/d]"
        assert harness.artifact_name(nodeid, ".png") == "test_a_b_c_d_.png"

    def test_keeps_a_class_in_the_name(self) -> None:
        assert harness.artifact_name("t.py::TestK::test_a", "-tail.log") == "TestK_test_a-tail.log"


class TestIniOverrides:
    @pytest.fixture
    def ini(self, tmp_path: Path) -> Path:
        path = tmp_path / "barks-reader.ini"
        path.write_text(LIVE_INI)
        return path

    def test_sets_the_keys_and_keeps_everything_else(self, ini: Path) -> None:
        harness.apply_ini_overrides(ini, {"confirm_quit": "1", "log_level": "DEBUG"})
        assert harness.read_ini_value(ini, "confirm_quit") == "1"
        assert harness.read_ini_value(ini, "log_level") == "DEBUG"  # added to the section
        assert harness.read_ini_value(ini, "goto_fullscreen_on_app_start") == "1"
        text = ini.read_text()
        assert "Fanta_Dir = /library" in text, "key case must survive, as the app writes it"
        assert "[kivy]\nlog_level = info" in text, "other sections are untouched"

    def test_creates_the_section_when_the_ini_has_none(self, tmp_path: Path) -> None:
        ini = tmp_path / "barks-reader.ini"
        ini.write_text("[kivy]\nlog_level = info\n")
        harness.apply_ini_overrides(ini, {"confirm_quit": "1"})
        assert harness.read_ini_value(ini, "confirm_quit") == "1"


class TestBuildTemplate:
    @pytest.fixture
    def live(self, tmp_path: Path) -> Path:
        live = tmp_path / "live"
        (live / "kivy" / "logs").mkdir(parents=True)
        (live / "barks-reader.ini").write_text(LIVE_INI)
        (live / "log-config.yaml").write_text("sinks: []\n")
        (live / "barks-reader.json").write_text("{}")  # the live json is never copied
        (live / "kivy" / "config.ini").write_text("[graphics]\nposition = custom\n")
        (live / "kivy" / "logs" / "kivy_1.txt").write_text("old log")
        return live

    def test_copies_the_profile_with_the_overrides_pinned(self, live: Path, tmp_path: Path) -> None:
        (tmp_path / "template").mkdir()  # the caller hands over an empty directory
        template = harness.build_template(live, tmp_path / "template")
        assert (template / "log-config.yaml").read_text() == "sinks: []\n"
        assert (template / "kivy" / "config.ini").is_file()
        assert not (template / "kivy" / "logs").exists(), "Kivy's logs are not part of a profile"
        assert not (template / "barks-reader.json").exists()
        assert harness.read_ini_value(template / "barks-reader.ini", "confirm_quit") == "1"
        assert harness.read_ini_value(template / "barks-reader.ini", "Fanta_Dir") == "/library"
        for key, value in harness.INI_OVERRIDES.items():
            assert harness.read_ini_value(template / "barks-reader.ini", key) == value

    def test_refuses_a_profile_with_no_ini(self, tmp_path: Path) -> None:
        live = tmp_path / "live"
        live.mkdir()
        (tmp_path / "template").mkdir()
        with pytest.raises(FileNotFoundError, match=r"no barks-reader\.ini"):
            harness.build_template(live, tmp_path / "template")


class TestArtifactsDir:
    @pytest.fixture(autouse=True)
    def _fresh_run(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
        monkeypatch.setattr(harness, "ARTIFACTS_ROOT", tmp_path / "gui-tests")
        monkeypatch.setattr(harness._RUN, "dir", None)  # noqa: SLF001
        yield
        monkeypatch.setattr(harness._RUN, "dir", None)  # noqa: SLF001

    def test_uses_the_runner_stamp_so_workers_share_one_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(harness.RUN_STAMP_ENV_VAR, "20260921-120000")
        out = harness.artifacts_dir()
        assert out == tmp_path / "gui-tests" / "20260921-120000"
        assert out.is_dir()
        assert harness.artifacts_dir() == out, "made once, then reused"

    def test_stamps_itself_when_run_outside_the_runner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(harness.RUN_STAMP_ENV_VAR, raising=False)
        out = harness.artifacts_dir()
        assert out.parent == tmp_path / "gui-tests"
        assert out.is_dir()


class TestAssertWindowSizeKept:
    """The teardown check: same size passes, a changed size fails with artifacts saved."""

    class _Driver:
        def __init__(
            self,
            geometry: tuple[int, int, int, int],
            log_path: Path,
            *,
            gone: bool = False,
        ) -> None:
            self.geometry = geometry
            self.log_path = log_path
            self.gone = gone

        def settle(self) -> None:
            pass

        def window_geometry(self) -> tuple[int, int, int, int]:
            if self.gone:
                msg = "app window not found"
                raise gd.DriverError(msg)
            return self.geometry

    @pytest.fixture
    def log(self, tmp_path: Path) -> Path:
        """Write an app log whose resize events go out to fullscreen and back."""
        lines = [
            markers.WINDOW_RESIZED.format(width=782, height=1225) + " Window.fullscreen = False,",
            "Entered fullscreen mode on MainScreen.",
            markers.WINDOW_RESIZED.format(width=900, height=1300) + " Window.fullscreen = auto,",
            markers.WINDOW_RESIZED.format(width=782, height=1225) + " Window.fullscreen = False,",
        ]
        path = tmp_path / "app.log"
        path.write_text("\n".join(lines) + "\n")
        return path

    @pytest.fixture
    def app_boot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> harness.AppBoot:
        app_boot = harness.AppBoot(scratch=tmp_path, nodeid="test_x.py::test_y")
        app_boot.boot_geometry = (782, 1225, 59, 10)
        monkeypatch.setattr(app_boot, "save_failure_artifacts", lambda: [tmp_path / "test_y.png"])
        return app_boot

    def test_same_size_passes(self, app_boot: harness.AppBoot, log: Path) -> None:
        app_boot.driver = self._Driver((782, 1225, 59, 10), log)  # ty: ignore[invalid-assignment]
        app_boot.assert_window_size_kept()

    def test_a_moved_window_still_passes(self, app_boot: harness.AppBoot, log: Path) -> None:
        app_boot.driver = self._Driver((782, 1225, 0, 0), log)  # ty: ignore[invalid-assignment]
        app_boot.assert_window_size_kept()

    def test_a_smaller_x_window_fails_naming_both_sizes_and_the_artifacts(
        self, app_boot: harness.AppBoot, log: Path, tmp_path: Path
    ) -> None:
        app_boot.driver = self._Driver((566, 900, 59, 10), log)  # ty: ignore[invalid-assignment]
        with pytest.raises(AssertionError, match=r"\(566, 900\).*\(782, 1225\)") as excinfo:
            app_boot.assert_window_size_kept()
        assert str(tmp_path / "test_y.png") in str(excinfo.value)

    def test_a_smaller_last_resize_event_fails_even_when_the_x_window_is_unchanged(
        self, app_boot: harness.AppBoot, log: Path
    ) -> None:
        with log.open("a") as out:
            out.write(markers.WINDOW_RESIZED.format(width=566, height=900) + "\n")
        app_boot.driver = self._Driver((782, 1225, 59, 10), log)  # ty: ignore[invalid-assignment]
        with pytest.raises(AssertionError, match=r"last resize event was \(566, 900\)"):
            app_boot.assert_window_size_kept()

    def test_a_log_with_no_resize_events_checks_only_the_x_window(
        self, app_boot: harness.AppBoot, tmp_path: Path
    ) -> None:
        empty = tmp_path / "empty.log"
        empty.write_text("Main screen is active (from start).\n")
        app_boot.driver = self._Driver((782, 1225, 59, 10), empty)  # ty: ignore[invalid-assignment]
        app_boot.assert_window_size_kept()

    def test_a_window_the_probe_cannot_find_is_not_a_failure(
        self, app_boot: harness.AppBoot, log: Path
    ) -> None:
        app_boot.driver = self._Driver((0, 0, 0, 0), log, gone=True)  # ty: ignore[invalid-assignment]
        app_boot.assert_window_size_kept()

    def test_without_a_boot_there_is_nothing_to_check(self, app_boot: harness.AppBoot) -> None:
        app_boot.driver = None
        app_boot.assert_window_size_kept()


class TestResizeEvents:
    def test_reads_every_size_in_order(self) -> None:
        text = "\n".join(
            [
                markers.WINDOW_RESIZED.format(width=782, height=1225)
                + " Window.fullscreen = False,",
                "Some other line.",
                markers.WINDOW_RESIZED.format(width=900, height=1300) + " guard = None,",
            ]
        )
        assert harness.resize_events(text) == [(782, 1225), (900, 1300)]

    def test_nothing_logged_is_an_empty_list(self) -> None:
        assert harness.resize_events("Main screen is active (from start).") == []
