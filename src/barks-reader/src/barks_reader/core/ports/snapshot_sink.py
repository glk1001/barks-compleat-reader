"""Snapshot-sink port — the destination for each computed `ViewSnapshot`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from barks_reader.core.view_snapshot import ViewSnapshot


@runtime_checkable
class SnapshotSink(Protocol):
    """Receives a `ViewSnapshot` and applies it to whatever it drives.

    Production: `ui.snapshot_applicator.SnapshotApplicator` pushes snapshot
    fields into Kivy widgets. Test adapter (`core.testing.fakes.RecordingSink`)
    appends each call to a list so tests can assert on the sequence of snapshots
    emitted.
    """

    def apply(self, snapshot: ViewSnapshot) -> None:
        """Apply *snapshot* to the underlying view (or record it, in tests)."""
        ...
