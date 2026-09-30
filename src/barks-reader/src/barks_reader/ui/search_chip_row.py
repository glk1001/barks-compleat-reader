"""A row of chips of which one is picked: a search filter a remote can walk.

The word search's speaker filter now, and the era and "only in tagged stories"
filters to come (docs/plans/advanced-search.md). The row owns its chips, the one
picked, and the keyboard while it has it: Left and Right walk the chips and Enter
picks the focused one, staying put so a filter can be tried out without losing
one's place. Every other way out it hands back as a `RowKey` for the screen to
route, since only the screen knows what lies above, below and beside the row.

The chips are the screen's own widgets, made by the factory it passes: their class
names are in the focus lines the app logs (``Nav focus on _SpeakerChipButton
"Donald"``), which the GUI tests wait on.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Protocol, cast

from barks_reader.core.reader_palette import theme

from .reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
    is_escape_key,
    log_nav_focus,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from kivy.uix.layout import Layout
    from kivy.uix.widget import Widget

    from barks_reader.core.reader_colors import Color

CHIP_BORDER_NONE: Color = (0, 0, 0, 0)

# Theme colors must be read lazily (the active theme is set after UI modules
# import), so chip colors are functions, not module constants.


def chip_bg_normal() -> Color:
    """Return a chip's fill when it is not picked."""
    return theme().tag_chip_bg


def chip_bg_active() -> Color:
    """Return a picked chip's fill."""
    return theme().accent_selection


def chip_border_focused() -> Color:
    """Return the border of the chip the keyboard is on."""
    return theme().focus_ring


class RowChip(Protocol):
    """What the row needs of a chip widget."""

    value: str
    chip_bg_color: Color
    chip_border_color: Color

    def bind(self, **kwargs: Callable[..., object]) -> None:
        """Bind event handlers (Kivy's ``bind``)."""
        ...

    def trigger_action(self, duration: float = 0.1) -> None:
        """Press the chip, as a click does."""
        ...


class RowKey(Enum):
    """What a key did on the row: handled there, not the row's, or a way out of it."""

    HANDLED = auto()
    UNHANDLED = auto()
    EXIT_LEFT = auto()
    EXIT_UP = auto()
    EXIT_DOWN = auto()
    EXIT_ESCAPE = auto()


class ChipRow:
    """One pick from a row of chips, by mouse, touch or the remote's arrows and Enter."""

    def __init__(
        self,
        layout: Layout,
        make_chip: Callable[[str, str], RowChip],
        on_select: Callable[[str], None],
        selected: str = "",
    ) -> None:
        """Make an empty row over `layout`.

        Args:
            layout: The widget the chips go in (a StackLayout, so they wrap).
            make_chip: Makes a chip from its value and label.
            on_select: Called with a chip's value when it is picked, after the row
                has marked it picked.
            selected: The value picked to begin with.

        """
        self._layout = layout
        self._make_chip = make_chip
        self._on_select = on_select
        self._selected = selected
        self._chips: list[RowChip] = []
        self._focused: int | None = None

    @property
    def chips(self) -> list[RowChip]:
        """The chips, in order."""
        return list(self._chips)

    @property
    def focused(self) -> int | None:
        """The index of the chip the keyboard is on, or None while the row does not have it."""
        return self._focused

    @property
    def selected(self) -> str:
        """The picked chip's value."""
        return self._selected

    def set_options(self, options: Sequence[tuple[str, str]]) -> None:
        """Replace the chips with one per ``(value, label)``; none empties the row."""
        self._layout.clear_widgets()
        self._chips = []
        self._focused = None
        for value, label in options:
            chip = self._make_chip(value, label)
            chip.bind(on_release=lambda _chip, v=value: self._pick(v))
            self._layout.add_widget(chip)
            self._chips.append(chip)
        self._recolor()

    def set_selected(self, value: str) -> None:
        """Mark `value` picked without telling the screen (a reset, say)."""
        self._selected = value
        self._recolor()

    def enter_focus(self, index: int | None = None) -> None:
        """Take the keyboard: on the chip at `index` (the last, past the end), or the picked one.

        Args:
            index: The chip to focus, or None for the picked chip (the first, if
                none is).

        """
        if index is None:
            index = next((i for i, c in enumerate(self._chips) if c.value == self._selected), 0)
        self._focused = index
        self._draw_focus()

    def clear_focus(self) -> None:
        """Give the keyboard up: no chip is bordered."""
        self._focused = None
        self._recolor()

    def handle_key(self, key: int) -> RowKey:
        """Act on a key while the row has the keyboard.

        Left and Right move along the chips (Left off the first is a way out;
        Right off the last stays put), Enter picks the focused chip and stays,
        and Up, Down or Tab, and Escape are ways out.

        Args:
            key: The key code.

        Returns:
            What the key did.

        """
        if key in (KEY_LEFT, KEY_RIGHT):
            return self._move(-1 if key == KEY_LEFT else 1)
        if key in (KEY_DOWN, KEY_TAB):
            return RowKey.EXIT_DOWN
        if key == KEY_UP:
            return RowKey.EXIT_UP
        if key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            if self._chips and self._focused is not None and self._focused < len(self._chips):
                self._chips[self._focused].trigger_action(duration=0)
                self._draw_focus()
            return RowKey.HANDLED
        if is_escape_key(key):
            return RowKey.EXIT_ESCAPE
        return RowKey.UNHANDLED

    def _move(self, step: int) -> RowKey:
        target = (self._focused or 0) + step
        if 0 <= target < len(self._chips):
            self._focused = target
            self._draw_focus()
            return RowKey.HANDLED
        return RowKey.EXIT_LEFT if target < 0 else RowKey.HANDLED

    def _pick(self, value: str) -> None:
        self._selected = value
        self._recolor()
        self._on_select(value)

    def _draw_focus(self) -> None:
        if not self._chips:
            return
        self._focused = min(self._focused or 0, len(self._chips) - 1)
        self._recolor()
        # The chips are the screen's widgets; RowChip names only what the row uses of them.
        log_nav_focus(cast("Widget", self._chips[self._focused]))

    def _recolor(self) -> None:
        """Fill the picked chip; border the focused one."""
        for i, chip in enumerate(self._chips):
            is_selected = chip.value == self._selected
            chip.chip_bg_color = chip_bg_active() if is_selected else chip_bg_normal()
            chip.chip_border_color = (
                chip_border_focused() if i == self._focused else CHIP_BORDER_NONE
            )
