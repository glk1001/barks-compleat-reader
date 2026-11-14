# ruff: noqa: PLC0415

"""Standalone popup utilities for displaying messages when Kivy may or may not be running."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.boot_splash import close_boot_splash
from barks_reader.core.keys import KEY_DOWN, KEY_ENTER, KEY_NUMPAD_ENTER, KEY_UP, is_escape_key
from barks_reader.core.popup_frame import FrameButton, PopupSize

if TYPE_CHECKING:
    from kivy.uix.widget import Widget

# How far Up or Down moves a popup's scrolling text, as a share of what shows of it.
_KEY_SCROLL_SHARE = 0.25


def closes_popup(key: int) -> bool:
    """Return whether a key closes a standalone popup: Escape, or Return as "OK".

    A standalone popup is a message with only a close button, and that button
    takes no keyboard focus, so with the remote's keys Return would otherwise do
    nothing.
    """
    return is_escape_key(key) or key in (KEY_ENTER, KEY_NUMPAD_ENTER)


def fit_window_to_screen(size: tuple[int, int]) -> tuple[int, int]:
    """Return `size`, made no larger than the primary screen has room for.

    The window is centred, and where the desktop keeps its taskbar or panel is not
    known, so the height leaves that allowance both above and below. A window taller
    than that had its title bar above the screen's top and its button below the bottom.

    Args:
        size: The width and height wanted.

    Returns:
        The width and height to open the window at.

    """
    from barks_reader.core.screen_metrics import SCREEN_METRICS, get_approximate_taskbar_height

    screen = SCREEN_METRICS.get_primary_screen_info()
    room_high = screen.height_pixels - 2 * get_approximate_taskbar_height()
    return min(size[0], screen.width_pixels), min(size[1], room_high)


def place_window(size: tuple[int, int], *, borderless: bool = False) -> tuple[int, int]:
    """Tell Kivy where the window opens and how large: centred, and fitted to the screen.

    Called before the window exists, so that it opens where and as large as it will
    stay; it does nothing to a window already open.

    Args:
        size: The width and height wanted.
        borderless: Whether the window has no frame of the desktop's, as one has
            whose popup's own title bar is its top.

    Returns:
        The width and height the window was given (`fit_window_to_screen`).

    """
    from kivy import Config

    from barks_reader.core.reader_utils import get_centred_position_on_primary_monitor

    width, height = fit_window_to_screen(size)
    x, y = get_centred_position_on_primary_monitor(width, height)
    Config.set("graphics", "left", x)  # ty: ignore[missing-union-attribute]
    Config.set("graphics", "top", y)  # ty: ignore[missing-union-attribute]
    Config.set("graphics", "width", width)  # ty: ignore[missing-union-attribute]
    Config.set("graphics", "height", height)  # ty: ignore[missing-union-attribute]
    if borderless:
        Config.set("graphics", "borderless", "1")  # ty: ignore[missing-union-attribute]
    return width, height


def scroll_keys(scroll_view: Any) -> Callable[[int], bool]:  # noqa: ANN401
    """Return a popup's key handler that scrolls `scroll_view` with Up and Down.

    A standalone popup's text is cut short on a small screen (`fit_window_to_screen`),
    and the remote has no wheel: without this, what is below the window's foot could
    not be read with it.

    Args:
        scroll_view: The popup's scroll view, holding its text.

    Returns:
        A `PopupFrame.key_handler`: True for Up and Down, which it has dealt with.

    """

    def on_key(key: int) -> bool:
        if key not in (KEY_UP, KEY_DOWN):
            return False
        text = scroll_view.children[0] if scroll_view.children else None
        hidden = text.height - scroll_view.height if text is not None else 0
        if hidden > 0:
            step = _KEY_SCROLL_SHARE * scroll_view.height / hidden
            # scroll_y is 1 at the top of the text and 0 at its foot.
            moved_to = scroll_view.scroll_y + (step if key == KEY_UP else -step)
            scroll_view.scroll_y = min(1.0, max(0.0, moved_to))
        return True

    return on_key


def log_popup_opened(title: str) -> None:
    """Log that a standalone popup is showing."""
    logger.info(log_markers.STANDALONE_POPUP_OPENED.format(title=title))


def log_popup_closed(title: str) -> None:
    """Log that a standalone popup has left the window."""
    logger.info(log_markers.STANDALONE_POPUP_CLOSED.format(title=title))


def divider_line() -> Any:  # Widget  # noqa: ANN401
    """Return a light divider line: a widget one pixel tall."""
    from kivy.graphics import Color, Rectangle
    from kivy.uix.widget import Widget

    w = Widget(size_hint_y=None, height=1)
    with w.canvas.before:  # ty: ignore[missing-union-attribute]
        Color(0.5, 0.5, 0.5, 1)
        w.rect = Rectangle(size=w.size, pos=w.pos)
    w.bind(size=lambda inst, val: setattr(inst.rect, "size", val))
    w.bind(pos=lambda inst, val: setattr(inst.rect, "pos", val))

    return w


def show_standalone_popup(
    title: str,
    content: "Widget",
    *,
    size: PopupSize = PopupSize.LARGE,
    fill_window: bool = False,
    fit_body_height: bool = False,
    buttons: Sequence[FrameButton] = (),
    timeout: float = 0,
    background_image_file: Path | None = None,
    on_dismiss: Callable[[], None] | None = None,
    in_running_loop: bool = False,
) -> None:
    """Show a popup on the shared frame (``ui.popup_frame``), even if no Kivy app is running.

    With no app running (the installers, the error popup), it runs a Kivy loop of its own
    until the popup has closed, unless the caller is in one already.

    Args:
        title: Text for the popup's title bar.
        content: The widget to place inside the popup; its ``popup_ref`` is set to the
            popup, for content that shows news in the title bar. Content with a
            ``scroll_view`` of its own is scrolled by Up and Down (`scroll_keys`).
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
        in_running_loop: Whether the caller is in a Kivy loop with no app (an
            installer's progress window): the popup is shown in that loop, which the
            caller's ``on_dismiss`` ends.

    """
    from kivy.app import App
    from kivy.base import EventLoop, runTouchApp, stopTouchApp
    from kivy.clock import Clock
    from kivy.core.window import Window

    from .popup_frame import PopupFrame

    app_already_running = in_running_loop or (
        (App.get_running_app() is not None) and (EventLoop.status == "started")
    )

    def _show(*_args: object) -> None:
        # All of it once the popup has left the window, not when its dismissal began:
        # Kivy fades a dismissed popup out first, and a caller's `on_dismiss` (the About
        # box's return to menu mode) must find the window clear. The temporary loop stops last:
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
        scroll_view = getattr(content, "scroll_view", None)
        if scroll_view is not None:
            popup.key_handler = scroll_keys(scroll_view)
        popup.bind(on_open=lambda *_: log_popup_opened(title))
        if timeout > 0:
            Clock.schedule_once(lambda _dt: popup.dismiss(), timeout)
        popup.open()

    try:
        # The Windows build's splash would otherwise sit beside the message.
        close_boot_splash()
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
