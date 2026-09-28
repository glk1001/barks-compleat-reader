"""Ask the app what it holds in memory, and read the answer back from the log.

The app answers a census request (``barks_reader.core.memory_census``: a request
id in, one ``MEMORY_CENSUS`` line out) after a full garbage collection, so the
counts are what it holds, not garbage the collector had yet to reach.

A leak test does one round trip - open a screen, use it, leave - several times.
The first rounds build what the app keeps on purpose (a screen, a cache: the
wiki builds some of its own on its second opening), so the census after them is
the baseline; one after the last round that holds more widgets or textures than
that, by more than a little, holds something the rounds left behind.
"""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from barks_gui.logs import last_field
from barks_reader.core import log_markers as markers
from barks_reader.core.log_markers import pattern
from barks_reader.core.memory_census import MemoryCensus

if TYPE_CHECKING:
    from collections.abc import Callable

    from gui_driver import Driver

ANSWER_TIMEOUT = 15
# How many times a leak test goes round, and how many of those only build.
ROUNDS = 6
WARMUP_ROUNDS = 2
# What the rounds after the warm-up may add. Widgets vary by a few (a popup still
# fading out). Textures by more: each of the screen manager's shader transitions
# (reader_screens: a fixed pool, used in turn) keeps its last run's frame buffers,
# three textures, until it runs again. A leak adds per round what the round builds:
# a page's hundreds of labels, a comic's pages.
WIDGET_SLACK = 10
TEXTURE_SLACK = 16

# Unique within a run: each test boots its own app, so a count is enough.
_REQUESTS = itertools.count(1)


def census(d: Driver) -> MemoryCensus:
    """Ask the app for a memory census and return it.

    Args:
        d: The driver.

    Returns:
        What the app held after a full collection.

    """
    request = str(next(_REQUESTS))
    with d.expect(pattern(markers.MEMORY_CENSUS, request=request), ANSWER_TIMEOUT):
        d.request_memory_census(request)

    def field(name: str) -> int:
        return int(last_field(d, markers.MEMORY_CENSUS, name, request=request))

    return MemoryCensus(
        widgets=field("widgets"),
        textures=field("textures"),
        objects=field("objects"),
        rss_mib=field("rss_mib"),
        took_ms=field("took_ms"),
    )


def growth_problems(first: MemoryCensus, last: MemoryCensus) -> list[str]:
    """Say what `last` holds beyond `first`, past the slack, or nothing.

    Args:
        first: The census after the warm-up rounds.
        last: The census after the last.

    Returns:
        One line per count that grew too far; empty when neither did.

    """
    problems = []
    for name, slack, before, after in (
        ("widgets", WIDGET_SLACK, first.widgets, last.widgets),
        ("textures", TEXTURE_SLACK, first.textures, last.textures),
    ):
        if after - before > slack:
            problems.append(f"{name}: {before} after the warm-up, {after} after the last round")
    return problems


def assert_round_trips_leave_nothing(d: Driver, round_trip: Callable[[], None]) -> None:
    """Go round `ROUNDS` times; fail if the rounds after the warm-up left things behind.

    A census follows every round, so a failure shows how the counts moved.

    Args:
        d: The driver.
        round_trip: One round: from a state, through the screen, back to that state.

    """
    after: list[MemoryCensus] = []
    for _ in range(ROUNDS):
        round_trip()
        d.settle()
        after.append(census(d))
    problems = growth_problems(after[WARMUP_ROUNDS - 1], after[-1])
    rounds = ", ".join(f"{c.widgets}/{c.textures}" for c in after)
    assert not problems, (
        f"{ROUNDS - WARMUP_ROUNDS} more round trips left things behind (widgets/textures"
        f" after each round: {rounds}): " + "; ".join(problems)
    )
