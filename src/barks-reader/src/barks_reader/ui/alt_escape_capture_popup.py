from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.core.window import Keyboard, Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from .reader_keyboard_nav import KEY_ESCAPE

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
    """Popup that captures a single keypress to use as an alternate Escape key."""

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
                "Press real Escape to cancel.\n\n"
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

        clear_btn.bind(on_release=self._handle_clear)
        cancel_btn.bind(on_release=lambda *_a: self.dismiss())

        Window.bind(on_key_down=self._on_key_down)
        self.bind(on_dismiss=self._unbind_window)

    def _unbind_window(self, *_args: object) -> bool:
        Window.unbind(on_key_down=self._on_key_down)
        return False

    def _handle_clear(self, *_args: object) -> None:
        self._captured = True
        self._on_clear()
        self.dismiss()

    def _on_key_down(
        self, _win: object, key: int, _scancode: int, _codepoint: str, _modifiers: list
    ) -> bool:
        if self._captured:
            return False
        if key == KEY_ESCAPE:
            self.dismiss()
            return True
        self._captured = True
        self._on_capture(key)
        self.dismiss()
        return True
