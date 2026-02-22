from __future__ import annotations

from pathlib import Path
from typing import Self

from kivy.properties import BooleanProperty  # ty: ignore[unresolved-import]
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from loguru import logger

STATISTICS_SCREEN_KV_FILE = Path(__file__).with_suffix(".kv")

_STAT_ITEMS: list[tuple[str, str]] = [
    ("Stories per Year", "stories_per_year.png"),
    ("Pages per Year", "pages_per_year.png"),
    ("Payments per Year", "payments_per_year.png"),
    ("Payment Rate ($/page)", "payment_rate.png"),
    ("Stories per Series", "stories_per_series.png"),
    ("Top Characters", "top_characters.png"),
    ("Top Locations", "top_locations.png"),
    ("Word Statistics", "word_statistics.png"),
]


class StatMenuButton(Button):
    """A named menu button for the Statistics left-side navigation."""

    is_selected = BooleanProperty(defaultvalue=False)


class StatisticsScreen(FloatLayout):
    """Screen that shows pre-rendered statistics PNG charts.

    A left column of StatMenuButton widgets lets the user choose which chart
    to display. The selected chart is shown as a Kivy Image on the right.
    The first item is auto-selected whenever the screen becomes visible.
    """

    is_visible = BooleanProperty(defaultvalue=False)

    def __init__(self, statistics_dir: Path, **kwargs) -> None:  # noqa: ANN003
        super().__init__(**kwargs)
        self._statistics_dir = statistics_dir
        self._selected_button: StatMenuButton | None = None
        self._stat_buttons: list[StatMenuButton] = []
        self._build_menu()

    def _build_menu(self) -> None:
        menu_layout = self.ids.stat_menu_layout
        for label, filename in _STAT_ITEMS:
            btn = StatMenuButton(text=label)
            btn.bind(on_press=lambda _, f=filename, b=btn: self._show_stat_by_filename(f, b))
            menu_layout.add_widget(btn)
            self._stat_buttons.append(btn)

    def on_is_visible(self, _instance: Self, value: bool) -> None:
        """Auto-select the first stat item when the screen becomes visible."""
        if value:
            self._on_screen_activated()

    def _on_screen_activated(self) -> None:
        if self._stat_buttons:
            first = self._stat_buttons[0]
            _, filename = _STAT_ITEMS[0]
            self._show_stat_by_filename(filename, first)

    def _show_stat_by_filename(self, filename: str, button: StatMenuButton) -> None:
        if self._selected_button is not None:
            self._selected_button.is_selected = False
        button.is_selected = True
        self._selected_button = button
        self.show_stat(self._statistics_dir / filename)

    def show_stat(self, png_path: Path) -> None:
        """Load and display the given PNG in the right-side image widget.

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
