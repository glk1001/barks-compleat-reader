from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.core.window import Keyboard, Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
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

from .reader_keyboard_nav import update_focus_in_list

_FOCUS_GROUP = "alt_escape_capture_focus"
_CLEAR, _CANCEL = 0, 1

if TYPE_CHECKING:
    from collections.abc import Callable


def keycode_to_name(keycode: int) -> str:
    if keycode == 0:
        return "<unset>"
    for name, code in Keyboard.keycodes.items():
        if code == keycode:
            return name.capitalize()
    return f"key {keycode}"


class AltEscapeCapturePopup(Popup):
    """Popup that captures a single keypress to use as an alternate Escape key.

    The remote's own keys are not captured, since each has work of its own: Escape
    cancels, Left and Right move between the Clear and Cancel buttons and Enter
    presses the one focused (Cancel to start), Up and Down do nothing. So "Clear"
    is reached by remote, and no key the navigation needs can be bound as Escape.
    """

    def __init__(
        self,
        current_keycode: int,
        on_capture: Callable[[int], None],
        on_clear: Callable[[], None],
        **kwargs: object,
    ) -> None:
        layout = BoxLayout(orientation="vertical", spacing=10, padding=15)
        message = Label(
            text=(
                "Press the key to use as an alternate Escape.\n"
                "Escape cancels; Left, Right and Enter work the buttons.\n\n"
                f"Current: {keycode_to_name(current_keycode)}"
            ),
            halign="center",
        )
        buttons = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=10)
        clear_btn = Button(text="Clear (unset)")
        cancel_btn = Button(text="Cancel")
        buttons.add_widget(clear_btn)
        buttons.add_widget(cancel_btn)
        layout.add_widget(message)
        layout.add_widget(buttons)

        super().__init__(
            title="Alternate Escape Key",
            content=layout,
            size_hint=(0.6, 0.4),
            auto_dismiss=False,
            **kwargs,
        )

        self._on_capture = on_capture
        self._on_clear = on_clear
        self._captured = False
        self._buttons = [clear_btn, cancel_btn]
        self._focused_btn = _CANCEL  # a slip of the hand must not clear the key

        clear_btn.bind(on_release=self._handle_clear)
        cancel_btn.bind(on_release=lambda *_a: self._cancel())

        Window.bind(on_key_down=self._on_key_down)
        self.bind(on_dismiss=self._unbind_window)
        self.bind(on_open=lambda *_a: self._on_opened(current_keycode))

    def _on_opened(self, current_keycode: int) -> None:
        logger.debug(
            log_markers.ALT_ESCAPE_CAPTURE_OPENED.format(name=keycode_to_name(current_keycode))
        )
        self._draw_button_focus()

    def _draw_button_focus(self) -> None:
        update_focus_in_list(self._buttons, self._focused_btn, _FOCUS_GROUP)

    def _cancel(self) -> None:
        logger.info(log_markers.ALT_ESCAPE_CAPTURE_CANCELLED)
        self.dismiss()

    def _unbind_window(self, *_args: object) -> bool:
        Window.unbind(on_key_down=self._on_key_down)
        return False

    def _handle_clear(self, *_args: object) -> None:
        self._captured = True
        logger.info(log_markers.ALT_ESCAPE_CLEARED)
        self._on_clear()
        self.dismiss()

    def _on_key_down(
        self, _win: object, key: int, _scancode: int, _codepoint: str, _modifiers: list[str]
    ) -> bool:
        if self._captured:
            return False
        if key == KEY_ESCAPE:
            self._cancel()
            return True
        if key in (KEY_LEFT, KEY_RIGHT):
            self._focused_btn = _CLEAR if key == KEY_LEFT else _CANCEL
            self._draw_button_focus()
            return True
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._buttons[self._focused_btn].trigger_action(duration=0)
            return True
        if key in (KEY_UP, KEY_DOWN):
            return True  # the remote's keys are not for capture: each has its own work
        self._captured = True
        logger.info(log_markers.ALT_ESCAPE_CAPTURED.format(name=keycode_to_name(key), keycode=key))
        self._on_capture(key)
        self.dismiss()
        return True
