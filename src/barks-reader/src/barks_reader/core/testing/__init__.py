"""In-memory adapters for the platform-service ports, intended for tests only."""

from .fakes import FakeScheduler, RecordingCursor, RecordingSink, ScriptedColorSource

__all__ = [
    "FakeScheduler",
    "RecordingCursor",
    "RecordingSink",
    "ScriptedColorSource",
]
