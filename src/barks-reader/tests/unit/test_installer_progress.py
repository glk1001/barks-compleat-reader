"""The installer's progress window: its count, its loop, and what it does without one."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import kivy.base
import kivy.clock
import pytest
from barks_reader import installer_progress
from barks_reader.installer_progress import ByteProgress, percent_text, run_showing_progress
from barks_reader.ui.popup_frame import PopupFrame
from kivy.animation import Animation
from kivy.core.window import Window
from kivy.uix.progressbar import ProgressBar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

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


@dataclass
class _Loop:
    """A Kivy loop that runs only what a test asks of it."""

    clock: MagicMock
    stop: MagicMock
    window_show: MagicMock

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
        patch.object(installer_progress.threading.Thread, "join", autospec=True, return_value=None),
    ):
        yield _Loop(clock, stop, window_show)
    for widget in list(Window.children):
        if isinstance(widget, PopupFrame):
            Window.remove_widget(widget)


def _run(
    work: Callable[[], Any],
    in_loop: Callable[[], None],
    show_next: Callable[[Any, Callable[[], None]], None] | None = None,
    progress: ByteProgress | None = None,
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
        show_next.assert_called_once_with("the result", loop.stop)
        loop.stop.assert_not_called()  # what follows ends the loop, when it has closed

    def test_the_bar_follows_the_bytes_and_ends_full(self, loop: _Loop) -> None:
        progress = ByteProgress(_TOTAL)
        seen: list[float] = []

        def in_loop() -> None:
            loop.start()
            (bar,) = [w for w in loop.popup.walk() if isinstance(w, ProgressBar)]
            progress.add(50)
            still_working = loop.tick()
            seen.append(bar.value)
            while still_working:
                still_working = loop.tick()
            seen.append(bar.value)

        _run(lambda: None, in_loop, progress=progress)

        assert seen[0] in (pytest.approx(0.25), 1.0)  # 1.0 if the work had already ended
        assert seen[-1] == 1.0

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
