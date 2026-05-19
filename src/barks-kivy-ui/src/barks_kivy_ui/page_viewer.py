"""Reusable Kivy per-page image viewer with arrow-key + click navigation."""

from collections.abc import Callable

from kivy.app import App
from kivy.core.image import Texture
from kivy.core.window import Window
from kivy.input.motionevent import MotionEvent
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image as KivyImage
from kivy.uix.label import Label
from PIL import Image

KEY_RIGHT = 275
KEY_LEFT = 276


def pil_to_texture(pil: Image.Image) -> Texture:
    """Upload an RGBA PIL image to a Kivy ``Texture``, flipped to Kivy's Y-up convention."""
    tex = Texture.create(size=pil.size)
    tex.blit_buffer(pil.tobytes(), colorfmt="rgba", bufferfmt="ubyte")
    tex.flip_vertical()

    return tex


class ClickNavLayout(BoxLayout):
    """BoxLayout that splits left-mouse clicks: left of centre vs right of centre."""

    def __init__(
        self,
        on_left_click: Callable[[], None],
        on_right_click: Callable[[], None],
        **kwargs,  # noqa: ANN003
    ) -> None:
        super().__init__(**kwargs)
        self._on_left_click = on_left_click
        self._on_right_click = on_right_click

    def on_touch_down(self, touch: MotionEvent) -> bool:
        # Let children intercept first (e.g. draggable overlay labels).
        if super().on_touch_down(touch):
            return True
        if not self.collide_point(*touch.pos):
            return False
        if getattr(touch, "button", "left") != "left":
            return False
        if touch.x < self.center_x:
            self._on_left_click()
        else:
            self._on_right_click()
        return True


class KivyPageViewer(App):
    """Reusable per-page image viewer with arrow-key + click navigation."""

    def __init__(
        self,
        *,
        window_title: str,
        pages: list[tuple[str, Image.Image]],
        start_page: int,
        win_left: int,
        win_top: int,
        win_size: tuple[int, int] = (900, 1300),
    ) -> None:
        super().__init__()
        self._window_title = window_title
        self._pages = pages
        self._index = max(0, min(len(pages) - 1, start_page - 1))
        self._win_left = win_left
        self._win_top = win_top
        self._win_size = win_size
        self._page_label: Label | None = None
        self._image_widget: KivyImage | None = None

    def build(self) -> BoxLayout:
        self.title = self._window_title
        Window.size = self._win_size
        Window.left = self._win_left
        Window.top = self._win_top

        root = ClickNavLayout(
            on_left_click=lambda: self._go(-1),
            on_right_click=lambda: self._go(+1),
            orientation="vertical",
        )

        self._page_label = Label(size_hint_y=None, height=30)
        self._image_widget = KivyImage(allow_stretch=True, keep_ratio=True)

        root.add_widget(self._page_label)
        root.add_widget(self._image_widget)

        Window.bind(on_key_down=self._on_key_down)
        self._show_current()

        return root

    def _on_key_down(
        self,
        _window: object,
        key: int,
        _scancode: int,
        _codepoint: str | None,
        _modifiers: list,
    ) -> bool:
        if key == KEY_LEFT:
            self._go(-1)
            return True
        if key == KEY_RIGHT:
            self._go(+1)
            return True
        return False

    def _go(self, delta: int) -> None:
        new_index = self._index + delta
        if 0 <= new_index < len(self._pages):
            self._index = new_index
            self._show_current()

    def _show_current(self) -> None:
        fanta_page, pil_image = self._pages[self._index]
        assert self._page_label is not None
        assert self._image_widget is not None

        self._page_label.text = (
            f"Page {self._index + 1} of {len(self._pages)}   [fanta: {fanta_page}]"
        )
        self._image_widget.texture = pil_to_texture(pil_image)
