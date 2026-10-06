"""Barks's own spellings: a word list the OCR tools check lettering against.

Nothing in this repo reads it (``../barks-ocr`` does), so these tests are what
loads it here: they hold it to the shape a lookup by lower-cased word needs.
"""

from __future__ import annotations

from barks_fantagraphics.barks_words import BARKSIAN_SPELLING


def test_it_is_a_frozen_set_of_words() -> None:
    assert isinstance(BARKSIAN_SPELLING, frozenset)
    assert BARKSIAN_SPELLING
    assert all(isinstance(word, str) for word in BARKSIAN_SPELLING)


def test_every_word_is_lower_case_so_a_lower_cased_lookup_finds_it() -> None:
    assert sorted(w for w in BARKSIAN_SPELLING if w != w.lower()) == []


def test_every_entry_is_one_word_with_no_whitespace() -> None:
    assert sorted(w for w in BARKSIAN_SPELLING if not w or w.split() != [w]) == []


def test_barks_spellings_beyond_plain_letters_are_kept() -> None:
    """The lettering's accents, fractions and subscripts are spellings too."""
    assert {"señor", "13½", "bo₂", "100-pigeon"} <= BARKSIAN_SPELLING
