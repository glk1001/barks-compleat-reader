# cspell:ignore chea shless lunt aeiou

from __future__ import annotations

import string

import pytest
from barks_fantagraphics.alpha_split import (
    MAX_PREFIX_BUTTONS_PER_LETTER,
    PREFERRED_BUCKET_SIZE,
    bucket_label,
    first_letter_key,
    group_by_first_letter,
    split_alpha_terms,
    split_letter_terms,
)


def _flatten(split: dict[str, dict[str, list[str]]]) -> list[str]:
    return [t for buckets in split.values() for bucket in buckets.values() for t in bucket]


class TestFirstLetterKey:
    @pytest.mark.parametrize(
        ("term", "expected"),
        [
            ("apple", "a"),
            ("Apple", "a"),
            ("'tis", "'"),
            ("7", "0"),
            ("500,000", "0"),
            ("zebra", "z"),
        ],
    )
    def test_key(self, term: str, expected: str) -> None:
        assert first_letter_key(term) == expected

    def test_empty_term_raises(self) -> None:
        with pytest.raises(ValueError, match="empty term"):
            first_letter_key("")

    def test_invalid_first_letter_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid first letter"):
            first_letter_key("-bad-term")


class TestGroupByFirstLetter:
    def test_groups_and_collapses_digits(self) -> None:
        grouped = group_by_first_letter(["1st", "7th", "apple", "ant", "bee"])
        assert grouped == {"0": ["1st", "7th"], "a": ["apple", "ant"], "b": ["bee"]}

    def test_non_contiguous_letter_runs_are_accumulated_not_overwritten(self) -> None:
        """A letter interrupted by collation ordering must keep all of its terms.

        The live index sorts "Si" between "shysters" and "si-e-lent" but puts the
        accented "si" in between, splitting the run. An implementation that assigns
        rather than accumulates silently loses the earlier terms.
        """
        grouped = group_by_first_letter(["ax", "bee", "az"])
        assert grouped == {"a": ["ax", "az"], "b": ["bee"]}


class TestBucketLabel:
    @pytest.mark.parametrize(
        ("bucket", "expected"),
        [
            (["show", "shy"], "sho-shy"),
            (["shoe", "show"], "shoe-show"),
            (["car", "cast"], "car-cas"),
            (["chea", "chew"], "chea-chew"),
            (["ant"], "ant"),
            (["a"], "a"),
        ],
    )
    def test_label(self, bucket: list[str], expected: str) -> None:
        assert bucket_label(bucket) == expected

    def test_trailing_punctuation_is_trimmed_from_range_ends(self) -> None:
        """A hyphen inside a term must not read as the range separator."""
        assert bucket_label(["sh-boom", "shless"]) == "sh-shl"
        assert bucket_label(["c-note", "cargo"]) == "c-ca"

    def test_label_parts_are_length_capped(self) -> None:
        """A narrow button cannot show a whole long word."""
        label = bucket_label(["antidisestablishmentarian", "antidisestablishmentarianism"])
        assert label == "anti"

    def test_differing_ends_give_a_range(self) -> None:
        assert bucket_label(["cash", "chip", "cove"]) == "ca-co"

    def test_empty_bucket_raises(self) -> None:
        with pytest.raises(ValueError, match="empty bucket"):
            bucket_label([])


class TestSplitLetterTerms:
    def test_empty_returns_empty(self) -> None:
        assert split_letter_terms([]) == []

    def test_small_letter_is_a_single_bucket(self) -> None:
        terms = [f"a{i:02d}" for i in range(10)]
        assert split_letter_terms(terms) == [terms]

    def test_oversized_shared_prefix_is_split_by_deepening(self) -> None:
        """A two-character prefix bigger than the target must still be broken up.

        The old algorithm could only merge neighbouring two-character buckets, so
        "co" stayed as one 548-term wall no matter what the target was.
        """
        terms = sorted(f"co{a}{b}" for a in string.ascii_lowercase for b in string.ascii_lowercase)
        buckets = split_letter_terms(terms)

        assert len(buckets) > 1
        assert max(len(b) for b in buckets) <= PREFERRED_BUCKET_SIZE

    def test_never_exceeds_the_prefix_bar_capacity(self) -> None:
        terms = [f"s{a}{b}{c}" for a in "abcde" for b in string.ascii_lowercase for c in "xyz"]
        buckets = split_letter_terms(sorted(terms))

        assert len(buckets) <= MAX_PREFIX_BUTTONS_PER_LETTER

    def test_identical_terms_that_cannot_be_split_do_not_recurse_forever(self) -> None:
        terms = ["same"] * (PREFERRED_BUCKET_SIZE * 3)
        buckets = split_letter_terms(terms)

        assert sum(len(b) for b in buckets) == len(terms)

    def test_every_term_is_kept_exactly_once_and_in_order(self) -> None:
        terms = sorted(f"a{a}{b}" for a in string.ascii_lowercase for b in string.ascii_lowercase)
        buckets = split_letter_terms(terms)

        assert [t for bucket in buckets for t in bucket] == terms


class TestSplitAlphaTerms:
    def test_loses_no_terms_when_a_prefix_run_is_interrupted(self) -> None:
        """Regression: the term "Si" used to vanish from the index entirely.

        Collation puts the accented "si" between "Si" and "si-e-lent", so the "si"
        prefix run is not contiguous. Resetting the bucket on every prefix change
        wiped the earlier one.
        """
        terms = ["shylocks", "shyster", "shysters", "Si", "si", "si-e-lent", "si-lunt"]

        split = split_alpha_terms(terms)

        assert sorted(_flatten(split)) == sorted(terms)
        assert "Si" in _flatten(split)

    def test_groups_by_letter_with_digits_under_zero(self) -> None:
        split = split_alpha_terms(["1st", "apple", "ant", "bee"])
        assert set(split) == {"0", "a", "b"}

    def test_invalid_first_letter_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid first letter"):
            split_alpha_terms(["-bad-term"])

    def test_empty_input_gives_empty_split(self) -> None:
        assert split_alpha_terms([]) == {}

    def test_all_buckets_stay_within_the_bar_capacity(self) -> None:
        terms = sorted(
            f"{a}{b}{c}"
            for a in string.ascii_lowercase
            for b in string.ascii_lowercase
            for c in "aeiou"
        )

        split = split_alpha_terms(terms)

        for letter, buckets in split.items():
            assert len(buckets) <= MAX_PREFIX_BUTTONS_PER_LETTER, letter
        assert sorted(_flatten(split)) == sorted(terms)
