# ruff: noqa: D205

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

from . import barks_titles
from .barks_titles import Titles


class Tags(Enum):
    AEOLIAN_ISLANDS = "Aeolian Islands"
    AIRPLANES = "airplanes"
    ALASKA = "Alaska"
    ALGERIA = "Algeria"
    ALKALI = "alkali"
    ANDES = "Andes"
    ANTARCTICA = "Antarctica"
    APPLECHEEKS_TEENGIGGLE = "Applecheeks Teengiggle"
    ARABIAN_PENINSULA = "Arabian Peninsula"
    ARCTIC_OCEAN = "Arctic Ocean"
    ARGUS_MCFIENDY = "Argus McFiendy"
    ARTICLES = "articles"
    ATLANTIS = "Atlantis"
    AUSTRALIA = "Australia"
    AUSTRALIAN_ABORIGINALS = "Australian aboriginals"
    AWFULTONIANS = "Awfultonians"
    AZURE_BLUE = "Azure Blue"
    BAGDAD = "Bagdad"
    BARKS_FAVOURITES = "Barks' Picks"
    BARNACLE_BAY = "Barnacle Bay"
    BEAGLE_BOYS = "The Beagle Boys"
    BENZENE_BANZOONY = "Benzene Banzoony"
    BOMBIE_THE_ZOMBIE = "Bombie the Zombie"
    BOP_BOP = "Bop Bop"
    BRITISH_GUIANA = "British Guiana"
    CABBAGE_PROFESSOR = "The Cabbage Professor"
    CALCIUM = "calcium"
    CAMERAS = "cameras"
    CANADA = "Canada"
    CARBON = "carbon"
    CARVER_BEAKOFF = "Doctor Carver Beakoff"
    CAR_313 = "313"
    CENSORED_STORIES_BUT_FIXED = "censored but fixed stories"
    CENTRAL_AFRICA = "Central Africa"
    CHEMICAL_FORMULA = "chemical formula"
    CHINA = "China"
    CHISEL_MC_SUE = "Chisel McSue"
    CHRISTMAS_STORIES = "christmas stories"
    CIGARETTES = "cigarettes"
    CLASSICS = "The Classics"
    COLUMBIUM = "columbium"
    CONGO = "Congo"
    COPPER = "copper"
    CORNELIUS_MC_COBB = "Cornelius McCobb"
    CRETE = "Crete"
    DAISY = "Daisy Duck"
    DAMASCUS = "Damascus"
    DUCKBURG = "Duckburg"
    DUCKMITE = "duckmite"
    EGYPT = "Egypt"
    EL_DORADO = "El Dorado"
    EVERY_GEEK_FAVOURITES = "everygeek.net"
    FERMIES = "Fermies"
    FIRE = "fire"
    FLINTHEART_GLOMGOLD = "Flintheart Glomgold"
    FLORIDA = "Florida"
    FOOLA_ZOOLA = "Foola Zoola"
    FORBIDIUM = "forbidium"
    FRANCE = "France"
    GENERAL_SNOZZIE = "General Snozzie"
    GERMANY = "Germany"
    GLADSTONE_GANDER = "Gladstone Gander"
    GNEEZLES = "Gneezles"
    GREECE = "Greece"
    GYRO_GEARLOOSE = barks_titles.GYRO_GEARLOOSE
    GYRO_NOT_IN_GG = "Gyro not in GG series"
    HASSAN_BEN_JAILD = "Hassan Ben Jaild"
    HDL_DRIVING_CAR = "HDL driving car"
    HERBERT = "Herbert"
    HIMALAYAS = "Himalayas"
    HONDORICA = "Hondorica"
    HYPNOSIS = "hypnosis"
    INDIA = "India"
    INDIAN_OCEAN = "Indian Ocean"
    INDO_CHINA = "Indo-China"
    INUIT = "Inuit"
    IRAQ = "Iraq"
    ISOTOPES = "isotopes"
    ITALY = "Italy"
    ITSA_FAKA = "Itsa Faka"
    JAYNE_GIRLSFIELD = "Jayne Girlsfield"
    JIVARO = "Jivaro"
    JUGHEAD_JONES = "Jughead Jones"
    JUNIOR_WOODCHUCKS = "Junior Woodchucks"
    J_MORGANBILT_GILTWHISKERS = "J. Morganbilt Giltwhiskers"
    KAKIMAW_INDIANS = "Kakimaw Indians"
    KAKIMAW_COUNTRY = "Kakimaw Country"
    LABRADOR = "labrador"
    LIBYA = "Libya"
    LITHIUM = "lithium"
    LONGHORN_TALLGRASS = "Longhorn Tallgrass"
    MAD_SCIENTIST = "The Mad Scientist"
    MAGIC = "magic"
    MAGICA_DE_SPELL = "Magica de Spell"
    MALI = "Mali"
    MANGANESE = "manganese"
    MERCURY = "mercury"
    MISSISSIPPI = "Mississippi"
    MONGOLIA = "Mongolia"
    MOROCCO = "Morocco"
    MOURNFUL_MARY = "Mournful Mary"
    MR_MC_SWINE = "Mr. McSwine"
    NAPHTHA = "naphtha"
    NEIGHBOR_JONES = "Neighbor Jones"
    NEUTRON = "neutron"
    NEWFOUNDLAND = "Newfoundland"
    NEW_VERSIONS = "new versions of old stories"
    NIAGARA_FALLS = "Niagara Falls"
    NICKEL = "nickel"
    NITROGEN = "nitrogen"
    NITROGLYCERIN = "nitroglycerine"
    NORWAY = "Norway"
    NOSUCHIUM = "nosuchium"
    OHIO = "Ohio"
    OLD_DEMON_TOOTH = "Old Demon Tooth"
    OPA = "OPA"
    OXYGEN = "oxygen"
    PAKISTAN = "Pakistan"
    PEEWEEGAH_INDIANS = "Peeweegah Indians"
    PERSIA = "Persia"
    PERSONAL_FAVOURITES = "My Picks"
    PERU = "Peru"
    PETER_SCHILLING_FAVOURITES = "Peter Schilling"
    PHOSPHORUS = "phosphorus"
    PHOTOGRAPHY = "photography"
    PLAIN_AWFUL = "Plain Awful"
    PLASMA = "plasma"
    PLATINUM = "platinum"
    PORKMAN_DE_LARDO = "Porkman de Lardo"
    POTASH = "potash"
    PULPHEART_CLABBERHEAD = "Pulpheart Clabberhead"
    P_J_MC_BRINE = "P.J.McBrine"
    RUSSIA = "Russia"
    SCOTLAND = "Scotland"
    SCROOGE_NOT_IN_US = "Uncle Scrooge not in US series"
    SELENIUM = "selenium"
    SOAPY_SLICK = "Soapy Slick"
    SOUTH_AFRICA = "South Africa"
    SPAIN = "Spain"
    SQUARE_EGGS = "square eggs"
    STICKAREE_INDIANS = "Stickaree Indians"
    STROMBOLIUM = "strombolium"
    SUDAN = "Sudan"
    SULPHUR = "sulphur"
    SULPHURIC_ACID = "sulphuric acid"
    SWEDEN = "Sweden"
    SWITZERLAND = "Switzerland"
    SYDNEY = "Sydney"
    SYRIA = "Syria"
    TANGANYIKA = "Tanganyika"
    TANGKOR_WAT = "Tangkor Wat"
    TANTALUM = "tantalum"
    TERRIES = "Terries"
    THORIUM = "thorium"
    WEEMITE = "weemite"
    WHATTISIUM = "whattisium"
    WIKI_NOTABLE_STORIES = "Wiki Notable Stories"
    WOLFRAMITE = "wolframite"
    WORRY_ROOM = "worry room"
    YOUGUESSIUM = "youguessium"
    ZINC = "zinc"
    ZIRCONIUM = "zirconium"


BARKS_TAG_EXTRA_ALIASES = {
    "aeolian": Tags.AEOLIAN_ISLANDS,
    "arabia": Tags.ARABIAN_PENINSULA,
    "arctic": Tags.ARCTIC_OCEAN,
    "argus": Tags.ARGUS_MCFIENDY,
    "azure": Tags.AZURE_BLUE,
    "banzoony": Tags.BENZENE_BANZOONY,
    "barnacle": Tags.BARNACLE_BAY,
    "beakoff": Tags.CARVER_BEAKOFF,
    "benzene": Tags.BENZENE_BANZOONY,
    "bombie": Tags.BOMBIE_THE_ZOMBIE,
    "car 313": Tags.CAR_313,
    "carver beakoff": Tags.CARVER_BEAKOFF,
    "carver": Tags.CARVER_BEAKOFF,
    "chisel": Tags.CHISEL_MC_SUE,
    "cornelius": Tags.CORNELIUS_MC_COBB,
    "daisy": Tags.DAISY,
    "demon": Tags.OLD_DEMON_TOOTH,
    "dorado": Tags.EL_DORADO,
    "driving car": Tags.HDL_DRIVING_CAR,
    "flintheart": Tags.FLINTHEART_GLOMGOLD,
    "foola": Tags.FOOLA_ZOOLA,
    "gearloose": Tags.GYRO_GEARLOOSE,
    "giltwhiskers": Tags.J_MORGANBILT_GILTWHISKERS,
    "gladstone": Tags.GLADSTONE_GANDER,
    "glomgold": Tags.FLINTHEART_GLOMGOLD,
    "gyro": Tags.GYRO_GEARLOOSE,
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
    "old demon tooth": Tags.OLD_DEMON_TOOTH,
    "pjmcbrine": Tags.P_J_MC_BRINE,
    "scrooge": Tags.SCROOGE_NOT_IN_US,
    "snozzie": Tags.GENERAL_SNOZZIE,
    "south pole": Tags.ANTARCTICA,
    "spell": Tags.MAGICA_DE_SPELL,
    "teengiggle": Tags.APPLECHEEKS_TEENGIGGLE,
    "the beagle boys": Tags.BEAGLE_BOYS,
    "woodchucks": Tags.JUNIOR_WOODCHUCKS,
    "zombie": Tags.BOMBIE_THE_ZOMBIE,
    "zoola": Tags.FOOLA_ZOOLA,
}

BARKS_TAG_ALIASES = {str(t.value).lower(): t for t in Tags} | BARKS_TAG_EXTRA_ALIASES
BARKS_TAGS_ALIAS_LISTS: dict[Tags, list[str]] = {
    t: [alias for alias in BARKS_TAG_EXTRA_ALIASES if BARKS_TAG_EXTRA_ALIASES[alias] == t]
    for t in BARKS_TAG_EXTRA_ALIASES.values()
}


class TagCategories(Enum):
    CHARACTERS = "Characters"
    FAVOURITES = "Favourites"
    PLACES = "Places"
    THEMES = "Themes"
    THINGS = "Things"


class TagGroups(Enum):
    AFRICA = "Africa"
    ASIA = "Asia"
    AUSTRALASIA = "Australasia"
    CARS = "cars"
    CHEMICAL_NAMES = "chemical names"
    CHEMISTRY = "chemistry"
    COUNTRIES = "countries"
    CULTURAL_GROUPS = "cultural groups"
    DRUGS = "drugs"
    EUROPE = "Europe"
    NORTH_AMERICA = "North America"
    ONE_OFF_CHARACTERS = "One-off Characters"
    OTHER_PLACES = "Other"
    PIG_VILLAINS = "Pig Villains"
    PRIMARY_CHARACTERS = "Primary Characters"
    SECONDARY_CHARACTERS = "Secondary Characters"
    SOUTH_AMERICA = "South America"


BARKS_TAG_GROUPS_ALIASES: dict[str, TagGroups] = {str(t.value).lower(): t for t in TagGroups}

BARKS_TAG_CATEGORIES_DICT = {cat.value: cat for cat in TagCategories}

# Late import: barks_tags_data imports Tags/TagCategories/TagGroups from this module.
# The circular import is safe because those enums are fully defined above this line.
from .barks_tags_data import (  # noqa: E402
    BARKS_TAG_CATEGORIES,
    BARKS_TAG_GROUPS,
    BARKS_TAGGED_PAGES,
    BARKS_TAGGED_TITLES,
)


def special_case_personal_favourites_tag_update(my_title_picks: list[Titles]) -> None:
    BARKS_TAGGED_TITLES[Tags.PERSONAL_FAVOURITES] = my_title_picks


def set_tag_alias(main_tag: Tags, alias_tag: Tags) -> None:
    assert alias_tag not in BARKS_TAGGED_TITLES
    BARKS_TAGGED_TITLES[alias_tag] = BARKS_TAGGED_TITLES[main_tag]

    main_tag_title_pages = [(k[1], v) for k, v in BARKS_TAGGED_PAGES.items() if main_tag == k[0]]
    for title, pages in main_tag_title_pages:
        assert (alias_tag, title) not in BARKS_TAGGED_PAGES
        BARKS_TAGGED_PAGES[(alias_tag, title)] = pages


set_tag_alias(Tags.CAMERAS, Tags.PHOTOGRAPHY)


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
