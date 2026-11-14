"""The installer's progress window: its count, its loop, and what it does without one."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import kivy.base
import kivy.clock
import kivy.core.window
import pytest
from barks_reader import installer_progress
from barks_reader.core import boot_splash, reader_utils, screen_metrics
from barks_reader.installer_progress import (
    ByteProgress,
    fit_window_to_screen,
    percent_text,
    place_window,
    run_showing_progress,
)
from barks_reader.ui.popup_frame import PopupFrame
from kivy.animation import Animation
from kivy.config import Config
from kivy.core.window import Window
from kivy.uix.progressbar import ProgressBar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

_SIZE = (800, 950)
_TOTAL = 200


class TestByteProgress:
    def test_it_is_the_share_written(self) -> None:
        progress = ByteProgress(_TOTAL)
        assert progress.fraction == 0.0
        progress.add(50)
        assert progress.fraction == pytest.approx(0.25)

    def test_more_written_than_promised_is_still_the_whole(self) -> None:
        progress = ByteProgress(_TOTAL)
        progress.add(_TOTAL + 1)
        assert progress.fraction == 1.0

    def test_nothing_to_write_is_no_progress_and_no_division(self) -> None:
        progress = ByteProgress(0)
        progress.add(10)
        assert progress.fraction == 0.0


@pytest.mark.parametrize(("fraction", "text"), [(0.0, "0%"), (0.229, "22%"), (1.0, "100%")])
def test_the_caption_is_a_whole_percentage(fraction: float, text: str) -> None:
    assert percent_text(fraction) == text


@pytest.fixture
def screen(monkeypatch: pytest.MonkeyPatch) -> Callable[[int, int], None]:
    """Make the primary screen a given size, with a 55-pixel taskbar allowance."""

    def set_size(width: int, height: int) -> None:
        info = MagicMock(width_pixels=width, height_pixels=height)
        monkeypatch.setattr(screen_metrics.SCREEN_METRICS, "get_primary_screen_info", lambda: info)
        monkeypatch.setattr(screen_metrics, "get_approximate_taskbar_height", lambda: 55)

    return set_size


class TestFitWindowToScreen:
    def test_a_window_the_screen_has_room_for_keeps_its_size(
        self, screen: Callable[[int, int], None]
    ) -> None:
        screen(1920, 1080)
        assert fit_window_to_screen(_SIZE) == _SIZE

    def test_a_window_taller_than_a_laptop_screen_is_cut_to_clear_a_bar_at_either_edge(
        self, screen: Callable[[int, int], None]
    ) -> None:
        screen(1366, 768)
        assert fit_window_to_screen(_SIZE) == (800, 768 - 2 * 55)

    def test_a_window_wider_than_the_screen_is_cut_to_its_width(
        self, screen: Callable[[int, int], None]
    ) -> None:
        screen(640, 1080)
        assert fit_window_to_screen(_SIZE) == (640, 950)

    def test_a_window_exactly_the_room_there_is_keeps_its_size(
        self, screen: Callable[[int, int], None]
    ) -> None:
        screen(800, 950 + 2 * 55)
        assert fit_window_to_screen(_SIZE) == _SIZE


class TestPlaceWindow:
    @pytest.fixture
    def config_set(self) -> Iterator[MagicMock]:
        """Kivy's Config is the process's: a test must not leave a window size in it."""
        with patch.object(Config, "set") as config_set:
            yield config_set

    @staticmethod
    def _graphics(config_set: MagicMock) -> dict[str, object]:
        assert {call.args[0] for call in config_set.call_args_list} == {"graphics"}
        return {call.args[1]: call.args[2] for call in config_set.call_args_list}

    def test_the_window_is_centred_at_the_size_the_screen_has_room_for(
        self, screen: Callable[[int, int], None], config_set: MagicMock
    ) -> None:
        screen(1366, 768)
        with patch.object(
            reader_utils, "get_centred_position_on_primary_monitor", return_value=(283, 55)
        ) as centred:
            size = place_window(_SIZE)

        assert size == (800, 658)
        centred.assert_called_once_with(800, 658)  # the fitted size, so its top is on screen
        assert self._graphics(config_set) == {"left": 283, "top": 55, "width": 800, "height": 658}

    def test_a_window_with_no_frame_of_the_desktops_says_so(
        self, screen: Callable[[int, int], None], config_set: MagicMock
    ) -> None:
        screen(1920, 1080)
        with patch.object(
            reader_utils, "get_centred_position_on_primary_monitor", return_value=(1, 2)
        ):
            place_window(_SIZE, borderless=True)

        assert self._graphics(config_set)["borderless"] == "1"


@dataclass
class _Loop:
    """A Kivy loop that runs only what a test asks of it."""

    clock: MagicMock
    stop: MagicMock
    window_show: MagicMock
    close_splash: MagicMock
    place_window: MagicMock

    def start(self) -> None:
        """Run what the window handed the clock for its first frame: it opens."""
        self.clock.schedule_once.call_args.args[0](0)

    def tick(self) -> bool:
        """Run the window's repeating check once, as a frame would."""
        return self.clock.schedule_interval.call_args.args[0](0)

    @property
    def popup(self) -> PopupFrame:
        (popup,) = [w for w in Window.children if isinstance(w, PopupFrame)]
        return popup

    def finish_closing(self, popup: PopupFrame) -> None:
        Animation.cancel_all(popup)
        popup._real_remove_widget()  # noqa: SLF001


@pytest.fixture
def loop() -> Iterator[_Loop]:
    with (
        patch.object(kivy.clock, "Clock") as clock,
        patch.object(kivy.base, "stopTouchApp") as stop,
        patch.object(Window, "show") as window_show,
        patch.object(boot_splash, "close_boot_splash") as close_splash,
        # Its own tests are above; here it must not leave a size in Kivy's Config.
        patch.object(installer_progress, "place_window") as place,
    ):
        yield _Loop(clock, stop, window_show, close_splash, place)
    for widget in list(Window.children):
        if isinstance(widget, PopupFrame):
            Window.remove_widget(widget)


def _run(
    work: Callable[[], Any],
    in_loop: Callable[[], None],
    show_next: Callable[[Any, Callable[[], None]], None] | None = None,
    progress: ByteProgress | None = None,
    *,
    borderless: bool = False,
) -> tuple[Any, bool]:
    """Run `work` behind the window, with `in_loop` standing in for Kivy's loop."""
    with patch.object(kivy.base, "runTouchApp", side_effect=in_loop):
        return run_showing_progress(
            work,
            progress or ByteProgress(_TOTAL),
            title="Installing",
            message="Working.",
            window_size=_SIZE,
            show_next=show_next or MagicMock(),
            borderless=borderless,
        )


def _work_until_done(loop: _Loop) -> PopupFrame:
    """Open the window, let the work's thread finish, and run the check that sees it."""
    loop.start()
    popup = loop.popup
    while loop.tick():
        pass
    return popup


class TestRunShowingProgress:
    def test_the_work_done_the_window_is_handed_on_in_the_same_loop(self, loop: _Loop) -> None:
        show_next = MagicMock()

        def in_loop() -> None:
            popup = _work_until_done(loop)
            loop.finish_closing(popup)

        result, next_shown = _run(lambda: "the result", in_loop, show_next)

        assert (result, next_shown) == ("the result", True)
        loop.window_show.assert_called_once_with()
        loop.close_splash.assert_called_once_with()  # the Windows build's, now behind a window
        show_next.assert_called_once_with("the result", loop.stop)
        loop.stop.assert_not_called()  # what follows ends the loop, when it has closed
        loop.place_window.assert_called_once_with(_SIZE, borderless=False)

    def test_a_window_with_no_frame_is_placed_as_one(self, loop: _Loop) -> None:
        def in_loop() -> None:
            loop.finish_closing(_work_until_done(loop))

        _run(lambda: None, in_loop, borderless=True)

        loop.place_window.assert_called_once_with(_SIZE, borderless=True)

    def test_the_bar_follows_the_bytes_and_ends_full(self, loop: _Loop) -> None:
        progress = ByteProgress(_TOTAL)
        seen: list[tuple[float, bool]] = []
        release = installer_progress.threading.Event()

        def captions(popup: PopupFrame) -> list[str]:
            return [w.text for w in popup.walk() if hasattr(w, "text")]

        def in_loop() -> None:
            loop.start()
            popup = loop.popup
            (bar,) = [w for w in popup.walk() if isinstance(w, ProgressBar)]
            progress.add(50)
            assert loop.tick() is True  # the work is held, so this is mid-way for certain
            seen.append((bar.value, "25%" in captions(popup)))
            release.set()
            while loop.tick():
                pass
            seen.append((bar.value, "100%" in captions(popup)))

        _run(lambda: release.wait(5), in_loop, progress=progress)

        assert seen == [(pytest.approx(0.25), True), (1.0, True)]

    def test_a_full_bar_says_the_work_is_finishing_while_it_still_runs(self, loop: _Loop) -> None:
        progress = ByteProgress(_TOTAL)
        seen: list[tuple[float, list[str]]] = []
        release = installer_progress.threading.Event()

        def bar_captions(popup: PopupFrame) -> list[str]:
            texts = [w.text for w in popup.walk() if hasattr(w, "text")]
            return [t for t in texts if t.endswith("%") or t == installer_progress.FINISHING_TEXT]

        def in_loop() -> None:
            loop.start()
            popup = loop.popup
            (bar,) = [w for w in popup.walk() if isinstance(w, ProgressBar)]
            progress.add(_TOTAL)  # every byte written, and the work (held) not done
            assert loop.tick() is True
            seen.append((bar.value, bar_captions(popup)))
            release.set()
            while loop.tick():
                pass
            seen.append((bar.value, bar_captions(popup)))

        _run(lambda: release.wait(5), in_loop, progress=progress)

        assert seen == [(1.0, [installer_progress.FINISHING_TEXT]), (1.0, ["100%"])]

    def test_the_window_cannot_be_closed_while_the_work_runs(self, loop: _Loop) -> None:
        refused: list[bool] = []
        release = installer_progress.threading.Event()

        def in_loop() -> None:
            loop.start()
            refused.append(Window.dispatch("on_request_close"))
            release.set()
            popup = _work_until_done_after(loop)
            refused.append(Window.dispatch("on_request_close"))
            loop.finish_closing(popup)

        def _work_until_done_after(loop_: _Loop) -> PopupFrame:
            popup = loop_.popup
            while loop_.tick():
                pass
            return popup

        _run(lambda: release.wait(5), in_loop)

        assert refused[0] is True
        assert not refused[1]

    def test_work_that_fails_ends_the_loop_and_raises_here(self, loop: _Loop) -> None:
        show_next = MagicMock()

        def work() -> None:
            msg = "the pack is bad"
            raise ValueError(msg)

        def in_loop() -> None:
            popup = _work_until_done(loop)
            loop.finish_closing(popup)

        with pytest.raises(ValueError, match="the pack is bad"):
            _run(work, in_loop, show_next)

        loop.stop.assert_called_once_with()
        show_next.assert_not_called()

    def test_a_loop_that_dies_under_the_work_waits_for_it(
        self, loop: _Loop, loguru_sink: list[str]
    ) -> None:
        """The work is not run again, and not abandoned: its thread is waited for."""
        release = installer_progress.threading.Event()
        calls: list[str] = []

        def work() -> str:
            calls.append("started")
            release.wait(5)
            installer_progress.threading.Event().wait(0.05)  # still going as the loop dies
            calls.append("ended")
            return "the result"

        def in_loop() -> None:
            loop.start()
            assert loop.tick() is True
            release.set()
            msg = "the display went away"
            raise RuntimeError(msg)

        show_next = MagicMock()
        result, next_shown = _run(work, in_loop, show_next)

        assert (result, next_shown) == ("the result", False)
        assert calls == ["started", "ended"]
        show_next.assert_not_called()
        assert any("Could not show the installer's progress window" in s for s in loguru_sink)

    def test_work_that_fails_as_the_loop_dies_raises_the_works_error(self, loop: _Loop) -> None:
        release = installer_progress.threading.Event()

        def work() -> None:
            release.wait(5)
            msg = "the pack is bad"
            raise ValueError(msg)

        def in_loop() -> None:
            loop.start()
            release.set()
            msg = "the display went away"
            raise RuntimeError(msg)

        with pytest.raises(ValueError, match="the pack is bad"):
            _run(work, in_loop)

    def test_a_window_that_fails_to_open_does_not_keep_refusing_to_close(self, loop: _Loop) -> None:
        """The caller shows its report or its error in this window next."""

        def in_loop() -> None:
            with patch.object(PopupFrame, "open", side_effect=RuntimeError("no font")):
                loop.start()

        result, next_shown = _run(lambda: "the result", in_loop)

        assert (result, next_shown) == ("the result", False)
        assert not Window.dispatch("on_request_close")

    def test_a_loop_that_dies_under_the_work_does_not_keep_refusing_to_close(
        self, loop: _Loop
    ) -> None:
        def in_loop() -> None:
            loop.start()
            assert Window.dispatch("on_request_close") is True  # refused while it works
            msg = "the display went away"
            raise RuntimeError(msg)

        _run(lambda: None, in_loop)

        assert not Window.dispatch("on_request_close")

    @pytest.mark.usefixtures("loop")
    def test_with_no_kivy_window_the_work_still_runs(self, loguru_sink: list[str]) -> None:
        with patch.object(kivy.core.window, "Window", None):
            result, next_shown = _run(lambda: "the result", MagicMock())

        assert (result, next_shown) == ("the result", False)
        assert any("Kivy has no window" in s for s in loguru_sink)

    @pytest.mark.usefixtures("loop")
    def test_with_no_window_the_work_still_runs(self, loguru_sink: list[str]) -> None:
        def no_window() -> None:
            msg = "no display"
            raise RuntimeError(msg)

        show_next = MagicMock()
        result, next_shown = _run(lambda: "the result", no_window, show_next)

        assert (result, next_shown) == ("the result", False)
        show_next.assert_not_called()
        assert any("Could not show the installer's progress window" in s for s in loguru_sink)

    def test_what_follows_failing_is_raised_not_taken_for_a_missing_window(
        self, loop: _Loop
    ) -> None:
        """The data is installed by then: running the work again would install it twice."""
        work = MagicMock(return_value="the result")

        def show_next(_result: object, _end_loop: object) -> None:
            msg = "the report could not be drawn"
            raise RuntimeError(msg)

        def in_loop() -> None:
            popup = _work_until_done(loop)
            loop.finish_closing(popup)

        with pytest.raises(RuntimeError, match="the report could not be drawn"):
            _run(work, in_loop, show_next)

        work.assert_called_once_with()


# What `TestTheRealLoop` runs, in a Python of its own: this process's Kivy clock holds
# whatever other tests left scheduled on it, and a real loop would run all of that.
_REAL_LOOP_SCRIPT = """
import json
import threading

from barks_reader.core.config_info import ConfigInfo

ConfigInfo()  # before any Kivy import: it points Kivy at the scratch config folder

from barks_reader.installer_progress import ByteProgress, run_showing_progress
from barks_reader.ui.popup_frame import PopupFrame
from kivy.clock import Clock
from kivy.core.window import Window

progress = ByteProgress(200)
release = threading.Event()
seen = []


def work():
    progress.add(200)
    release.wait(30)
    return "the result"


def refused_then_released(_dt):
    if not [w for w in Window.children if isinstance(w, PopupFrame)]:
        return True  # the window has not opened yet: look again next frame
    seen.append(Window.dispatch("on_request_close"))  # the desktop's close, mid-work
    release.set()
    return False


def show_next(result, end_loop):
    seen.append(result)
    seen.append(bool(Window.dispatch("on_request_close")))  # closable by now
    end_loop()


Clock.schedule_interval(refused_then_released, 0)
outcome = run_showing_progress(
    work, progress, title="Installing", message="Working.", window_size=(800, 950),
    show_next=show_next,
)
popups_left = len([w for w in Window.children if isinstance(w, PopupFrame)])
print("RESULT " + json.dumps({"outcome": outcome, "seen": seen, "popups_left": popups_left}))
"""


def _kivy_log_tails(config_dir: Path) -> list[str]:
    """Return the end of each log file under `config_dir`, for a failure's message."""
    return [
        f"{log}:\n{log.read_text(encoding='utf-8', errors='replace')[-3000:]}"
        for log in sorted(config_dir.rglob("*.txt")) + sorted(config_dir.rglob("*.log"))
    ]


class TestTheRealLoop:
    """Kivy's own loop and clock, with nothing standing in: the window as an install has it."""

    # The loop runs in a process of its own, and on a Mac with no OpenGL driver (the CI
    # runner, the VirtualBox guest) that process cannot open a window: the library that
    # lets Kivy draw there takes itself out of the environment once loaded, so no child
    # inherits it (scripts/macos/with-soft-gl.sh).
    @pytest.mark.skipif(sys.platform == "darwin", reason="a child process gets no window here")
    def test_the_work_runs_behind_the_window_which_is_then_handed_on_and_closed(
        self, tmp_path: Path
    ) -> None:
        env = os.environ | {
            "BARKS_READER_CONFIG_DIR": str(tmp_path / "config"),
            "BARKS_READER_DATA_DIR": str(tmp_path / "data"),
            "KIVY_NO_ARGS": "1",
        }

        done = subprocess.run(  # noqa: S603  (this interpreter, a fixed script)
            [sys.executable, "-c", _REAL_LOOP_SCRIPT],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )

        # Kivy's console log is off in the app (config_info), so its own word on a
        # failure is in the log file it wrote to the scratch config folder.
        assert done.returncode == 0, "\n".join(
            [done.stderr[-3000:], done.stdout[-1000:], *_kivy_log_tails(tmp_path / "config")]
        )
        (line,) = [ln for ln in done.stdout.splitlines() if ln.startswith("RESULT ")]
        assert json.loads(line.removeprefix("RESULT ")) == {
            "outcome": ["the result", True],
            "seen": [True, "the result", False],
            "popups_left": 0,
        }
        assert "Could not show the installer's progress window" not in done.stderr
