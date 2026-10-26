"""Kivy-free Protocol ports for UI/platform services.

The ports define the narrow surfaces that `core/` modules need from the host
environment (Kivy in production, in-memory adapters in tests). Each port's
production implementation lives where it is built:

- `Scheduler` and `Cursor`: `KivyClockScheduler` and `KivyCursor` in `ui.adapters`.
- `ColorSource`: `FixedColorSource` in `core.reader_colors`, which needs no Kivy.
- `SnapshotSink`: `SnapshotApplicator` in `ui.snapshot_applicator`.
- `ComicBookReaderPort` and `ComicBookReaderScreenPort`: the `ComicBookReader` and
  `ComicBookReaderScreen` widgets in `ui.comic_book_reader`.

The in-memory adapters for tests live in `core.testing.fakes`. Core modules import
the ports from this package, not from its submodules.

The ports are for `core`, which must stay Kivy-free. A `ui` module that wants the
`dt` Kivy passes a callback, or Kivy's own event ordering (`ui.app_window_geometry`,
`ui.tree_scroll_pinner`), uses `kivy.clock.Clock` directly and is tested with
`core.testing.fakes.FakeClock`; that is by design, not a port waiting to be used.
"""

from .color_source import ColorSource, PaletteId
from .comic_reader import ComicBookReaderPort, ComicBookReaderScreenPort
from .cursor import Cursor
from .scheduler import CancelHandle, Scheduler
from .snapshot_sink import SnapshotSink

__all__ = [
    "CancelHandle",
    "ColorSource",
    "ComicBookReaderPort",
    "ComicBookReaderScreenPort",
    "Cursor",
    "PaletteId",
    "Scheduler",
    "SnapshotSink",
]
