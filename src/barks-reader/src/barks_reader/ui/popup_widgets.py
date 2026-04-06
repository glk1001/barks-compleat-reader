from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from kivy.properties import (  # ty: ignore[unresolved-import]
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.popup import Popup

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
