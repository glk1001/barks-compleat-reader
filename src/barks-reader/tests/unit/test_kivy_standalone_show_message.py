"""The standalone popup: how it opens with and without a running app, and how it closes.

The popup is real, opened on the test process's window, but neither the clock nor
a run loop runs here: Kivy's clock and run-loop calls are stood in for, and what
the popup schedules is run by hand. A real popup fades in and out; ``_Loop``
finishes each fade at once, as the clock would.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import kivy.app
import kivy.base
import kivy.clock
import pytest
from barks_reader.core import log_markers
from barks_reader.core.keys import KEY_ENTER, KEY_ESCAPE
from barks_reader.core.popup_frame import FrameButton, PopupSize
from barks_reader.ui.kivy_standalone_show_message import divider_line, show_standalone_popup
from barks_reader.ui.popup_frame import PopupFrame
from kivy.animation import Animation
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from kivy.uix.modalview import ModalView

_TITLE = "Barks Reader Installation"


@dataclass
class _Loop:
    clock: MagicMock
    run: MagicMock
    stop: MagicMock
    window_show: MagicMock
    content: Any = field(default_factory=BoxLayout)

    def run_scheduled(self, index: int = 0) -> None:
        """Run what the popup handed the clock, as the next frame would."""
        self.clock.schedule_once.call_args_list[index].args[0](0)

    @property
    def popup(self) -> ModalView:
        return self.content.popup_ref

    def finish_opening(self) -> None:
        Animation.cancel_all(self.popup)
        self.popup.dispatch("on_open")

    def finish_closing(self) -> None:
        Animation.cancel_all(self.popup)
        self.popup._real_remove_widget()  # noqa: SLF001


def _loop(app_running: bool) -> Iterator[_Loop]:
    with (
        patch.object(kivy.clock, "Clock") as clock,
        patch.object(kivy.base, "runTouchApp") as run,
        patch.object(kivy.base, "stopTouchApp") as stop,
        patch.object(kivy.base.EventLoop, "status", "started"),
        patch.object(
            kivy.app.App, "get_running_app", return_value=MagicMock() if app_running else None
        ),
        patch.object(Window, "show") as window_show,
    ):
        loop = _Loop(clock, run, stop, window_show)
        yield loop
        # Whatever a test left open comes off the window, its key handler with it.
        if getattr(loop.content, "popup_ref", None) is not None and loop.popup.parent is not None:
            loop.popup.dismiss()
            loop.finish_closing()


@pytest.fixture
def no_app() -> Iterator[_Loop]:
    """Run with no app: the popup must start a run loop of its own."""
    yield from _loop(app_running=False)


@pytest.fixture
def app() -> Iterator[_Loop]:
    """Run with the app: the popup only schedules itself on the app's loop."""
    yield from _loop(app_running=True)


def _open(loop: _Loop, **kwargs: Any) -> ModalView:  # noqa: ANN401
    loop.content.popup_ref = None
    show_standalone_popup(_TITLE, loop.content, **kwargs)
    loop.run_scheduled()
    loop.finish_opening()
    return loop.popup


class TestWithoutAnApp:
    def test_it_shows_the_window_and_runs_a_loop_of_its_own(
        self, no_app: _Loop, loguru_sink: list[str]
    ) -> None:
        popup = _open(no_app)

        no_app.window_show.assert_called_once_with()
        no_app.run.assert_called_once_with()
        assert "No Kivy app running, starting temporary UI loop for popup." in loguru_sink
        assert popup.parent is Window
        assert no_app.content.parent is not None
        assert log_markers.STANDALONE_POPUP_OPENED.format(title=_TITLE) in loguru_sink

    def test_return_closes_it_and_ends_the_loop_once_it_has_left_the_window(
        self, no_app: _Loop, loguru_sink: list[str]
    ) -> None:
        on_dismiss = MagicMock()
        popup = _open(no_app, on_dismiss=on_dismiss)
        closed = log_markers.STANDALONE_POPUP_CLOSED.format(title=_TITLE)

        assert Window.dispatch("on_key_down", KEY_ENTER, 0, None, [])

        # Dismissed, but still fading out: nothing has closed yet.
        assert closed not in loguru_sink
        on_dismiss.assert_not_called()
        no_app.stop.assert_not_called()

        no_app.finish_closing()

        assert popup.parent is None
        assert closed in loguru_sink
        on_dismiss.assert_called_once_with()
        no_app.stop.assert_called_once_with()

    def test_escape_lands_on_the_close_button_first(
        self, no_app: _Loop, loguru_sink: list[str]
    ) -> None:
        """As everywhere: Escape to the X, Return closes; Escape there gives it back."""
        popup = _open(no_app)
        with patch.object(popup, "dismiss", wraps=popup.dismiss) as dismiss:
            assert Window.dispatch("on_key_down", KEY_ESCAPE, 0, None, [])
            dismiss.assert_not_called()
            assert any("Nav focus on Button" in line for line in loguru_sink)
            assert Window.dispatch("on_key_down", KEY_ESCAPE, 0, None, [])  # back again
            dismiss.assert_not_called()
            assert Window.dispatch("on_key_down", KEY_ESCAPE, 0, None, [])  # to the X
            assert Window.dispatch("on_key_down", KEY_ENTER, 0, None, [])
            dismiss.assert_called_once()
        no_app.finish_closing()

    def test_once_closed_it_takes_no_more_keys(self, no_app: _Loop) -> None:
        """Its key handler leaves the window with it.

        Checked by the handler itself, not by a key sent to the window: the
        window is the test process's one, and a key sent there once reached a
        handler another test had left bound (a random-order run, 2026-10-05).
        """
        with (
            patch.object(Window, "bind", wraps=Window.bind) as bind,
            patch.object(Window, "unbind", wraps=Window.unbind) as unbind,
        ):
            _open(no_app)
            (handler,) = [
                c.kwargs["on_key_down"] for c in bind.call_args_list if "on_key_down" in c.kwargs
            ]
            no_app.popup.dismiss()
            no_app.finish_closing()

        assert handler in [c.kwargs.get("on_key_down") for c in unbind.call_args_list]

    def test_a_loop_that_fails_is_logged_and_raised(
        self, no_app: _Loop, loguru_sink: list[str]
    ) -> None:
        no_app.run.side_effect = RuntimeError("no window")

        with pytest.raises(RuntimeError, match="no window"):
            show_standalone_popup(_TITLE, no_app.content)

        assert "Failed to show standalone popup: no window" in loguru_sink


class TestWithTheApp:
    def test_it_opens_on_the_apps_loop_and_leaves_that_loop_running(self, app: _Loop) -> None:
        popup = _open(app)
        app.run.assert_not_called()
        app.window_show.assert_not_called()

        popup.dismiss()
        app.finish_closing()

        app.stop.assert_not_called()

    def test_it_is_the_shared_frame_sized_as_asked(self, app: _Loop) -> None:
        popup = _open(app, size=PopupSize.MEDIUM)
        assert isinstance(popup, PopupFrame)
        assert popup.size_class is PopupSize.MEDIUM
        assert not popup.fill_window

    def test_a_popup_that_is_its_windows_only_content_fills_it(self, no_app: _Loop) -> None:
        popup = _open(no_app, fill_window=True)
        assert popup.fill_window
        assert tuple(popup.size_hint) == (1, 1)

    def test_the_close_button_closes_it(self, app: _Loop) -> None:
        popup = _open(app)
        close = next(w for w in popup.walk() if isinstance(w, Button) and w.text == "X")

        with patch.object(popup, "dismiss") as dismiss:
            close.dispatch("on_release")

        dismiss.assert_called_once_with()

    def test_buttons_take_the_place_of_the_close_button(self, app: _Loop) -> None:
        start = MagicMock()
        popup = _open(app, buttons=(FrameButton("Start", start),))
        assert [w.text for w in popup.walk() if isinstance(w, Button)] == ["Start"]

        with patch.object(popup, "dismiss") as dismiss:
            assert Window.dispatch("on_key_down", KEY_ENTER, 0, None, [])

        dismiss.assert_called_once_with()
        start.assert_called_once_with()

    def test_a_timeout_closes_it(self, app: _Loop) -> None:
        popup = _open(app, timeout=5)
        assert app.clock.schedule_once.call_args_list[1].args[1] == 5  # noqa: PLR2004

        with patch.object(popup, "dismiss") as dismiss:
            app.run_scheduled(1)

        dismiss.assert_called_once_with()

    def test_the_art_is_drawn_behind_the_content(self, app: _Loop, tmp_path: Path) -> None:
        art = tmp_path / "background.png"
        popup = _open(app, background_image_file=art)
        assert [w.source for w in popup.walk() if isinstance(w, Image)] == [str(art)]

    def test_no_art_draws_no_image(self, app: _Loop) -> None:
        popup = _open(app)
        assert not any(isinstance(w, Image) for w in popup.walk())


def test_a_divider_line_is_one_pixel_and_follows_its_widget() -> None:
    line = divider_line()
    line.pos = (5, 6)
    line.size = (200, 1)
    assert line.height == 1
    assert (tuple(line.rect.pos), tuple(line.rect.size)) == ((5, 6), (200, 1))
