"""The popup frame's size classes, buttons and keys, free of Kivy.

Every popup the app owns is one of three sizes (``docs/plans/popup-consistency.md``).
A size is measured in comic pages across and in the window's height down, a page being
the window's height over the page aspect, as the two-page spread lays its pages out
(``core/main_layout.py``). So a popup comes out the same size on the single page and on
the spread at the same height, as the fonts do (they are sized from the height alone),
rather than stretching across the spread's two pages.

What each key does to a frame (`frame_key_action`), where the focus goes along its
row of buttons (`focus_after_step`) and which button Escape presses (`cancel_button`)
are here too; the frame (``ui/popup_frame.py``) keeps the widgets and does it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum, auto
from typing import TYPE_CHECKING

from .focus_cursors import clamped, wrapped
from .keys import (
    KEY_ENTER,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    is_escape_key,
    is_escape_key_for_text_input,
)
from .main_layout import page_width_at
from .reader_utils import COMIC_PAGE_ASPECT_RATIO

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


def closes_popup(key: int) -> bool:
    """Return whether a key closes a standalone popup: Escape, or Return as "OK".

    A standalone popup is a message with only a close button, and that button
    takes no keyboard focus, so with the remote's keys Return would otherwise do
    nothing.
    """
    return is_escape_key(key) or key in (KEY_ENTER, KEY_NUMPAD_ENTER)


class PopupSize(StrEnum):
    """A popup's size class."""

    SMALL = "small"  # a question: Quit, Delete, Clear
    MEDIUM = "medium"  # a message, an error, a setting
    LARGE = "large"  # a long list or text: About, speech bubbles, the installers


@dataclass(frozen=True, slots=True)
class FrameButton:
    """A button on the frame's row: its label, and what pressing it does.

    A button closes the popup before its action runs, unless it is one that leaves the
    popup up (Save to File, Copy to Clipboard). Free of Kivy, so the popups that are
    their own window can name their buttons before Kivy is imported.
    """

    text: str
    on_press: Callable[[], None]
    closes: bool = True


class FrameKeyAction(Enum):
    """What a key does to an open frame."""

    LEFT_TO_THE_TEXT_BOX = auto()  # typed into the box that has the keyboard
    FOCUS_LEFT = auto()
    FOCUS_RIGHT = auto()
    PRESS_FOCUSED = auto()  # the ringed button, if the row has the focus
    CANCEL = auto()  # the last button that closes; the frame itself if none does
    TOGGLE_CLOSE_FOCUS = auto()  # the ring onto the close X, or off it
    CLOSE = auto()
    NOTHING = auto()  # kept from the screen beneath, and that is all


def frame_key_action(
    key: int, codepoint: str | None, *, typing: bool, has_buttons: bool, closable: bool
) -> FrameKeyAction:
    """Return what `key` does to a frame, after a body's own key handler has passed on it.

    Args:
        key: The key's code.
        codepoint: The character it types, if any.
        typing: Whether a text box in the frame has the keyboard. Every key is then
            the box's but Escape, which still cancels.
        has_buttons: Whether the frame has a row of buttons. Left and Right then move
            along it, Return presses the focused one and Escape cancels.
        closable: Whether a frame with no buttons can be closed by a key: Escape lands
            on its close X first, as everywhere in the app, and Return closes it.

    Returns:
        The action. Only a key left to the text box reaches anything but the frame.

    """
    if typing and not is_escape_key_for_text_input(key, codepoint):
        return FrameKeyAction.LEFT_TO_THE_TEXT_BOX
    if not has_buttons:
        return _key_action_with_no_buttons(key, closable=closable)
    if key in (KEY_LEFT, KEY_RIGHT):
        return FrameKeyAction.FOCUS_RIGHT if key == KEY_RIGHT else FrameKeyAction.FOCUS_LEFT
    if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
        return FrameKeyAction.PRESS_FOCUSED
    return FrameKeyAction.CANCEL if is_escape_key(key) else FrameKeyAction.NOTHING


def _key_action_with_no_buttons(key: int, *, closable: bool) -> FrameKeyAction:
    if not closable:
        return FrameKeyAction.NOTHING  # no key closes it: what opened it does
    if is_escape_key(key):
        return FrameKeyAction.TOGGLE_CLOSE_FOCUS
    return FrameKeyAction.CLOSE if closes_popup(key) else FrameKeyAction.NOTHING


def focus_after_step(focused: int | None, step: int, count: int, *, wrap: bool) -> int:
    """Return the button the focus is on after Left (-1) or Right (1) along a row of `count`.

    Onto the row from outside it (`focused` None), the focus lands at the row's near
    end. Along it, the focus goes round from one end to the other where the row wraps,
    and stops at the end where it does not.
    """
    if focused is None:
        return 0 if step > 0 else count - 1
    return wrapped(focused, step, count) if wrap else clamped(focused + step, count)


def cancel_button(buttons: Sequence[FrameButton]) -> FrameButton | None:
    """Return the button Escape presses: the last that closes the popup; None if none does."""
    return next((button for button in reversed(buttons) if button.closes), None)


@dataclass(frozen=True, slots=True)
class SizeClass:
    """A size class: its width in pages, its height as a fraction of the window's."""

    pages_wide: float
    window_high: float


SIZE_CLASSES: dict[PopupSize, SizeClass] = {
    PopupSize.SMALL: SizeClass(pages_wide=0.70, window_high=0.28),
    PopupSize.MEDIUM: SizeClass(pages_wide=0.85, window_high=0.42),
    PopupSize.LARGE: SizeClass(pages_wide=0.95, window_high=0.80),
}

# However wide a page would be, a popup leaves this much of a narrow window showing.
MAX_WINDOW_WIDTH_FRACTION = 0.95


def popup_size(
    size: PopupSize,
    window_width: float,
    window_height: float,
    page_aspect_ratio: float = COMIC_PAGE_ASPECT_RATIO,
) -> tuple[float, float]:
    """Return a popup's width and height on a window of the given size.

    Args:
        size: The popup's size class.
        window_width: The window's width.
        window_height: The window's height.
        page_aspect_ratio: A page's height over its width.

    Returns:
        The popup's width and height, in the window's units.

    """
    size_class = SIZE_CLASSES[size]
    page_width = page_width_at(window_height, page_aspect_ratio)
    width = min(size_class.pages_wide * page_width, MAX_WINDOW_WIDTH_FRACTION * window_width)
    return width, size_class.window_high * window_height
