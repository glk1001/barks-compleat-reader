# ruff: noqa: SIM117

import unittest
from copy import deepcopy
from enum import Enum  # For creating mock enums in tests
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
    get_tagged_titles,
)


class TestBarksTags(unittest.TestCase):
    def test_initial_validation_passes(self) -> None:
        """Test that validate_tag_data passes with the default data."""
        try:
            barks_tags.validate_tag_data()
        except AssertionError as e:
            self.fail(f"validate_tag_data failed with presumably valid data: {e}")

    # --- Tests for validate_tag_data failures ---

    def test_validate_invalid_tag_key_in_barks_tagged_titles(self) -> None:
        invalid_data_content = {"NOT_A_TAG_OBJECT": [Titles.FIREBUG_THE]}
        with patch.dict(barks_tags.BARKS_TAGGED_TITLES, invalid_data_content, clear=True):
            with pytest.raises(AssertionError, match="Invalid tag key in BARKS_TAGGED_TITLES"):
                barks_tags.validate_tag_data()

    def test_validate_invalid_title_in_barks_tagged_titles(self) -> None:
        # Deepcopy to avoid modifying the original during test setup
        invalid_data_content = deepcopy(barks_tags.BARKS_TAGGED_TITLES)
        # Ensure the tag exists before trying to append to its list
        if not invalid_data_content or Tags.FIRE not in invalid_data_content:
            # If BARKS_TAGGED_TITLES was empty for some reason
            invalid_data_content[Tags.FIRE] = []

        # Test that bad enum is caught.
        # noinspection PyTypeChecker
        invalid_data_content[Tags.FIRE].append("NOT_A_TITLE_ENUM_MEMBER")

        with patch.dict(barks_tags.BARKS_TAGGED_TITLES, invalid_data_content, clear=True):
            with pytest.raises(AssertionError, match="Invalid title .* in BARKS_TAGGED_TITLES"):
                barks_tags.validate_tag_data()

    def test_validate_invalid_tag_key_in_barks_tagged_pages(self) -> None:
        invalid_data_content = {("NOT_A_TAG_ENUM", Titles.FIREBUG_THE): ["1"]}
        with patch.dict(barks_tags.BARKS_TAGGED_PAGES, invalid_data_content, clear=True):
            # This test assumes BARKS_TAGGED_TITLES is valid, otherwise an earlier check might fail.
            with pytest.raises(AssertionError, match="Invalid tag key in BARKS_TAGGED_PAGES"):
                barks_tags.validate_tag_data()

    def test_validate_invalid_title_key_in_barks_tagged_pages(self) -> None:
        invalid_data_content = {(Tags.NEIGHBOR_JONES, "NOT_A_TITLE_ENUM"): ["1"]}
        with patch.dict(barks_tags.BARKS_TAGGED_PAGES, invalid_data_content, clear=True):
            with pytest.raises(AssertionError, match="Invalid title key in BARKS_TAGGED_PAGES"):
                barks_tags.validate_tag_data()

    def test_validate_tag_in_tagged_pages_not_in_tagged_titles(self) -> None:
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
                    match=f"Tag '{test_tag.value}'"
                    f" in BARKS_TAGGED_PAGES is not in BARKS_TAGGED_TITLES",
                ):
                    barks_tags.validate_tag_data()

    def test_validate_title_in_tagged_pages_not_in_tagged_titles_for_that_tag(self) -> None:
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

    def test_validate_invalid_page_type_in_barks_tagged_pages(self) -> None:
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
        # noinspection PyTypeChecker
        invalid_data_content[key_to_test] = [123]  # Page as int, not str

        with patch.dict(barks_tags.BARKS_TAGGED_PAGES, invalid_data_content, clear=True):
            with pytest.raises(AssertionError, match="Page .* must be a string"):
                barks_tags.validate_tag_data()

    def test_validate_invalid_category_key_in_barks_tag_categories(self) -> None:
        invalid_data_content = deepcopy(barks_tags.BARKS_TAG_CATEGORIES)
        invalid_data_content["NOT_A_CATEGORY_ENUM"] = [Tags.FIRE]
        with patch.dict(barks_tags.BARKS_TAG_CATEGORIES, invalid_data_content, clear=True):
            with pytest.raises(AssertionError, match="Invalid category key"):
                barks_tags.validate_tag_data()

    def test_validate_invalid_item_in_barks_tag_categories(self) -> None:
        invalid_data_content = deepcopy(barks_tags.BARKS_TAG_CATEGORIES)
        # Ensure TagCategories.THINGS exists
        if TagCategories.THINGS not in invalid_data_content:
            invalid_data_content[TagCategories.THINGS] = []
        invalid_data_content[TagCategories.THINGS].append("NOT_A_TAG_OR_GROUP_ENUM")

        with patch.dict(barks_tags.BARKS_TAG_CATEGORIES, invalid_data_content, clear=True):
            with pytest.raises(
                AssertionError,
                match="Invalid item .* in category .* Must be Tags or TagGroups",
            ):
                barks_tags.validate_tag_data()

    def test_validate_invalid_group_key_in_barks_tag_groups(self) -> None:
        invalid_data_content = deepcopy(barks_tags.BARKS_TAG_GROUPS)
        invalid_data_content["NOT_A_GROUP_ENUM"] = [Tags.FIRE]
        with patch.dict(barks_tags.BARKS_TAG_GROUPS, invalid_data_content, clear=True):
            with pytest.raises(AssertionError, match="Invalid group key"):
                barks_tags.validate_tag_data()

    def test_validate_invalid_tag_in_barks_tag_groups(self) -> None:
        invalid_data_content = deepcopy(barks_tags.BARKS_TAG_GROUPS)
        # Ensure TagGroups.AFRICA exists
        if TagGroups.AFRICA not in invalid_data_content:
            invalid_data_content[TagGroups.AFRICA] = []
        invalid_data_content[TagGroups.AFRICA].append("NOT_A_TAG_ENUM")

        with patch.dict(barks_tags.BARKS_TAG_GROUPS, invalid_data_content, clear=True):
            with pytest.raises(AssertionError, match="Invalid tag .* in group .* Must be Tags"):
                barks_tags.validate_tag_data()

    # --- Tests for getter functions ---
    def test_get_tagged_titles(self) -> None:
        titles_fire = get_tagged_titles(Tags.FIRE)
        assert isinstance(titles_fire, list)
        assert Titles.FIREBUG_THE in titles_fire
        assert Titles.FIREMAN_DONALD in titles_fire
        assert titles_fire == sorted(set(titles_fire)), "Titles should be sorted and unique"

        titles_square_eggs = get_tagged_titles(Tags.SQUARE_EGGS)
        assert titles_square_eggs == [Titles.LOST_IN_THE_ANDES]

        # Test with a tag not in BARKS_TAGGED_TITLES
        class MockNonExistentTag(Enum):
            NON_EXISTENT = "Non Existent Tag"

        # Test invalid Tag enum is caught.
        # noinspection PyTypeChecker
        assert get_tagged_titles(MockNonExistentTag.NON_EXISTENT) == []

    def test_barks_tag_categories_titles_computation(self) -> None:
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

    def test_barks_character_tag_groups(self) -> None:
        character_groups = BARKS_TAG_CATEGORIES[TagCategories.CHARACTERS]
        for tag_group in character_groups:
            mutually_exclusive_groups = character_groups.copy()
            mutually_exclusive_groups.remove(tag_group)
            for tag in BARKS_TAG_GROUPS[tag_group]:
                for excl_group in mutually_exclusive_groups:
                    assert tag not in BARKS_TAG_GROUPS[excl_group]

    def test_barks_tag_aliases(self) -> None:
        assert BARKS_TAG_ALIASES["fire"] == Tags.FIRE
        assert BARKS_TAG_ALIASES["arabia"] == Tags.ARABIAN_PENINSULA
        assert BARKS_TAG_ALIASES["beagles"] == Tags.BEAGLE_BOYS
        assert "non_existent_alias" not in BARKS_TAG_ALIASES

    def test_barks_tag_groups_aliases(self) -> None:
        assert BARKS_TAG_GROUPS_ALIASES["africa"] == TagGroups.AFRICA
        assert BARKS_TAG_GROUPS_ALIASES["europe"] == TagGroups.EUROPE
        assert "non_existent_group_alias" not in BARKS_TAG_GROUPS_ALIASES

    def test_barks_tag_categories_dict(self) -> None:
        assert BARKS_TAG_CATEGORIES_DICT["Characters"] == TagCategories.CHARACTERS
        assert BARKS_TAG_CATEGORIES_DICT["Places"] == TagCategories.PLACES
        assert BARKS_TAG_CATEGORIES_DICT["Things"] == TagCategories.THINGS
        with pytest.raises(KeyError):
            _ = BARKS_TAG_CATEGORIES_DICT["NON_EXISTENT"]


if __name__ == "__main__":
    pytest.main()
