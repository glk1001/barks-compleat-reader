"""The navigation model over every destination the tree can hold: what holds for any.

The backlog's "every reachable destination resolves to a valid view state", as a
property over the ``destinations`` strategy rather than the hand-picked cases of
test_navigation_model.py. Module-level ``@given`` functions, for mutmut's repeated
pytest runs (docs/mutation-testing.md).
"""

from __future__ import annotations

from dataclasses import fields

from barks_reader.core.navigation import NavigationModel
from barks_reader.core.navigation.destinations import (
    Destination,
    PlaylistDestination,
    RandomTitlesDestination,
    TagDestination,
    TagGroupDestination,
    TagYearRangeDestination,
    TitleDestination,
    YearRangeDestination,
    YearRangeKind,
)
from barks_reader.core.navigation.view_states import ViewStates
from barks_reader.core.view_request import ViewRequest
from hypothesis import given
from hypothesis import strategies as st
from strategies import (
    DESTINATION_TYPES_BUILT,
    destinations,
    no_payload_destinations,
    year_range_destinations,
)

_MODEL = NavigationModel()


def _all_subclasses(kind: type[Destination]) -> set[type[Destination]]:
    found: set[type[Destination]] = set()
    for sub in kind.__subclasses__():
        found.add(sub)
        found |= _all_subclasses(sub)
    return found


def test_the_strategy_builds_every_destination_kind() -> None:
    """A new `Destination` subclass must be added to the strategies to be covered below.

    The kinds the destinations module defines, by name: test_navigation_model.py
    re-imports that module, which leaves a second copy of each class among
    `Destination`'s subclasses, and defines an unregistered kind of its own.
    """
    defined = {
        k.__name__ for k in _all_subclasses(Destination) if k.__module__ == Destination.__module__
    }
    assert defined == {k.__name__ for k in DESTINATION_TYPES_BUILT}


@given(destinations())
def test_every_destination_resolves_to_a_view_state_and_always_the_same_one(
    dest: Destination,
) -> None:
    request = _MODEL.view_state_for(dest)
    assert isinstance(request, ViewRequest)
    assert request.view_state in ViewStates
    assert _MODEL.view_state_for(dest) == request
    # The renderer-owned fields are the caller's to set, never the model's.
    assert request.fun_image_themes is None
    assert request.title_image_file is None
    assert not request.preserve_top_view
    assert not request.preserve_fun_view
    assert request.title_str == ""


@given(no_payload_destinations())
def test_a_destination_without_a_payload_sets_only_the_view_state(dest: Destination) -> None:
    request = _MODEL.view_state_for(dest)
    for field in fields(ViewRequest):
        if field.name != "view_state":
            assert getattr(request, field.name) == field.default


@given(destinations())
def test_the_tag_context_is_the_tag_the_view_request_carries(dest: Destination) -> None:
    context = _MODEL.tag_context(dest)
    request = _MODEL.view_state_for(dest)
    match dest:
        case TagDestination() | TagYearRangeDestination():
            assert context is dest.tag
            assert request.tag is dest.tag
            assert request.view_state is ViewStates.ON_TAG_NODE
        case TagGroupDestination():
            assert context is dest.tag_group
            assert request.tag_group is dest.tag_group
        case RandomTitlesDestination():
            assert context is dest.tag
            assert request.tag is dest.tag
        case _:
            assert context is None
            assert request.tag is None
            assert request.tag_group is None


@given(year_range_destinations())
def test_a_year_range_names_its_years_in_the_one_field_its_kind_uses(
    dest: YearRangeDestination,
) -> None:
    request = _MODEL.view_state_for(dest)
    expected = f"{dest.start}-{dest.end}"
    ranges = {
        "year_range": request.year_range,
        "cs_year_range": request.cs_year_range,
        "us_year_range": request.us_year_range,
    }
    set_fields = {name for name, value in ranges.items() if value}
    match dest.kind:
        case YearRangeKind.CS:
            assert set_fields == {"cs_year_range"}
            assert request.cs_year_range == expected
        case YearRangeKind.US:
            assert set_fields == {"us_year_range"}
            assert request.us_year_range == expected
        case YearRangeKind.ONE_PAGER | YearRangeKind.COVER:
            # These reuse their series' top view, with no range of their own.
            assert set_fields == set()
        case _:
            assert set_fields == {"year_range"}
            assert request.year_range == expected


@given(destinations(), st.lists(destinations(), max_size=6))
def test_auto_select_picks_the_one_title_child_and_nothing_else(
    parent: Destination, children: list[Destination]
) -> None:
    target = _MODEL.auto_select_target(parent, children)
    title_children = [c for c in children if isinstance(c, TitleDestination)]
    if len(title_children) == 1:
        assert target is title_children[0]
    else:
        assert target is None


@given(st.none() | destinations())
def test_the_top_view_is_kept_only_under_the_choose_for_me_and_playlist_nodes(
    parent: Destination | None,
) -> None:
    assert _MODEL.keep_top_view_for_title_under(parent) == isinstance(
        parent, RandomTitlesDestination | PlaylistDestination
    )
