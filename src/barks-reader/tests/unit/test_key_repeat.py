"""A held key against a deliberate press (barks_reader.core.key_repeat)."""

from __future__ import annotations

from barks_reader.core.key_repeat import KeyRepeatDetector


def test_the_first_press_is_deliberate_and_a_quick_second_is_rapid() -> None:
    clock = [10.0]
    repeat = KeyRepeatDetector(lambda: clock[0], 0.2)
    assert repeat.is_rapid() is False
    clock[0] += 0.1
    assert repeat.is_rapid() is True
    clock[0] += 0.5
    assert repeat.is_rapid() is False


def test_a_press_a_whole_threshold_after_the_last_is_deliberate() -> None:
    clock = [10.0]
    repeat = KeyRepeatDetector(lambda: clock[0], 0.25)
    repeat.is_rapid()
    clock[0] += 0.25  # exact in binary: the gap is the threshold, not a hair under
    assert repeat.is_rapid() is False
