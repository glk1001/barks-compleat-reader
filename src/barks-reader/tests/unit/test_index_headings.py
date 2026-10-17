"""How the Main Index heads a tag or tag group (barks_reader.core.index_headings)."""

from __future__ import annotations

import pytest
from barks_fantagraphics.barks_tags import TagGroups, Tags
from barks_reader.core.index_headings import (
    SEE_REFERENCES,
    TAG_INDEX_HEADING_MARKUP,
    TAG_INDEX_HEADINGS,
    index_sort_key,
    tag_group_heading,
    tag_heading,
    tag_heading_markup,
)


@pytest.mark.parametrize(
    ("tag", "heading"),
    [
        (Tags.FLINTHEART_GLOMGOLD, "Glomgold, Flintheart"),  # by surname
        (Tags.MR_MC_SWINE, "McSwine, Mr."),  # a title after the name
        (Tags.DAISY, "Daisy Duck"),  # the core cast, as known
        (Tags.BLACK_PETE, "Black Pete"),  # a nickname, whole
        (Tags.FIRST_DAISY, "Daisy Duck: first appearance"),  # a first, under its subject
        (Tags.BEAGLE_BOYS, "Beagle Boys"),  # no leading article
        (Tags.AMNESIA_STORIES, "amnesia stories"),  # a common noun, lower case
        (Tags.LABRADOR, "Labrador"),  # a place, with its capital
    ],
)
def test_a_tag_is_headed_as_an_index_heads_it(tag: Tags, heading: str) -> None:
    assert tag_heading(tag) == heading


def test_a_tag_group_is_headed_in_lower_case_unless_a_proper_noun() -> None:
    assert tag_group_heading(TagGroups.PIG_VILLAINS) == "pig villains"
    assert tag_group_heading(TagGroups.AFRICA) == "Africa"


def test_every_first_is_filed_under_its_subject() -> None:
    firsts = [tag for tag in Tags if tag.value.startswith("first ")]
    assert firsts
    assert all(not tag_heading(tag).startswith("first ") for tag in firsts)


def test_a_first_sits_beside_its_subjects_own_heading() -> None:
    """A first's subject is spelled as its subject's heading, so the two sort together."""
    subjects = {tag_heading(tag) for tag in Tags}
    for tag in (Tags.FIRST_DAISY, Tags.FIRST_FLINTHEART, Tags.FIRST_GLADSTONE, Tags.FIRST_BOLIVAR):
        assert tag_heading(tag).split(":")[0] in subjects


def test_no_heading_override_repeats_the_tag_name() -> None:
    assert all(heading != tag.value for tag, heading in TAG_INDEX_HEADINGS.items())


@pytest.mark.parametrize("name", ["Scrooge", "Goldie", "Helper", "Zombie", "Gearloose", "Pete"])
def test_the_names_the_cast_is_known_by_are_cross_referenced(name: str) -> None:
    """Once alias rows, these left the index with them; a reader looks for "Scrooge" at S."""
    assert name in SEE_REFERENCES


def test_no_cross_reference_points_to_where_the_reader_already_is() -> None:
    """A "See" whose name is its target's heading, or starts it, would sit beside it."""
    for name, tag in SEE_REFERENCES.items():
        assert not tag_heading(tag).lower().startswith(name.lower()), name


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("Officer of the Day", "O'Gilt, Goldie"),  # the apostrophe ignored
        ("O'Gilt, Goldie", "Ohio"),
        ("Daisy Duck", "Daisy Duck: first appearance"),
        ("Daisy Duck: first appearance", "Daisy's Dazed Days"),  # word by word
        ("McBrine, P.J.", "McCobb, Cornelius"),
    ],
)
def test_entries_sort_word_by_word_ignoring_case_and_punctuation(before: str, after: str) -> None:
    assert index_sort_key(before) < index_sort_key(after)


def test_the_sort_key_is_the_letters_digits_and_spaces_lower_cased() -> None:
    """Its words kept apart, so "Daisy Duck" sorts before "Daisy's Dazed Days"."""
    assert index_sort_key("Donald's Gold-Mine, 1952!") == "donalds goldmine 1952"


def test_neighbor_jones_first_real_appearance_has_real_in_italics() -> None:
    tag = Tags.FIRST_REAL_NEIGHBOR_JONES
    assert tag_heading(tag) == "Neighbor Jones: first real appearance"  # sorts plain
    assert tag_heading_markup(tag) == "Neighbor Jones: first [i]real[/i] appearance"


def test_a_heading_without_markup_is_escaped() -> None:
    assert tag_heading_markup(Tags.DAISY) == "Daisy Duck"


def test_every_markup_heading_reads_as_its_plain_heading() -> None:
    for tag, markup in TAG_INDEX_HEADING_MARKUP.items():
        assert markup.replace("[i]", "").replace("[/i]", "") == tag_heading(tag)
