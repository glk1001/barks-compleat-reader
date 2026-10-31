"""The frame every popup the app owns is built on (``docs/plans/popup-consistency.md``).

One look, from the standalone family's: a warm-dark title bar with the title in the
theme's title colour, and under it a dark card, with art beneath a scrim if the popup
has art, holding the popup's body and a row of buttons along the bottom, right-aligned.
A popup with no buttons has a close X in its title bar instead. The frame is centred,
sized by its class (``core/popup_frame.py``), and follows the window as it resizes; a
popup that is its own window's only content fills that window instead.

The remote's six keys work it as they work the confirm popups: Left and Right move the
focus ring along the buttons, Return presses the focused one, Escape presses the last
that closes the popup (the cancel). A popup with no buttons closes on Return; Escape
lands on its close X first, as everywhere in the app, and Return there closes it. Every
key is kept while the frame is open.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty, StringProperty  # ty: ignore[unresolved-import]
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.widget import Widget

from barks_reader.core.keys import KEY_ENTER, KEY_LEFT, KEY_NUMPAD_ENTER, KEY_RIGHT, is_escape_key
from barks_reader.core.popup_frame import FrameButton, PopupSize, popup_size
from barks_reader.core.reader_palette import theme

from .kivy_standalone_show_message import closes_popup
from .reader_keyboard_nav import (
    MENU_FOCUS_HIGHLIGHT_GROUP,
    clear_focus_highlight,
    draw_focus_highlight,
    update_focus_in_list,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

# The title bar: the standalone family's warm near-black, two bands for a gradient.
TITLE_BAR_HEIGHT = dp(56)
TITLE_BAR_TOP = (0.10, 0.09, 0.08, 1.0)
TITLE_BAR_BOTTOM = (0.14, 0.12, 0.10, 1.0)
TITLE_FONT_SIZE = sp(18)
CLOSE_BUTTON_WIDTH = dp(44)

# The card: a solid warm dark, and over any art a scrim dark enough for cream text.
CARD_BACKING = (0.14, 0.12, 0.10, 1.0)
CARD_SCRIM = (0.10, 0.09, 0.08, 0.62)
CARD_PADDING = dp(18)

# The button row.
BUTTON_HEIGHT = dp(48)
BUTTON_MIN_WIDTH = dp(130)
BUTTON_TEXT_PADDING = dp(32)
BUTTON_SPACING = dp(12)
BUTTON_FONT_SIZE = sp(16)
BUTTON_BACKGROUND = (0.26, 0.23, 0.20, 1.0)

_FOCUS_GROUP = "popup_frame_focus"


def message_body(text: str, *, font_size: float, centred: bool = False) -> Label:
    """Return the frame's body text: prose left-aligned, a short question centred.

    Args:
        text: The message, with Kivy markup.
        font_size: Its font size.
        centred: Whether it is centred (a question) rather than left-aligned (prose).

    Returns:
        The label, wrapping to the card's width.

    """
    label = Label(
        text=text,
        markup=True,
        font_size=font_size,
        color=list(theme().text_secondary),
        halign="center" if centred else "left",
        valign="middle",
    )
    label.bind(size=_wrap_to_size)
    return label


def _wrap_to_size(label: Label, size: tuple[float, float]) -> None:
    label.text_size = size


class PopupFrame(ModalView):
    """A popup on the shared frame: a title, a body, and buttons or a close X."""

    # The title bar's text; set it to show a moment's news there (Saved, Copied).
    title = StringProperty()
    title_font_size = NumericProperty(TITLE_FONT_SIZE)

    def __init__(
        self,
        *,
        title: str,
        body: Widget,
        size: PopupSize = PopupSize.MEDIUM,
        buttons: Sequence[FrameButton] = (),
        art_file: str = "",
        on_closed: Callable[[], None] | None = None,
        title_font_size: float = TITLE_FONT_SIZE,
        button_font_size: float = BUTTON_FONT_SIZE,
        fill_window: bool = False,
        title_markup: bool = False,
        title_font_name: str = "",
        close_on_outside_tap: bool = False,
    ) -> None:
        """Build the frame; `open()` shows it.

        Args:
            title: The title bar's text.
            body: The popup's own content, above the button row.
            size: The frame's size class.
            buttons: The row's buttons, left to right, the last being the cancel; none
                puts a close X in the title bar.
            art_file: Art to show beneath the card's scrim, or "" for none.
            on_closed: Called once the frame has left the window, however it closed.
            title_font_size: The title's font size.
            button_font_size: The buttons' font size.
            fill_window: Whether the frame fills the window, as a popup does that is its
                own window's only content, rather than being sized by its class.
            title_markup: Whether the title carries Kivy markup.
            title_font_name: The title's font, or "" for the app's.
            close_on_outside_tap: Whether a tap outside the frame closes it, as it does
                a popup browsed beside the screen it came from (the speech bubbles).

        """
        super().__init__(
            size_hint=(1, 1) if fill_window else (None, None),
            pos_hint={"center_x": 0.5, "center_y": 0.5},
            auto_dismiss=close_on_outside_tap,
            background="",
            background_color=(0, 0, 0, 0),
        )
        self.title = title
        self.title_font_size = title_font_size
        self.size_class = size
        self.fill_window = fill_window
        self._frame_buttons = tuple(buttons)
        self._on_closed = on_closed
        self._focused_idx = 0  # the first button, the confirming one, starts focused
        self._close_button: Button | None = None
        self._close_focused = False
        # Asked first about every key, by a body that takes keys of its own (a list's
        # Up and Down); what it does not take, the frame does.
        self.key_handler: Callable[[int], bool] | None = None
        self._body = body

        self._button_widgets = [self._button(b, button_font_size) for b in self._frame_buttons]
        root = BoxLayout(orientation="vertical")
        root.add_widget(self._title_bar(title_markup, title_font_name))
        root.add_widget(self._card(body, art_file))
        self.add_widget(root)

        self.fit_to_window()
        self.bind(
            on_pre_open=self._on_pre_open, on_dismiss=self._on_dismiss, parent=self._on_parent
        )

    @property
    def button_widgets(self) -> list[Button]:
        """The row's buttons, left to right."""
        return self._button_widgets

    @property
    def body(self) -> Widget:
        """The popup's own content."""
        return self._body

    def set_body(self, body: Widget) -> None:
        """Put `body` in the place of the popup's content, for a popup shown again."""
        content = self._body.parent
        assert content is not None
        content.remove_widget(self._body)
        content.add_widget(body, index=len(content.children))  # above the button row
        self._body = body

    def fit_to_window(self, *_args: object) -> None:
        """Size the frame by its class for the window as it is now (unless it fills it)."""
        if not self.fill_window:
            self.size = popup_size(self.size_class, Window.width, Window.height)

    def _title_bar(self, markup: bool, font_name: str) -> BoxLayout:
        bar = BoxLayout(
            size_hint_y=None, height=TITLE_BAR_HEIGHT, padding=[dp(12), dp(8)], spacing=dp(8)
        )
        # pyrefly: ignore[missing-attribute]  # Kivy sets `canvas` in Widget.__init__.
        with bar.canvas.before:  # ty: ignore[unresolved-attribute]
            Color(*TITLE_BAR_BOTTOM)
            bottom = Rectangle()
            Color(*TITLE_BAR_TOP)
            top = Rectangle()

        def fit_bands(widget: Widget, *_args: object) -> None:
            half = widget.height / 2
            bottom.pos, bottom.size = widget.pos, (widget.width, half)
            top.pos, top.size = (widget.x, widget.y + half), (widget.width, half)

        bar.bind(pos=fit_bands, size=fit_bands)

        title_label = Label(
            text=self.title,
            markup=markup,
            color=list(theme().text_title),
            font_size=self.title_font_size,
            bold=True,
            halign="left",
            valign="middle",
        )
        if font_name:
            title_label.font_name = font_name
        title_label.bind(size=_wrap_to_size)
        self.bind(title=title_label.setter("text"), title_font_size=title_label.setter("font_size"))
        bar.add_widget(title_label)
        if not self._frame_buttons:
            close = Button(
                text="X",
                size_hint_x=None,
                width=CLOSE_BUTTON_WIDTH,
                background_normal="",
                background_color=[*theme().danger[:3], 0.85],
                color=[1, 1, 1, 1],
                font_size=sp(16),
            )
            close.bind(on_release=lambda *_: self.dismiss())
            bar.add_widget(close)
            self._close_button = close
        return bar

    def _card(self, body: Widget, art_file: str) -> FloatLayout:
        card = FloatLayout()
        # pyrefly: ignore[missing-attribute]  # Kivy sets `canvas` in Widget.__init__.
        with card.canvas.before:  # ty: ignore[unresolved-attribute]
            Color(*CARD_BACKING)
            backing = Rectangle()
        card.bind(pos=lambda _w, pos: setattr(backing, "pos", pos))
        card.bind(size=lambda _w, size: setattr(backing, "size", size))

        whole = {"x": 0, "y": 0}
        if art_file:
            card.add_widget(Image(source=art_file, fit_mode="cover", mipmap=True, pos_hint=whole))
        scrim = Widget(pos_hint=whole)
        # pyrefly: ignore[missing-attribute]  # Kivy sets `canvas` in Widget.__init__.
        with scrim.canvas.before:  # ty: ignore[unresolved-attribute]
            Color(*CARD_SCRIM)
            scrim_rect = Rectangle()
        scrim.bind(pos=lambda _w, pos: setattr(scrim_rect, "pos", pos))
        scrim.bind(size=lambda _w, size: setattr(scrim_rect, "size", size))
        card.add_widget(scrim)

        content = BoxLayout(
            orientation="vertical", padding=CARD_PADDING, spacing=CARD_PADDING, pos_hint=whole
        )
        content.add_widget(body)
        if self._button_widgets:
            row = BoxLayout(size_hint_y=None, height=BUTTON_HEIGHT, spacing=BUTTON_SPACING)
            row.add_widget(Widget())  # the buttons sit at the right
            for button in self._button_widgets:
                row.add_widget(button)
            content.add_widget(row)
        card.add_widget(content)
        return card

    def _button(self, frame_button: FrameButton, font_size: float) -> Button:
        button = Button(
            text=frame_button.text,
            size_hint_x=None,
            width=BUTTON_MIN_WIDTH,
            font_size=font_size,
            bold=frame_button is self._frame_buttons[0],
            background_normal="",
            background_color=list(BUTTON_BACKGROUND),
            color=list(theme().text_secondary),
        )
        button.bind(texture_size=_fit_button_width)
        button.bind(on_release=lambda *_: self._press(frame_button))
        return button

    def _press(self, frame_button: FrameButton) -> None:
        if frame_button.closes:
            self.dismiss()
        frame_button.on_press()

    def _press_cancel(self) -> None:
        closing = [b for b in self._frame_buttons if b.closes]
        if closing:
            self._press(closing[-1])
        else:
            self.dismiss()

    def _toggle_close_focus(self) -> None:
        assert self._close_button is not None
        if self._close_focused:
            clear_focus_highlight(self._close_button, MENU_FOCUS_HIGHLIGHT_GROUP)
        else:
            draw_focus_highlight(self._close_button, MENU_FOCUS_HIGHLIGHT_GROUP)
        self._close_focused = not self._close_focused

    def _show_focus(self) -> None:
        update_focus_in_list(self._button_widgets, self._focused_idx, _FOCUS_GROUP)

    def _on_pre_open(self, *_args: object) -> None:
        # Before the fade-in, not after it: the screen beneath already yields every key
        # to an open modal, so a key pressed while it faded in would reach no one.
        Window.bind(on_key_down=self._on_key_down, size=self.fit_to_window)
        if self._button_widgets:
            self._show_focus()

    def _on_dismiss(self, *_args: object) -> bool:
        Window.unbind(on_key_down=self._on_key_down, size=self.fit_to_window)
        return False

    def _on_parent(self, _frame: object, parent: object) -> None:
        if parent is None and self._on_closed is not None:
            self._on_closed()

    def _on_key_down(
        self, _win: object, key: int, _scancode: int, _codepoint: str, _modifiers: list[str]
    ) -> bool:
        if self.key_handler is not None and self.key_handler(key):
            return True
        if not self._frame_buttons:
            if is_escape_key(key):
                self._toggle_close_focus()  # Escape to the X, as everywhere; again, away
            elif closes_popup(key):
                self.dismiss()
        elif key in (KEY_RIGHT, KEY_LEFT):
            step = 1 if key == KEY_RIGHT else -1
            self._focused_idx = (self._focused_idx + step) % len(self._frame_buttons)
            self._show_focus()
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._press(self._frame_buttons[self._focused_idx])
        elif is_escape_key(key):
            self._press_cancel()
        return True  # the frame is modal: no key reaches the screen beneath it


def _fit_button_width(button: Button, texture_size: tuple[float, float]) -> None:
    button.width = max(BUTTON_MIN_WIDTH, texture_size[0] + BUTTON_TEXT_PADDING)
