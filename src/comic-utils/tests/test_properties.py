"""Property-based tests for the pure parts of comic_utils: what holds for any input.

Module-level ``@given`` functions, as the reader's test_properties.py explains: mutmut
runs pytest many times in one process, and a class-scoped ``@given`` trips
Hypothesis's differing-executors health check from the second run on.
"""

from __future__ import annotations

import math
import statistics

import pytest
from comic_utils.cpi_calculator import get_adjusted_usd, get_latest_year
from comic_utils.cpi_table import ANNUAL_CPI
from comic_utils.panel_segmentation import (
    TIER_TOLERANCE_FRACTION,
    apply_panel_order_override,
    sort_panels_in_reading_order,
)
from hypothesis import given
from hypothesis import strategies as st

# --- panel reading order ----------------------------------------------------------

_COORD = st.integers(min_value=0, max_value=3000)
_SIZE = st.integers(min_value=1, max_value=2000)
_PANELS = st.lists(st.tuples(_COORD, _COORD, _SIZE, _SIZE).map(list), max_size=16)


@given(_PANELS)
def test_reading_order_is_a_permutation_of_the_panels_and_settles_at_once(
    panels: list[list[int]],
) -> None:
    ordered = sort_panels_in_reading_order(panels)
    assert sorted(ordered) == sorted(panels)
    assert all(isinstance(p, list) for p in ordered)
    assert sort_panels_in_reading_order(ordered) == ordered


@given(_PANELS)
def test_the_first_panel_read_is_on_the_top_tier(panels: list[list[int]]) -> None:
    ordered = sort_panels_in_reading_order(panels)
    if ordered:
        tolerance = TIER_TOLERANCE_FRACTION * statistics.median(p[3] for p in panels)
        lowest_top = min(p[1] for p in panels)
        assert ordered[0][1] <= lowest_top + tolerance


@st.composite
def panels_with_an_order(draw: st.DrawFn) -> tuple[list[list[int]], list[int]]:
    panels = draw(st.lists(st.tuples(_COORD, _COORD, _SIZE, _SIZE).map(list), max_size=12))
    order = draw(st.permutations(list(range(1, len(panels) + 1))))
    return panels, order


@given(panels_with_an_order())
def test_an_order_override_picks_each_panel_once_and_its_inverse_undoes_it(
    panels_and_order: tuple[list[list[int]], list[int]],
) -> None:
    panels, order = panels_and_order
    reordered = apply_panel_order_override(panels, order)
    assert reordered == [panels[n - 1] for n in order]
    inverse = [0] * len(order)
    for place, n in enumerate(order, start=1):
        inverse[n - 1] = place
    assert apply_panel_order_override(reordered, inverse) == [list(p) for p in panels]


@given(panels_with_an_order(), st.integers(min_value=0, max_value=20))
def test_an_order_that_is_no_permutation_is_refused(
    panels_and_order: tuple[list[list[int]], list[int]], extra: int
) -> None:
    panels, order = panels_and_order
    for bad in ([*order, extra], order[1:], [n + 1 for n in order]):
        if sorted(bad) == list(range(1, len(panels) + 1)):
            continue
        with pytest.raises(ValueError, match="not a permutation"):
            apply_panel_order_override(panels, bad)


# --- inflation ----------------------------------------------------------------------

_YEARS = st.sampled_from(sorted(ANNUAL_CPI))
_AMOUNTS = st.floats(min_value=0.01, max_value=1e9)


@given(_AMOUNTS, _YEARS)
def test_a_year_to_itself_changes_nothing(amount: float, year: int) -> None:
    assert get_adjusted_usd(amount, year, year) == amount


@given(_AMOUNTS, _YEARS, _YEARS)
def test_there_and_back_gives_the_amount_within_rounding(
    amount: float, base_year: int, to_year: int
) -> None:
    there = get_adjusted_usd(amount, base_year, to_year)
    assert there > 0
    assert math.isclose(get_adjusted_usd(there, to_year, base_year), amount, rel_tol=1e-9)


@given(_AMOUNTS, _AMOUNTS, _YEARS)
def test_a_larger_amount_adjusts_to_a_larger_amount(first: float, second: float, year: int) -> None:
    if first < second:
        assert get_adjusted_usd(first, year) <= get_adjusted_usd(second, year)
    assert get_adjusted_usd(first, year) == get_adjusted_usd(first, year, get_latest_year())


@given(_AMOUNTS, st.integers(max_value=1800) | st.integers(min_value=2200))
def test_a_year_the_table_lacks_is_refused(amount: float, year: int) -> None:
    with pytest.raises(ValueError, match="No CPI data"):
        get_adjusted_usd(amount, year)
