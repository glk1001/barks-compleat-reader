# ruff: noqa: D205

from __future__ import annotations

from typing import TYPE_CHECKING

from .barks_tags_data import (
    BARKS_TAG_CATEGORIES,
    BARKS_TAG_GROUPS,
    BARKS_TAGGED_PAGES,
    BARKS_TAGGED_TITLES,
)
from .barks_tags_enums import TagCategories, TagGroups, Tags
from .barks_titles import (
    US_1_FC_ISSUE_NUM,
    US_2_FC_ISSUE_NUM,
    US_3_FC_ISSUE_NUM,
    Titles,
)
from .comic_book_info import BARKS_TITLE_INFO
from .comic_issues import Issues

if TYPE_CHECKING:
    from collections.abc import Sequence


BARKS_TAG_EXTRA_ALIASES = {
    "abduction": Tags.ABDUCTION_STORIES,
    "aeolian": Tags.AEOLIAN_ISLANDS,
    "aliens": Tags.ALIEN_STORIES,
    "amerind": Tags.AMERIND_STORIES,
    "amerinds": Tags.AMERIND_STORIES,
    "amnesia": Tags.AMNESIA_STORIES,
    "arabia": Tags.ARABIAN_PENINSULA,
    "artifacts": Tags.ARTIFACT_STORIES,
    "arctic": Tags.ARCTIC_OCEAN,
    "argus": Tags.ARGUS_MCFIENDY,
    "azure": Tags.AZURE_BLUE,
    "banzoony": Tags.BENZENE_BANZOONY,
    "barnacle": Tags.BARNACLE_BAY,
    "beakoff": Tags.CARVER_BEAKOFF,
    "benzene": Tags.BENZENE_BANZOONY,
    "bombie": Tags.BOMBIE_THE_ZOMBIE,
    "bumrisk": Tags.ROCKJAW_BUMRISK,
    "car 313": Tags.CAR_313,
    "carver beakoff": Tags.CARVER_BEAKOFF,
    "carver": Tags.CARVER_BEAKOFF,
    "chisel": Tags.CHISEL_MC_SUE,
    "coot": Tags.CORNELIUS_COOT,
    "cornelius": Tags.CORNELIUS_MC_COBB,
    "daisy": Tags.DAISY,
    "demon": Tags.OLD_DEMON_TOOTH,
    "dorado": Tags.EL_DORADO,
    "driving car": Tags.HDL_DRIVING_CAR,
    "flintheart": Tags.FLINTHEART_GLOMGOLD,
    "foola": Tags.FOOLA_ZOOLA,
    "gearloose": Tags.GYRO_GEARLOOSE,
    "ghosts": Tags.GHOST_STORIES,
    "giltwhiskers": Tags.J_MORGANBILT_GILTWHISKERS,
    "gladstone": Tags.GLADSTONE_GANDER,
    "glittering goldie": Tags.GOLDIE_OGILT,
    "glomgold": Tags.FLINTHEART_GLOMGOLD,
    "goldie": Tags.GOLDIE_OGILT,
    "grandma": Tags.GRANDMA_DUCK,
    "gyro": Tags.GYRO_GEARLOOSE,
    "helper": Tags.LITTLE_HELPER,
    "jones": Tags.NEIGHBOR_JONES,
    "magica": Tags.MAGICA_DE_SPELL,
    "mcbrine": Tags.P_J_MC_BRINE,
    "mccobb": Tags.CORNELIUS_MC_COBB,
    "mcfiendy": Tags.ARGUS_MCFIENDY,
    "mcsue": Tags.CHISEL_MC_SUE,
    "mcswine": Tags.MR_MC_SWINE,
    "morganbilt": Tags.J_MORGANBILT_GILTWHISKERS,
    "mount demon tooth": Tags.OLD_DEMON_TOOTH,
    "niagara": Tags.NIAGARA_FALLS,
    "ogilt": Tags.GOLDIE_OGILT,
    "old demon tooth": Tags.OLD_DEMON_TOOTH,
    "pete": Tags.BLACK_PETE,
    "pjmcbrine": Tags.P_J_MC_BRINE,
    "rockjaw": Tags.ROCKJAW_BUMRISK,
    "scrooge": Tags.SCROOGE_NOT_IN_US,
    "snozzie": Tags.GENERAL_SNOZZIE,
    "south pole": Tags.ANTARCTICA,
    "spell": Tags.MAGICA_DE_SPELL,
    "teengiggle": Tags.APPLECHEEKS_TEENGIGGLE,
    "the beagle boys": Tags.BEAGLE_BOYS,
    "utopia": Tags.UTOPIAN_STORIES,
    "utopias": Tags.UTOPIAN_STORIES,
    "woodchucks": Tags.JUNIOR_WOODCHUCKS,
    "zombie": Tags.BOMBIE_THE_ZOMBIE,
    "zoola": Tags.FOOLA_ZOOLA,
}

BARKS_TAG_ALIASES = {str(t.value).lower(): t for t in Tags} | BARKS_TAG_EXTRA_ALIASES
BARKS_TAGS_ALIAS_LISTS: dict[Tags, list[str]] = {
    t: [alias for alias in BARKS_TAG_EXTRA_ALIASES if BARKS_TAG_EXTRA_ALIASES[alias] == t]
    for t in BARKS_TAG_EXTRA_ALIASES.values()
}

BARKS_FIRSTS_MAP: dict[Tags, Tags] = {
    Tags.FIRST_BEAGLE_BOYS: Tags.BEAGLE_BOYS,
    Tags.FIRST_BOLIVAR: Tags.BOLIVAR,
    Tags.FIRST_CAR_313: Tags.CAR_313,
    Tags.FIRST_DAISY: Tags.DAISY,
    Tags.FIRST_DUCKBURG: Tags.DUCKBURG,
    Tags.FIRST_FLINTHEART: Tags.FLINTHEART_GLOMGOLD,
    # Tags.FIRST_GARE_INK,
    Tags.FIRST_GLADSTONE: Tags.GLADSTONE_GANDER,
    Tags.FIRST_GYRO_NOT_IN_GG: Tags.GYRO_NOT_IN_GG,
    Tags.FIRST_HERBERT: Tags.HERBERT,
    Tags.FIRST_LITTLE_HELPER: Tags.LITTLE_HELPER,
    Tags.FIRST_MAGICA: Tags.MAGICA_DE_SPELL,
    # Tags.FIRST_MONEY_BIN,
    # Tags.FIRST_MONEY_SWIM,
    Tags.FIRST_NEIGHBOR_JONES: Tags.NEIGHBOR_JONES,
    # Tags.FIRST_NUMBER_ONE_DIME,
    Tags.FIRST_PIG_VILLAIN: Tags.PORKO_DE_LARDO,
    # Tags.FIRST_REAL_NEIGHBOR_JONES,
    Tags.FIRST_UNCLE_SCROOGE: Tags.SCROOGE_NOT_IN_US,
    Tags.FIRST_WORRY_ROOM: Tags.WORRY_ROOM,
}


BARKS_TAG_GROUPS_ALIASES: dict[str, TagGroups] = {str(t.value).lower(): t for t in TagGroups}

BARKS_TAG_CATEGORIES_DICT = {cat.value: cat for cat in TagCategories}


def _set_firsts_tags() -> None:
    submission_date = {
        info.title: (info.submitted_year, info.submitted_month, info.submitted_day)
        for info in BARKS_TITLE_INFO
    }

    for firsts_tag in BARKS_TAG_GROUPS[TagGroups.FIRSTS]:
        if firsts_tag in BARKS_FIRSTS_MAP:
            tag = BARKS_FIRSTS_MAP[firsts_tag]
            titles = BARKS_TAGGED_TITLES[tag]
            # Sort the titles in order of submission dates from BARKS_TITLE_INFO
            titles = sorted(titles, key=lambda t: submission_date[t])
            first_title = titles[0]
            BARKS_TAGGED_TITLES[firsts_tag] = [first_title]
            if (tag, first_title) in BARKS_TAGGED_PAGES:
                BARKS_TAGGED_PAGES[(firsts_tag, first_title)] = [
                    BARKS_TAGGED_PAGES[(tag, first_title)][0]
                ]

    BARKS_TAGGED_TITLES[Tags.FIRST_GARE_INK] = [Titles.SOMETHIN_FISHY_HERE]
    BARKS_TAGGED_TITLES[Tags.FIRST_MONEY_BIN] = [Titles.BIG_BIN_ON_KILLMOTOR_HILL_THE]
    BARKS_TAGGED_TITLES[Tags.FIRST_MONEY_SWIM] = [Titles.BILLIONS_TO_SNEEZE_AT]
    BARKS_TAGGED_TITLES[Tags.FIRST_NUMBER_ONE_DIME] = [Titles.ROUND_MONEY_BIN_THE]
    BARKS_TAGGED_TITLES[Tags.FIRST_REAL_NEIGHBOR_JONES] = [Titles.GOOD_NEIGHBORS]

    BARKS_TAGGED_PAGES[(Tags.FIRST_NUMBER_ONE_DIME, Titles.ROUND_MONEY_BIN_THE)] = ["2", "9"]


_set_firsts_tags()


def _validate_firsts_tags() -> None:
    """Validate that every 'Tags' enum starting with 'FIRST_' is in 'BARKS_TAG_GROUPS[FIRSTS]'."""
    firsts_group = set(BARKS_TAG_GROUPS[TagGroups.FIRSTS])
    first_tags = {tag for tag in Tags if tag.name.startswith("FIRST_")}
    missing = first_tags - firsts_group
    assert not missing, f"FIRST_ tags missing from BARKS_TAG_GROUPS[FIRSTS]: {missing}"


def _validate_gyro_tags() -> None:
    gyro_titles = set(BARKS_TAGGED_TITLES[Tags.GYRO_GEARLOOSE])
    gyro_not_in_gg_titles = set(BARKS_TAGGED_TITLES[Tags.GYRO_NOT_IN_GG])
    assert gyro_not_in_gg_titles.issubset(gyro_titles), f"{gyro_not_in_gg_titles - gyro_titles}"


def _validate_uncle_scrooge_tags() -> None:
    us_not_in_us_titles = set(BARKS_TAGGED_TITLES[Tags.SCROOGE_NOT_IN_US])
    wrong_titles = [
        t
        for t in us_not_in_us_titles
        if (BARKS_TITLE_INFO[t].issue_name == Issues.US)
        or (
            BARKS_TITLE_INFO[t].issue_number
            in [US_1_FC_ISSUE_NUM, US_2_FC_ISSUE_NUM, US_3_FC_ISSUE_NUM]
        )
    ]
    assert len(wrong_titles) == 0, f"{wrong_titles}"


def special_case_personal_favourites_tag_update(my_title_picks: list[Titles]) -> None:
    BARKS_TAGGED_TITLES[Tags.PERSONAL_FAVOURITES] = my_title_picks


def _set_tag_alias(main_tag: Tags, alias_tag: Tags) -> None:
    assert alias_tag not in BARKS_TAGGED_TITLES
    BARKS_TAGGED_TITLES[alias_tag] = BARKS_TAGGED_TITLES[main_tag]

    main_tag_title_pages = [(k[1], v) for k, v in BARKS_TAGGED_PAGES.items() if main_tag == k[0]]
    for title, pages in main_tag_title_pages:
        assert (alias_tag, title) not in BARKS_TAGGED_PAGES
        BARKS_TAGGED_PAGES[(alias_tag, title)] = pages


_set_tag_alias(Tags.CAMERAS, Tags.PHOTOGRAPHY)


def is_tag_group_enum(value: str) -> bool:
    try:
        TagGroups(value)
    except ValueError:
        return False
    else:
        return True


def get_tag_group_enum(value: str) -> TagGroups | None:
    try:
        return TagGroups(value)
    except ValueError:
        return None


def is_tag_enum(value: str) -> bool:
    try:
        Tags(value)
    except ValueError:
        return False
    else:
        return True


def get_tag_enum(value: str) -> Tags | None:
    try:
        return Tags(value)
    except ValueError:
        return None


def get_num_tagged_titles() -> int:
    num = 0
    for titles_list in BARKS_TAGGED_TITLES.values():
        num += len(titles_list)

    return num


def validate_tag_data() -> None:
    """Perform various assertions to ensure the integrity of the tag data.

    Raise AssertionError if any validation fails.
    """
    # Validate BARKS_TAGGED_TITLES keys and values
    for tag, titles_list in BARKS_TAGGED_TITLES.items():
        assert isinstance(tag, Tags), f"Invalid tag key in BARKS_TAGGED_TITLES: {tag}"
        for title in titles_list:
            assert isinstance(
                title,
                Titles,
            ), f"Invalid title '{title}' for tag '{tag.value}' in BARKS_TAGGED_TITLES"

    # Validate BARKS_TAGGED_PAGES
    for (tag, title), pages in BARKS_TAGGED_PAGES.items():
        assert isinstance(tag, Tags), f"Invalid tag key in BARKS_TAGGED_PAGES: {tag}"
        assert isinstance(title, Titles), f"Invalid title key in BARKS_TAGGED_PAGES: {title}"
        assert tag in BARKS_TAGGED_TITLES, (
            f"Tag '{tag.value}' in BARKS_TAGGED_PAGES is not in BARKS_TAGGED_TITLES."
        )
        assert title in BARKS_TAGGED_TITLES[tag], (
            f"Title '{title.value}' for tag '{tag.value}' in BARKS_TAGGED_PAGES "
            f"is not listed under that tag in BARKS_TAGGED_TITLES."
        )
        for page in pages:
            assert isinstance(
                page,
                str,
            ), f"Page '{page}' for ({tag.value}, {title.value}) must be a string."

    # Validate BARKS_TAG_CATEGORIES
    for category, tags_or_groups_list in BARKS_TAG_CATEGORIES.items():
        assert isinstance(category, TagCategories), f"Invalid category key: {category}"
        for item in tags_or_groups_list:
            assert isinstance(
                item,
                (Tags, TagGroups),
            ), f"Invalid item '{item}' in category '{category.value}'. Must be Tags or TagGroups."

    # Validate BARKS_TAG_GROUPS
    for group, tags_list in BARKS_TAG_GROUPS.items():
        assert isinstance(group, TagGroups), f"Invalid group key: {group}"
        for tag_item in tags_list:
            assert isinstance(tag_item, (Tags, TagGroups)), (
                f"Invalid tag '{tag_item}' in group '{group.value}'. Must be Tags or TagGroups."
            )

    _validate_places()
    _validate_firsts_tags()
    _validate_gyro_tags()
    _validate_uncle_scrooge_tags()


def _validate_places() -> None:
    places_groups = {
        TagGroups.AFRICA,
        TagGroups.AUSTRALASIA,
        TagGroups.AUSTRALASIA,
        TagGroups.ASIA,
        TagGroups.EUROPE,
        TagGroups.OTHER_PLACES,
        TagGroups.NORTH_AMERICA,
        TagGroups.SOUTH_AMERICA,
    }

    places_tags = set()
    for group in places_groups:
        places_tags.update(get_all_tags_in_tag_group(group))

    symmetric_diff = places_tags ^ _get_all_tags_in_tag_category(TagCategories.PLACES)
    assert len(symmetric_diff) == 0, f"Non-empty diff: '{symmetric_diff}'"


def get_sorted_tagged_titles(tag: Tags) -> list[Titles]:
    """Retrieve a sorted list of unique titles associated with a specific tag.

    Return an empty list if the tag is not found or has no titles.
    """
    if tag not in BARKS_TAGGED_TITLES:
        return []
    return sorted(set(BARKS_TAGGED_TITLES[tag]))  # Ensure uniqueness and sort


def get_tag_titles(tag: Tags) -> set[Titles]:
    """Retrieve a set of titles associated with a specific tag."""
    if tag not in BARKS_TAGGED_TITLES:
        return set()
    return set(BARKS_TAGGED_TITLES[tag])


def get_tag_group_titles(tag_group: TagGroups) -> set[Titles]:
    """Retrieve a set titles associated with a specific tag group."""
    return _get_titles_for_tags_or_groups([tag_group])


def _get_tag_categories_titles() -> dict[TagCategories, list[Titles]]:
    """Get a dictionary mapping each TagCategory to a sorted list of unique
    titles associated with the tags/groups in that category.
    """
    tag_categories_titles: dict[TagCategories, list[Titles]] = {}
    for category, items_list in BARKS_TAG_CATEGORIES.items():
        tag_categories_titles[category] = sorted(_get_titles_for_tags_or_groups(items_list))
    return tag_categories_titles


def _get_tag_groups_titles() -> dict[TagGroups, list[Titles]]:
    """Get a dictionary mapping each TagGroup to a sorted list of unique
    titles associated with the tags/groups in that tag group.
    """
    tag_groups_titles: dict[TagGroups, list[Titles]] = {}
    for tag_group, items_list in BARKS_TAG_GROUPS.items():
        tag_groups_titles[tag_group] = sorted(_get_titles_for_tags_or_groups(items_list))
    return tag_groups_titles


def _get_titles_for_tags_or_groups(items_list: Sequence[Tags | TagGroups]) -> set[Titles]:
    """Recursively collect all unique titles for a list that may contain individual
    Tags or TagGroups.
    """
    all_tags = set()
    for tag_or_group in items_list:
        if isinstance(tag_or_group, Tags):
            all_tags.add(tag_or_group)
        else:
            all_tags.update(get_all_tags_in_tag_group(tag_or_group))

    collected_titles: set[Titles] = set()
    for tag in all_tags:
        if tag in BARKS_TAGGED_TITLES:
            collected_titles.update(BARKS_TAGGED_TITLES[tag])

    return collected_titles


def _get_all_tags_in_tag_category(tag_category: TagCategories) -> set[Tags]:
    """Recursively collect all unique tags for a tag category."""
    tags = set()
    for tag_or_group in BARKS_TAG_CATEGORIES[tag_category]:
        if isinstance(tag_or_group, Tags):
            tags.add(tag_or_group)
        else:
            assert isinstance(tag_or_group, TagGroups)
            tags.update(get_all_tags_in_tag_group(tag_or_group))

    return tags


def get_all_tags_in_tag_group(tag_group: TagGroups) -> set[Tags]:
    """Recursively collect all unique tags for a tag group."""
    tags = set()
    for tag_or_group in BARKS_TAG_GROUPS[tag_group]:
        if isinstance(tag_or_group, Tags):
            tags.add(tag_or_group)
        else:
            tags.update(get_all_tags_in_tag_group(tag_or_group))

    return tags


BARKS_TAG_CATEGORIES_TITLES: dict[TagCategories, list[Titles]] = _get_tag_categories_titles()
BARKS_TAG_GROUPS_TITLES: dict[TagGroups, list[Titles]] = _get_tag_groups_titles()
