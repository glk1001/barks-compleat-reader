# ruff: noqa: PLC0415

"""A window that says an installer is working, and how far along it is.

Unpacking the data takes about half a minute, and until 2026-11-11 nothing showed for
it: a first run looked like an app that had not started. The window opens first, the
work runs on another thread, and a bar follows the bytes it has written. What comes
next (the installer's success message) is shown in the same window, in the same Kivy
loop.

A machine whose window cannot open still installs: the work then runs with nothing
showing, as it used to.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable

# How often the bar catches up with the work, in seconds.
_TICK_SECS = 1 / 15


class ByteProgress:
    """How many of an installer's bytes have been written, counted from its thread."""

    def __init__(self, total: int) -> None:
        """Start at nothing written, of `total` bytes."""
        self.total = total
        self._done = 0
        self._lock = threading.Lock()

    def add(self, num_bytes: int) -> None:
        """Count `num_bytes` more as written."""
        with self._lock:
            self._done += num_bytes

    @property
    def fraction(self) -> float:
        """The share written, from 0 to 1; 0 when there is nothing to write."""
        if self.total <= 0:
            return 0.0
        with self._lock:
            return min(1.0, self._done / self.total)


class _Run[T]:
    """One run's state, shared by the Kivy loop and the work's thread."""

    def __init__(self, work: Callable[[], T]) -> None:
        self._work = work
        self.thread = threading.Thread(target=self._do_work, name="installer-work")
        self.started = False
        self.finished = False
        self.next_shown = False
        self._results: list[T] = []  # what the work returned, once it has
        self.error: BaseException | None = None

    @property
    def result(self) -> T:
        """What the work returned; only once it has ended without an error."""
        return self._results[0]

    def _do_work(self) -> None:
        try:
            self._results.append(self._work())
        except BaseException as e:  # noqa: BLE001  (handed to the caller's thread, whole)
            self.error = e

    def outcome(self) -> T:
        """Wait for the work, then return what it returned or raise what it raised."""
        self.thread.join()
        if self.error is not None:
            raise self.error
        return self.result


def percent_text(fraction: float) -> str:
    """Return a share from 0 to 1 as the bar's caption."""
    return f"{int(fraction * 100)}%"


def run_showing_progress[T](
    work: Callable[[], T],
    progress: ByteProgress,
    *,
    title: str,
    message: str,
    window_size: tuple[int, int],
    show_next: Callable[[T, Callable[[], None]], None],
    borderless: bool = False,
) -> tuple[T, bool]:
    """Run `work` on another thread behind a window that shows its progress.

    The window cannot be closed while the work runs. When the work is done the window
    is handed to `show_next`; if the work raised, the window's loop is stopped and the
    error is raised here, for the caller's own error popup.

    Args:
        work: The installer's work; it counts what it writes on `progress`.
        progress: The count the bar follows.
        title: The window's title bar text.
        message: What is happening, as Kivy markup.
        window_size: The window's width and height.
        show_next: Called in the window's Kivy loop with what `work` returned and a
            function that ends the loop: it shows what follows (a popup opened with
            ``in_running_loop``), and ends the loop when that has closed.
        borderless: Whether the window has no frame of the desktop's, as one has
            whose popup's own title bar is its top.

    Returns:
        What `work` returned, and whether `show_next` was called. False means the
        window could not be opened, and the work ran with nothing showing.

    Raises:
        BaseException: Whatever `work` raised.

    """
    run = _Run(work)
    try:
        _run_window_loop(run, progress, title, message, window_size, show_next, borderless)
    except Exception as e:  # any Kivy failure: the install matters more than its window
        if run.started:
            run.thread.join()
        if run.error is None and run.finished:
            raise  # the work is done and what followed it failed: the caller's to report
        logger.warning(f"Could not show the installer's progress window: {e!r}.")

    if not run.started:
        return work(), False
    return run.outcome(), run.next_shown


def _run_window_loop[T](
    run: _Run[T],
    progress: ByteProgress,
    title: str,
    message: str,
    window_size: tuple[int, int],
    show_next: Callable[[T, Callable[[], None]], None],
    borderless: bool,
) -> None:
    from barks_reader.core.reader_utils import get_centred_position_on_primary_monitor

    x, y = get_centred_position_on_primary_monitor(*window_size)

    # Before the window exists, so that it opens where and as large as it will stay.
    from kivy import Config

    Config.set("graphics", "left", x)  # ty:ignore[unresolved-attribute]
    Config.set("graphics", "top", y)  # ty:ignore[unresolved-attribute]
    Config.set("graphics", "width", window_size[0])  # ty:ignore[unresolved-attribute]
    Config.set("graphics", "height", window_size[1])  # ty:ignore[unresolved-attribute]
    if borderless:
        Config.set("graphics", "borderless", "1")  # ty:ignore[unresolved-attribute]

    from kivy.base import runTouchApp, stopTouchApp
    from kivy.clock import Clock
    from kivy.core.window import Window

    from barks_reader.core.popup_frame import PopupSize
    from barks_reader.ui.popup_frame import PopupFrame

    if Window is None:
        msg = "Kivy has no window"
        raise RuntimeError(msg)

    def keep_window(*_args: object, **_kwargs: object) -> bool:
        return not run.finished  # True refuses the close

    def on_closed() -> None:
        Window.unbind(on_request_close=keep_window)
        if run.error is not None:
            stopTouchApp()
            return
        run.next_shown = True
        show_next(run.result, stopTouchApp)

    def start(_dt: float) -> None:
        body, bar, caption = _progress_body(message)
        popup = PopupFrame(
            title=title,
            body=body,
            size=PopupSize.LARGE,
            fill_window=True,
            on_closed=on_closed,
            closable=False,
        )
        Window.bind(on_request_close=keep_window)
        popup.open()

        def tick(_dt: float) -> bool:
            fraction = progress.fraction
            bar.value = fraction
            caption.text = percent_text(fraction)
            if run.thread.is_alive():
                return True
            run.finished = True
            bar.value = 1.0
            caption.text = percent_text(1.0)
            popup.dismiss()
            return False

        run.thread.start()
        run.started = True
        Clock.schedule_interval(tick, _TICK_SECS)

    # The window may be hidden (the main app's config hides it until it is built).
    Window.show()
    Clock.schedule_once(start, 0)
    runTouchApp()


def _progress_body(message: str) -> tuple[Any, Any, Any]:
    """Return the window's content, its bar and the bar's caption."""
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.progressbar import ProgressBar
    from kivy.uix.widget import Widget

    from barks_reader.core.reader_palette import theme
    from barks_reader.ui.popup_frame import message_body, popup_fonts

    body = BoxLayout(orientation="vertical", padding=[dp(24), 0], spacing=dp(12))
    body.add_widget(Widget(size_hint_y=0.6))
    body.add_widget(message_body(message, centred=True))
    bar = ProgressBar(max=1.0, value=0.0, size_hint_y=None, height=dp(28))
    body.add_widget(bar)
    caption = Label(
        text=percent_text(0.0),
        font_size=popup_fonts().text,
        color=list(theme().text_secondary),
        size_hint_y=None,
        height=dp(32),
    )
    body.add_widget(caption)
    body.add_widget(Widget())
    return body, bar, caption
