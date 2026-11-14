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
from barks_kivy_ui.scrolling import ReaderScrollView
from barks_reader.core import log_markers, reader_utils, screen_metrics
from barks_reader.core.keys import KEY_DOWN, KEY_ENTER, KEY_ESCAPE, KEY_LEFT, KEY_UP
from barks_reader.core.popup_frame import FrameButton, PopupSize
from barks_reader.ui import kivy_standalone_show_message
from barks_reader.ui.kivy_standalone_show_message import divider_line, show_standalone_popup
from barks_reader.ui.popup_frame import PopupFrame
from kivy.animation import Animation
from kivy.config import Config
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.widget import Widget

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from kivy.uix.modalview import ModalView

_TITLE = "Barks Reader Installation"
_SIZE = (800, 950)


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


def _closes_the_boot_splash(loop: _Loop) -> None:
    with patch.object(kivy_standalone_show_message, "close_boot_splash") as close_splash:
        _open(loop)

    close_splash.assert_called_once_with()


def test_the_boot_splash_comes_down_for_a_message_with_no_app(no_app: _Loop) -> None:
    """An error before the main window is up must not be left beside the splash."""
    _closes_the_boot_splash(no_app)


def test_the_boot_splash_comes_down_for_a_message_in_the_app(app: _Loop) -> None:
    _closes_the_boot_splash(app)


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

    def test_in_a_loop_already_running_it_starts_none_and_leaves_that_one_running(
        self, no_app: _Loop
    ) -> None:
        """An installer's progress window has a loop and no app: its caller ends it."""
        on_dismiss = MagicMock()
        popup = _open(no_app, in_running_loop=True, on_dismiss=on_dismiss)

        no_app.run.assert_not_called()
        no_app.window_show.assert_not_called()
        popup.dismiss()
        no_app.finish_closing()
        on_dismiss.assert_called_once_with()
        no_app.stop.assert_not_called()

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
        assert not popup.fit_body_height

    def test_a_popup_can_be_as_tall_as_its_content(self, app: _Loop) -> None:
        assert _open(app, fit_body_height=True).fit_body_height

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
        assert kivy_standalone_show_message.fit_window_to_screen(_SIZE) == _SIZE

    def test_a_window_taller_than_a_laptop_screen_is_cut_to_clear_a_bar_at_either_edge(
        self, screen: Callable[[int, int], None]
    ) -> None:
        screen(1366, 768)
        assert kivy_standalone_show_message.fit_window_to_screen(_SIZE) == (800, 768 - 2 * 55)

    def test_a_window_wider_than_the_screen_is_cut_to_its_width(
        self, screen: Callable[[int, int], None]
    ) -> None:
        screen(640, 1080)
        assert kivy_standalone_show_message.fit_window_to_screen(_SIZE) == (640, 950)

    def test_a_window_exactly_the_room_there_is_keeps_its_size(
        self, screen: Callable[[int, int], None]
    ) -> None:
        screen(800, 950 + 2 * 55)
        assert kivy_standalone_show_message.fit_window_to_screen(_SIZE) == _SIZE


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
            size = kivy_standalone_show_message.place_window(_SIZE)

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
            kivy_standalone_show_message.place_window(_SIZE, borderless=True)

        assert self._graphics(config_set)["borderless"] == "1"


def _scrolling(view_height: int, text_height: int) -> ReaderScrollView:
    scroll_view = ReaderScrollView(size_hint=(None, None), size=(400, view_height))
    scroll_view.add_widget(Widget(size_hint=(None, None), size=(400, text_height)))
    return scroll_view


class TestScrollKeys:
    def test_down_and_up_move_the_text_a_quarter_of_what_shows(self) -> None:
        scroll_view = _scrolling(400, 800)  # 400 hidden: a press moves 100 of them
        on_key = kivy_standalone_show_message.scroll_keys(scroll_view)

        assert on_key(KEY_DOWN) is True
        assert scroll_view.scroll_y == pytest.approx(0.75)
        assert on_key(KEY_UP) is True
        assert scroll_view.scroll_y == pytest.approx(1.0)

    def test_it_stops_at_the_top_and_at_the_foot(self) -> None:
        scroll_view = _scrolling(400, 500)  # a press is the whole of what is hidden
        on_key = kivy_standalone_show_message.scroll_keys(scroll_view)

        on_key(KEY_UP)
        assert scroll_view.scroll_y == 1.0
        on_key(KEY_DOWN)
        on_key(KEY_DOWN)
        assert scroll_view.scroll_y == 0.0

    def test_text_that_all_shows_is_left_where_it_is(self) -> None:
        scroll_view = _scrolling(400, 300)
        on_key = kivy_standalone_show_message.scroll_keys(scroll_view)

        assert on_key(KEY_DOWN) is True  # still the popup's key: it reaches nothing else
        assert scroll_view.scroll_y == 1.0

    def test_a_view_with_nothing_in_it_is_no_error(self) -> None:
        on_key = kivy_standalone_show_message.scroll_keys(ReaderScrollView())

        assert on_key(KEY_DOWN) is True

    def test_other_keys_are_left_to_the_popup(self) -> None:
        on_key = kivy_standalone_show_message.scroll_keys(_scrolling(400, 800))

        assert on_key(KEY_ENTER) is False
        assert on_key(KEY_LEFT) is False

    def test_a_popup_whose_content_scrolls_is_scrolled_by_the_remote(self, app: _Loop) -> None:
        app.content.scroll_view = _scrolling(400, 800)
        _open(app, buttons=(FrameButton("OK", lambda: None),))

        assert Window.dispatch("on_key_down", KEY_DOWN, 0, None, [])

        assert app.content.scroll_view.scroll_y == pytest.approx(0.75)

    def test_content_with_nothing_to_scroll_gets_no_key_handler(self, app: _Loop) -> None:
        popup = _open(app)

        assert popup.key_handler is None
