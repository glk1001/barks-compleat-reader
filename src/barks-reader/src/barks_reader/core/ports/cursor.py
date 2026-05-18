"""Cursor port — UI-affordance hook for indicating long-running work."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Cursor(Protocol):
    """Indicates whether the application is in a busy or normal state.

    Production wraps Kivy's cursor helpers; tests provide a no-op or recording
    implementation. Callers are typically long-running loaders that want to
    show a wait indicator while work is in flight.
    """

    def set_busy(self) -> None:
        """Show the busy cursor (typically called from the UI thread)."""
        ...

    def set_normal(self) -> None:
        """Restore the normal cursor."""
        ...
