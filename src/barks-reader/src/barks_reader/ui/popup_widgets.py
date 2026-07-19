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

from .reader_keyboard_nav import KEY_ENTER, KEY_NUMPAD_ENTER, is_escape_key

if TYPE_CHECKING:
    from collections.abc import Callable

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

    While the popup is open it captures all key input: Enter confirms, Escape
    cancels — so it works with a 6-button remote. The window key binding is
    removed again when the popup is dismissed.

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
    popup: MessagePopup | None = None

    def confirm() -> None:
        assert popup is not None
        popup.dismiss()
        on_ok()

    def cancel() -> None:
        assert popup is not None
        popup.dismiss()

    def on_key_down(
        _win: object, key: int, _scancode: int, _codepoint: str, _modifiers: list[str]
    ) -> bool:
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            confirm()
        elif is_escape_key(key):
            cancel()
        # Consume every key while the popup is modal.
        return True

    def unbind_window(*_args: object) -> bool:
        Window.unbind(on_key_down=on_key_down)
        return False

    popup = MessagePopup(
        text=text,
        ok_func=confirm,
        ok_text=ok_text,
        cancel_func=cancel,
        cancel_text=cancel_text,
        title=title,
        msg_halign="center",
        bg_image_source=bg_image,
    )
    Window.bind(on_key_down=on_key_down)
    popup.bind(on_dismiss=unbind_window)
    popup.open()
    return popup
