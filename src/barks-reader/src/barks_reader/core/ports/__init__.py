"""Kivy-free Protocol ports for UI/platform services.

The ports define the narrow surfaces that `core/` modules need from the host
environment (Kivy in production, in-memory adapters in tests). Production
adapters live in `ui.adapters`; in-memory adapters for tests live in
`core.testing.fakes`.
"""

from .color_source import ColorSource, PaletteId
from .cursor import Cursor
from .scheduler import CancelHandle, Scheduler
from .snapshot_sink import SnapshotSink

__all__ = [
    "CancelHandle",
    "ColorSource",
    "Cursor",
    "PaletteId",
    "Scheduler",
    "SnapshotSink",
]
