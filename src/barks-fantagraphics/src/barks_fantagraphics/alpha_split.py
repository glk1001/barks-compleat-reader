"""Split a sorted term list into the A-Z / prefix buckets the index screens browse.

The reader shows a side A-Z menu and, for the word index, a row of prefix buttons
across the top. Each prefix button opens one bucket of terms into a multi-column
grid. This module decides where those buckets fall.

Two constraints shape the algorithm:

* The prefix bar is a single fixed row, so a letter must not need more buttons than
  it has slots (``MAX_PREFIX_BUTTONS_PER_LETTER``).
* A bucket has to fit comfortably on screen, so buckets should be as close to
  ``PREFERRED_BUCKET_SIZE`` as the first constraint allows.

Bucketing purely by two-character prefix cannot satisfy either one: "co" alone holds
several hundred terms and can never be made smaller, while "bc" holds one. So an
oversized group is re-bucketed on a longer prefix until it fits, and undersized
neighbors are merged back up to the target.

Pure and Whoosh-free, so it can be tested without an index.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .search_ports import AlphaSplitTerms

# Terms per prefix bucket when the bar has room for it.
PREFERRED_BUCKET_SIZE = 56

# Slots in the prefix bar (`alphabet_top_split_layout` in index_screen.kv). A letter
# whose terms will not fit in this many buckets gets proportionally larger buckets.
MAX_PREFIX_BUTTONS_PER_LETTER = 20

# Terms are bucketed on a two-character prefix, lengthened while a bucket is too big.
_MIN_PREFIX_LEN = 2
_MAX_PREFIX_LEN = 16

# Longest prefix shown on a button; the bar's columns are narrow.
_MAX_LABEL_PART_LEN = 3

# Digits all collapse into a single "0" letter group.
_DIGIT_GROUP_KEY = "0"


def first_letter_key(term: str) -> str:
    """Return the A-Z menu key a term belongs under.

    Args:
        term: A non-empty index term.

    Returns:
        The lowercased first character, with all digits collapsed to ``"0"``.

    Raises:
        ValueError: If the term is empty or does not start with a letter, digit or
            apostrophe.

    """
    if not term:
        msg = "Cannot take the first-letter key of an empty term."
        raise ValueError(msg)

    first = term[0].lower()
    if first.isdigit():
        return _DIGIT_GROUP_KEY
    if not (("a" <= first <= "z") or first == "'"):
        msg = f'Invalid first letter: "{first}". Term: "{term}".'
        raise ValueError(msg)
    return first


def group_by_first_letter(terms: Iterable[str]) -> dict[str, list[str]]:
    """Group terms under their A-Z menu key, preserving the given order.

    Unlike a single pass that assumes each letter's terms are contiguous, this
    accumulates, so a letter interrupted by collation ordering keeps all its terms.

    Args:
        terms: Index terms, already sorted for display.

    Returns:
        A mapping of first-letter key to the terms under it.

    """
    grouped: dict[str, list[str]] = OrderedDict()
    for term in terms:
        grouped.setdefault(first_letter_key(term), []).append(term)
    return grouped


def _bucket_by_prefix(terms: list[str], prefix_len: int) -> list[list[str]]:
    """Bucket terms by their first ``prefix_len`` characters, preserving order."""
    buckets: dict[str, list[str]] = OrderedDict()
    for term in terms:
        buckets.setdefault(term[:prefix_len].lower(), []).append(term)
    return list(buckets.values())


def _split_to_fit(terms: list[str], target: int, prefix_len: int) -> list[list[str]]:
    """Recursively lengthen the prefix until every bucket is within ``target``."""
    if len(terms) <= target or prefix_len > _MAX_PREFIX_LEN:
        return [terms]

    buckets = _bucket_by_prefix(terms, prefix_len)
    if len(buckets) == 1:
        # Every term shares this prefix -- "co" holds hundreds of them. A longer
        # prefix may still separate them, so deepen rather than give up. The
        # prefix-length ceiling terminates the recursion on genuine duplicates.
        return _split_to_fit(terms, target, prefix_len + 1)

    split: list[list[str]] = []
    for bucket in buckets:
        split.extend(_split_to_fit(bucket, target, prefix_len + 1))
    return split


def _merge_small_neighbors(buckets: list[list[str]], target: int) -> list[list[str]]:
    """Combine consecutive buckets while they still fit within ``target``."""
    merged: list[list[str]] = []
    for bucket in buckets:
        if merged and len(merged[-1]) + len(bucket) <= target:
            merged[-1].extend(bucket)
        else:
            merged.append(list(bucket))
    return merged


def _target_bucket_size(term_count: int, max_buckets: int) -> int:
    """Return the smallest bucket size that keeps a letter within ``max_buckets``."""
    if max_buckets <= 0:
        return max(PREFERRED_BUCKET_SIZE, term_count)
    return max(PREFERRED_BUCKET_SIZE, math.ceil(term_count / max_buckets))


def split_letter_terms(
    terms: list[str],
    max_buckets: int = MAX_PREFIX_BUTTONS_PER_LETTER,
) -> list[list[str]]:
    """Split one letter's terms into display buckets.

    Args:
        terms: The letter's terms, already sorted for display.
        max_buckets: How many prefix buttons the bar can show for one letter.

    Returns:
        The buckets, in display order. Every term appears exactly once.

    """
    if not terms:
        return []

    target = _target_bucket_size(len(terms), max_buckets)
    buckets = _merge_small_neighbors(_split_to_fit(terms, target, _MIN_PREFIX_LEN), target)

    # A letter dominated by one inseparable prefix can still overflow the bar, because
    # such a bucket cannot be split at any depth. Widen the target until it fits.
    while max_buckets > 0 and len(buckets) > max_buckets:
        target = max(target + 1, math.ceil(target * 1.1))
        buckets = _merge_small_neighbors(_split_to_fit(terms, target, _MIN_PREFIX_LEN), target)

    return buckets


def bucket_label(bucket: list[str]) -> str:
    """Return the prefix-button label for a bucket.

    Labelling with only the bucket's first prefix hides what it covers -- a button
    reading "cd" may run to "cf". A range makes the span visible.

    Args:
        bucket: A non-empty bucket of terms in display order.

    Returns:
        A single prefix when the ends agree, otherwise ``"first-last"``.

    Raises:
        ValueError: If the bucket is empty.

    """
    if not bucket:
        msg = "Cannot label an empty bucket."
        raise ValueError(msg)

    first, last = bucket[0].lower(), bucket[-1].lower()
    shared = 0
    while shared < min(len(first), len(last)) and first[shared] == last[shared]:
        shared += 1

    length = min(max(_MIN_PREFIX_LEN, shared + 1), _MAX_LABEL_PART_LEN)
    start, end = _trim_label_part(first[:length]), _trim_label_part(last[:length])
    return start if start == end else f"{start}-{end}"


def _trim_label_part(part: str) -> str:
    """Drop trailing punctuation from one side of a range label.

    Terms may contain hyphens ("si-e-lent"), which would otherwise collide with the
    hyphen separating the two ends of the range and read as "sh--shl".
    """
    trimmed = part.rstrip("-.,")
    return trimmed or part


def split_alpha_terms(
    terms: Iterable[str],
    max_buckets: int = MAX_PREFIX_BUTTONS_PER_LETTER,
) -> AlphaSplitTerms:
    """Split a sorted term list into ``{first_letter: {label: terms}}``.

    Args:
        terms: All index terms, already sorted for display.
        max_buckets: How many prefix buttons the bar can show for one letter.

    Returns:
        Terms grouped by first letter and then by prefix-button label. Every input
        term appears exactly once.

    """
    split: AlphaSplitTerms = {}
    for letter, letter_terms in group_by_first_letter(terms).items():
        buckets = split_letter_terms(letter_terms, max_buckets)
        labelled: dict[str, list[str]] = OrderedDict()
        for bucket in buckets:
            label = bucket_label(bucket)
            # Two buckets can only collide on a label if one spans a sub-range of the
            # other; merging keeps the guarantee that no term is ever dropped.
            labelled.setdefault(label, []).extend(bucket)
        split[letter] = labelled
    return split
