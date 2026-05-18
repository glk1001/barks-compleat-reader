"""In-memory adapters for the view-pipeline ports, intended for tests only."""

from .fakes import FakeScheduler, RecordingSink, ScriptedColorSource

__all__ = [
    "FakeScheduler",
    "RecordingSink",
    "ScriptedColorSource",
]
