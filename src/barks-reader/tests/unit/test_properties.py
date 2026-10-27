"""Property-based tests for the pure core: what must hold for any input, not one example.

Module-level ``@given`` functions, as test_wiki_integration.py explains: mutmut
runs pytest many times in one process, and a class-scoped ``@given`` trips
Hypothesis's differing-executors health check from the second run on.
"""

from __future__ import annotations

import re
import string
from datetime import datetime
from typing import TYPE_CHECKING

from barks_fantagraphics.alpha_split import bucket_label
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.search_query import Combine
from barks_fantagraphics.speech_markup import escape_markup
from barks_fantagraphics.tag_query import TagSelection
from barks_reader.core import log_markers
from barks_reader.core.collection_page_groups import year_range_group, year_range_group_index
from barks_reader.core.comic_book_page_info import (
    ComicLayout,
    DisplayUnit,
    PageInfo,
    slice_comic_layout,
    slice_page_map,
)
from barks_reader.core.font_sizes import FontGroup, font_group_for_height
from barks_reader.core.goto_page import GotoPageOffer, goto_page_after_reading
from barks_reader.core.hyphen_break_engine import (
    NO_BREAK_CHARS,
    SOFT_HYPHEN,
    build_markup,
    parse_marked_text,
)
from barks_reader.core.image_history import ImageHistory
from barks_reader.core.image_selector import ImageInfo
from barks_reader.core.index_text import shorten_if_necessary, sortable_string, stacked_prefix_label
from barks_reader.core.log_markers import capture, pattern
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE, FIRST_BODY_PAGE
from barks_reader.core.reader_formatter import (
    escape_editorial_brackets,
    escape_kivy_markup,
    get_text_with_markup_stripped,
)
from barks_reader.core.reader_utils import get_page_run_starts, get_page_sort_key
from barks_reader.core.reading_history import ReadEvent
from barks_reader.core.saved_page_info import SavedPageInfo
from barks_reader.core.scroll_reveal import reveal_distance, scroll_y_keeping_row
from barks_reader.core.search_state import TagBasket, TagState, WordBasket
from barks_reader.core.statistics_series import Series, dump_series, load_series
from hypothesis import given, settings
from hypothesis import strategies as st
from okf_reader.core.render import escape_markup as okf_escape
from strategies import page_maps

if TYPE_CHECKING:
    from collections import OrderedDict

# --- page maps and layouts ----------------------------------------------------


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


# --- Kivy markup escapes --------------------------------------------------------


@given(st.text(max_size=60))
def test_the_two_kivy_escapers_agree_byte_for_byte(text: str) -> None:
    """The wiki table rewriter matches okf-escaped text against ours (`escape_kivy_markup`).

    The app escapes with barks_fantagraphics' `escape_markup` and okf_reader with its
    own: two implementations, so the one place they can drift apart.
    """
    escaped = escape_markup(text)
    assert escaped == okf_escape(text)
    assert escape_kivy_markup(text) == escaped  # the wrapper the rewriter calls
    assert "[" not in escaped
    assert "]" not in escaped
    assert get_text_with_markup_stripped(escaped) == escaped


@given(st.text(alphabet=st.sampled_from(["a", " ", "[", "]", "/", "b", "i", "&"]), max_size=20))
def test_escaping_editorial_brackets_leaves_only_the_bold_and_italic_tags(text: str) -> None:
    escaped = escape_editorial_brackets(text)
    # One pass over the original: removing a tag must not join the text around it into
    # another ("[i[b]]" keeps its "[i" and "]").
    expected = re.sub(
        r"\[/?[bi]\]|[][]", lambda m: {"[": "&bl;", "]": "&br;"}.get(m.group(), ""), text
    )
    assert get_text_with_markup_stripped(escaped) == expected
    assert set(re.findall(r"\[[^\]]*\]", escaped)) <= {"[b]", "[/b]", "[i]", "[/i]"}


# --- JSON round trips ----------------------------------------------------------

_LABELS = st.lists(st.integers(min_value=1940, max_value=1970) | st.text(max_size=12), max_size=8)
_CENTS = st.floats(min_value=0, max_value=1e7).map(lambda v: round(v, 2))
_VALUES = st.integers(min_value=0, max_value=100_000) | _CENTS


@st.composite
def series(draw: st.DrawFn) -> Series:
    labels = draw(_LABELS)
    values = draw(st.lists(_VALUES, min_size=len(labels), max_size=len(labels)))
    return Series(draw(st.text(max_size=20)), tuple(labels), tuple(values))


@given(st.lists(series(), max_size=5))
def test_series_survive_the_sidecar_s_json(all_series: list[Series]) -> None:
    assert load_series(dump_series(all_series)) == all_series


_SECONDS = st.datetimes(
    min_value=datetime(2000, 1, 1),  # noqa: DTZ001
    max_value=datetime(2099, 12, 31),  # noqa: DTZ001
).map(lambda t: t.replace(microsecond=0))
_PAGES = st.sampled_from(["", COMIC_BEGIN_PAGE, "1", "7", "23", "i", "iv"])


@given(st.text(max_size=40), _SECONDS, st.none() | _SECONDS, _PAGES, _PAGES)
def test_a_read_event_survives_its_json(
    title: str, opened: datetime, closed: datetime | None, display_page: str, body_page: str
) -> None:
    event = ReadEvent(ReadEvent.new_event_id(), title, opened, closed, display_page, body_page)
    assert ReadEvent.from_json(event.to_json()) == event


# --- the goto-page offer ---------------------------------------------------------

_PAGE_NUMS = st.integers(min_value=1, max_value=60)


@st.composite
def tagged_and_offered(draw: st.DrawFn) -> tuple[list[str], str, str]:
    tagged = [str(n) for n in draw(st.lists(_PAGE_NUMS, max_size=12, unique=True))]
    pages = st.sampled_from([*tagged, "", COMIC_BEGIN_PAGE]) | _PAGE_NUMS.map(str)
    return draw(st.permutations(tagged)), draw(pages), draw(pages)


@given(tagged_and_offered())
def test_an_offer_steps_through_each_run_start_and_the_pages_it_was_given(
    drawn: tuple[list[str], str, str],
) -> None:
    tagged, page, kept = drawn
    offer = GotoPageOffer.make(page, tagged_pages=tagged, kept_page=kept)
    assert list(offer.pages) == sorted(set(offer.pages), key=get_page_sort_key)
    starts = get_page_run_starts(tagged)
    assert set(starts) <= set(offer.pages)
    if starts:
        assert set(offer.pages) - set(starts) <= {page, kept} - {"", COMIC_BEGIN_PAGE}
    else:
        assert offer.pages == ()
    if offer.page:
        assert offer.page not in {"", COMIC_BEGIN_PAGE}
        if offer.pages:
            assert offer.page in offer.pages


@given(tagged_and_offered(), st.integers(min_value=-3, max_value=3))
def test_stepping_wraps_round_and_steps_back(drawn: tuple[list[str], str, str], delta: int) -> None:
    tagged, page, kept = drawn
    offer = GotoPageOffer.make(page, tagged_pages=tagged, kept_page=kept)
    stepped = offer.stepped(delta)
    if not offer.can_step:
        assert stepped is offer
        assert offer.position == ""
        return
    assert stepped.active
    assert stepped.page in stepped.pages
    assert stepped.pages == offer.pages
    back = stepped.stepped(-delta)
    assert back.page == (offer.page if offer.index is not None else offer.pages[0])
    round_trip = stepped
    for _ in range(len(offer.pages)):
        round_trip = round_trip.stepped(delta)
    assert round_trip.page == stepped.page
    assert stepped.index is not None
    assert stepped.position == f" ({stepped.index + 1} of {len(stepped.pages)})"
    assert stepped.text.endswith(f"{stepped.position}:")


@given(tagged_and_offered())
def test_after_reading_the_page_last_read_is_offered_else_a_tag_s_first(
    drawn: tuple[list[str], str, str],
) -> None:
    tagged, last_read, _ = drawn
    offer = goto_page_after_reading(last_read, tagged)
    if last_read not in {"", COMIC_BEGIN_PAGE}:
        assert (offer.page, offer.active) == (last_read, True)
    elif tagged:
        assert (offer.page, offer.active) == (tagged[0], True)
    else:
        assert offer == GotoPageOffer()


# --- image history ----------------------------------------------------------------


@given(
    st.integers(min_value=1, max_value=6),
    st.lists(st.sampled_from(["add", "back", "forward"]), max_size=30),
)
def test_the_image_on_show_is_always_one_kept_and_back_then_forward_returns(
    max_images: int, steps: list[str]
) -> None:
    history = ImageHistory(max_images)
    assert history.index == -1
    shown = None
    for step_number, step in enumerate(steps):
        if step == "add":
            shown = ImageInfo(fit_mode=f"image {step_number}")
            history.add(shown)
            assert history.images[-1] is shown
            assert history.index == len(history.images) - 1
        elif step == "back":
            before = history.index
            image = history.back()
            if image is None:
                assert before <= 0
            else:
                assert history.index == before - 1
                assert history.forward() is shown
                history.back()
        else:
            before = history.index
            image = history.forward()
            if image is None:
                assert before >= len(history.images) - 1
            else:
                assert history.index == before + 1
        assert len(history.images) <= max_images
        if history.images:
            assert 0 <= history.index < len(history.images)
            shown = history.images[history.index]


# --- search baskets ----------------------------------------------------------------

_WORDS = st.text(alphabet=string.ascii_lowercase + " '-", min_size=1, max_size=12)


@given(st.lists(_WORDS, max_size=8), _WORDS, st.booleans())
def test_a_word_toggled_twice_is_as_it_was_and_the_query_quotes_each_word(
    words: list[str], word: str, flip: bool
) -> None:
    basket = WordBasket()
    for w in words:
        basket.toggle(w)
    if flip:
        basket.flip()
    picked: list[str] = []
    for w in words:  # A word put back and picked again goes to the end: its latest pick.
        if w in picked:
            picked.remove(w)
        else:
            picked.append(w)
    assert basket.words == picked
    assert len(basket) == len(picked)
    assert re.findall(r'"([^"]*)"', basket.query_text()) == picked
    assert (" | " in basket.query_text()) == (flip and len(picked) > 1)
    assert len(basket.chip_options()) == (len(picked) + 1 if picked else 0)
    was_in = word in basket
    basket.toggle(word)
    basket.toggle(word)
    assert (word in basket) == was_in
    basket.clear()
    assert len(basket) == 0
    assert basket.combine is Combine.ALL


@given(
    st.lists(_WORDS, min_size=1, max_size=6, unique=True), st.lists(st.integers(0, 3), max_size=6)
)
def test_a_tag_cycles_included_excluded_then_out_and_a_basket_fills_from_its_selection(
    tags: list[str], cycles: list[int]
) -> None:
    basket = TagBasket()
    for tag, turns in zip(tags, cycles, strict=False):
        assert basket.toggle(tag) is True
        for _ in range(turns):
            basket.cycle(tag)
        expected = {0: TagState.INCLUDED, 1: TagState.EXCLUDED, 2: None, 3: None}[turns]
        assert basket.tags.get(tag) == expected
    selection = basket.selection()
    refilled = TagBasket()
    refilled.fill(selection)
    assert refilled.selection() == selection
    assert len(refilled) == len(basket)
    assert isinstance(selection, TagSelection)
    assert set(selection.included).isdisjoint(selection.excluded)


# --- scroll reveal ------------------------------------------------------------------

_PX = st.floats(min_value=-5000, max_value=5000)


@given(_PX, _PX, _PX, _PX, st.floats(min_value=0, max_value=100))
def test_a_reveal_never_pushes_the_row_out_and_is_zero_when_the_items_show(
    view_bottom: float, view_top: float, items_bottom: float, owner_top: float, padding: float
) -> None:
    distance = reveal_distance(
        view_bottom=view_bottom,
        view_top=view_top,
        items_bottom=items_bottom,
        owner_top=owner_top,
        padding=padding,
    )
    assert distance >= 0
    assert distance <= max(0.0, view_top - owner_top)
    if view_bottom - items_bottom + padding <= 0:  # The items (and padding) already show.
        assert distance == 0


@given(_PX, _PX, st.floats(min_value=0, max_value=5000), st.floats(min_value=0, max_value=5000))
def test_a_kept_row_s_scroll_y_is_a_share_or_none_for_content_that_does_not_scroll(
    row_from_content_top: float, row_from_view_top: float, content: float, view: float
) -> None:
    scroll_y = scroll_y_keeping_row(
        row_from_content_top=row_from_content_top,
        row_from_view_top=row_from_view_top,
        content_height=content,
        view_height=view,
    )
    if content <= view:
        assert scroll_y is None
    else:
        assert scroll_y is not None
        assert 0 <= scroll_y <= 1


# --- index text -----------------------------------------------------------------------


@given(st.text(max_size=40))
def test_a_leading_article_moves_to_the_end_and_nothing_else_changes(text: str) -> None:
    sortable = sortable_string(text)
    if text.upper().startswith("THE "):
        assert sortable == text[4:] + ", The"
    elif text.upper().startswith("A "):
        assert sortable == text[2:] + ", A"
    else:
        assert sortable == text
    assert sortable_string(sortable) in {sortable, sortable_string(sortable)}


@given(st.text(max_size=80).filter(lambda t: not t.startswith("500,000")))
def test_a_shortened_term_fits_its_row(text: str) -> None:
    shortened = shorten_if_necessary(text)
    assert len(shortened) <= 30  # noqa: PLR2004
    if len(text) <= 30:  # noqa: PLR2004
        assert shortened == text


_TERMS = st.text(alphabet=string.ascii_lowercase + "'-.", min_size=1, max_size=8).filter(
    lambda t: t[0] not in "-."
)


@given(st.lists(_TERMS, min_size=1, max_size=20).map(sorted))
def test_a_stacked_label_rejoins_to_the_bucket_s_label(bucket: list[str]) -> None:
    label = bucket_label(bucket)
    stacked = stacked_prefix_label(label, bucket)
    assert stacked.replace("\n", "-") == label
    assert stacked.count("\n") <= 1
    assert stacked_prefix_label("other", bucket) == "other"


# --- font groups -----------------------------------------------------------------------


@given(st.integers(min_value=0, max_value=5000), st.integers(min_value=0, max_value=5000))
def test_a_taller_window_never_takes_a_smaller_font_group(a: int, b: int) -> None:
    low, high = sorted((a, b))
    rank = {FontGroup.LOW_RES: 0, FontGroup.HI_RES: 1}
    assert rank[font_group_for_height(low)] <= rank[font_group_for_height(high)]


__all__ = ["DisplayUnit"]
