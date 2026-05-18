"""Kivy-free Protocol ports used by the view-rendering pipeline.

The ports define the narrow surfaces that `core.view_pipeline.ViewPipeline`
needs from external systems (periodic scheduling, color generation, snapshot
delivery). Production adapters live in `ui.adapters`; in-memory adapters
for tests live in `core.testing.fakes`.
"""

from .color_source import ColorSource, PaletteId
from .scheduler import CancelHandle, PeriodicScheduler
from .snapshot_sink import SnapshotSink

__all__ = [
    "CancelHandle",
    "ColorSource",
    "PaletteId",
    "PeriodicScheduler",
    "SnapshotSink",
]
