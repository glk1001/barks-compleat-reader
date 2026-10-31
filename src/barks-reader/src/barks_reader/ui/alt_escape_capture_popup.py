from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.core.window import Keyboard
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.keys import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_UP,
)
from barks_reader.core.popup_frame import FrameButton, PopupSize

from .popup_frame import PopupFrame, message_body

ALT_ESCAPE_POPUP_TITLE = "Alternate Escape Key"
# The keys the frame works the buttons with: never captured, each having its own work.
_FRAME_KEYS = (KEY_ESCAPE, KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_NUMPAD_ENTER)

if TYPE_CHECKING:
    from collections.abc import Callable


def keycode_to_name(keycode: int) -> str:
    if keycode == 0:
        return "<unset>"
    for name, code in Keyboard.keycodes.items():
        if code == keycode:
            return name.capitalize()
    return f"key {keycode}"


class AltEscapeCapturePopup(PopupFrame):
    """Popup that captures a single keypress to use as an alternate Escape key.

    On the shared frame (``ui.popup_frame``). The remote's own keys are not captured,
    since each has work of its own: Escape cancels, Left and Right move between the
    Clear and Cancel buttons and Enter presses the one focused (Cancel to start), Up
    and Down do nothing. So "Clear" is reached by remote, and no key the navigation
    needs can be bound as Escape.
    """

    def __init__(
        self,
        current_keycode: int,
        on_capture: Callable[[int], None],
        on_clear: Callable[[], None],
    ) -> None:
        super().__init__(
            title=ALT_ESCAPE_POPUP_TITLE,
            body=message_body(
                "Press the key to use as an alternate Escape.\n"
                "Escape cancels; Left, Right and Enter work the buttons.\n\n"
                f"Current: {keycode_to_name(current_keycode)}",
                centred=True,
            ),
            size=PopupSize.SMALL,
            buttons=(
                FrameButton("Clear (unset)", self._handle_clear),
                FrameButton("Cancel", self._cancel),
            ),
            first_focus=1,  # a slip of the hand must not clear the key
        )

        self._on_capture = on_capture
        self._on_clear = on_clear
        self._captured = False
        self.key_handler = self._capture
        self.bind(on_open=lambda *_a: self._on_opened(current_keycode))

    @staticmethod
    def _on_opened(current_keycode: int) -> None:
        logger.debug(
            log_markers.ALT_ESCAPE_CAPTURE_OPENED.format(name=keycode_to_name(current_keycode))
        )

    @staticmethod
    def _cancel() -> None:
        logger.info(log_markers.ALT_ESCAPE_CAPTURE_CANCELLED)

    def _handle_clear(self) -> None:
        self._captured = True
        logger.info(log_markers.ALT_ESCAPE_CLEARED)
        self._on_clear()

    def _capture(self, key: int) -> bool:
        """Capture any key but the frame's own; Up and Down do nothing.

        Asked before the frame, so the alternate Escape set now is captured again
        rather than cancelling: only the real Escape cancels.
        """
        if self._captured or key in _FRAME_KEYS:
            return False
        if key in (KEY_UP, KEY_DOWN):
            return True  # the remote's keys are not for capture: each has its own work
        self._captured = True
        logger.info(log_markers.ALT_ESCAPE_CAPTURED.format(name=keycode_to_name(key), keycode=key))
        self._on_capture(key)
        self.dismiss()
        return True
