from __future__ import annotations

from pathlib import Path

from kivy.app import App
from kivy.factory import Factory
from kivy.metrics import dp, sp
from kivy.properties import (  # ty: ignore[unresolved-import]
    BooleanProperty,
    ColorProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.floatlayout import FloatLayout

from barks_reader.ui.reader_ui_classes import ARROW_WIDTH, TouchExpandedButton

GOTO_TITLE_OVERLAY_KV_FILE = Path(__file__).with_suffix(".kv")

OVERLAY_ARROW_WIDTH = ARROW_WIDTH


class GotoTitleOverlay(FloatLayout):
    """A shared overlay widget containing a title label and arrow navigation button.

    Supports two position variants:
    - "bottom-right": label + up arrow in the bottom-right corner
    - "top-right": label + down arrow in the top-right corner
    """

    current_title_str = StringProperty("")
    show_title = BooleanProperty(defaultvalue=True)
    is_active = BooleanProperty(defaultvalue=True)
    label_color = ColorProperty((1, 1, 0, 1))
    label_opacity = NumericProperty(0.8)
    label_bg_color = ColorProperty((0.1, 0.1, 0.1, 0.5))
    arrow_direction = StringProperty("up")
    position = StringProperty("bottom-right")
    goto_button = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        self.register_event_type("on_arrow_press")
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget) -> None:  # noqa: ANN001, ARG002
        if self.position == "top-right":
            self._build_top_right()
        else:
            self._build_bottom_right()

    def on_arrow_press(self) -> None:
        pass

    def _get_arrow_source(self) -> str:
        sys_paths = App.get_running_app().reader_settings.sys_file_paths
        if self.arrow_direction == "up":
            return str(sys_paths.get_up_arrow_file())
        return str(sys_paths.get_down_arrow_file())

    def _create_button(self) -> TouchExpandedButton:
        button = TouchExpandedButton(
            source=self._get_arrow_source(),
            visual_size=OVERLAY_ARROW_WIDTH,
            is_active=self.is_active,
        )
        button.bind(on_press=lambda _inst: self.dispatch("on_arrow_press"))
        self.bind(is_active=button.setter("is_active"))
        self.goto_button = button
        return button

    def _create_label(self) -> Factory.BgColorLabel:
        label = Factory.BgColorLabel(
            text="[i]" + self.current_title_str + "[/i]",
            markup=True,
            color=self.label_color,
            font_size=sp(15),
            size_hint=(None, None),
        )
        label.background_color = self.label_bg_color
        label.sizing_factor_x = 1.07
        label.bind(texture_size=label.setter("size"))

        self.bind(
            current_title_str=lambda _inst, val: setattr(label, "text", "[i]" + val + "[/i]"),
        )
        self.bind(label_color=label.setter("color"))
        self.bind(label_bg_color=label.setter("background_color"))
        self.bind(show_title=lambda *_args: self._update_label_opacity(label))
        self.bind(label_opacity=lambda *_args: self._update_label_opacity(label))
        self._update_label_opacity(label)

        return label

    def _update_label_opacity(self, label: Factory.BgColorLabel) -> None:
        label.opacity = self.label_opacity if self.show_title else 0

    def _build_bottom_right(self) -> None:
        button = self._create_button()
        label = self._create_label()

        def update_button_pos(*_args: object) -> None:
            button.x = self.x + self.width - (1.4 * OVERLAY_ARROW_WIDTH) - button.touch_padding
            button.y = self.y + (0.4 * OVERLAY_ARROW_WIDTH) - button.touch_padding

        self.bind(pos=update_button_pos, size=update_button_pos)

        def update_label_pos(*_args: object) -> None:
            label.x = button.x - label.width - dp(5)
            label.y = button.y + button.touch_padding

        button.bind(pos=update_label_pos)
        label.bind(size=update_label_pos)

        self.add_widget(label)
        self.add_widget(button)

    def _build_top_right(self) -> None:
        button = self._create_button()
        label = self._create_label()

        def update_button_pos(*_args: object) -> None:
            button.x = self.x + self.width - (1.4 * OVERLAY_ARROW_WIDTH) - button.touch_padding
            button.y = self.y + self.height - OVERLAY_ARROW_WIDTH - button.touch_padding - dp(10)

        self.bind(pos=update_button_pos, size=update_button_pos)

        def update_label_pos(*_args: object) -> None:
            label.x = button.x - label.width - dp(5)
            label.y = button.y + button.touch_padding

        button.bind(pos=update_label_pos)
        label.bind(size=update_label_pos)

        self.add_widget(label)
        self.add_widget(button)
