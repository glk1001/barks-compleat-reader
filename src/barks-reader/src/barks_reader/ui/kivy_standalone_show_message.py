# ruff: noqa: PLC0415

"""Standalone popup utilities for displaying messages when Kivy may or may not be running."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.keys import KEY_ENTER, KEY_NUMPAD_ENTER, is_escape_key
from barks_reader.core.popup_frame import FrameButton, PopupSize


# --- Light divider line widget ---
def closes_popup(key: int) -> bool:
    """Return whether a key closes a standalone popup: Escape, or Return as "OK".

    A standalone popup is a message with only a close button, and that button
    takes no keyboard focus, so with the remote's keys Return would otherwise do
    nothing.
    """
    return is_escape_key(key) or key in (KEY_ENTER, KEY_NUMPAD_ENTER)


def log_popup_opened(title: str) -> None:
    """Log that a standalone popup is showing."""
    logger.info(log_markers.STANDALONE_POPUP_OPENED.format(title=title))


def log_popup_closed(title: str) -> None:
    """Log that a standalone popup has left the window."""
    logger.info(log_markers.STANDALONE_POPUP_CLOSED.format(title=title))


def divider_line() -> Any:  # Widget  # noqa: ANN401
    from kivy.graphics import Color, Rectangle
    from kivy.uix.widget import Widget

    w = Widget(size_hint_y=None, height=1)
    with w.canvas.before:  # ty:ignore[unresolved-attribute]
        Color(0.5, 0.5, 0.5, 1)
        w.rect = Rectangle(size=w.size, pos=w.pos)
    w.bind(size=lambda inst, val: setattr(inst.rect, "size", val))
    w.bind(pos=lambda inst, val: setattr(inst.rect, "pos", val))

    return w


def show_standalone_popup(
    title: str,
    content,  # noqa: ANN001
    *,
    size: PopupSize = PopupSize.LARGE,
    fill_window: bool = False,
    fit_body_height: bool = False,
    buttons: Sequence[FrameButton] = (),
    timeout: float = 0,
    background_image_file: Path | None = None,
    on_dismiss: Callable[[], None] | None = None,
) -> None:
    """Show a popup on the shared frame (``ui.popup_frame``), even if no Kivy app is running.

    With no app running (the installers, the error popup), it runs a Kivy loop of its own
    until the popup has closed.

    Args:
        title: Text for the popup's title bar.
        content: The widget to place inside the popup; its ``popup_ref`` is set to the
            popup, for content that shows news in the title bar.
        size: The frame's size class, over the app.
        fill_window: Whether the popup fills its window, as one that is its window's only
            content does.
        fit_body_height: Whether the popup is only as tall as its content needs (its
            ``minimum_height``), never taller than its size class.
        buttons: The frame's buttons; none puts a close X in the title bar.
        timeout: Auto-dismiss after this many seconds (0 = wait for the user).
        background_image_file: Optional art drawn behind the content, under the scrim.
        on_dismiss: Called once the popup has closed and left the window, however
            it was closed.

    """
    from kivy.app import App
    from kivy.base import EventLoop, runTouchApp, stopTouchApp
    from kivy.clock import Clock
    from kivy.core.window import Window

    from .popup_frame import PopupFrame

    app_already_running = (App.get_running_app() is not None) and (EventLoop.status == "started")

    def _show(*_args: object) -> None:
        # All of it once the popup has left the window, not when its dismissal began:
        # Kivy fades a dismissed popup out first, and the main screen ignores every key
        # while a modal is still on the window, so a caller that logs "dismissed" in
        # `on_dismiss` can be waited on for the next key. The temporary loop stops last:
        # stopped at the dismissal, as it once was, it never ran the removal, and the
        # closed line was never logged.
        def on_closed() -> None:
            log_popup_closed(title)
            if on_dismiss is not None:
                on_dismiss()
            if not app_already_running:
                stopTouchApp()

        popup = PopupFrame(
            title=title,
            body=content,
            size=size,
            buttons=buttons,
            art_file=str(background_image_file) if background_image_file else "",
            on_closed=on_closed,
            fill_window=fill_window,
            fit_body_height=fit_body_height,
        )
        content.popup_ref = popup
        popup.bind(on_open=lambda *_: log_popup_opened(title))
        if timeout > 0:
            Clock.schedule_once(lambda _dt: popup.dismiss(), timeout)
        popup.open()

    try:
        if app_already_running:
            Clock.schedule_once(_show, 0)
        else:
            logger.warning("No Kivy app running, starting temporary UI loop for popup.")
            # Window may be hidden (graphics.window_state=hidden is set during boot
            # and Window.show() normally runs only after a successful build()). If an
            # error popup is rendered into a hidden Window, the user can't dismiss
            # it and the runTouchApp loop below hangs forever.
            Window.show()
            Clock.schedule_once(_show, 0)
            runTouchApp()
    except Exception as e:
        logger.critical(f"Failed to show standalone popup: {e}")
        raise
