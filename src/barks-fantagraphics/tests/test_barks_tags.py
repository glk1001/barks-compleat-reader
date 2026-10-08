# ruff: noqa: SIM117

from copy import deepcopy
from enum import Enum  # For creating mock enums in tests
from typing import cast
from unittest.mock import patch

import pytest

# Import the module to be tested and its components
from barks_fantagraphics import barks_tags
from barks_fantagraphics.barks_tags import (
    BARKS_TAG_ALIASES,
    BARKS_TAG_CATEGORIES,
    BARKS_TAG_CATEGORIES_DICT,
    BARKS_TAG_CATEGORIES_TITLES,
    BARKS_TAG_GROUPS,
    BARKS_TAG_GROUPS_ALIASES,
    TagCategories,
    TagGroups,
    Tags,
    Titles,
    get_all_tags_in_tag_category,
    get_sorted_tagged_titles,
)


def test_initial_validation_passes() -> None:
    """Test that validate_tag_data passes with the default data."""
    try:
        barks_tags.validate_tag_data()
    except AssertionError as e:
        pytest.fail(f"validate_tag_data failed with presumably invalid data: {e}")


# --- Tests for validate_tag_data failures ---


def test_validate_invalid_tag_key_in_barks_tagged_titles() -> None:
    invalid_data_content = {"NOT_A_TAG_OBJECT": [Titles.FIREBUG_THE]}
    with patch.dict(barks_tags.BARKS_TAGGED_TITLES, invalid_data_content, clear=True):
        with pytest.raises(AssertionError, match="Invalid tag key in BARKS_TAGGED_TITLES"):
            barks_tags.validate_tag_data()


def test_validate_invalid_title_in_barks_tagged_titles() -> None:
    # Deepcopy to avoid modifying the original during test setup
    invalid_data_content = deepcopy(barks_tags.BARKS_TAGGED_TITLES)
    # Ensure the tag exists before trying to append to its list
    if not invalid_data_content or Tags.FIRE not in invalid_data_content:
        # If BARKS_TAGGED_TITLES was empty for some reason
        invalid_data_content[Tags.FIRE] = []

    # Test that bad enum is caught.
    invalid_data_content[Tags.FIRE].append("NOT_A_TITLE_ENUM_MEMBER")  # ty: ignore[invalid-argument-type]

    with patch.dict(barks_tags.BARKS_TAGGED_TITLES, invalid_data_content, clear=True):
        with pytest.raises(AssertionError, match=r"Invalid title .* in BARKS_TAGGED_TITLES"):
            barks_tags.validate_tag_data()


def test_validate_invalid_tag_key_in_barks_tagged_pages() -> None:
    invalid_data_content = {("NOT_A_TAG_ENUM", Titles.FIREBUG_THE): ["1"]}
    with patch.dict(barks_tags.BARKS_TAGGED_PAGES, invalid_data_content, clear=True):
        # This test assumes BARKS_TAGGED_TITLES is valid, otherwise an earlier check might fail.
        with pytest.raises(AssertionError, match="Invalid tag key in BARKS_TAGGED_PAGES"):
            barks_tags.validate_tag_data()


def test_validate_invalid_title_key_in_barks_tagged_pages() -> None:
    invalid_data_content = {(Tags.NEIGHBOR_JONES, "NOT_A_TITLE_ENUM"): ["1"]}
    with patch.dict(barks_tags.BARKS_TAGGED_PAGES, invalid_data_content, clear=True):
        with pytest.raises(AssertionError, match="Invalid title key in BARKS_TAGGED_PAGES"):
            barks_tags.validate_tag_data()


def test_validate_tag_in_tagged_pages_not_in_tagged_titles() -> None:
    # Use a valid Tag enum that we'll ensure is not in BARKS_TAGGED_TITLES
    test_tag = Tags.SYRIA  # Assuming SYRIA might not always have page-specific tags

    temp_tagged_titles = deepcopy(barks_tags.BARKS_TAGGED_TITLES)
    if test_tag in temp_tagged_titles:
        del temp_tagged_titles[test_tag]  # Remove it for this test

    temp_tagged_pages = deepcopy(barks_tags.BARKS_TAGGED_PAGES)
    temp_tagged_pages[(test_tag, Titles.FIREBUG_THE)] = ["1"]

    with patch.dict(barks_tags.BARKS_TAGGED_TITLES, temp_tagged_titles, clear=True):
        with patch.dict(barks_tags.BARKS_TAGGED_PAGES, temp_tagged_pages, clear=True):
            with pytest.raises(
                AssertionError,
                match=f"Tag '{test_tag.value}' in BARKS_TAGGED_PAGES is not in BARKS_TAGGED_TITLES",
            ):
                barks_tags.validate_tag_data()


def test_validate_title_in_tagged_pages_not_in_tagged_titles_for_that_tag() -> None:
    test_tag = Tags.FIRE
    # A title that is valid but not associated with Tags.FIRE in BARKS_TAGGED_TITLES
    unassociated_title = Titles.LOST_IN_THE_ANDES

    temp_tagged_titles = deepcopy(barks_tags.BARKS_TAGGED_TITLES)
    if test_tag in temp_tagged_titles:
        if unassociated_title in temp_tagged_titles[test_tag]:
            temp_tagged_titles[test_tag].remove(unassociated_title)
    else:  # If Tags.FIRE isn't in the dict, add it as an empty list
        temp_tagged_titles[test_tag] = []

    temp_tagged_pages = deepcopy(barks_tags.BARKS_TAGGED_PAGES)
    temp_tagged_pages[(test_tag, unassociated_title)] = ["1"]

    with patch.dict(barks_tags.BARKS_TAGGED_TITLES, temp_tagged_titles, clear=True):
        with patch.dict(barks_tags.BARKS_TAGGED_PAGES, temp_tagged_pages, clear=True):
            with pytest.raises(
                AssertionError,
                match=f"Title '{unassociated_title.value}' for tag '{test_tag.value}'"
                f" in BARKS_TAGGED_PAGES is not listed",
            ):
                barks_tags.validate_tag_data()


def test_validate_invalid_page_type_in_barks_tagged_pages() -> None:
    # Ensure the key exists in BARKS_TAGGED_PAGES for the test to be meaningful
    key_to_test = (Tags.NEIGHBOR_JONES, Titles.GOOD_DEEDS)
    if key_to_test not in barks_tags.BARKS_TAGGED_PAGES:
        # If this specific key isn't there, we can't test modifying its value this way.
        # This might indicate a data change in the main module.
        # For now, we'll add it if it's missing, assuming it's a valid combination.
        # A more robust test might pick an existing key.
        pass  # Let's assume it exists as per current data.

    invalid_data_content = deepcopy(barks_tags.BARKS_TAGGED_PAGES)
    # Test invalid int page is caught.
    # Page as int, not str
    invalid_data_content[key_to_test] = [123]  # ty: ignore[invalid-assignment]

    with patch.dict(barks_tags.BARKS_TAGGED_PAGES, invalid_data_content, clear=True):
        with pytest.raises(AssertionError, match=r"Page .* must be a string"):
            barks_tags.validate_tag_data()


def test_validate_invalid_category_key_in_barks_tag_categories() -> None:
    invalid_data_content = deepcopy(barks_tags.BARKS_TAG_CATEGORIES)
    invalid_data_content["NOT_A_CATEGORY_ENUM"] = [Tags.FIRE]  # ty: ignore[invalid-assignment]
    with patch.dict(barks_tags.BARKS_TAG_CATEGORIES, invalid_data_content, clear=True):
        with pytest.raises(AssertionError, match="Invalid category key"):
            barks_tags.validate_tag_data()


def test_validate_invalid_item_in_barks_tag_categories() -> None:
    invalid_data_content = deepcopy(barks_tags.BARKS_TAG_CATEGORIES)
    # Ensure TagCategories.THINGS exists
    if TagCategories.THINGS not in invalid_data_content:
        invalid_data_content[TagCategories.THINGS] = []
    invalid_data_content[TagCategories.THINGS].append("NOT_A_TAG_OR_GROUP_ENUM")  # ty: ignore[invalid-argument-type]

    with patch.dict(barks_tags.BARKS_TAG_CATEGORIES, invalid_data_content, clear=True):
        with pytest.raises(
            AssertionError,
            match=r"Invalid item .* in category .* Must be Tags or TagGroups",
        ):
            barks_tags.validate_tag_data()


def test_validate_invalid_group_key_in_barks_tag_groups() -> None:
    invalid_data_content = deepcopy(barks_tags.BARKS_TAG_GROUPS)
    invalid_data_content["NOT_A_GROUP_ENUM"] = [Tags.FIRE]  # ty: ignore[invalid-assignment]
    with patch.dict(barks_tags.BARKS_TAG_GROUPS, invalid_data_content, clear=True):
        with pytest.raises(AssertionError, match="Invalid group key"):
            barks_tags.validate_tag_data()


def test_validate_invalid_tag_in_barks_tag_groups() -> None:
    invalid_data_content = deepcopy(barks_tags.BARKS_TAG_GROUPS)
    # Ensure TagGroups.AFRICA exists
    if TagGroups.AFRICA not in invalid_data_content:
        invalid_data_content[TagGroups.AFRICA] = []
    invalid_data_content[TagGroups.AFRICA].append("NOT_A_TAG_ENUM")  # ty: ignore[invalid-argument-type]

    with patch.dict(barks_tags.BARKS_TAG_GROUPS, invalid_data_content, clear=True):
        with pytest.raises(AssertionError, match=r"Invalid tag .* in group .* Must be Tags"):
            barks_tags.validate_tag_data()


# --- Tests for getter functions ---
def test_get_tagged_titles() -> None:
    titles_fire = get_sorted_tagged_titles(Tags.FIRE)
    assert isinstance(titles_fire, list)
    assert Titles.FIREBUG_THE in titles_fire
    assert Titles.FIREMAN_DONALD in titles_fire
    assert titles_fire == sorted(set(titles_fire)), "Titles should be sorted and unique"

    titles_square_eggs = get_sorted_tagged_titles(Tags.SQUARE_EGGS)
    assert titles_square_eggs == [Titles.LOST_IN_THE_ANDES]

    # Test with a tag not in BARKS_TAGGED_TITLES
    class MockNonExistentTag(Enum):
        NON_EXISTENT = "Non Existent Tag"

    # Test invalid Tag enum is caught.
    assert get_sorted_tagged_titles(MockNonExistentTag.NON_EXISTENT) == []  # ty: ignore[invalid-argument-type]


def test_barks_tag_categories_titles_computation() -> None:
    # BARKS_TAG_CATEGORIES_TITLES is computed at module import.
    # We test its computed state.
    result = BARKS_TAG_CATEGORIES_TITLES

    assert TagCategories.THINGS in result
    things_titles = result[TagCategories.THINGS]
    assert isinstance(things_titles, list)
    assert Titles.FIREBUG_THE in things_titles  # From Tags.FIRE
    assert Titles.LOST_IN_THE_ANDES in things_titles  # From Tags.SQUARE_EGGS
    assert Titles.TRUANT_NEPHEWS_THE in things_titles  # From Tags.AIRPLANE
    assert things_titles == sorted(set(things_titles)), (
        "Category (THINGS) titles should be sorted and unique"
    )

    assert TagCategories.PLACES in result
    places_titles = result[TagCategories.PLACES]
    # Example: Algeria is in TagGroups.AFRICA, which is in TagCategories.PLACES
    assert Titles.ROCKET_RACE_AROUND_THE_WORLD in places_titles
    # Example: Andes is directly inside TagCategories.PLACES
    assert Titles.LOST_IN_THE_ANDES in places_titles
    assert places_titles == sorted(set(places_titles)), (
        "Category (PLACES) titles should be sorted and unique"
    )


def test_barks_character_tag_groups() -> None:
    character_groups = cast("list[TagGroups]", BARKS_TAG_CATEGORIES[TagCategories.CHARACTERS])
    for tag_group in character_groups:
        mutually_exclusive_groups = character_groups.copy()
        mutually_exclusive_groups.remove(tag_group)
        for tag in BARKS_TAG_GROUPS[tag_group]:
            for excl_group in mutually_exclusive_groups:
                assert tag not in BARKS_TAG_GROUPS[excl_group]


def test_barks_tag_aliases() -> None:
    assert BARKS_TAG_ALIASES["fire"] == Tags.FIRE
    assert BARKS_TAG_ALIASES["arabia"] == Tags.ARABIAN_PENINSULA
    assert BARKS_TAG_ALIASES["morganbilt"] == Tags.J_MORGANBILT_GILTWHISKERS
    assert "non_existent_alias" not in BARKS_TAG_ALIASES


def test_barks_tag_groups_aliases() -> None:
    assert BARKS_TAG_GROUPS_ALIASES["africa"] == TagGroups.AFRICA
    assert BARKS_TAG_GROUPS_ALIASES["europe"] == TagGroups.EUROPE
    assert "non_existent_group_alias" not in BARKS_TAG_GROUPS_ALIASES


def test_barks_tag_categories_dict() -> None:
    assert BARKS_TAG_CATEGORIES_DICT["Characters"] == TagCategories.CHARACTERS
    assert BARKS_TAG_CATEGORIES_DICT["Places"] == TagCategories.PLACES
    assert BARKS_TAG_CATEGORIES_DICT["Things"] == TagCategories.THINGS
    with pytest.raises(KeyError):
        _ = BARKS_TAG_CATEGORIES_DICT["NON_EXISTENT"]


class TestGetAllTagsInTagCategory:
    """The category flattener is public API, shared with the sibling repos."""

    def test_direct_tags_and_group_members_are_both_returned(self) -> None:
        places = get_all_tags_in_tag_category(TagCategories.PLACES)

        assert Tags.ANDES in places  # listed directly under PLACES
        assert Tags.ALGERIA in places  # reached through TagGroups.AFRICA
        assert all(isinstance(tag, Tags) for tag in places)

    def test_nested_groups_are_flattened_and_deduplicated(self) -> None:
        """A group inside a group contributes its tags, and a repeat adds nothing."""
        categories = {TagCategories.THINGS: [Tags.FIRE, TagGroups.CHEMISTRY]}
        groups = {
            TagGroups.CHEMISTRY: [Tags.FIRE, TagGroups.CHEMICAL_NAMES],
            TagGroups.CHEMICAL_NAMES: [Tags.SQUARE_EGGS],
        }

        with patch.dict(barks_tags.BARKS_TAG_CATEGORIES, categories, clear=True):
            with patch.dict(barks_tags.BARKS_TAG_GROUPS, groups, clear=True):
                assert get_all_tags_in_tag_category(TagCategories.THINGS) == {
                    Tags.FIRE,
                    Tags.SQUARE_EGGS,
                }

    def test_an_empty_category_returns_an_empty_set(self) -> None:
        with patch.dict(barks_tags.BARKS_TAG_CATEGORIES, {TagCategories.THINGS: []}, clear=True):
            assert get_all_tags_in_tag_category(TagCategories.THINGS) == set()


class TestTitleLookups:
    def test_a_tag_with_no_titles_has_none(self) -> None:
        with patch.dict(barks_tags.BARKS_TAGGED_TITLES, {}, clear=True):
            assert barks_tags.get_tag_titles(Tags.CLASSICS) == set()

    def test_the_personal_favourites_are_the_picks_given(self) -> None:
        picks = [Titles.LOST_IN_THE_ANDES, Titles.GOLDEN_HELMET_THE]
        with patch.dict(barks_tags.BARKS_TAGGED_TITLES):
            barks_tags.special_case_personal_favourites_tag_update(picks)
            assert barks_tags.get_tag_titles(Tags.PERSONAL_FAVOURITES) == set(picks)


# --- The Gyro tags: every Gyro story, split by first issue ---

_GG_STORY = Titles.GAB_MUFFER_THE  # Four Color 1047, Gyro's own comic.
_NOT_GG_STORY = Titles.TALKING_DOG_THE  # Comics and Stories 152.


def _gyro_tags(gyro: set[Titles], in_gg: set[Titles], not_in_gg: set[Titles]) -> dict:
    return {
        Tags.GYRO_GEARLOOSE: sorted(gyro),
        Tags.GYRO_IN_GG: sorted(in_gg),
        Tags.GYRO_NOT_IN_GG: sorted(not_in_gg),
    }


def _validate_gyro_with(gyro: set[Titles], in_gg: set[Titles], not_in_gg: set[Titles]) -> None:
    """Validate the real Gyro lists after the given titles have been added or taken away."""
    with patch.dict(barks_tags.BARKS_TAGGED_TITLES, _gyro_tags(gyro, in_gg, not_in_gg)):
        barks_tags.validate_tag_data()


def _real_gyro_sets() -> tuple[set[Titles], set[Titles], set[Titles]]:
    return (
        set(barks_tags.BARKS_TAGGED_TITLES[Tags.GYRO_GEARLOOSE]),
        set(barks_tags.BARKS_TAGGED_TITLES[Tags.GYRO_IN_GG]),
        set(barks_tags.BARKS_TAGGED_TITLES[Tags.GYRO_NOT_IN_GG]),
    )


def test_gyro_story_in_both_parts_fails() -> None:
    gyro, in_gg, not_in_gg = _real_gyro_sets()
    with pytest.raises(AssertionError, match="In both GYRO_IN_GG and GYRO_NOT_IN_GG"):
        _validate_gyro_with(gyro, in_gg, not_in_gg | {_GG_STORY})


def test_gyro_story_in_neither_part_fails() -> None:
    gyro, in_gg, not_in_gg = _real_gyro_sets()
    with pytest.raises(AssertionError, match="in neither GYRO_IN_GG nor GYRO_NOT_IN_GG"):
        _validate_gyro_with(gyro, in_gg, not_in_gg - {_NOT_GG_STORY})


def test_gyro_part_not_in_gyro_gearloose_fails() -> None:
    gyro, in_gg, not_in_gg = _real_gyro_sets()
    with pytest.raises(AssertionError, match="Not in GYRO_GEARLOOSE"):
        _validate_gyro_with(gyro - {_NOT_GG_STORY}, in_gg, not_in_gg)


def test_gyro_in_gg_story_from_another_comic_fails() -> None:
    gyro, in_gg, not_in_gg = _real_gyro_sets()
    with pytest.raises(AssertionError, match="In GYRO_IN_GG but not from a Gyro Gearloose issue"):
        _validate_gyro_with(gyro, in_gg | {_NOT_GG_STORY}, not_in_gg - {_NOT_GG_STORY})


def test_gyro_not_in_gg_story_from_gyros_comic_fails() -> None:
    gyro, in_gg, not_in_gg = _real_gyro_sets()
    with pytest.raises(AssertionError, match="In GYRO_NOT_IN_GG but from a Gyro Gearloose issue"):
        _validate_gyro_with(gyro, in_gg - {_GG_STORY}, not_in_gg | {_GG_STORY})


def test_gyro_comic_story_missing_from_gyro_in_gg_fails() -> None:
    gyro, in_gg, not_in_gg = _real_gyro_sets()
    with pytest.raises(AssertionError, match="missing from GYRO_IN_GG"):
        _validate_gyro_with(gyro - {_GG_STORY}, in_gg - {_GG_STORY}, not_in_gg)


def test_gyro_series_missing_from_the_bibliography_fails() -> None:
    with patch.object(barks_tags, "BIBLIOGRAPHY", []):
        with pytest.raises(AssertionError, match="series in the bibliography"):
            barks_tags.validate_tag_data()


# --- Every tag's titles in chronological order ---


def test_tag_titles_out_of_chronological_order_fail() -> None:
    titles = [Titles.FIREMAN_DONALD, Titles.FIREBUG_THE]  # FIREBUG_THE comes first.
    with patch.dict(barks_tags.BARKS_TAGGED_TITLES, {Tags.FIRE: titles}):
        with pytest.raises(
            AssertionError, match="not in chronological order:\n  FIRE: move FIREBUG_THE to the top"
        ):
            barks_tags.validate_tag_data()


def test_personal_favourites_keep_their_own_order() -> None:
    titles = [Titles.FIREMAN_DONALD, Titles.FIREBUG_THE]
    with patch.dict(barks_tags.BARKS_TAGGED_TITLES, {Tags.PERSONAL_FAVOURITES: titles}):
        barks_tags.validate_tag_data()


# --- No title twice under one tag ---


def test_tag_listing_a_title_twice_fails() -> None:
    titles = [Titles.FIREBUG_THE, Titles.FIREBUG_THE, Titles.FIREMAN_DONALD]
    with patch.dict(barks_tags.BARKS_TAGGED_TITLES, {Tags.FIRE: titles}):
        with pytest.raises(AssertionError, match=r"more than once: \{'FIRE': \['FIREBUG_THE'\]\}"):
            barks_tags.validate_tag_data()


def test_personal_favourites_listing_a_title_twice_fails() -> None:
    titles = [Titles.FIREMAN_DONALD, Titles.FIREBUG_THE, Titles.FIREMAN_DONALD]
    with patch.dict(barks_tags.BARKS_TAGGED_TITLES, {Tags.PERSONAL_FAVOURITES: titles}):
        with pytest.raises(AssertionError, match="PERSONAL_FAVOURITES"):
            barks_tags.validate_tag_data()


# --- Where to move titles that are out of order ---

_A, _B, _C, _D, _E = sorted(
    [
        Titles.FIREBUG_THE,
        Titles.FIREMAN_DONALD,
        Titles.GOOD_DEEDS,
        Titles.LIFEGUARD_DAZE,
        Titles.RABBITS_FOOT_THE,
    ]
)


@pytest.mark.parametrize(
    ("titles", "moves"),
    [
        ([], []),
        ([_A, _B, _C], []),
        # A new title put on the end goes back to its place.
        ([_A, _C, _D, _B], [f"move {_B.name} after {_A.name}"]),
        ([_B, _C, _A], [f"move {_A.name} to the top"]),
        # One title too early moves, not the run it jumped ahead of.
        ([_D, _A, _B, _C, _E], [f"move {_D.name} after {_C.name}"]),
        # Fully reversed: all but one move.
        (
            [_C, _B, _A],
            [f"move {_A.name} to the top", f"move {_B.name} after {_A.name}"],
        ),
    ],
)
def test_title_moves_name_the_fewest_titles_and_where_they_go(
    titles: list[Titles], moves: list[str]
) -> None:
    assert barks_tags.get_title_moves(titles) == moves


def test_following_the_title_moves_sorts_the_list() -> None:
    titles = [_E, _B, _D, _A, _C]
    moves = barks_tags.get_title_moves(titles)
    for move in moves:
        _, name, *where = move.split()
        title = Titles[name]
        titles.remove(title)
        titles.insert(
            0 if where == ["to", "the", "top"] else titles.index(Titles[where[1]]) + 1, title
        )
    assert titles == sorted(titles)
