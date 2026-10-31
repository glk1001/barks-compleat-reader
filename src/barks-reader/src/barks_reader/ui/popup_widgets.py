"""The app's confirm and message popups, opened on the shared frame (``ui.popup_frame``)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kivy.app import App
from kivy.clock import Clock
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.popup_frame import FrameButton, PopupSize

from .popup_frame import PopupFrame, message_body

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.label import Label

    from .font_manager import FontManager

# A question's text, short and alone in a small popup, is set this much larger.
QUESTION_FONT_SCALE = 1.35


@dataclass(frozen=True, slots=True)
class _Markers:
    """The lines a popup logs: a confirm popup's, or a message popup's."""

    opened: str
    confirmed: str
    cancelled: str
    closed: str


_CONFIRM_MARKERS = _Markers(
    log_markers.CONFIRM_POPUP_OPENED,
    log_markers.CONFIRM_POPUP_CONFIRMED,
    log_markers.CONFIRM_POPUP_CANCELLED,
    log_markers.CONFIRM_POPUP_CLOSED,
)
_MESSAGE_MARKERS = _Markers(
    log_markers.MESSAGE_POPUP_OPENED,
    log_markers.MESSAGE_POPUP_OK,
    log_markers.MESSAGE_POPUP_CANCELLED,
    log_markers.MESSAGE_POPUP_CLOSED,
)


def open_confirm_popup(
    *,
    title: str,
    text: str,
    ok_text: str,
    cancel_text: str,
    on_ok: Callable[[], None],
    bg_image: str = "",
    on_cancel: Callable[[], None] | None = None,
) -> PopupFrame:
    """Open a confirmation popup on the shared frame (``ui.popup_frame``).

    The frame's keys work it with a 6-button remote: Left/Right move the focus ring
    between the two buttons (the confirming one starts focused), Enter presses the
    focused one, and Escape always cancels.

    Args:
        title: The popup window title.
        text: The confirmation question to show.
        ok_text: Label of the confirming button.
        cancel_text: Label of the cancelling button.
        on_ok: Called after dismissal when the user confirms.
        bg_image: Optional path of artwork to show behind the message.
        on_cancel: Called after dismissal when the user declines, or None.

    Returns:
        The opened popup.

    """
    fm = _font_manager()
    frame = _logged_frame(
        _CONFIRM_MARKERS,
        title=title,
        body=message_body(
            text, font_size=QUESTION_FONT_SCALE * fm.error_popup_font_size, centred=True
        ),
        size=PopupSize.SMALL,
        ok=(ok_text, on_ok),
        cancel=(cancel_text, on_cancel),
        art_file=bg_image,
    )
    frame.open()
    logger.debug(_CONFIRM_MARKERS.opened.format(title=title))
    return frame


def open_message_popup(
    *,
    title: str,
    text: str,
    ok_text: str,
    on_ok: Callable[[], None] | None,
    cancel_text: str,
    on_cancel: Callable[[], None] | None,
    centred: bool = False,
) -> PopupFrame:
    """Open a message popup (the error popups) on the shared frame, one frame from now.

    The same keys as the confirm popup: Left/Right move the focus ring between
    the buttons it shows (the first starts focused), Enter presses the focused
    one and Escape is its cancel. A popup with no ok_text has only its cancel
    button, which Enter and Escape both press.

    Args:
        title: The popup window title.
        text: The message.
        ok_text: Label of the first button, or "" for none.
        on_ok: Called after dismissal when that button is pressed.
        cancel_text: Label of the cancelling button.
        on_cancel: Called after dismissal on cancel, or None.
        centred: Whether the message is centred (a short notice) rather than
            left-aligned (prose).

    Returns:
        The popup, opened on the next frame (to avoid graphics issues at startup).

    """
    frame = _logged_frame(
        _MESSAGE_MARKERS,
        title=title,
        body=message_body(text, font_size=_font_manager().error_popup_font_size, centred=centred),
        size=PopupSize.MEDIUM,
        ok=(ok_text, on_ok),
        cancel=(cancel_text, on_cancel),
    )

    def _open(_dt: float) -> None:
        frame.open()
        logger.debug(_MESSAGE_MARKERS.opened.format(title=title))

    Clock.schedule_once(_open, 0)
    return frame


def _font_manager() -> FontManager:
    # pyrefly: ignore[missing-attribute]  # a popup opens only in the running app.
    return App.get_running_app().font_manager


def _logged_frame(
    markers: _Markers,
    *,
    title: str,
    body: Label,
    size: PopupSize,
    ok: tuple[str, Callable[[], None] | None],
    cancel: tuple[str, Callable[[], None] | None],
    art_file: str = "",
) -> PopupFrame:
    """Return a frame whose buttons, ok (if it has a label) then cancel, log their press.

    The closing line is logged once the frame has left the window, not when its
    dismissal began: Kivy fades a dismissed popup out before removing it, and the
    main screen ignores every key while a modal is still on the window, so a driver
    that pressed its next key on the dismissal line lost it whenever the fade
    outlasted the key gap.
    """
    ok_text, on_ok = ok
    cancel_text, on_cancel = cancel

    def _confirmed() -> None:
        logger.info(markers.confirmed.format(title=title, button=ok_text))
        if on_ok is not None:
            on_ok()

    def _cancelled() -> None:
        logger.info(markers.cancelled.format(title=title))
        if on_cancel is not None:
            on_cancel()

    fm = _font_manager()
    buttons = [FrameButton(ok_text, _confirmed)] if ok_text else []
    buttons.append(FrameButton(cancel_text, _cancelled))
    return PopupFrame(
        title=title,
        body=body,
        size=size,
        buttons=buttons,
        art_file=art_file,
        on_closed=lambda: logger.debug(markers.closed.format(title=title)),
        title_font_size=fm.message_title_size,
        button_font_size=fm.error_popup_button_font_size,
    )
