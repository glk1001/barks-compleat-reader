"""How the index screens write a title or tag (barks_reader.core.index_text)."""

from __future__ import annotations

import pytest
from barks_fantagraphics.barks_tags import BARKS_TAG_EXTRA_ALIASES, Tags
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.index_text import (
    ALIAS_INDEX_NAMES,
    MAX_TITLE_AND_PAGES_LEN,
    SEARCH_ONLY_ALIASES,
    alias_index_name,
    indexable_title,
    indexable_title_from_str,
    sortable_string,
)


@pytest.mark.parametrize(
    ("text", "listed"),
    [
        ("The Ghost of the Grotto", "Ghost of the Grotto, The"),
        ("A Christmas for Shacktown", "Christmas for Shacktown, A"),
        ("Lost in the Andes!", "Lost in the Andes!"),
        ("Theatre Trouble", "Theatre Trouble"),  # "The" only as a word of its own
    ],
)
def test_a_leading_article_moves_to_the_end(text: str, listed: str) -> None:
    assert sortable_string(text) == listed


def test_a_long_title_is_shortened_to_fit_a_row() -> None:
    listed = indexable_title_from_str("The " + "word " * 20)
    assert len(listed) <= MAX_TITLE_AND_PAGES_LEN + len(", The")
    assert "..." in listed


def test_a_title_enum_is_listed_by_its_title() -> None:
    assert indexable_title(Titles.GHOST_OF_THE_GROTTO_THE) == "Ghost of the Grotto, The"


@pytest.mark.parametrize(
    ("alias", "tag_name"),
    [
        ("amnesia", "amnesia stories"),  # the tag's first word
        ("artifacts", "artifact stories"),  # its plural
        ("splashes", "splash pages"),
        ("utopias", "utopian stories"),
        ("gyro", "Gyro Gearloose"),  # a first name
        ("the beagle boys", "The Beagle Boys"),  # the whole name
        ("pjmcbrine", "P.J.McBrine"),  # the whole name run together
        ("zoola", "Foola Zoola"),  # search only
        ("scrooge", "Uncle Scrooge not in US series"),
    ],
)
def test_an_alias_beside_its_tag_is_left_out(alias: str, tag_name: str) -> None:
    assert alias_index_name(alias, tag_name) is None


@pytest.mark.parametrize(
    ("alias", "tag_name", "listed"),
    [
        ("glomgold", "Flintheart Glomgold", "Glomgold"),
        ("mcbrine", "P.J.McBrine", "McBrine"),  # a full stop ends a word
        ("mcswine", "Mr. McSwine", "McSwine"),
        ("ogilt", "Goldie O'Gilt", "O'Gilt"),  # the apostrophe kept
        ("driving car", "HDL driving car", "driving car"),  # lower case stays
        ("carver beakoff", "Doctor Carver Beakoff", "Carver Beakoff"),
        ("south pole", "Antarctica", "South Pole"),  # not in the name: as listed
        ("spell", "Magica De Spell", "De Spell"),  # the whole surname
    ],
)
def test_a_cross_reference_alias_is_spelled_as_its_tag(
    alias: str, tag_name: str, listed: str
) -> None:
    assert alias_index_name(alias, tag_name) == listed


def test_an_alias_is_only_part_of_a_word_by_a_word_boundary() -> None:
    assert alias_index_name("gilt", "Goldie Giltwhiskers") is None


@pytest.mark.parametrize(("alias", "tag"), BARKS_TAG_EXTRA_ALIASES.items())
def test_every_alias_the_index_lists_has_a_spelling(alias: str, tag: Tags) -> None:
    """A new alias not in its tag's name needs an entry in ALIAS_INDEX_NAMES, or vanishes."""
    tag_name = tag.value
    listed = alias_index_name(alias, tag_name)
    repeats_tag = any(
        tag_name.lower().startswith(stem)
        for stem in (alias, alias.removesuffix("s"), alias.removesuffix("es"))
    ) or alias.replace(" ", "") == "".join(c for c in tag_name.lower() if c.isalnum())
    assert repeats_tag or alias in SEARCH_ONLY_ALIASES or listed is not None
    if listed is not None:
        assert listed.lower().replace("'", "") == alias or alias in ALIAS_INDEX_NAMES


def test_every_search_only_alias_is_an_alias() -> None:
    """A search-only alias the search no longer has is a stale entry."""
    assert BARKS_TAG_EXTRA_ALIASES.keys() >= SEARCH_ONLY_ALIASES


def test_every_alias_index_name_is_an_alias() -> None:
    assert ALIAS_INDEX_NAMES.keys() <= BARKS_TAG_EXTRA_ALIASES.keys()
