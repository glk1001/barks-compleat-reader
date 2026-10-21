"""Property-based tests for the pure parts of barks_fantagraphics: what holds for any input.

Module-level ``@given`` functions, as the reader's test_properties.py explains: mutmut
runs pytest many times in one process, and a class-scoped ``@given`` trips
Hypothesis's differing-executors health check from the second run on.
"""

from __future__ import annotations

import re
import string
from typing import Any

import pytest
from barks_fantagraphics.alpha_split import (
    bucket_label,
    bucket_label_parts,
    first_letter_key,
    group_by_first_letter,
    split_alpha_terms,
    split_letter_terms,
)
from barks_fantagraphics.panel_geometry import centered_bbox, scale_height
from barks_fantagraphics.search_query import Combine, read_range
from barks_fantagraphics.speech_groupers import join_line_breaks
from barks_fantagraphics.speech_markup import (
    EMPHASIS_TAGS,
    escape_markup,
    has_markup,
    markup_from_spans,
    same_text_ignoring_markup,
    strip_markup,
    transform_lettering_only,
    unescape_markup,
    validate_markup,
)
from barks_fantagraphics.tag_query import (
    ParsedTagQuery,
    TagSelection,
    has_tag_syntax,
    parse_tag_query,
    range_text,
)
from barks_fantagraphics.whoosh_punct_tokenizer import WordWithPunctTokenizer
from hypothesis import given, settings
from hypothesis import strategies as st

# --- speech markup ------------------------------------------------------------

_TEXT = st.text(max_size=60)


@given(_TEXT)
def test_escaping_then_unescaping_gives_the_text_back(text: str) -> None:
    assert unescape_markup(escape_markup(text)) == text


@given(_TEXT)
def test_stripping_escaped_text_gives_the_text_back_and_it_validates(text: str) -> None:
    """The docstring's claim: strip_markup inverts escape_markup for text carrying no tag."""
    escaped = escape_markup(text)
    assert strip_markup(escaped) == text
    assert validate_markup(escaped) == []
    assert not has_markup(escaped)


@st.composite
def texts_with_spans(draw: st.DrawFn) -> tuple[str, list[list]]:
    """Plain text and non-overlapping emphasis spans over it, in any order and either naming."""
    text = draw(_TEXT)
    cuts = sorted(draw(st.sets(st.integers(min_value=0, max_value=len(text)), max_size=8)))
    kinds = st.sampled_from(["b", "i", "bold", "italic"])
    spans = [[start, end, draw(kinds)] for start, end in zip(cuts[::2], cuts[1::2], strict=False)]
    return text, draw(st.permutations(spans))


@given(texts_with_spans())
def test_markup_from_spans_validates_and_strips_back_to_the_text(
    text_and_spans: tuple[str, list[list]],
) -> None:
    text, spans = text_and_spans
    marked = markup_from_spans(text, spans)
    assert validate_markup(marked) == []
    assert strip_markup(marked) == text
    assert has_markup(marked) == bool(spans)
    assert same_text_ignoring_markup(marked, escape_markup(text))


@given(texts_with_spans())
def test_a_transform_of_the_lettering_leaves_every_markup_token_in_place(
    text_and_spans: tuple[str, list[list]],
) -> None:
    text, spans = text_and_spans
    marked = markup_from_spans(text, spans)
    assert transform_lettering_only(marked, lambda s: s) == marked
    # The same length-preserving change made to the text first lands in the same markup.
    changed = transform_lettering_only(marked, lambda s: s.replace("a", "@"))
    assert changed == markup_from_spans(text.replace("a", "@"), spans)
    assert re.findall(r"\[/?[bi]\]|&amp;|&bl;|&br;", changed) == re.findall(
        r"\[/?[bi]\]|&amp;|&bl;|&br;", marked
    )


def test_the_tags_the_spans_name_are_the_emphasis_tags() -> None:
    assert EMPHASIS_TAGS == ("b", "i")


@given(st.text(alphabet=st.sampled_from(["a", "-", "\n", "­", "\u200b", " "]), max_size=30))
def test_joining_line_breaks_never_grows_the_text_and_commutes_with_stripping(text: str) -> None:
    joined = join_line_breaks(text)
    assert len(joined) <= len(text)
    if "\n" not in text:
        assert joined == text
    assert strip_markup(join_line_breaks(escape_markup(text))) == joined


# --- tag queries ----------------------------------------------------------------

_TAG_PIECES = [
    "scrooge",
    "gyro",
    "x",
    " ",
    "+",
    ",",
    "|",
    "-",
    "year:",
    "vol:",
    "1950",
    "55",
    "7",
    "indo-china",
]


def _is_one_outcome(parsed: ParsedTagQuery) -> bool:
    return (parsed.selection is None) != (parsed.error is None)


@given(st.text(max_size=60))
@settings(max_examples=300)
def test_no_text_makes_the_tag_parser_raise(text: str) -> None:
    assert _is_one_outcome(parse_tag_query(text))
    has_tag_syntax(text)


@given(st.lists(st.sampled_from(_TAG_PIECES), max_size=12).map("".join))
@settings(max_examples=500)
def test_no_mix_of_the_tag_syntax_makes_the_parser_raise(text: str) -> None:
    assert _is_one_outcome(parse_tag_query(text))


_NAMES = st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=8)
_YEARS = st.integers(min_value=1940, max_value=1970)
_VOLUMES = st.integers(min_value=1, max_value=30)


@st.composite
def ranges(draw: st.DrawFn, values: st.SearchStrategy[int]) -> tuple[int, int]:
    first, last = sorted((draw(values), draw(values)))
    return first, last


@st.composite
def selections(draw: st.DrawFn) -> TagSelection:
    """Draw a selection as typed could give: distinct names, ANY only where a separator shows it."""
    names = draw(st.lists(_NAMES, min_size=1, max_size=5, unique=True))
    split = draw(st.integers(min_value=0, max_value=len(names)))
    included, excluded = tuple(names[:split]), tuple(names[split:])
    combine = draw(st.sampled_from(list(Combine))) if len(included) > 1 else Combine.ALL
    return TagSelection(
        included,
        excluded,
        combine,
        years=draw(st.none() | ranges(_YEARS)),
        volumes=draw(st.none() | ranges(_VOLUMES)),
    )


@given(selections())
def test_a_selection_described_then_parsed_is_the_same_selection(selection: TagSelection) -> None:
    parsed = parse_tag_query(selection.describe())
    assert parsed.error is None
    assert parsed.selection == selection


@given(ranges(st.integers(min_value=1900, max_value=2099)))
def test_a_years_range_as_text_reads_back(first_last: tuple[int, int]) -> None:
    assert read_range(range_text(first_last, years=True), years=True) == first_last


@given(ranges(st.integers(min_value=1, max_value=99)))
def test_a_volumes_range_as_text_reads_back(first_last: tuple[int, int]) -> None:
    assert read_range(range_text(first_last, years=False), years=False) == first_last


# --- alpha split ----------------------------------------------------------------

_TERM_CHARS = string.ascii_lowercase + string.digits + "'-. "
_TERMS = st.text(alphabet=_TERM_CHARS, min_size=1, max_size=10).filter(
    lambda t: t[0] != " " and t[0] not in "-."
)


@st.composite
def sorted_terms(draw: st.DrawFn) -> list[str]:
    return sorted(draw(st.lists(_TERMS, max_size=60)))


@given(sorted_terms(), st.integers(min_value=1, max_value=6))
def test_every_term_lands_in_one_bucket_under_its_letter(
    terms: list[str], max_buckets: int
) -> None:
    split = split_alpha_terms(terms, max_buckets)
    assert [t for buckets in split.values() for b in buckets.values() for t in b] == terms
    for letter, buckets in split.items():
        assert len(buckets) <= max_buckets
        for terms_in_bucket in buckets.values():
            assert all(first_letter_key(t) == letter for t in terms_in_bucket)


@given(sorted_terms())
def test_grouping_by_first_letter_keeps_the_order_within_each_letter(terms: list[str]) -> None:
    grouped = group_by_first_letter(terms)
    for letter, letter_terms in grouped.items():
        assert letter_terms == [t for t in terms if first_letter_key(t) == letter]
    assert split_letter_terms([]) == []


@given(st.lists(_TERMS, min_size=1, max_size=20).map(sorted))
def test_a_bucket_label_is_short_lowercase_and_made_of_its_two_ends(bucket: list[str]) -> None:
    start, end = bucket_label_parts(bucket)
    for part in (start, end):
        assert 1 <= len(part) <= 3  # noqa: PLR2004
        assert part == part.lower()
    assert bucket_label(bucket) == (start if start == end else f"{start}-{end}")
    with pytest.raises(ValueError, match="empty bucket"):
        bucket_label([])


# --- panel geometry -------------------------------------------------------------


@st.composite
def page_and_box(draw: st.DrawFn) -> tuple[int, int, int, int, int]:
    page_w = draw(st.integers(min_value=1, max_value=5000))
    page_h = draw(st.integers(min_value=1, max_value=7000))
    box_w = draw(st.integers(min_value=1, max_value=page_w))
    box_h = draw(st.integers(min_value=1, max_value=page_h))
    margin = draw(st.integers(min_value=0, max_value=(page_w - box_w) // 2))
    return page_w, page_h, box_w, box_h, margin


@given(page_and_box())
def test_a_centered_box_has_its_size_and_sits_inside_the_page(
    dims: tuple[int, int, int, int, int],
) -> None:
    page_w, page_h, box_w, box_h, margin = dims
    box = centered_bbox(page_w, page_h, box_w, box_h, margin)
    assert (box.get_width(), box.get_height()) == (box_w, box_h)
    assert 0 <= box.x_min <= box.x_max < page_w
    assert 0 <= box.y_min <= box.y_max < page_h
    assert box.x_min == margin
    assert abs(box.y_min - (page_h - 1 - box.y_max)) <= 1


@given(
    st.integers(min_value=1, max_value=10_000),
    st.integers(min_value=1, max_value=10_000),
    st.integers(min_value=0, max_value=10_000),
)
def test_a_scaled_height_keeps_the_aspect_within_rounding(
    target_w: int, source_w: int, source_h: int
) -> None:
    scaled = scale_height(target_w, source_w, source_h)
    assert abs(scaled * source_w - source_h * target_w) <= source_w / 2


# --- tokenizer ------------------------------------------------------------------


@given(st.text(max_size=80))
@settings(max_examples=300)
def test_every_token_is_the_text_at_its_characters_and_positions_count_up(text: str) -> None:
    tokenizer = WordWithPunctTokenizer()
    tokens: list[tuple[str, int, int, int]] = []
    for token in tokenizer(text, positions=True, chars=True):
        t: Any = token  # Whoosh's Token takes its attributes at runtime; no stubs.
        tokens.append((t.text, t.pos, t.startchar, t.endchar))
    assert [pos for _, pos, _, _ in tokens] == list(range(len(tokens)))
    for token_text, _, start, end in tokens:
        assert token_text
        assert text[start:end] == token_text
        assert any(c.isalnum() for c in token_text)
    assert [s for _, _, s, _ in tokens] == sorted(s for _, _, s, _ in tokens)
