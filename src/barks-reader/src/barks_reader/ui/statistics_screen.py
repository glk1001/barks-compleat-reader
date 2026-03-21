from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Callable

    from kivy.uix.widget import Widget

from kivy.clock import Clock
from kivy.factory import Factory
from kivy.properties import BooleanProperty  # ty: ignore[unresolved-import]
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.togglebutton import ToggleButton
from loguru import logger

from barks_reader.ui.reader_keyboard_nav import (
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    MENU_FOCUS_HIGHLIGHT_GROUP,
    DropdownNavMixin,
    clear_focus_in_list,
    update_focus_in_list,
)

STATISTICS_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

_STAT_ITEMS: list[tuple[str, str]] = [
    ("Stories per Year", "stories_per_year.png"),
    ("Pages per Year", "pages_per_year.png"),
    ("Payments per Year", "payments_per_year.png"),
    ("Payment Rate ($/page)", "payment_rate.png"),
    ("Stories per Series", "stories_per_series.png"),
    ("Top Characters", "top_characters.png"),
    ("Top Locations", "top_locations.png"),
]


class StatMenuButton(ToggleButton):
    """A tab button for the Statistics action bar."""

    def _do_press(self) -> None:
        """Prevent deselecting the active tab by suppressing press when already down."""
        if self.state == "normal":
            super()._do_press()


class StatisticsScreen(FloatLayout, DropdownNavMixin):
    """Screen that shows pre-rendered statistics PNG charts.

    A top action bar of StatMenuButton tabs lets the user choose which chart to
    display. The selected chart is shown as a Kivy Image below the bar.
    The first item is auto-selected whenever the screen becomes visible.
    The last button opens a dropdown for word-statistics sub-items.
    """

    is_visible = BooleanProperty(defaultvalue=False)

    def __init__(self, statistics_dir: Path, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self._statistics_dir = statistics_dir
        self._stat_buttons: list[StatMenuButton] = []
        self._word_stat_button: StatMenuButton | None = None
        self._word_stat_dropdown = None
        self._nav_active: bool = False
        self._nav_on_exit_request: Callable | None = None
        self._nav_focused_idx: int = 0
        self._setup_dropdown_nav()
        self._build_menu()

    def _build_menu(self) -> None:
        menu_layout = self.ids.stat_menu_layout
        for label, filename in _STAT_ITEMS:
            btn = StatMenuButton(text=label, group="stats")
            btn.bind(on_press=lambda _b, f=filename: self.show_stat(self._statistics_dir / f))
            menu_layout.add_widget(btn)
            self._stat_buttons.append(btn)

        word_stat_btn = StatMenuButton(text="Word Statistics", group="stats")
        word_stat_btn.bind(on_press=self._on_word_stat_button_pressed)
        menu_layout.add_widget(word_stat_btn)
        self._stat_buttons.append(word_stat_btn)
        self._word_stat_button = word_stat_btn

        self._word_stat_dropdown = Factory.WordStatDropDown()
        self._word_stat_dropdown.bind(on_select=self._on_word_stat_selected)
        self._word_stat_dropdown.bind(on_dismiss=self._on_dropdown_dismissed)

    def _on_word_stat_button_pressed(self, button: StatMenuButton) -> None:
        self._word_stat_dropdown.open(button)

    def _on_word_stat_selected(self, _dropdown: object, filename: str) -> None:
        if self._word_stat_button:
            self._word_stat_button.state = "down"
        self.show_stat(self._statistics_dir / filename)

    def on_is_visible(self, _instance: Self, value: bool) -> None:
        """Auto-select the first stat item when the screen becomes visible."""
        if value:
            self._on_screen_activated()

    def _on_screen_activated(self) -> None:
        if not self._stat_buttons:
            return
        self._stat_buttons[0].state = "down"
        _, filename = _STAT_ITEMS[0]
        self.show_stat(self._statistics_dir / filename)

    def show_stat(self, png_path: Path) -> None:
        """Load and display the given PNG in the image widget below the bar.

        Args:
            png_path: Absolute path to the statistics PNG image to display.

        """
        stat_image = self.ids.stat_image
        if png_path.is_file():
            logger.debug(f'Statistics: loading image "{png_path}".')
            stat_image.source = str(png_path)
            stat_image.reload()
        else:
            logger.warning(f'Statistics: image not found: "{png_path}".')
            stat_image.source = ""

    # --- DropdownNavMixin hooks ---

    def _get_dropdown_buttons(self) -> list:
        """Return dropdown buttons in visual top-to-bottom order."""
        # Kivy stores children in reverse order; reverse to get visual top-to-bottom.
        buttons = list(reversed(self._word_stat_dropdown.container.children))
        return [b for b in buttons if hasattr(b, "trigger_action")]

    def _dismiss_dropdown(self) -> None:
        self._word_stat_dropdown.dismiss()

    def _enter_dropdown_nav(self, initial_idx: int = 0) -> None:
        super()._enter_dropdown_nav(initial_idx)
        logger.debug("StatisticsScreen: entered dropdown nav.")

    def _on_dropdown_dismissed(self, _dropdown: Widget | None) -> None:
        """Override to match Kivy's on_dismiss callback signature (no ActionBarNavMixin)."""
        if self._dropdown_nav_mode:
            self._exit_dropdown_nav()
            logger.debug("StatisticsScreen: exited dropdown nav.")

    # --- Keyboard navigation ---

    def enter_nav_focus(self, on_exit_request: Callable) -> None:
        """Enter keyboard navigation mode, focusing the first tab button."""
        self._nav_on_exit_request = on_exit_request
        self._nav_active = True
        self._nav_focused_idx = 0
        update_focus_in_list(self._stat_buttons, self._nav_focused_idx, MENU_FOCUS_HIGHLIGHT_GROUP)
        logger.debug("StatisticsScreen: entered nav focus.")

    def exit_nav_focus(self) -> None:
        """Exit keyboard navigation mode and clean up all highlights."""
        clear_focus_in_list(self._stat_buttons, MENU_FOCUS_HIGHLIGHT_GROUP)
        if self._dropdown_nav_mode:
            self._exit_dropdown_nav()
        if self._word_stat_dropdown:
            self._word_stat_dropdown.dismiss()
        self._nav_active = False
        logger.debug("StatisticsScreen: exited nav focus.")

    def handle_key(self, key: int) -> bool:
        """Handle a keyboard key. Return True if consumed."""
        if not self._nav_active:
            return False
        if self._dropdown_nav_mode:
            return self._handle_dropdown_key(key)
        return self._handle_tab_key(key)

    def _handle_tab_key(self, key: int) -> bool:
        if key == KEY_RIGHT:
            self._move_tab_focus(1)
        elif key == KEY_LEFT:
            self._move_tab_focus(-1)
        elif key in (KEY_ENTER, KEY_NUMPAD_ENTER):
            self._activate_focused_tab()
        elif key == KEY_ESCAPE:
            if self._nav_on_exit_request:
                self._nav_on_exit_request()
        else:
            return False
        return True

    def _move_tab_focus(self, delta: int) -> None:
        self._nav_focused_idx = (self._nav_focused_idx + delta) % len(self._stat_buttons)
        update_focus_in_list(self._stat_buttons, self._nav_focused_idx, MENU_FOCUS_HIGHLIGHT_GROUP)

    def _activate_focused_tab(self) -> None:
        btn = self._stat_buttons[self._nav_focused_idx]
        btn.trigger_action()
        if btn is self._word_stat_button:
            Clock.schedule_once(lambda _dt: self._enter_dropdown_nav(), 0)
