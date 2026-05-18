"""Production `Cursor` adapter that delegates to `ui_helpers` Kivy cursor functions."""

from __future__ import annotations

from barks_reader.ui.ui_helpers import set_kivy_busy_cursor, set_kivy_normal_cursor


class KivyCursor:
    """A `Cursor` that flips the Kivy `Window.set_system_cursor` state."""

    @staticmethod
    def set_busy() -> None:
        """Switch to the busy/wait cursor."""
        set_kivy_busy_cursor()

    @staticmethod
    def set_normal() -> None:
        """Restore the normal cursor."""
        set_kivy_normal_cursor()
