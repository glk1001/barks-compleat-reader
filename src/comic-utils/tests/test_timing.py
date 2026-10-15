"""Timing: the elapsed time since a start, read against a clock the test sets."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from comic_utils import timing as timing_module
from comic_utils.timing import Timing

if TYPE_CHECKING:
    from collections.abc import Iterator

START = datetime(2024, 1, 1, tzinfo=UTC)


@pytest.fixture
def now() -> Iterator[MagicMock]:
    """Patch the module's clock: ``now.return_value`` is what ``datetime.now`` answers."""
    with patch.object(timing_module, "datetime") as fake_datetime:
        fake_datetime.now.return_value = START
        yield fake_datetime.now


def test_a_new_timing_starts_now(now: MagicMock) -> None:
    now.return_value = START + timedelta(minutes=1)

    assert Timing().get_start_time() == START + timedelta(minutes=1)


def test_restart_moves_the_start_to_now(now: MagicMock) -> None:
    timing = Timing(START)
    now.return_value = START + timedelta(seconds=5)

    timing.restart()

    assert timing.get_start_time() == START + timedelta(seconds=5)


@pytest.mark.parametrize(
    ("elapsed", "seconds", "with_unit"),
    [
        (timedelta(seconds=3), 3, "3.0s"),
        (timedelta(seconds=1.5), 1, "1.5s"),
        (timedelta(milliseconds=50), 0, "50ms"),
    ],
)
def test_elapsed_time(now: MagicMock, elapsed: timedelta, seconds: int, with_unit: str) -> None:
    timing = Timing(START)
    now.return_value = START + elapsed

    assert timing.get_elapsed_time_in_seconds() == seconds
    assert timing.get_elapsed_time_with_unit() == with_unit
