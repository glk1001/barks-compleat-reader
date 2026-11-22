"""How the index screens write a title or tag (barks_reader.core.index_text)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_reader.core.index_text import (
    INDEX_ITEM_MAX_TEXT_WIDTH,
    MAX_TITLE_AND_PAGES_LEN,
    indexable_title,
    indexable_title_from_str,
    shorten_if_necessary,
    shortened_at_a_word,
    shortened_keeping_pages,
    sortable_string,
    stacked_prefix_label,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.parametrize(
    ("text", "listed"),
    [
        ("The Ghost of the Grotto", "Ghost of the Grotto, The"),
        ("A Christmas for Shacktown", "Christmas for Shacktown, A"),
        ("Lost in the Andes!", "Lost in the Andes!"),
        ("Theatre Trouble", "Theatre Trouble"),  # "The" only as a word of its own
        ("THE END", "END, THE"),  # The article keeps its case.
        ("a day at the beach", "day at the beach, a"),
    ],
)
def test_a_leading_article_moves_to_the_end(text: str, listed: str) -> None:
    assert sortable_string(text) == listed


def test_a_long_title_is_shortened_to_fit_a_row() -> None:
    listed = indexable_title_from_str("The " + "word " * 20)
    assert len(listed) <= MAX_TITLE_AND_PAGES_LEN + len(", The")
    assert "..." in listed


def test_a_title_of_one_long_word_is_cut_not_dropped() -> None:
    listed = indexable_title_from_str("X" * (MAX_TITLE_AND_PAGES_LEN + 5))
    assert listed == "X" * (MAX_TITLE_AND_PAGES_LEN - 3) + "..."


def test_a_title_enum_is_listed_by_its_title() -> None:
    assert indexable_title(Titles.GHOST_OF_THE_GROTTO_THE) == "Ghost of the Grotto, The"


class TestShortenIfNecessary:
    def test_a_short_term_is_left_as_it_is(self) -> None:
        assert shorten_if_necessary("Uncle Scrooge") == "Uncle Scrooge"

    def test_a_term_as_long_as_a_row_is_left_as_it_is(self) -> None:
        text = "Uncle Scrooge and Donald Duck!"
        assert len(text) == INDEX_ITEM_MAX_TEXT_WIDTH
        assert shorten_if_necessary(text) == text

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

    @pytest.mark.parametrize("term", ["500,000", "500,000,000", "500,000 dollars"])
    def test_an_ordinary_number_starting_like_the_huge_one_is_kept(self, term: str) -> None:
        """Only the 77-zero number is written out: one that merely starts "500,000" was refused."""
        assert shorten_if_necessary(term) == term

    @pytest.mark.parametrize(
        ("term", "shown"),
        [
            pytest.param(
                "500,000,000,000,000,000,000,000,000,000,000",
                "500,000,000,000,000,000,000...",
                id="a number",
            ),
            pytest.param("Duck" * 10 + " too", "Duck" * 6 + "Duc...", id="a word"),
        ],
    )
    def test_a_first_word_too_long_for_the_row_is_cut_not_dropped(
        self, term: str, shown: str
    ) -> None:
        """`textwrap.shorten` dropped such a word whole, and the row showed only "..."."""
        assert shorten_if_necessary(term) == shown
        assert len(shown) == INDEX_ITEM_MAX_TEXT_WIDTH

    def test_a_long_term_starting_like_the_huge_number_is_shortened(self) -> None:
        term = "500,000 dollars in a bag on the bank's back step"
        assert shorten_if_necessary(term) == "500,000 dollars in a bag on..."


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


def test_a_cut_is_marked_by_the_ellipsis_asked_for() -> None:
    """One helper for the index's rows ("...") and the search's scope chip ("…")."""
    assert shortened_at_a_word("gold and more gold", 12) == "gold and..."
    assert shortened_at_a_word("gold and more gold", 12, ellipsis="…") == "gold and…"
    assert shortened_at_a_word("Duckburg", 5, ellipsis="…") == "Duck…"
    assert shortened_at_a_word("gold", 12, ellipsis="…") == "gold"


def _fits_in(width: int, tried: list[str] | None = None) -> Callable[[str], bool]:
    """Return a row that holds `width` characters, noting each text it is asked about."""

    def fits(text: str) -> bool:
        if tried is not None:
            tried.append(text)
        return len(text) <= width

    return fits


class TestShortenedKeepingPages:
    """A title row too long for its row: the title gives way, the pages stay."""

    def test_a_text_that_fits_is_left_whole(self) -> None:
        full = "Lost in the Andes!, 3-5,12"
        assert shortened_keeping_pages(full, _fits_in(len(full))) == full

    def test_the_title_is_cut_and_its_pages_kept(self) -> None:
        cut = shortened_keeping_pages("Lost in the Andes!, 3-5,12", _fits_in(20))

        assert cut == "Lost in the\u2026, 3-5,12"
        assert len(cut) <= 20  # noqa: PLR2004

    def test_as_much_of_the_title_is_kept_as_fits(self) -> None:
        """One more letter of the title would not fit."""
        full = "Lost in the Andes!, 3-5,12"
        for width in range(len("\u2026, 3-5,12"), len(full)):
            cut = shortened_keeping_pages(full, _fits_in(width))
            kept = cut[: cut.index("\u2026")]
            assert len(cut) <= width
            longer = full[: len(kept) + 1].rstrip()
            assert longer == kept or len(f"{longer}\u2026, 3-5,12") > width

    def test_a_space_before_the_ellipsis_is_dropped(self) -> None:
        cut = shortened_keeping_pages("Lost in the Andes!, 3", _fits_in(len("Lost in \u2026, 3")))
        assert cut == "Lost in\u2026, 3"

    def test_a_title_with_no_pages_is_cut_at_its_end(self) -> None:
        assert shortened_keeping_pages("Lost in the Andes!", _fits_in(8)) == "Lost in\u2026"

    def test_a_comma_in_the_title_is_not_where_its_pages_start(self) -> None:
        """Only a comma before a digit starts the pages."""
        cut = shortened_keeping_pages("Ghost of the Grotto, The, 7", _fits_in(18))
        assert cut == "Ghost of the G\u2026, 7"
        assert len(cut) == 18  # noqa: PLR2004

    def test_a_row_too_narrow_for_any_of_the_title_shows_the_ellipsis_and_pages(self) -> None:
        assert shortened_keeping_pages("Lost in the Andes!, 3-5", _fits_in(2)) == "\u2026, 3-5"

    def test_the_search_asks_about_few_texts(self) -> None:
        """Each ask measures text: a halving, not a walk along the title."""
        tried: list[str] = []
        shortened_keeping_pages("A" * 64 + ", 3", _fits_in(20, tried))
        assert len(tried) <= 8  # noqa: PLR2004
