"""In-memory adapters for the platform-service ports, intended for tests only."""

from .fakes import (
    FakeClock,
    FakeScheduler,
    RecordingCursor,
    RecordingSink,
    ScriptedColorSource,
    fake_fanta_info,
)

__all__ = [
    "FakeClock",
    "FakeScheduler",
    "RecordingCursor",
    "RecordingSink",
    "ScriptedColorSource",
    "fake_fanta_info",
]
