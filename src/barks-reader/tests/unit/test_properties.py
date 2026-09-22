"""Property-based tests for the pure core: what must hold for any input, not one example.

Module-level ``@given`` functions, as test_wiki_integration.py explains: mutmut
runs pytest many times in one process, and a class-scoped ``@given`` trips
Hypothesis's differing-executors health check from the second run on.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from unittest.mock import MagicMock

from barks_fantagraphics.comics_consts import PageType
from barks_reader.core import log_markers
from barks_reader.core.collection_page_groups import year_range_group, year_range_group_index
from barks_reader.core.comic_book_page_info import (
    ComicLayout,
    DisplayUnit,
    PageInfo,
    slice_comic_layout,
    slice_page_map,
)
from barks_reader.core.hyphen_break_engine import (
    NO_BREAK_CHARS,
    SOFT_HYPHEN,
    build_markup,
    parse_marked_text,
)
from barks_reader.core.log_markers import capture, pattern
from barks_reader.core.reader_consts_and_types import FIRST_BODY_PAGE
from barks_reader.core.saved_page_info import SavedPageInfo
from hypothesis import given, settings
from hypothesis import strategies as st

# --- page maps and layouts ----------------------------------------------------

_PAGE_TYPES = st.sampled_from([PageType.FRONT, PageType.TITLE, PageType.BODY, PageType.BACK_MATTER])


@st.composite
def page_maps(draw: st.DrawFn) -> OrderedDict[str, PageInfo]:
    """Draw a page map as the layout builder makes them: indexes 0..n-1, display numbers 1..n."""
    count = draw(st.integers(min_value=1, max_value=40))
    types = draw(st.lists(_PAGE_TYPES, min_size=count, max_size=count))
    solos = draw(st.lists(st.booleans(), min_size=count, max_size=count))
    page_map: OrderedDict[str, PageInfo] = OrderedDict()
    for index in range(count):
        page_map[str(index + 1)] = PageInfo(
            page_index=index,
            display_page_num=str(index + 1),
            page_type=types[index],
            srce_page=MagicMock(),
            dest_page=MagicMock(),
            is_solo=solos[index],
        )
    return page_map


@given(page_maps(), st.data())
def test_a_slice_keeps_order_and_keys_and_renumbers_indexes_from_zero(
    page_map: OrderedDict[str, PageInfo], data: st.DataObject
) -> None:
    count = len(page_map)
    first = data.draw(st.integers(min_value=1, max_value=count))
    last = data.draw(st.integers(min_value=first, max_value=count))

    sliced = slice_page_map(page_map, first, last)

    assert list(sliced) == [str(n) for n in range(first, last + 1)]
    assert [p.page_index for p in sliced.values()] == list(range(last - first + 1))
    for key, page in sliced.items():
        assert page.display_page_num == key
        assert page.page_type == page_map[key].page_type


@given(page_maps())
def test_slicing_the_whole_map_changes_nothing(page_map: OrderedDict[str, PageInfo]) -> None:
    sliced = slice_page_map(page_map, 1, len(page_map))
    assert list(sliced) == list(page_map)
    assert [p.page_index for p in sliced.values()] == [p.page_index for p in page_map.values()]


@given(page_maps(), st.data())
def test_a_sliced_layout_ends_on_its_last_page(
    page_map: OrderedDict[str, PageInfo], data: st.DataObject
) -> None:
    layout = ComicLayout(page_map, last_body_page=next(reversed(page_map)))
    first = data.draw(st.integers(min_value=1, max_value=len(page_map)))
    last = data.draw(st.integers(min_value=first, max_value=len(page_map)))

    sliced = slice_comic_layout(layout, first, last)

    assert sliced.last_body_page == str(last)
    assert len(sliced.page_map) == last - first + 1


@given(page_maps())
def test_display_units_tile_the_pages_in_order(page_map: OrderedDict[str, PageInfo]) -> None:
    """Every page is in exactly one unit; units are ascending; a solo page sits alone."""
    layout = ComicLayout(page_map, last_body_page=next(reversed(page_map)))
    units = layout.display_units

    covered = [
        i for unit in units for i in (unit.left_page_index, unit.right_page_index) if i is not None
    ]
    assert covered == list(range(len(page_map)))
    for unit_index, unit in enumerate(units):
        assert layout.unit_idx_for(unit.left_page_index) == unit_index
        if unit.right_page_index is not None:
            assert unit.right_page_index == unit.left_page_index + 1
            assert layout.unit_idx_for(unit.right_page_index) == unit_index
            left = layout.page_by_index(unit.left_page_index)
            right = layout.page_by_index(unit.right_page_index)
            assert left is not None
            assert right is not None
            assert not left.is_solo
            assert not right.is_solo


@given(page_maps())
def test_page_lookups_agree(page_map: OrderedDict[str, PageInfo]) -> None:
    layout = ComicLayout(page_map, last_body_page=next(reversed(page_map)))
    for key, page in page_map.items():
        assert layout.page_by_display(key) is page
        assert layout.page_by_index(page.page_index) is page
    assert layout.page_by_index(len(page_map)) is None


@given(page_maps(), st.data())
def test_in_single_page_mode_the_page_shown_is_the_page_saved(
    page_map: OrderedDict[str, PageInfo], data: st.DataObject
) -> None:
    layout = ComicLayout(page_map, last_body_page=next(reversed(page_map)))
    current = data.draw(st.sampled_from(list(page_map)))

    saved = layout.resolve_last_read(current, None, double_page_mode=False)

    assert saved.display_page_num == current
    assert saved.page_index == page_map[current].page_index
    assert saved.last_body_page == layout.last_body_page


@given(page_maps(), st.data())
def test_in_double_page_mode_the_page_saved_is_in_the_unit_shown(
    page_map: OrderedDict[str, PageInfo], data: st.DataObject
) -> None:
    layout = ComicLayout(page_map, last_body_page=next(reversed(page_map)))
    unit = data.draw(st.sampled_from(layout.display_units))
    current = page_map[str(unit.left_page_index + 1)].display_page_num

    saved = layout.resolve_last_read(current, unit, double_page_mode=True)

    assert saved.page_index in (unit.left_page_index, unit.right_page_index)


@given(page_maps())
def test_inside_body_means_a_body_page_that_is_not_an_edge(
    page_map: OrderedDict[str, PageInfo],
) -> None:
    last_body = next(reversed(page_map))
    layout = ComicLayout(page_map, last_body_page=last_body)
    for page in page_map.values():
        expected = page.page_type == PageType.BODY and page.display_page_num not in (
            FIRST_BODY_PAGE,
            last_body,
        )
        assert layout.is_inside_body(page) == expected
        assert layout.to_saved(page).is_inside_body() == expected


# --- saved pages --------------------------------------------------------------


@given(
    st.integers(min_value=0, max_value=10_000),
    st.text(min_size=1),
    st.sampled_from(list(PageType)),
    st.text(min_size=1),
)
def test_a_saved_page_survives_its_json(
    index: int, display: str, page_type: PageType, last_body: str
) -> None:
    saved = SavedPageInfo(index, display, page_type, last_body)
    assert SavedPageInfo.from_json(saved.to_json()) == saved


# --- year ranges --------------------------------------------------------------


@st.composite
def year_ranges(draw: st.DrawFn) -> list[tuple[int, int]]:
    """Ascending, non-overlapping (start, end) ranges, at least one."""
    count = draw(st.integers(min_value=1, max_value=8))
    year = draw(st.integers(min_value=1900, max_value=1960))
    ranges: list[tuple[int, int]] = []
    for _ in range(count):
        length = draw(st.integers(min_value=0, max_value=6))
        ranges.append((year, year + length))
        year += length + 1
    return ranges


@given(year_ranges(), st.integers(min_value=-1, max_value=2100))
def test_every_year_lands_in_one_range_and_a_year_outside_all_folds_into_the_last(
    ranges: list[tuple[int, int]], year: int
) -> None:
    index = year_range_group_index(year, ranges)
    assert 0 <= index < len(ranges)
    inside = [i for i, (start, end) in enumerate(ranges) if start <= year <= end]
    assert index == (inside[0] if inside else len(ranges) - 1)
    assert year_range_group(year, ranges) == ranges[index]


# --- hyphenation --------------------------------------------------------------

_PLAIN = st.text(
    alphabet=st.characters(
        blacklist_characters=[*NO_BREAK_CHARS, SOFT_HYPHEN], blacklist_categories=["Cs"]
    ),
    max_size=40,
)


@st.composite
def marked_texts(draw: st.DrawFn) -> str:
    """Words joined by single spaces, some carrying soft hyphens."""
    words = draw(st.lists(_PLAIN, min_size=1, max_size=6))
    marked = []
    for word in words:
        cut = draw(st.integers(min_value=0, max_value=len(word)))
        marked.append(word[:cut] + SOFT_HYPHEN + word[cut:] if word else word)
    return " ".join(marked)


def _strip_refs(markup: str) -> str:
    return re.sub(r"\[/?ref[^\]]*\]", "", markup)


@given(marked_texts())
def test_markup_with_no_hyphens_shows_the_text_unchanged(text: str) -> None:
    """Splitting into ref runs never loses, adds or reorders a character."""
    parsed = parse_marked_text(text)
    markup = build_markup(parsed, hyphens=frozenset(), disabled=frozenset())
    assert _strip_refs(markup) == text.replace(SOFT_HYPHEN, "")


@given(marked_texts())
def test_gaps_are_exactly_the_breaks_between_a_token_s_fragments(text: str) -> None:
    parsed = parse_marked_text(text)
    expected: set[int] = set()
    for token in parsed.tokens:
        expected.update(
            range(token.first_fragment_id, token.first_fragment_id + len(token.fragments) - 1)
        )
    assert parsed.gaps == expected
    assert sum(len(t.fragments) for t in parsed.tokens) == (
        max((t.first_fragment_id + len(t.fragments) for t in parsed.tokens), default=0)
    )


# --- log markers --------------------------------------------------------------

_FIELD_VALUES = st.text(
    alphabet=st.characters(whitelist_categories=["L", "N"], whitelist_characters=" _"),
    min_size=1,
    max_size=20,
)


@settings(max_examples=200)
@given(st.integers(min_value=0, max_value=999), _FIELD_VALUES)
def test_a_marker_line_matches_its_pattern_and_gives_back_its_fields(
    index: int, elapsed: str
) -> None:
    """Format with values, then match and capture: the round trip every GUI wait relies on."""
    line = log_markers.SHOWED_PAGE.format(index=index, elapsed=elapsed)
    assert re.search(pattern(log_markers.SHOWED_PAGE), line)
    assert re.search(pattern(log_markers.SHOWED_PAGE, index=index), line)
    found = re.search(capture(log_markers.SHOWED_PAGE, "elapsed", index=index), line)
    assert found is not None
    assert found["elapsed"] == elapsed
    assert not re.search(pattern(log_markers.SHOWED_PAGE, index=index + 1), line)


__all__ = ["DisplayUnit"]
