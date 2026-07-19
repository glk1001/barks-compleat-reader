from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kivy.core.window import Window
from kivy.properties import (  # ty: ignore[unresolved-import]
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.popup import Popup

from .reader_keyboard_nav import (
    KEY_ENTER,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    is_escape_key,
    update_focus_in_list,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.button import Button

_CONFIRM_FOCUS_GROUP = "confirm_popup_focus"

READER_POPUPS_KV_FILE = Path(__file__).parent / "reader_popups.kv"


class LoadingDataPopup(Popup):
    progress_bar_value = NumericProperty(0)
    splash_image_texture = ObjectProperty()


class MessagePopup(Popup):
    msg_text = StringProperty()
    ok_text = StringProperty()
    cancel_text = StringProperty()
    # Optional background artwork shown behind the message (empty = plain popup).
    bg_image_source = StringProperty("")
    # Multiplier on the standard message font size (e.g. 1.35 for the quit popup).
    msg_font_scale = NumericProperty(1.0)
    ok = ObjectProperty(None, allownone=True)
    cancel = ObjectProperty(None, allownone=True)

    def __init__(
        self,
        text: str,
        ok_func: Callable[[], None] | None,
        ok_text: str,
        cancel_func: Callable[[], None] | None,
        cancel_text: str,
        msg_halign: str,
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)

        self.msg_text = text
        self.ok_text = ok_text
        self.cancel_text = cancel_text
        self.msg_halign = msg_halign

        self.ok = ok_func
        self.cancel = cancel_func


def open_confirm_popup(
    *,
    title: str,
    text: str,
    ok_text: str,
    cancel_text: str,
    on_ok: Callable[[], None],
    bg_image: str = "",
) -> MessagePopup:
    """Open a keyboard-operable confirmation popup.

    While the popup is open it captures all key input: Left/Right move the
    focus ring between the two buttons (the confirming button starts focused),
    Enter activates the focused button, and Escape always cancels — so it
    works with a 6-button remote. The window key binding is removed again
    when the popup is dismissed.

    Args:
        title: The popup window title.
        text: The confirmation question to show.
        ok_text: Label of the confirming button.
        cancel_text: Label of the cancelling button.
        on_ok: Called after dismissal when the user confirms.
        bg_image: Optional path of artwork to show behind the message.

    Returns:
        The opened popup.

    """
    popup = MessagePopup(
        text=text,
        ok_func=None,
        ok_text=ok_text,
        cancel_func=None,
        cancel_text=cancel_text,
        title=title,
        msg_halign="center",
        bg_image_source=bg_image,
        msg_font_scale=1.35,
    )
    nav = _ConfirmPopupNav(popup, on_ok)
    popup.ok = nav.confirm
    popup.cancel = nav.cancel
    popup.open()
    nav.show_focus()
    return popup


class _ConfirmPopupNav:
    """Keyboard driver for a two-button confirmation popup.

    Owns the focus ring and the window key binding; the binding is removed
    when the popup is dismissed.
    """

    def __init__(self, popup: MessagePopup, on_ok: Callable[[], None]) -> None:
        self._popup = popup
        self._on_ok = on_ok
        self._buttons: list[Button] = [popup.ids.ok_button, popup.ids.cancel_button]
        self._focused_idx = 0  # The confirming button starts focused.
        Window.bind(on_key_down=self._on_key_down)
        popup.bind(on_dismiss=self._unbind_window)

    def confirm(self) -> None:
        self._popup.dismiss()
        self._on_ok()

    def cancel(self) -> None:
        self._popup.dismiss()

    def show_focus(self) -> None:
        update_focus_in_list(self._buttons, self._focused_idx, _CONFIRM_FOCUS_GROUP)

    def _move_focus(self, delta: int) -> None:
        self._focused_idx = (self._focused_idx + delta) % len(self._buttons)
        self.show_focus()

    def _activate_focused(self) -> None:
        if self._focused_idx == 0:
            self.confirm()
        else:
            self.cancel()

    def _on_key_down(
        self, _win: object, key: int, _scancode: int, _codepoint: str, _modifiers: list[str]
    ) -> bool:
        if key == KEY_RIGHT:
            self._move_focus(1)
        elif key == KEY_LEFT:
            self._move_focus(-1)
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._activate_focused()
        elif is_escape_key(key):
            self.cancel()
        # Consume every key while the popup is modal.
        return True

    def _unbind_window(self, *_args: object) -> bool:
        Window.unbind(on_key_down=self._on_key_down)
        return False
