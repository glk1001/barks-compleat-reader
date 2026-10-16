"""How the Main Index heads a tag or tag group, after the usual book-index conventions.

The tags' own names serve the search, the wiki joins and the sibling repos, so they stay
as they are; the index writes them its own way:

- People are filed by surname ("Glomgold, Flintheart"), a rank or title after the name
  ("McSwine, Mr."). A name known whole stays whole: the core cast ("Daisy Duck", "Gyro
  Gearloose"), nicknames ("Black Pete") and puns that only work whole ("Hassan Ben Jaild").
- A "first" is filed under its subject, beside the subject's own heading ("Daisy Duck:
  first appearance"), not under F.
- Common nouns are lower case, proper nouns with capitals, and a subject heading has no
  leading article ("Beagle Boys"; titles keep theirs, moved to the end).
- A reader's other name for an entry is a "See" cross-reference to it.
- Sorting is word by word, ignoring case and punctuation ("O'Gilt" files as "ogilt").

Kivy-free, so the headings can be tested without the screen.
"""

from __future__ import annotations

from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_fantagraphics.speech_markup import escape_markup

# The tags the index heads otherwise than by their names.
TAG_INDEX_HEADINGS: dict[Tags, str] = {
    # People, by surname.
    Tags.APPLECHEEKS_TEENGIGGLE: "Teengiggle, Applecheeks",
    Tags.ARGUS_MCFIENDY: "McFiendy, Argus",
    Tags.AZURE_BLUE: "Blue, Azure",
    Tags.BENZENE_BANZOONY: "Banzoony, Benzene",
    Tags.CARVER_BEAKOFF: "Beakoff, Doctor Carver",
    Tags.CHISEL_MC_SUE: "McSue, Chisel",
    Tags.CORNELIUS_COOT: "Coot, Cornelius",
    Tags.CORNELIUS_MC_COBB: "McCobb, Cornelius",
    Tags.FLINTHEART_GLOMGOLD: "Glomgold, Flintheart",
    Tags.GOLDIE_OGILT: "O'Gilt, Goldie",
    Tags.J_MORGANBILT_GILTWHISKERS: "Giltwhiskers, J. Morganbilt",
    Tags.JAYNE_GIRLSFIELD: "Girlsfield, Jayne",
    Tags.JUGHEAD_JONES: "Jones, Jughead",
    Tags.LONGHORN_TALLGRASS: "Tallgrass, Longhorn",
    Tags.MR_MC_SWINE: "McSwine, Mr.",
    Tags.P_J_MC_BRINE: "McBrine, P.J.",
    Tags.PETER_SCHILLING_FAVOURITES: "Schilling, Peter",
    Tags.PORKMAN_DE_LARDO: "Lardo, Porkman de",
    Tags.PORKO_DE_LARDO: "Lardo, Porko de",
    Tags.PULPHEART_CLABBERHEAD: "Clabberhead, Pulpheart",
    Tags.ROCKJAW_BUMRISK: "Bumrisk, Rockjaw",
    Tags.SOAPY_SLICK: "Slick, Soapy",
    # Firsts, under their subjects.
    Tags.FIRST_BEAGLE_BOYS: "Beagle Boys: first appearance",
    Tags.FIRST_BOLIVAR: "Bolivar: first appearance",
    Tags.FIRST_CAR_313: "313: first appearance",
    Tags.FIRST_DAISY: "Daisy Duck: first appearance",
    Tags.FIRST_DUCKBURG: "Duckburg: first mention",
    Tags.FIRST_FLINTHEART: "Glomgold, Flintheart: first appearance",
    Tags.FIRST_GARE_INK: "Garé: first inked story",
    Tags.FIRST_GLADSTONE: "Gladstone Gander: first appearance",
    Tags.FIRST_GYRO_NOT_IN_GG: "Gyro Gearloose: first appearance",
    Tags.FIRST_HERBERT: "Herbert: first appearance",
    Tags.FIRST_LITTLE_HELPER: "Little Helper: first appearance",
    Tags.FIRST_MAGICA: "Magica De Spell: first appearance",
    Tags.FIRST_MONEY_BIN: "Money Bin: first appearance",
    Tags.FIRST_MONEY_SWIM: "Uncle Scrooge: first money swim",
    Tags.FIRST_NEIGHBOR_JONES: "Jones, Mr.: first appearance",
    Tags.FIRST_NUMBER_ONE_DIME: "number one dime: first appearance",
    Tags.FIRST_PIG_VILLAIN: "pig villains: first",
    Tags.FIRST_REAL_NEIGHBOR_JONES: "Neighbor Jones: first real appearance",
    Tags.FIRST_UNCLE_SCROOGE: "Uncle Scrooge: first appearance",
    Tags.FIRST_WORRY_ROOM: "worry room: first appearance",
    # Case and wording.
    Tags.LABRADOR: "Labrador",
    Tags.WIKI_NOTABLE_STORIES: "notable stories (wiki)",
    Tags.SCROOGE_NOT_IN_US: "Uncle Scrooge: outside the Uncle Scrooge series",
    Tags.GYRO_IN_GG: "Gyro Gearloose: in his own series",
    Tags.GYRO_NOT_IN_GG: "Gyro Gearloose: outside his own series",
}

# The headings the index shows with Kivy markup; each reads as its plain heading.
# Mr. Jones first appeared earlier, but only became Neighbor Jones in "Good Neighbors".
TAG_INDEX_HEADING_MARKUP: dict[Tags, str] = {
    Tags.FIRST_REAL_NEIGHBOR_JONES: "Neighbor Jones: first [i]real[/i] appearance",
}

# The tag groups the index heads otherwise than by their names.
TAG_GROUP_INDEX_HEADINGS: dict[TagGroups, str] = {
    TagGroups.ONE_OFF_CHARACTERS: "one-off characters",
    TagGroups.OTHER_PLACES: "other places",
    TagGroups.PIG_VILLAINS: "pig villains",
    TagGroups.PRIMARY_CHARACTERS: "primary characters",
    TagGroups.SECONDARY_CHARACTERS: "secondary characters",
}

# A reader's other names for a tag, each listed as "<name>. See <the tag's heading>".
SEE_REFERENCES: dict[str, Tags] = {
    "car 313": Tags.CAR_313,
    "De Spell": Tags.MAGICA_DE_SPELL,
    "driving car": Tags.HDL_DRIVING_CAR,
    "Gearloose": Tags.GYRO_GEARLOOSE,
    "Glittering Goldie": Tags.GOLDIE_OGILT,
    "Jones": Tags.NEIGHBOR_JONES,
    "Mount Demon Tooth": Tags.OLD_DEMON_TOOTH,
    "Pete": Tags.BLACK_PETE,
    "Snozzie": Tags.GENERAL_SNOZZIE,
    "South Pole": Tags.ANTARCTICA,
    "Woodchucks": Tags.JUNIOR_WOODCHUCKS,
}


def tag_heading(tag: Tags) -> str:
    """Return the Main Index heading for `tag`.

    Args:
        tag: The tag.

    Returns:
        Its heading in `TAG_INDEX_HEADINGS`, else its name without a leading "The".

    """
    return TAG_INDEX_HEADINGS.get(tag) or _without_leading_article(tag.value)


def tag_heading_markup(tag: Tags) -> str:
    """Return the Main Index heading for `tag` as Kivy markup.

    Args:
        tag: The tag.

    Returns:
        Its markup in `TAG_INDEX_HEADING_MARKUP`, else its heading, escaped.

    """
    return TAG_INDEX_HEADING_MARKUP.get(tag) or escape_markup(tag_heading(tag))


def tag_group_heading(tag_group: TagGroups) -> str:
    """Return the Main Index heading for `tag_group`.

    Args:
        tag_group: The tag group.

    Returns:
        Its heading in `TAG_GROUP_INDEX_HEADINGS`, else its name.

    """
    return TAG_GROUP_INDEX_HEADINGS.get(tag_group) or tag_group.value


def index_sort_key(text: str) -> str:
    """Return the key an index entry sorts by: word by word, ignoring case and punctuation.

    Args:
        text: The entry as the index shows it.

    Returns:
        The text lower-cased, with only its letters, digits and spaces.

    """
    return "".join(c for c in text.lower() if c.isalnum() or c == " ")


def _without_leading_article(text: str) -> str:
    return text.removeprefix("The ")
