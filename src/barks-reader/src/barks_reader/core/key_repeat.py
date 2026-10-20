"""Whether a key press follows the last so closely that it is a held key. Kivy-free."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class KeyRepeatDetector:
    """Tells a rapid press, one within `threshold` seconds of the last, from a deliberate one."""

    def __init__(self, now: Callable[[], float], threshold: float) -> None:
        """Make one that reads the clock with `now` and calls presses within `threshold` rapid."""
        self._now = now
        self._threshold = threshold
        self._last_time = float("-inf")

    def is_rapid(self) -> bool:
        """Record a press and return whether it came within the threshold of the last."""
        now = self._now()
        rapid = (now - self._last_time) < self._threshold
        self._last_time = now
        return rapid
