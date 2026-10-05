"""The GUI suite's harness helpers: pure functions, so they run here without an app.

The harness lives beside the GUI tests (``tests/gui/barks_gui``), outside the
unit tree and not installed, so the paths go in by hand the way the GUI
conftest does. ``gui_driver`` is stdlib-only, so nothing here touches Kivy.
"""

# cspell:ignore getloadavg

from __future__ import annotations

import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

_TESTS_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _TESTS_DIR.parents[2]
for _path in (_REPO_ROOT / "scripts", _TESTS_DIR / "gui"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import gui_driver as gd  # noqa: E402
from barks_gui import expected, harness, logs, memory, persisted, shots, timings  # noqa: E402
from barks_reader.core import log_markers as markers  # noqa: E402
from barks_reader.core.memory_census import MemoryCensus  # noqa: E402
from barks_reader.core.wiki_integration import wiki_session_path  # noqa: E402
from okf_reader.core.session import load_session_state  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

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
        for key, value in harness.INI_DEFAULTS.items():
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

    def test_a_smaller_settled_geometry_fails_even_when_the_rest_is_unchanged(
        self, app_boot: harness.AppBoot, log: Path
    ) -> None:
        # The app said where its window settled: at boot, then after a reader close.
        with log.open("a") as out:
            for reason, width, height in (("boot", 782, 1225), ("reader windowed", 566, 900)):
                out.write(
                    markers.WINDOW_GEOMETRY.format(
                        reason=reason, width=width, height=height, left=59, top=10
                    )
                    + "\n"
                )
        app_boot.driver = self._Driver((782, 1225, 59, 10), log)  # ty: ignore[invalid-assignment]
        with pytest.raises(AssertionError, match=r"last settled at \(566, 900\), at boot"):
            app_boot.assert_window_size_kept()

    def test_a_round_trip_with_no_resize_event_at_boot_passes(
        self, app_boot: harness.AppBoot, tmp_path: Path
    ) -> None:
        """Windows: the window is created at its size, so the first resize is the test's own."""
        log = tmp_path / "windows.log"
        log.write_text(
            "\n".join(
                [
                    markers.WINDOW_GEOMETRY.format(
                        reason="boot", width=782, height=1225, left=59, top=10
                    ),
                    markers.WINDOW_RESIZED.format(width=2105, height=1299),
                    markers.WINDOW_RESIZED.format(width=782, height=1225),
                    markers.WINDOW_GEOMETRY.format(
                        reason="MainScreen windowed", width=782, height=1225, left=59, top=10
                    ),
                ]
            )
            + "\n"
        )
        app_boot.driver = self._Driver((782, 1225, 59, 10), log)  # ty: ignore[invalid-assignment]
        app_boot.assert_window_size_kept()

    def test_a_last_resize_off_the_boot_geometry_fails_with_no_boot_resize(
        self, app_boot: harness.AppBoot, tmp_path: Path
    ) -> None:
        log = tmp_path / "windows.log"
        log.write_text(
            markers.WINDOW_GEOMETRY.format(reason="boot", width=782, height=1225, left=59, top=10)
            + "\n"
            + markers.WINDOW_RESIZED.format(width=2105, height=1299)
            + "\n"
            + markers.WINDOW_RESIZED.format(width=566, height=900)
            + "\n"
        )
        app_boot.driver = self._Driver((782, 1225, 59, 10), log)  # ty: ignore[invalid-assignment]
        with pytest.raises(
            AssertionError, match=r"last resize event was \(566, 900\), but it booted"
        ):
            app_boot.assert_window_size_kept()

    def test_a_settled_window_that_only_moved_passes(
        self, app_boot: harness.AppBoot, log: Path
    ) -> None:
        with log.open("a") as out:
            for left in (59, 61):
                out.write(
                    markers.WINDOW_GEOMETRY.format(
                        reason="x", width=782, height=1225, left=left, top=10
                    )
                    + "\n"
                )
        app_boot.driver = self._Driver((782, 1225, 59, 10), log)  # ty: ignore[invalid-assignment]
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


class TestIniOverridesFromEnv:
    def test_parses_pairs_in_order_ignoring_blanks(self) -> None:
        parsed = harness.ini_overrides_from_env(" use_prebuilt_comics=0 ; ;use_png_images = 1;")
        assert parsed == {"use_prebuilt_comics": "0", "use_png_images": "1"}

    def test_empty_is_nothing(self) -> None:
        assert harness.ini_overrides_from_env("") == {}

    @pytest.mark.parametrize("bad", ["use_prebuilt_comics", "=0", "a=b;junk"])
    def test_an_entry_that_is_not_key_value_is_refused(self, bad: str) -> None:
        with pytest.raises(ValueError, match="expected key=value"):
            harness.ini_overrides_from_env(bad)

    def test_a_setting_the_harness_pins_is_refused(self) -> None:
        with pytest.raises(ValueError, match="pinned by the GUI harness"):
            harness.ini_overrides_from_env("confirm_quit=0")

    def test_a_default_the_harness_only_starts_from_is_accepted(self) -> None:
        assert harness.ini_overrides_from_env("double_page_mode=1") == {"double_page_mode": "1"}
        assert "double_page_mode" in harness.INI_DEFAULTS
        assert "double_page_mode" not in harness.INI_OVERRIDES


class TestBuildTemplateRunOverrides:
    def test_run_overrides_go_on_top_of_the_pins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        live = tmp_path / "live"
        live.mkdir()
        (live / "barks-reader.ini").write_text(
            "[Barks Reader]\nuse_prebuilt_comics = 1\nconfirm_quit = 0\n"
        )
        monkeypatch.setenv(harness.INI_ENV_VAR, "use_prebuilt_comics=0")
        (tmp_path / "template").mkdir()

        template = harness.build_template(live, tmp_path / "template")

        ini = template / "barks-reader.ini"
        assert harness.read_ini_value(ini, "use_prebuilt_comics") == "0"
        assert harness.read_ini_value(ini, "confirm_quit") == harness.INI_OVERRIDES["confirm_quit"]

    def test_a_run_override_replaces_a_harness_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        live = tmp_path / "live"
        live.mkdir()
        (live / "barks-reader.ini").write_text("[Barks Reader]\ndouble_page_mode = 0\n")
        monkeypatch.setenv(harness.INI_ENV_VAR, "double_page_mode=1")
        (tmp_path / "template").mkdir()

        template = harness.build_template(live, tmp_path / "template")

        assert harness.read_ini_value(template / "barks-reader.ini", "double_page_mode") == "1"


class TestStrayKeyPresses:
    @staticmethod
    def _pressed(*names: str) -> str:
        codes = {"escape": 27, "down": 274, "enter": 13, "shift": 304, "g": 103}
        return "\n".join(markers.KEY_PRESSED.format(key=codes[n], name=n) for n in names)

    def test_every_press_the_probe_sent_is_accounted_for(self) -> None:
        app = self._pressed("escape", "down", "enter")
        probe = "10:00:00.000 key Escape\n10:00:00.150 key Down\n10:00:00.300 key Return\n"
        assert harness.stray_key_presses(app, probe) == 0

    def test_a_press_the_probe_never_sent_is_stray(self) -> None:
        app = self._pressed("escape", "escape")
        probe = "10:00:00.000 key Escape\n"
        assert harness.stray_key_presses(app, probe) == 1

    def test_typed_text_counts_one_press_per_character_and_shift_is_ignored(self) -> None:
        app = self._pressed("shift", "g", "g")
        probe = "10:00:00.000 type Gg\n"
        assert harness.stray_key_presses(app, probe) == 0

    def test_clicks_and_other_lines_are_not_keys(self) -> None:
        app = self._pressed("down")
        probe = "10:00:00.000 click 10 20\n10:00:00.100 key Down\nnoise\n"
        assert harness.stray_key_presses(app, probe) == 0

    def test_fewer_presses_than_sent_is_not_negative(self) -> None:
        assert harness.stray_key_presses("", "10:00:00.000 key Down\n") == 0


class TestLogProblems:
    STAMP = "2026-09-22 16:47:07.257"

    def _line(self, level: str, message: str) -> str:
        return f"{self.STAMP} | {level:<8} | app : some.module:func:12 - {message}"

    def test_a_clean_log_has_none(self) -> None:
        text = "\n".join(
            [
                self._line("DEBUG", "Screen 'main_screen' entered."),
                self._line("WARNING", "kivy: Factory: Ignored class re-declaration."),
                self._line("INFO", "Showed page 3 in 12ms."),
            ]
        )
        assert harness.log_problems(text) == []

    @pytest.mark.parametrize("level", ["ERROR", "CRITICAL"])
    def test_an_error_level_line_is_a_problem(self, level: str) -> None:
        text = self._line(level, "Could not find monitor for pos (0,0).")
        assert harness.log_problems(text) == [text]

    def test_an_expected_error_is_excused_and_no_other(self) -> None:
        """A test that leaves a volume out expects its error; any other still fails it."""
        expected = self._line("ERROR", 'Cannot show the title "X". The volume 5 is missing.')
        other = self._line("ERROR", "Could not find monitor for pos (0,0).")
        traceback = self._line("DEBUG", "Traceback (most recent call last):")
        text = f"{expected}\n{other}\n{traceback}"
        excused = [r"Cannot show the title .* is missing"]
        assert harness.log_problems(text, excused) == [other, traceback]

    def test_a_traceback_and_an_image_failure_are_problems_at_any_level(self) -> None:
        text = "\n".join(
            [
                self._line("DEBUG", "Traceback (most recent call last):"),
                self._line("WARNING", "kivy: Image: Unable to load image </x/y.png>"),
            ]
        )
        problems = harness.log_problems(text)
        assert [p.split(" - ", 1)[1] for p in problems] == [
            "Traceback (most recent call last):",
            "kivy: Image: Unable to load image </x/y.png>",
        ]

    def test_the_screen_still_showing_is_allowed(self) -> None:
        text = "\n".join(
            [
                self._line("DEBUG", "Screen 'main_screen' entered."),
                self._line("DEBUG", "Screen 'wiki_reader' entered."),
                self._line("DEBUG", "Screen 'main_screen' left."),
                self._line("DEBUG", "Screen 'main_screen' entered."),
                self._line("DEBUG", "Screen 'wiki_reader' left."),
            ]
        )
        assert harness.log_problems(text) == []

    def test_after_a_quit_no_screen_need_be_showing(self) -> None:
        text = "\n".join(
            [
                self._line("DEBUG", "Screen 'main_screen' entered."),
                self._line("DEBUG", "Screen 'main_screen' left."),
            ]
        )
        assert harness.log_problems(text) == []

    def test_two_screens_never_left_is_a_problem(self) -> None:
        text = "\n".join(
            [
                self._line("DEBUG", "Screen 'main_screen' entered."),
                self._line("DEBUG", "Screen 'wiki_reader' entered."),
            ]
        )
        problems = harness.log_problems(text)
        assert problems == ["2 screens entered and never left - only one can be showing"]

    def test_a_screen_left_more_than_entered_is_a_problem(self) -> None:
        text = "\n".join(
            [
                self._line("DEBUG", "Screen 'main_screen' entered."),
                self._line("DEBUG", "Screen 'main_screen' left."),
                self._line("DEBUG", "Screen 'main_screen' left."),
            ]
        )
        assert harness.log_problems(text) == ["screen 'main_screen' entered 1 times, left 2"]

    def test_a_screen_left_but_never_entered_is_a_problem(self) -> None:
        """A screen seen only leaving is counted too, not skipped for never entering."""
        text = "\n".join(
            [
                self._line("DEBUG", "Screen 'main_screen' entered."),
                self._line("DEBUG", "Screen 'wiki_reader' left."),
            ]
        )
        assert harness.log_problems(text) == ["screen 'wiki_reader' entered 0 times, left 1"]


class TestAssertLogClean:
    class _Driver:
        def __init__(self, log_path: Path) -> None:
            self.log_path = log_path

    @pytest.fixture
    def app_boot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> harness.AppBoot:
        app_boot = harness.AppBoot(scratch=tmp_path, nodeid="test_x.py::test_y")
        monkeypatch.setattr(app_boot, "save_failure_artifacts", lambda: [tmp_path / "y.png"])
        return app_boot

    def test_a_clean_log_passes(self, app_boot: harness.AppBoot, tmp_path: Path) -> None:
        log = tmp_path / "app.log"
        log.write_text("2026-09-22 16:47:07.257 | DEBUG    | app : m:f:1 - Screen 'a' entered.\n")
        (tmp_path / "input.log").write_text("")
        app_boot.driver = self._Driver(log)  # ty: ignore[invalid-assignment]
        app_boot.assert_log_clean()

    def test_an_error_line_fails_naming_it_and_the_artifacts(
        self, app_boot: harness.AppBoot, tmp_path: Path
    ) -> None:
        log = tmp_path / "app.log"
        log.write_text("2026-09-22 16:47:07.257 | ERROR    | app : m:f:1 - Boom.\n")
        (tmp_path / "input.log").write_text("")
        app_boot.driver = self._Driver(log)  # ty: ignore[invalid-assignment]
        with pytest.raises(AssertionError, match="Boom") as excinfo:
            app_boot.assert_log_clean()
        assert str(tmp_path / "y.png") in str(excinfo.value)

    def test_a_stray_key_fails_too(self, app_boot: harness.AppBoot, tmp_path: Path) -> None:
        log = tmp_path / "app.log"
        log.write_text(markers.KEY_PRESSED.format(key=27, name="escape") + "\n")
        (tmp_path / "input.log").write_text("")
        app_boot.driver = self._Driver(log)  # ty: ignore[invalid-assignment]
        with pytest.raises(AssertionError, match="STRAY INPUT"):
            app_boot.assert_log_clean()


class TestLogMessages:
    def test_the_location_suffix_is_stripped_from_every_line(self) -> None:
        text = (
            "2026-09-22 16:47:07.257 | INFO     | app : m:f:1 - Last page: requested index = 28."
            "  [barks_reader.ui.comic_book_reader:goto_last_page:186]\n"
            "2026-09-22 16:47:07.258 | DEBUG    | kivy: ImageSDL2: Load <x.png>  [kivy:load:454]\n"
        )
        stripped = logs.messages(text)
        first, second = stripped.splitlines()
        assert first.endswith("requested index = 28.")
        assert second.endswith("ImageSDL2: Load <x.png>")

    def test_a_message_ending_in_brackets_of_its_own_is_kept(self) -> None:
        line = "... - Index item pressed: IndexItem(id='a-1')  [barks_reader.ui.index_screen:_on:1]"
        assert logs.messages(line) == "... - Index item pressed: IndexItem(id='a-1')"


class TestImageExists:
    def test_a_file_on_disk(self, tmp_path: Path) -> None:
        image = tmp_path / "072-5.png"
        image.write_bytes(b"png")
        assert logs.image_exists(image)
        assert not logs.image_exists(tmp_path / "missing.png")

    def test_a_member_logged_as_if_the_zip_were_a_directory(self, tmp_path: Path) -> None:
        archive = tmp_path / "Barks Panels.zip"
        with zipfile.ZipFile(archive, "w") as out:
            out.writestr("Favourites/Knights of the Flying Sleds/072-5.jpg", b"jpg")
        assert logs.image_exists(archive / "Favourites/Knights of the Flying Sleds/072-5.jpg")
        assert not logs.image_exists(archive / "Favourites/Other/072-5.jpg")

    def test_no_zip_on_the_way_is_missing(self, tmp_path: Path) -> None:
        assert not logs.image_exists(tmp_path / "no.zip" / "a.jpg")


class TestExpected:
    """The data-free parts; the rest needs the real corpus, which only a GUI run has."""

    def test_a_titles_member_name_is_a_title_and_a_node_text_is_not(self) -> None:
        assert expected.is_title("GHOST_OF_THE_GROTTO_THE")
        assert not expected.is_title("Main Index")
        assert not expected.is_title("")

    def test_document_pages_are_its_image_files_whatever_their_case(self, tmp_path: Path) -> None:
        pages = ("page-1.jpg", "page-2.PNG", "page-3.jpeg")
        for name in (*pages, "notes.txt", "cover.gif"):
            (tmp_path / name).write_bytes(b"")
        assert expected.document_page_count(tmp_path) == len(pages)


class TestAppDataDir:
    def test_the_env_var_wins(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("BARKS_READER_DATA_DIR", str(tmp_path))
        assert harness.app_data_dir() == tmp_path

    def test_else_env_runtime_with_home_expanded(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("BARKS_READER_DATA_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        (tmp_path / ".env.runtime").write_text('BARKS_READER_DATA_DIR="${HOME}/opt/barks-reader"\n')
        monkeypatch.setattr(harness, "REPO_ROOT", tmp_path)
        assert harness.app_data_dir() == tmp_path / "opt" / "barks-reader"

    def test_nothing_configured_is_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("BARKS_READER_DATA_DIR", raising=False)
        monkeypatch.setattr(harness, "REPO_ROOT", tmp_path)
        assert harness.app_data_dir() is None


class TestBlockLegacyWikiSession:
    """A machine's old wiki session, left in the data dir, never reaches a scratch profile."""

    @staticmethod
    def _dirs(tmp_path: Path, live_bundle: str = "") -> tuple[Path, Path, Path]:
        data, profile = tmp_path / "data", tmp_path / "profile"
        bundle = data / "Reader Files" / "Carl Barks Wiki"
        bundle.mkdir(parents=True)
        profile.mkdir()
        (profile / "barks-reader.ini").write_text(
            f"[Barks Reader]\nwiki_bundle_dir = {live_bundle}\n", encoding="utf-8"
        )
        return data, profile, bundle

    def test_a_leftover_is_blocked_by_an_empty_session(self, tmp_path: Path) -> None:
        data, profile, bundle = self._dirs(tmp_path)
        wiki_session_path(data, bundle).write_text('{"page": "concept/x.md"}', encoding="utf-8")
        with patch.object(harness, "app_data_dir", return_value=data):
            written = harness.block_legacy_wiki_session(profile)
        target = wiki_session_path(profile, bundle)
        assert written == [target]
        # Present to the app (no migration), no session to the viewer (the home page).
        assert target.read_text(encoding="utf-8") == "{}\n"
        assert load_session_state(target, bundle) is None

    def test_the_live_bundle_is_covered_too(self, tmp_path: Path) -> None:
        live = tmp_path / "okf"
        live.mkdir()
        data, profile, _ = self._dirs(tmp_path, str(live))
        wiki_session_path(data, live).write_text('{"page": "index.md"}', encoding="utf-8")
        with patch.object(harness, "app_data_dir", return_value=data):
            assert harness.block_legacy_wiki_session(profile) == [wiki_session_path(profile, live)]

    def test_nothing_is_written_without_a_leftover(self, tmp_path: Path) -> None:
        data, profile, _ = self._dirs(tmp_path)
        with patch.object(harness, "app_data_dir", return_value=data):
            assert harness.block_legacy_wiki_session(profile) == []
        assert list(profile.glob("okf-reader-session-*.json")) == []

    def test_a_session_the_profile_has_is_kept(self, tmp_path: Path) -> None:
        data, profile, bundle = self._dirs(tmp_path)
        wiki_session_path(data, bundle).write_text("{}", encoding="utf-8")
        own = wiki_session_path(profile, bundle)
        own.write_text('{"page": "concept/mine.md"}', encoding="utf-8")
        with patch.object(harness, "app_data_dir", return_value=data):
            assert harness.block_legacy_wiki_session(profile) == []
        assert own.read_text(encoding="utf-8") == '{"page": "concept/mine.md"}'

    def test_no_data_dir_is_nothing_to_do(self, tmp_path: Path) -> None:
        with patch.object(harness, "app_data_dir", return_value=None):
            assert harness.block_legacy_wiki_session(tmp_path) == []


class TestReadsPersisted:
    """The profile against the reads the app logged."""

    TITLE = "The Ghost of the Grotto"

    @pytest.fixture(autouse=True)
    def _no_layout(self) -> Iterator[None]:
        """Judge by the cue unless a test says otherwise: CI has no data pack for layouts."""
        with patch.object(persisted, "_page_is_inside_body", return_value=None):
            yield

    @staticmethod
    def _scratch(
        tmp_path: Path, cue: dict[str, object] | None, events: list[dict[str, object]]
    ) -> Path:
        settings: dict[str, object] = {"AAA_Settings": {"last_selected_node": ["root"]}}
        if cue is not None:
            settings[TestReadsPersisted.TITLE] = {"last_read_page": cue}
        (tmp_path / "barks-reader.json").write_text(json.dumps(settings))
        canned = json.loads((harness.FIXTURES_DIR / "barks-reader-history.json").read_text())
        canned["events"] = [*canned["events"], *events]
        (tmp_path / "barks-reader-history.json").write_text(json.dumps(canned))
        return tmp_path

    def _log(self, *, page: str = "4", index: int = 3, closed: bool = True) -> str:
        lines = [
            markers.HISTORY_OPEN_RECORDED.format(title=self.TITLE),
            markers.SHOWED_PAGE.format(index=0, elapsed="1s"),
            markers.SHOWED_PAGE.format(index=index, elapsed="1s"),
        ]
        if closed:
            lines += [
                markers.LAST_READ_PAGE_SAVED.format(title=self.TITLE, page=page),
                markers.HISTORY_CLOSE_RECORDED.format(title=self.TITLE),
            ]
        return "\n".join(lines) + "\n"

    def _event(self, *, page: str = "4", closed: bool = True) -> dict[str, object]:
        return {
            "id": "ffffffffffffffffffffffffffffffff",
            "title": self.TITLE,
            "opened_at": "2026-09-22T10:00:00",
            "closed_at": "2026-09-22T10:05:00" if closed else None,
            "last_display_page": page if closed else "",
            "last_body_page": "26",
        }

    def _cue(self, *, page: str = "4", index: int = 3) -> dict[str, object]:
        return {
            "page_index": index,
            "display_page_num": page,
            "page_type": "BODY",
            "last_body_page": "26",
        }

    def test_a_read_saved_as_logged_is_clean(self, tmp_path: Path) -> None:
        scratch = self._scratch(tmp_path, self._cue(), [self._event()])
        assert persisted.reads_persisted_problems(scratch, self._log()) == []

    def test_no_reads_and_only_the_canned_history_is_clean(self, tmp_path: Path) -> None:
        scratch = self._scratch(tmp_path, None, [])
        assert persisted.reads_persisted_problems(scratch, "Main screen is active.\n") == []

    def test_a_missing_cue_is_a_problem(self, tmp_path: Path) -> None:
        scratch = self._scratch(tmp_path, None, [self._event()])
        assert persisted.reads_persisted_problems(scratch, self._log()) == [
            f'no last-read cue for "{self.TITLE}", which the app said it saved'
        ]

    def test_a_cue_on_another_page_than_logged_is_a_problem(self, tmp_path: Path) -> None:
        scratch = self._scratch(tmp_path, self._cue(page="9", index=8), [self._event()])
        problems = persisted.reads_persisted_problems(scratch, self._log())
        assert len(problems) == 2, problems  # noqa: PLR2004
        assert "cue page '9', app saved '4'" in problems[0]
        assert "cue page index 8, the reader was last on 3" in problems[1]

    def test_a_page_turned_to_and_still_loading_is_the_one_the_reader_is_on(
        self, tmp_path: Path
    ) -> None:
        """The soak, 2026-10-06: Left to a page not loaded yet, then Close before it came."""
        scratch = self._scratch(tmp_path, self._cue(page="3", index=2), [self._event(page="3")])
        log = self._log(page="3").replace(
            markers.LAST_READ_PAGE_SAVED.format(title=self.TITLE, page="3"),
            markers.PAGE_AWAITING_LOAD.format(index=2)
            + "\n"
            + markers.LAST_READ_PAGE_SAVED.format(title=self.TITLE, page="3"),
        )
        assert persisted.reads_persisted_problems(scratch, log) == []

    def test_the_index_is_not_held_to_the_page_shown_in_double_page_mode(
        self, tmp_path: Path
    ) -> None:
        scratch = self._scratch(tmp_path, self._cue(index=8), [self._event()])
        log = markers.DOUBLE_PAGE_TOGGLED.format(mode=True) + "\n" + self._log()
        assert persisted.reads_persisted_problems(scratch, log) == []

    def test_a_profile_booted_two_up_does_not_hold_the_index_either(self, tmp_path: Path) -> None:
        """The matrix boots with double_page_mode=1; no toggle line is logged then."""
        scratch = self._scratch(tmp_path, self._cue(index=9), [self._event()])
        (scratch / "barks-reader.ini").write_text("[Barks Reader]\ndouble_page_mode = 1\n")
        assert persisted.reads_persisted_problems(scratch, self._log()) == []

    def test_an_open_without_its_event_is_a_problem(self, tmp_path: Path) -> None:
        scratch = self._scratch(tmp_path, self._cue(), [])
        problems = persisted.reads_persisted_problems(scratch, self._log())
        assert any("do not match the opens" in p for p in problems)

    def test_a_close_that_left_no_close_time_is_a_problem(self, tmp_path: Path) -> None:
        scratch = self._scratch(tmp_path, self._cue(), [self._event(closed=False)])
        problems = persisted.reads_persisted_problems(scratch, self._log())
        assert any("has no close time" in p for p in problems)

    def test_a_read_still_open_needs_no_close_time(self, tmp_path: Path) -> None:
        scratch = self._scratch(tmp_path, None, [self._event(closed=False)])
        assert persisted.reads_persisted_problems(scratch, self._log(closed=False)) == []

    def test_a_read_that_ended_on_the_last_body_page_is_recorded_at_the_beginning(
        self, tmp_path: Path
    ) -> None:
        """The cue keeps the page; the history gets the normalised one (the next open restarts)."""
        scratch = self._scratch(tmp_path, self._cue(page="26", index=28), [self._event(page="0")])
        assert persisted.reads_persisted_problems(scratch, self._log(page="26", index=28)) == []

    def _two_reads(self) -> str:
        """Return the log of the title read twice: ending on front matter ("i"), then the body."""
        return self._log(page="i", index=1) + self._log(page="4", index=3)

    def test_each_save_is_judged_by_its_own_page(self, tmp_path: Path) -> None:
        """The layout says "i" is outside the body, whatever the title's last cue says."""
        events = [self._event(page="0"), {**self._event(page="4"), "id": "e" * 32}]
        scratch = self._scratch(tmp_path, self._cue(), events)
        with patch.object(
            persisted, "_page_is_inside_body", side_effect=lambda _t, p, _n: p != "i"
        ):
            assert persisted.reads_persisted_problems(scratch, self._two_reads()) == []

    def test_without_a_layout_the_last_cue_judges_every_save(self, tmp_path: Path) -> None:
        """The limit the layout lifts: the body cue of the second read misjudges the first."""
        events = [self._event(page="0"), {**self._event(page="4"), "id": "e" * 32}]
        scratch = self._scratch(tmp_path, self._cue(), events)
        problems = persisted.reads_persisted_problems(scratch, self._two_reads())
        assert any("are not the pages saved" in p for p in problems)

    def test_an_event_page_other_than_the_one_saved_is_a_problem(self, tmp_path: Path) -> None:
        scratch = self._scratch(tmp_path, self._cue(), [self._event(page="7")])
        problems = persisted.reads_persisted_problems(scratch, self._log())
        assert any("are not the pages saved" in p for p in problems)

    def test_a_read_closed_while_loading_keeps_no_count_from_the_read_before(self) -> None:
        """The soak closed a story before its pages loaded; the count was the last story's."""
        log = "\n".join(
            [
                markers.HISTORY_OPEN_RECORDED.format(title="Rocks to Riches"),
                markers.SHOWED_PAGE.format(index=0, elapsed="1s"),
                markers.COMIC_IMAGES_LOADED.format(count=11, comic="Rocks to Riches.cbz"),
                markers.LAST_READ_PAGE_SAVED.format(title="Rocks to Riches", page="i"),
                markers.HISTORY_OPEN_RECORDED.format(title=self.TITLE),
                markers.LAST_READ_PAGE_SAVED.format(title=self.TITLE, page="i"),
            ]
        )

        assert persisted._saves_logged(log) == [  # noqa: SLF001
            ("Rocks to Riches", "i", 0, 11),
            (self.TITLE, "i", None, None),
        ]


class TestRenderStats:
    """A capture of the nested screen, judged by the app window's part of it alone."""

    WINDOW = (80, 60, 10, 5)  # width, height, left, top on a 100x70 screen

    @staticmethod
    def _capture(tmp_path: Path, paint: Callable[[int, int], tuple[int, int, int]]) -> Path:
        image = Image.new("RGB", (100, 70))
        for y in range(70):
            for x in range(100):
                image.putpixel((x, y), paint(x, y))
        path = tmp_path / "shot.png"
        image.save(path)
        return path

    def test_a_flat_window_is_blank(self, tmp_path: Path) -> None:
        capture = self._capture(tmp_path, lambda _x, _y: (0, 0, 0))
        stats = shots.render_stats(capture, self.WINDOW)
        assert stats.dominant_fraction == 1.0
        assert stats.distinct_colours == 1
        assert shots.looks_blank(stats)

    def test_a_drawn_window_is_not(self, tmp_path: Path) -> None:
        capture = self._capture(tmp_path, lambda x, y: (x * 2 % 256, y * 3 % 256, (x + y) % 256))
        stats = shots.render_stats(capture, self.WINDOW)
        assert stats.dominant_fraction < shots.BLANK_DOMINANT_FRACTION
        assert stats.distinct_colours >= shots.BLANK_MIN_COLOURS
        assert not shots.looks_blank(stats)

    def test_only_the_window_counts(self, tmp_path: Path) -> None:
        """A busy screen around a flat window must not rescue it."""
        width, height, left, top = self.WINDOW

        def paint(x: int, y: int) -> tuple[int, int, int]:
            inside = left <= x < left + width and top <= y < top + height
            return (255, 255, 255) if inside else (x % 256, y % 256, 7)

        stats = shots.render_stats(self._capture(tmp_path, paint), self.WINDOW)
        assert shots.looks_blank(stats)

    def test_samples_cover_the_window_at_the_sample_step(self, tmp_path: Path) -> None:
        capture = self._capture(tmp_path, lambda _x, _y: (1, 2, 3))
        stats = shots.render_stats(capture, self.WINDOW)
        assert stats.samples == (80 // shots.SAMPLE_STEP) * (60 // shots.SAMPLE_STEP)

    @staticmethod
    def _window_capture(tmp_path: Path, paint: Callable[[int, int], tuple[int, int, int]]) -> Path:
        """Save a capture of the window alone, as the Windows probe takes it."""
        image = Image.new("RGB", (80, 60))
        for y in range(60):
            for x in range(80):
                image.putpixel((x, y), paint(x, y))
        path = tmp_path / "window.png"
        image.save(path)
        return path

    def test_a_window_only_capture_is_judged_whole(self, tmp_path: Path) -> None:
        """Not cropped at the window's screen position, which pads it with black."""
        capture = self._window_capture(tmp_path, lambda x, y: (x * 3 % 256, y * 4 % 256, 9))
        stats = shots.render_stats(capture, self.WINDOW)
        assert stats.samples == (80 // shots.SAMPLE_STEP) * (60 // shots.SAMPLE_STEP)
        assert not shots.looks_blank(stats)

    def test_a_flat_window_only_capture_is_still_blank(self, tmp_path: Path) -> None:
        capture = self._window_capture(tmp_path, lambda _x, _y: (0, 0, 0))
        assert shots.looks_blank(shots.render_stats(capture, self.WINDOW))


class TestTimings:
    """The durations the app logs, read back and held to their budgets."""

    def test_elapsed_fields_parse_in_both_forms_the_app_writes(self) -> None:
        assert timings.parse_elapsed("2.4s") == 2.4  # noqa: PLR2004
        assert timings.parse_elapsed("12ms") == 0.012  # noqa: PLR2004
        assert timings.parse_elapsed(" 0.3s ") == 0.3  # noqa: PLR2004
        for bad in ("2.4", "fast", "1m", ""):
            with pytest.raises(ValueError, match="not an elapsed time"):
                timings.parse_elapsed(bad)

    @staticmethod
    def _log() -> str:
        return "\n".join(
            [
                "prefix | " + markers.TREE_NODES_LOADED.format(elapsed="1.2s"),
                "prefix | " + markers.IMAGE_LOADED.format(filename="a.png", elapsed="87ms"),
                "prefix | " + markers.IMAGE_LOADED.format(filename="b.png", elapsed="0.4s"),
                "prefix | " + markers.SHOWED_PAGE.format(index=3, elapsed="0.2s"),
                "prefix | Main screen is active (from comic reader).",
            ]
        )

    def test_a_line_with_the_log_location_after_it_is_still_read(self) -> None:
        """The first calibration pass saw only the two markers whose elapsed is not last."""
        line = (
            "2026-09-23 01:15:19.003 | INFO     | app : "
            + markers.TREE_NODES_LOADED.format(elapsed="2.4s")
            + "  [barks_reader.ui.reader_tree_builder:build_main_screen_tree:127]"
        )
        (found,) = timings.durations(line)
        assert (found.name, found.seconds) == ("tree nodes loaded", 2.4)

    def test_every_timed_line_is_read_with_its_seconds(self) -> None:
        found = timings.durations(self._log())
        assert [(d.name, d.seconds) for d in found] == [
            ("tree nodes loaded", 1.2),
            ("view image loaded", 0.087),
            ("view image loaded", 0.4),
            ("page shown", 0.2),
        ]
        assert found[0].line.endswith("Finished loading all nodes in 1.2s.")

    def test_the_slowest_of_each_kind_is_kept(self) -> None:
        assert timings.slowest(timings.durations(self._log())) == {
            "tree nodes loaded": 1.2,
            "view image loaded": 0.4,
            "page shown": 0.2,
        }

    def test_within_budget_is_no_problem(self) -> None:
        assert timings.budget_problems(self._log(), timings.BUDGETS) == []

    @staticmethod
    def _at(time: str, message: str) -> str:
        return f"2026-10-01 {time} | INFO     | app : {message}  [barks_reader.ui.x:y:1]"

    def _census_log(self) -> str:
        """Return the soak walk's lines on the second PC: a census during a comic's load."""
        census = markers.MEMORY_CENSUS.format(
            request=2, widgets=4109, textures=2941, objects=2337576, rss_mib=1570, took_ms=6659
        )
        return "\n".join(
            [
                self._at("15:50:20.000", markers.SHOWED_PAGE.format(index=3, elapsed="0.9s")),
                self._at("15:50:33.742", census),
                self._at("15:50:33.749", markers.ALL_IMAGES_LOADED.format(elapsed="7.5s", index=0)),
                self._at("15:50:40.000", markers.SHOWED_PAGE.format(index=4, elapsed="0.3s")),
            ]
        )

    def test_a_census_runs_from_its_took_ms_before_its_answer(self) -> None:
        ((start, end),) = timings.census_spans(self._census_log())
        assert (end - start).total_seconds() == 6.659  # noqa: PLR2004

    def test_a_duration_a_census_ran_into_is_left_out(self) -> None:
        found = timings.durations(self._census_log())
        assert [(d.name, d.seconds) for d in found] == [("page shown", 0.9), ("page shown", 0.3)]
        assert timings.budget_problems(self._census_log(), timings.BUDGETS) == []

    def test_a_duration_a_census_did_not_touch_is_still_held_to_its_budget(self) -> None:
        log = (
            self._census_log()
            + "\n"
            + self._at("15:51:00.000", markers.ALL_IMAGES_LOADED.format(elapsed="7.5s", index=0))
        )
        (problem,) = timings.budget_problems(log, timings.BUDGETS)
        assert problem.startswith("comic images loaded took 7.5s, over its 6s budget")

    def test_over_budget_names_the_duration_its_budget_and_the_line(self) -> None:
        slow = self._log() + "\n" + markers.SHOWED_PAGE.format(index=4, elapsed="9.5s")
        (problem,) = timings.budget_problems(slow, {**timings.BUDGETS, "page shown": 2.5})
        assert problem.startswith("page shown took 9.5s, over its 2.5s budget: Showed page 4")

    def test_every_timed_marker_has_a_budget_of_at_least_a_second(self) -> None:
        assert set(timings.TIMED) == set(timings.BUDGETS)
        assert all(budget >= 1.0 for budget in timings.BUDGETS.values())

    def test_the_load_rule_discounts_the_runs_own_workers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Four workers on eight cores must not silence the check on their own."""
        monkeypatch.setattr(timings.os, "cpu_count", lambda: 8)
        monkeypatch.setattr(timings.os, "getloadavg", lambda: (12.0, 0.0, 0.0), raising=False)
        assert timings.machine_is_busy(workers=4) is None  # 8 + 3 * 4 = 20 allowed
        monkeypatch.setattr(timings.os, "getloadavg", lambda: (21.5, 0.0, 0.0), raising=False)
        assert timings.machine_is_busy(workers=4) == (
            "the load average is 22, over the 20 that 8 cores and 4 worker(s) account for"
        )

    def test_the_worker_count_comes_from_the_runner_when_not_given(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(timings.os, "cpu_count", lambda: 8)
        monkeypatch.setattr(timings.os, "getloadavg", lambda: (12.0, 0.0, 0.0), raising=False)
        monkeypatch.delenv(timings.WORKERS_ENV_VAR, raising=False)
        assert timings.machine_is_busy() is not None  # one worker: 11 allowed
        monkeypatch.setenv(timings.WORKERS_ENV_VAR, "4")
        assert timings.machine_is_busy() is None

    def test_a_platform_without_a_load_average_is_never_busy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Windows has no ``os.getloadavg``: the check runs rather than crash."""
        monkeypatch.delattr(timings.os, "getloadavg", raising=False)
        assert timings.machine_is_busy(workers=4) is None

    def test_a_recording_run_folds_to_the_slowest_of_each_kind(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "timings.jsonl"
        timings.record_slowest(jsonl, "a", {"page shown": 0.2, "tree nodes loaded": 0.5})
        timings.record_slowest(jsonl, "b", {"page shown": 0.9})
        timings.record_slowest(jsonl, "c", {})
        assert timings.fold(jsonl) == {"page shown": 0.9, "tree nodes loaded": 0.5}

    def test_a_ranked_fold_takes_that_slowest_test_or_the_fastest_of_fewer(
        self, tmp_path: Path
    ) -> None:
        jsonl = tmp_path / "timings.jsonl"
        for name, seconds in [("a", 0.7), ("b", 2.7), ("c", 0.9), ("d", 1.5)]:
            timings.record_slowest(jsonl, name, {"title inset image set": seconds})
        timings.record_slowest(jsonl, "e", {"page shown": 0.4})
        assert timings.fold(jsonl, 3) == {"title inset image set": 0.9, "page shown": 0.4}

    def test_a_baseline_round_trips_with_its_date_host_and_workers(self, tmp_path: Path) -> None:
        path = tmp_path / ".benchmarks" / "gui-timings.json"
        written = timings.write_baseline(path, {"page shown": 0.9}, workers=4)
        assert timings.read_baseline(path) == written
        assert written.workers == 4  # noqa: PLR2004
        assert written.slowest == {"page shown": 0.9}
        assert len(written.calibrated) == len("2026-09-23")

    def test_no_baseline_or_a_broken_one_reads_as_none(self, tmp_path: Path) -> None:
        assert timings.read_baseline(tmp_path / "missing.json") is None
        (tmp_path / "broken.json").write_text("{not json")
        assert timings.read_baseline(tmp_path / "broken.json") is None
        (tmp_path / "partial.json").write_text('{"calibrated": "x"}')
        assert timings.read_baseline(tmp_path / "partial.json") is None

    def test_budgets_come_from_the_baseline_when_there_is_one(self, tmp_path: Path) -> None:
        """Three times the slowest seen, never under a second; unseen kinds stay committed."""
        path = tmp_path / "gui-timings.json"
        seen = {"page shown": 0.9, "index built": 0.01, "volumes loaded": 0.2}
        timings.write_baseline(path, seen, workers=1)
        in_force, source = timings.budgets(path)
        assert in_force["page shown"] == pytest.approx(2.7)
        assert in_force["index built"] == 1.0
        assert in_force["volumes loaded"] == timings.MIN_BUDGETS["volumes loaded"]  # cold cache
        assert in_force["view image loaded"] == timings.BUDGETS["view image loaded"]
        assert source.startswith("budgets calibrated on ")
        assert str(path) in source

    def test_budgets_are_the_committed_ones_without_a_baseline(self, tmp_path: Path) -> None:
        in_force, source = timings.budgets(tmp_path / "none.json")
        assert in_force == timings.BUDGETS
        assert source == "the committed budgets"

    def test_calibrate_writes_the_baseline_and_prints_every_kind(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        jsonl = tmp_path / "timings.jsonl"
        timings.record_slowest(jsonl, "a", {"page shown": 0.9})
        monkeypatch.setattr(timings, "BASELINE_FILE", tmp_path / "gui-timings.json")
        assert timings.main(["calibrate", str(jsonl), "4"]) == 0
        out = capsys.readouterr().out
        assert "page shown" in out
        assert "0.9s seen" in out
        assert "not seen, committed budget" in out
        assert timings.read_baseline(tmp_path / "gui-timings.json") is not None
        assert timings.main(["nonsense"]) == 2  # noqa: PLR2004

    def test_drift_is_a_factor_past_the_calibration_and_not_a_mere_tenth(self) -> None:
        calibrated = {"page shown": 0.9, "index built": 0.01, "tree nodes loaded": 0.5}
        seen = {
            "page shown": 1.4,
            "index built": 0.05,
            "tree nodes loaded": 0.7,
            "post tree setup": 9,
        }
        (problem,) = timings.drifted(seen, calibrated)  # only page shown: 1.56x and 0.5s more
        assert problem == "page shown: 1.4s, calibrated 0.9s (1.6x)"
        assert timings.drifted(calibrated, calibrated) == []

    def test_drift_compares_a_recording_with_the_calibration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        baseline = tmp_path / "gui-timings.json"
        monkeypatch.setattr(timings, "BASELINE_FILE", baseline)
        jsonl = tmp_path / "timings.jsonl"
        timings.record_slowest(jsonl, "a", {"page shown": 0.9})

        assert timings.main(["drift", str(jsonl)]) == 0  # no calibration: nothing to compare
        assert "no calibration" in capsys.readouterr().out

        timings.write_baseline(baseline, {"page shown": 0.9}, workers=4)
        assert timings.main(["drift", str(jsonl)]) == 0
        assert "no drift" in capsys.readouterr().out

        # One stalled worker's sample is the slowest, not a drift.
        timings.record_slowest(jsonl, "b", {"page shown": 2.7})
        timings.record_slowest(jsonl, "c", {"page shown": 0.8})
        assert timings.main(["drift", str(jsonl)]) == 0
        assert "no drift" in capsys.readouterr().out

        # Every test slower is.
        for name in ("a", "b", "c"):
            timings.record_slowest(jsonl, name, {"page shown": 2.0})
        assert timings.main(["drift", str(jsonl)]) == 1
        assert "page shown: 2s, calibrated 0.9s (2.2x)" in capsys.readouterr().out

        assert timings.main(["drift", str(tmp_path / "missing.jsonl")]) == 2  # noqa: PLR2004

    def test_slowest_durations_are_appended_as_json_lines(self, tmp_path: Path) -> None:
        out = tmp_path / "timings.jsonl"
        timings.record_slowest(out, "test_a", {"page shown": 0.2})
        timings.record_slowest(out, "test_b", {})
        lines = [json.loads(ln) for ln in out.read_text().splitlines()]
        assert lines == [
            {"test": "test_a", "slowest": {"page shown": 0.2}},
            {"test": "test_b", "slowest": {}},
        ]


class TestKeepArtifactsIfAsked:
    """--keep-logs saves a passing test's artifacts as a failure's; off, nothing is saved."""

    @pytest.fixture
    def app_boot(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> harness.AppBoot:
        app_boot = harness.AppBoot(scratch=tmp_path, nodeid="test_x.py::test_y")
        monkeypatch.setattr(app_boot, "save_failure_artifacts", lambda: [tmp_path / "test_y.log"])
        return app_boot

    def test_on_it_saves_them(
        self, app_boot: harness.AppBoot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(harness.KEEP_LOGS_ENV_VAR, "1")
        assert app_boot.keep_artifacts_if_asked() == [tmp_path / "test_y.log"]

    @pytest.mark.parametrize("value", [None, "", "0"])
    def test_off_it_saves_nothing(
        self, app_boot: harness.AppBoot, monkeypatch: pytest.MonkeyPatch, value: str | None
    ) -> None:
        if value is None:
            monkeypatch.delenv(harness.KEEP_LOGS_ENV_VAR, raising=False)
        else:
            monkeypatch.setenv(harness.KEEP_LOGS_ENV_VAR, value)
        assert app_boot.keep_artifacts_if_asked() == []


class TestLiveProfileGuardMessage:
    """A live profile changed by a hand-started reader says so, not blames the tests."""

    SINCE = datetime(2026, 9, 27, 16, 36, 58)  # noqa: DTZ001 - the app logs local time

    @staticmethod
    def _live_dir(tmp_path: Path, *starts: str) -> Path:
        log = tmp_path / harness.APP_LOG_IN_CONFIG
        log.parent.mkdir(parents=True)
        log.write_text(
            "".join(
                f"{start}.220 | INFO     | app : __main__:start_logging:109"
                f" - {markers.APP_STARTING}\n{start}.221 | INFO     | app : x - app dir = x.\n"
                for start in starts
            )
        )
        return tmp_path

    def test_runs_started_during_the_session_are_named(self, tmp_path: Path) -> None:
        live = self._live_dir(tmp_path, "2026-09-26 19:58:10", "2026-09-27 16:55:11")
        assert harness.live_runs_since(live / harness.APP_LOG_IN_CONFIG, self.SINCE) == [
            "2026-09-27 16:55:11"
        ]
        message = harness.live_profile_changed_message(["barks-reader.json"], live, self.SINCE)
        assert message.startswith("the GUI tests changed the live profile: ['barks-reader.json']")
        assert (
            "reader was started with the live profile, outside the tests, at 2026-09-27 16:55:11"
            in message
        )

    def test_with_no_such_run_the_message_blames_the_tests_alone(self, tmp_path: Path) -> None:
        live = self._live_dir(tmp_path, "2026-09-26 19:58:10")
        message = harness.live_profile_changed_message(["barks-reader.json"], live, self.SINCE)
        assert "outside the tests" not in message

    def test_no_log_is_no_runs(self, tmp_path: Path) -> None:
        assert harness.live_runs_since(tmp_path / "missing.log", self.SINCE) == []


def _census(widgets: int, textures: int) -> MemoryCensus:
    return MemoryCensus(widgets=widgets, textures=textures, objects=0, rss_mib=0, took_ms=0)


class TestMemoryGrowth:
    """The leak tests' rule: after the warm-up, rounds may add only the slack."""

    def test_within_the_slack_is_no_problem(self) -> None:
        first = _census(900, 800)
        last = _census(900 + memory.WIDGET_SLACK, 800 + memory.TEXTURE_SLACK)
        assert memory.growth_problems(first, last) == []

    def test_fewer_is_no_problem(self) -> None:
        assert memory.growth_problems(_census(900, 800), _census(850, 700)) == []

    def test_past_the_slack_names_each_count(self) -> None:
        first = _census(900, 800)
        last = _census(901 + memory.WIDGET_SLACK, 801 + memory.TEXTURE_SLACK)
        problems = memory.growth_problems(first, last)
        assert [p.split(":")[0] for p in problems] == ["widgets", "textures"]
        assert problems[0] == (
            f"widgets: 900 after the warm-up, {901 + memory.WIDGET_SLACK} after the last round"
        )


class TestLayoutOfAnotherLength:
    """A prebuilt collection can hold fewer pages than its data lists; its layout cannot judge."""

    @pytest.fixture
    def layout(self) -> Iterator[MagicMock]:
        """Stand in a 133-page layout (the collection's data) that calls every page body."""
        stand_in = MagicMock()
        stand_in.page_map = {str(n): n for n in range(133)}
        stand_in.is_inside_body.return_value = True
        with patch.object(persisted, "_layout", return_value=stand_in):
            yield stand_in

    def test_a_layout_of_the_loaded_length_judges(self, layout: MagicMock) -> None:
        assert persisted._page_is_inside_body("All One-Pagers", "43", 133) is True  # noqa: SLF001
        layout.is_inside_body.assert_called_once()

    def test_a_layout_of_another_length_cannot_say(self, layout: MagicMock) -> None:
        """The 43-page prebuilt comic's page 43 is its last: the 133-page layout must not judge."""
        assert persisted._page_is_inside_body("All One-Pagers", "43", 43) is None  # noqa: SLF001
        layout.is_inside_body.assert_not_called()

    @pytest.mark.usefixtures("layout")
    def test_with_no_load_logged_the_layout_judges(self) -> None:
        assert persisted._page_is_inside_body("All One-Pagers", "43", None) is True  # noqa: SLF001

    @pytest.mark.usefixtures("layout")
    def test_the_soaks_read_passes(self, tmp_path: Path) -> None:
        """The overnight soak's read: the last page of the 43-page comic, recorded at the start."""
        title = "All One-Pagers"
        cue = {
            "display_page_num": "43",
            "page_index": 42,
            "page_type": "BODY",
            "last_body_page": "43",
        }
        settings = {"AAA_Settings": {}, title: {"last_read_page": cue}}
        (tmp_path / "barks-reader.json").write_text(json.dumps(settings))
        canned = json.loads((harness.FIXTURES_DIR / "barks-reader-history.json").read_text())
        event = {"id": "f" * 32, "title": title, "last_display_page": "0", "closed_at": "x"}
        canned["events"] = [*canned["events"], event]
        (tmp_path / "barks-reader-history.json").write_text(json.dumps(canned))
        log = "\n".join(
            [
                markers.HISTORY_OPEN_RECORDED.format(title=title),
                markers.COMIC_IMAGES_LOADED.format(count=43, comic="459 All One-Pagers.cbz"),
                markers.SHOWED_PAGE.format(index=42, elapsed=17),
                markers.LAST_READ_PAGE_SAVED.format(title=title, page="43"),
                markers.HISTORY_CLOSE_RECORDED.format(title=title),
            ]
        )
        assert persisted.reads_persisted_problems(tmp_path, log) == []


def _placed_line(stamp: str, x: int, width: int = 1280, win_width: int = 2560) -> str:
    """Return a PAGE_PLACED line as the app's log writes it, at `stamp` (HH:MM:SS.mmm)."""
    message = markers.PAGE_PLACED.format(
        width=width, height=1440, x=x, y=0, win_width=win_width, win_height=1440
    )
    return f"2026-10-02 {stamp} | DEBUG    | app : barks_reader.core.page_placement - {message}"


def _reader_line(stamp: str, *, entered: bool = True) -> str:
    """Return the line the reader's screen logs as it comes to rest on show, or leaves."""
    marker = markers.SCREEN_ENTERED if entered else markers.SCREEN_LEFT
    message = marker.format(name="comic_book_reader")
    return f"2026-10-02 {stamp} | DEBUG    | app : barks_reader.ui.reader_screens - {message}"


def _on_screen(*lines: str) -> str:
    """Return `lines` as a log in which the reader's screen came on show first."""
    return "\n".join([_reader_line("12:00:00.000"), *lines])


def _census_line(stamp: str, took_ms: int) -> str:
    """Return the line the app logs as it answers a memory census, at `stamp`."""
    message = markers.MEMORY_CENSUS.format(
        request=2, widgets=1988, textures=1483, objects=1256598, rss_mib=685, took_ms=took_ms
    )
    return f"2026-10-02 {stamp} | DEBUG    | app : barks_reader.ui.memory_census - {message}"


class TestPagePlacement:
    def test_a_placement_line_is_read_back_with_its_time(self) -> None:
        (placed,) = harness.page_placements(_placed_line("13:43:30.131", x=640))
        assert (placed.x, placed.width, placed.win_width) == (640, 1280, 2560)
        assert placed.at == datetime(2026, 10, 2, 13, 43, 30, 131000)  # noqa: DTZ001
        assert placed.off_centre == 0

    def test_a_spread_left_past_the_middle_is_off_centre(self) -> None:
        """The layout seen on the macOS guest: the spread's left edge past half way."""
        problems = harness.off_centre_pages(_on_screen(_placed_line("13:43:30.131", x=1400)))
        assert len(problems) == 1
        assert "+760px" in problems[0]

    def test_a_centred_page_and_a_pixel_of_rounding_pass(self) -> None:
        log = _on_screen(_placed_line("13:00:00.000", x=640), _placed_line("13:00:05.000", x=641))
        assert harness.off_centre_pages(log) == []

    def test_a_frame_on_the_way_through_a_resize_is_not_judged(self) -> None:
        """Replaced within the settle time it never stood on screen."""
        log = _on_screen(_placed_line("13:00:00.000", x=1400), _placed_line("13:00:00.300", x=640))
        assert harness.off_centre_pages(log) == []

    def test_a_frame_a_census_held_up_is_not_judged(self) -> None:
        """A frame stood longer only while the test's own census held the app.

        The macOS soak, 2026-10-05: a closing reader's fullscreen-sized frame stood
        1.045s, 952ms of it while the app answered the census.
        """
        log = _on_screen(
            _placed_line("21:15:17.543", x=804, width=954, win_width=838),
            _census_line("21:15:18.576", took_ms=952),
            _placed_line("21:15:18.588", x=0, width=838, win_width=838),
        )
        assert harness.off_centre_pages(log) == []

    def test_a_placement_that_stood_beyond_a_census_is_judged(self) -> None:
        log = _on_screen(
            _placed_line("13:00:00.000", x=1400),
            _census_line("13:00:01.000", took_ms=300),
            _placed_line("13:00:01.500", x=640),
        )
        assert len(harness.off_centre_pages(log)) == 1

    def test_a_census_is_read_back_as_the_span_it_held_the_app(self) -> None:
        ((start, end),) = harness.census_holds(_census_line("21:15:18.576", took_ms=952))
        assert end == datetime(2026, 10, 2, 21, 15, 18, 576000)  # noqa: DTZ001
        assert (end - start).total_seconds() == pytest.approx(0.952)

    def test_a_placement_that_stood_is_judged_though_a_later_one_is_fine(self) -> None:
        log = _on_screen(_placed_line("13:00:00.000", x=1400), _placed_line("13:00:04.000", x=640))
        assert len(harness.off_centre_pages(log)) == 1

    def test_the_last_placement_stands_while_the_reader_is_on_show(self) -> None:
        log = _on_screen(_placed_line("13:00:00.000", x=640), _placed_line("13:00:00.200", x=-300))
        problems = harness.off_centre_pages(log)
        assert len(problems) == 1
        assert "x=-300" in problems[0]

    def test_a_windowed_page_is_judged_against_its_own_window(self) -> None:
        line = _placed_line("13:00:00.000", x=0, width=838, win_width=838)
        assert harness.off_centre_pages(_on_screen(line)) == []

    def test_a_placement_as_the_reader_slides_in_is_not_judged(self) -> None:
        """The screen moves, not the page: measured mid-transition, then afresh at rest."""
        log = "\n".join(
            [
                _placed_line("19:24:06.608", x=501, width=924),
                _reader_line("19:24:06.780"),
                _placed_line("19:24:06.800", x=818, width=924),
            ]
        )
        assert harness.off_centre_pages(log) == []

    def test_a_placement_after_the_reader_left_is_not_judged(self) -> None:
        """A closing reader laid out in a window that went fullscreen as it left."""
        log = _on_screen(
            _placed_line("19:17:00.000", x=0, width=838, win_width=838),
            _reader_line("19:17:02.500", entered=False),
            _placed_line("19:17:03.158", x=0, width=838),
        )
        assert harness.off_centre_pages(log) == []

    def test_a_placement_the_reader_left_soon_after_is_not_judged(self) -> None:
        log = _on_screen(
            _placed_line("13:00:00.000", x=1400), _reader_line("13:00:00.400", entered=False)
        )
        assert harness.off_centre_pages(log) == []

    def test_a_placement_that_stood_until_the_reader_left_is_judged(self) -> None:
        log = _on_screen(
            _placed_line("13:00:00.000", x=1400), _reader_line("13:00:05.000", entered=False)
        )
        assert len(harness.off_centre_pages(log)) == 1

    def test_the_reader_on_show_is_read_from_its_screen_lines(self) -> None:
        log = "\n".join(
            [
                _reader_line("13:00:00.000"),
                _reader_line("13:00:05.000", entered=False),
                _reader_line("13:00:09.000"),
            ]
        )
        (first, second) = harness.reader_on_screen(log)
        assert first[1] is not None
        assert second[1] is None
