"""Cursor port — UI-affordance hook for indicating long-running work."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Cursor(Protocol):
    """Indicates whether the application is in a busy or normal state.

    Production wraps Kivy's cursor helpers; tests provide a no-op or recording
    implementation. Callers are long-running loaders that want to show a wait
    indicator while work is in flight, and they call from whatever thread the
    work is on: `set_busy` from the UI thread as a load starts, `set_normal` from
    the loader's worker thread as it ends. Either method may be called from any
    thread; an implementation marshals the cursor change onto the UI thread itself.
    """

    def set_busy(self) -> None:
        """Show the busy cursor. Safe to call from any thread."""
        ...

    def set_normal(self) -> None:
        """Restore the normal cursor. Safe to call from any thread."""
        ...
