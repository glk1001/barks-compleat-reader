"""How the index screens write a title or tag (barks_reader.core.index_text)."""

from __future__ import annotations

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.index_text import (
    INDEX_ITEM_MAX_TEXT_WIDTH,
    MAX_TITLE_AND_PAGES_LEN,
    indexable_title,
    indexable_title_from_str,
    shorten_if_necessary,
    sortable_string,
    stacked_prefix_label,
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


class TestShortenIfNecessary:
    def test_a_short_term_is_left_as_it_is(self) -> None:
        assert shorten_if_necessary("Uncle Scrooge") == "Uncle Scrooge"

    def test_a_long_term_is_cut_at_a_word_with_an_ellipsis(self) -> None:
        text = "the quick brown fox jumps over the lazy dog again"
        shortened = shorten_if_necessary(text)
        assert shortened == "the quick brown fox jumps..."
        assert len(shortened) <= INDEX_ITEM_MAX_TEXT_WIDTH

    def test_the_huge_number_is_written_out_in_words(self) -> None:
        """A number of 77 zeros, said in a story, would not shorten readably."""
        number = "500,000" + ",000" * 24 + ".16"
        assert (
            shorten_if_necessary(number) == "500,000,\u2014plus sixty-nine more zeroes\u2014,000.16"
        )


class TestStackedPrefixLabel:
    def test_a_range_is_stacked_over_two_lines(self) -> None:
        assert stacked_prefix_label("sho-shy", ["shop", "shy"]) == "sho\nshy"

    def test_a_single_prefix_label_stays_on_one_line(self) -> None:
        assert stacked_prefix_label("ska", ["skate", "skating"]) == "ska"

    def test_a_part_may_hold_the_separator_itself(self) -> None:
        """A label like "s-sa" runs "s" to "sa", so the ends cannot come from a split."""
        assert stacked_prefix_label("s-sa", ["s", "sap"]) == "s\nsa"

    def test_ends_that_no_longer_rejoin_fall_back_to_the_prefix(self) -> None:
        """Colliding labels are merged upstream; never show a label for the wrong span."""
        assert stacked_prefix_label("sho-shy", ["about", "zebra"]) == "sho-shy"
