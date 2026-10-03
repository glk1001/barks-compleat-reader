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
from barks_reader.ui.kivy_standalone_show_message import (
    _get_background_image_pos_and_size,
    divider_line,
    show_standalone_popup,
)
from barks_reader.ui.reader_keyboard_nav import KEY_ESCAPE
from kivy.animation import Animation
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from PIL import Image

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


def _write_png(path: Path, size: tuple[int, int]) -> Path:
    Image.new("RGBA", size, (200, 180, 120, 255)).save(path)
    return path


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

    def test_escape_closes_it_and_ends_the_loop_once_it_has_left_the_window(
        self, no_app: _Loop, loguru_sink: list[str]
    ) -> None:
        on_dismiss = MagicMock()
        popup = _open(no_app, on_dismiss=on_dismiss)
        closed = log_markers.STANDALONE_POPUP_CLOSED.format(title=_TITLE)

        assert Window.dispatch("on_key_down", KEY_ESCAPE, 0, None, [])

        # Dismissed, but still fading out: nothing has closed yet.
        assert closed not in loguru_sink
        on_dismiss.assert_not_called()
        no_app.stop.assert_not_called()

        no_app.finish_closing()

        assert popup.parent is None
        assert closed in loguru_sink
        on_dismiss.assert_called_once_with()
        no_app.stop.assert_called_once_with()

    def test_once_closed_it_takes_no_more_keys(self, no_app: _Loop) -> None:
        _open(no_app)
        no_app.popup.dismiss()
        no_app.finish_closing()

        with patch.object(no_app.popup, "dismiss") as dismiss:
            Window.dispatch("on_key_down", KEY_ESCAPE, 0, None, [])

        dismiss.assert_not_called()

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

    def test_the_close_button_closes_it(self, app: _Loop) -> None:
        popup = _open(app)
        close = next(w for w in popup.walk() if isinstance(w, Button) and w.text == "X")

        with patch.object(popup, "dismiss") as dismiss:
            close.dispatch("on_press")

        dismiss.assert_called_once_with()

    def test_it_can_have_no_close_button(self, app: _Loop) -> None:
        popup = _open(app, add_close_button=False)
        assert not any(isinstance(w, Button) and w.text == "X" for w in popup.walk())

    def test_a_timeout_closes_it(self, app: _Loop) -> None:
        popup = _open(app, timeout=5)
        assert app.clock.schedule_once.call_args_list[1].args[1] == 5  # noqa: PLR2004

        with patch.object(popup, "dismiss") as dismiss:
            app.run_scheduled(1)

        dismiss.assert_called_once_with()

    def test_the_title_bar_follows_its_size(self, app: _Loop) -> None:
        popup = _open(app)
        title_bar = popup.content.children[-1]
        title_bar.pos = (10, 20)
        title_bar.size = (300, 56)
        shadow, top, bottom = (
            i for i in title_bar.canvas.before.children if type(i).__name__ == "Rectangle"
        )
        assert (tuple(shadow.pos), tuple(shadow.size)) == ((10, 16), (300, 6))
        assert (tuple(top.pos), tuple(bottom.pos)) == ((10, 48), (10, 20))
        assert tuple(top.size) == tuple(bottom.size) == (300, 28)


class TestBackgroundImage:
    def test_the_image_is_drawn_behind_the_content(self, app: _Loop, tmp_path: Path) -> None:
        background = _write_png(tmp_path / "background.png", (40, 20))

        popup = _open(app, background_image_file=background)

        wrapper = popup.content.children[0]
        sizes = [
            tuple(i.texture.size)
            for i in wrapper.canvas.before.children
            if getattr(i, "texture", None) is not None
        ]
        assert (40, 20) in sizes


class TestBackgroundFit:
    """The image fits inside its box, centred, its longer side filling the box."""

    def test_a_wide_image_fills_the_width(self) -> None:
        assert _get_background_image_pos_and_size((0, 0), (400, 400), 2.0) == (
            (0, 100),
            (400, 200),
        )

    def test_a_tall_image_fills_the_height(self) -> None:
        assert _get_background_image_pos_and_size((10, 20), (400, 400), 0.5) == (
            (110, 20),
            (200, 400),
        )

    def test_a_side_within_ten_pixels_of_the_box_is_snapped_to_it(self) -> None:
        assert _get_background_image_pos_and_size((0, 0), (400, 300), 400 / 295) == (
            (0, 0),
            (400, 300),
        )

    def test_a_rounding_hair_over_the_box_is_snapped_back(self) -> None:
        # 3422 * (4042 / 3422) is 4042.0000000000005 in floating point.
        assert _get_background_image_pos_and_size((0, 0), (4042, 3422), 4042 / 3422) == (
            (0, 0),
            (4042, 3422),
        )

    def test_a_box_with_no_height_gets_no_image(self) -> None:
        assert _get_background_image_pos_and_size((0, 0), (100, 0), 1.0) == ((50, 0), (0, 0))


def test_a_divider_line_is_one_pixel_and_follows_its_widget() -> None:
    line = divider_line()
    line.pos = (5, 6)
    line.size = (200, 1)
    assert line.height == 1
    assert (tuple(line.rect.pos), tuple(line.rect.size)) == ((5, 6), (200, 1))
