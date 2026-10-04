"""Tags picked together, typed: names with + , | and a leading - between them."""

from __future__ import annotations

import pytest
from barks_fantagraphics.search_query import Combine
from barks_fantagraphics.tag_query import (
    TagSelection,
    has_tag_syntax,
    parse_tag_query,
    range_text,
)

ALL, ANY = Combine.ALL, Combine.ANY


@pytest.mark.parametrize(
    ("text", "selection"),
    [
        ("scrooge", TagSelection(("scrooge",))),
        ("  Uncle   Scrooge ", TagSelection(("uncle scrooge",))),
        ("scrooge + gyro", TagSelection(("scrooge", "gyro"), (), ALL)),
        ("scrooge,gyro , donald", TagSelection(("scrooge", "gyro", "donald"), (), ALL)),
        ("scrooge | gyro", TagSelection(("scrooge", "gyro"), (), ANY)),
        ("scrooge -gyro", TagSelection(("scrooge",), ("gyro",))),
        (
            "scrooge + gyro -christmas stories",
            TagSelection(("scrooge", "gyro"), ("christmas stories",)),
        ),
        (
            "scrooge | gyro -andes -africa",
            TagSelection(("scrooge", "gyro"), ("andes", "africa"), ANY),
        ),
        ("scrooge + -gyro", TagSelection(("scrooge",), ("gyro",))),
        ("-gyro", TagSelection((), ("gyro",))),
        ("indo-china", TagSelection(("indo-china",))),  # a hyphen inside a name is the name's
        ("one-off characters", TagSelection(("one-off characters",))),
        ("scrooge + scrooge", TagSelection(("scrooge",))),
    ],
)
def test_a_typed_selection_parses(text: str, selection: TagSelection) -> None:
    parsed = parse_tag_query(text)
    assert (parsed.selection, parsed.error) == (selection, None)


@pytest.mark.parametrize(
    ("text", "says"),
    [
        ("scrooge + gyro | donald", "not both"),
        ("scrooge +", "missing next to"),
        ("| gyro", "missing next to"),
        ("scrooge + -", "missing after -"),
        ("", "No tag is named"),
    ],
)
def test_a_bad_selection_says_why(text: str, says: str) -> None:
    parsed = parse_tag_query(text)
    assert parsed.selection is None
    assert parsed.error is not None
    assert says in parsed.error


@pytest.mark.parametrize(
    ("text", "syntax"),
    [
        ("scrooge", False),
        ("uncle scrooge", False),
        ("indo-china", False),
        ("one-off characters", False),
        ("scrooge + gyro", True),
        ("scrooge,gyro", True),
        ("scrooge | gyro", True),
        ("scrooge -gyro", True),
        ("-gyro", True),
    ],
)
def test_has_tag_syntax(text: str, syntax: bool) -> None:
    assert has_tag_syntax(text) is syntax


def test_a_selection_describes_itself_as_typed() -> None:
    assert TagSelection(("Scrooge", "Gyro"), ("Christmas",)).describe() == (
        "Scrooge + Gyro -Christmas"
    )
    assert TagSelection(("Scrooge", "Gyro"), (), ANY).describe() == "Scrooge | Gyro"
    assert TagSelection((), ("Gyro",)).describe() == "-Gyro"


@pytest.mark.parametrize(
    ("text", "selection"),
    [
        ("scrooge year:1950-55", TagSelection(("scrooge",), years=(1950, 1955))),
        ("Year:1951 gyro", TagSelection(("gyro",), years=(1951, 1951))),
        ("scrooge vol:7", TagSelection(("scrooge",), volumes=(7, 7))),
        (
            "gyro year:1948-9 vol:5-8 -andes",
            TagSelection(("gyro",), ("andes",), years=(1948, 1949), volumes=(5, 8)),
        ),
        ("scrooge | gyro year:1950", TagSelection(("scrooge", "gyro"), (), ANY, (1950, 1950))),
        # beside a separator, a range is a part of its own
        ("scrooge + year:1950", TagSelection(("scrooge",), years=(1950, 1950))),
        ("scrooge,year:1950", TagSelection(("scrooge",), years=(1950, 1950))),
        ("year:1950 | gyro", TagSelection(("gyro",), (), ANY, (1950, 1950))),
        ("scrooge + vol:7 + gyro", TagSelection(("scrooge", "gyro"), volumes=(7, 7))),
        ("year:1950,vol:7 gyro", TagSelection(("gyro",), years=(1950, 1950), volumes=(7, 7))),
    ],
)
def test_a_typed_selection_takes_years_and_volumes(text: str, selection: TagSelection) -> None:
    parsed = parse_tag_query(text)
    assert (parsed.selection, parsed.error) == (selection, None)


@pytest.mark.parametrize(
    ("text", "says"),
    [
        ("gyro year:x", "year: a year must be a number or a range"),
        ("gyro vol:8-5", "vol: a volume range runs backwards"),
        ("gyro year:1950 year:1951", "year: is given twice"),
        ("year:1950", "No tag is named"),
        ("year:1950 + vol:7", "No tag is named"),
        ("year:1950 + + gyro", "A tag name is missing next to"),
    ],
)
def test_a_bad_year_or_volume_says_why(text: str, says: str) -> None:
    parsed = parse_tag_query(text)
    assert parsed.selection is None
    assert parsed.error is not None
    assert says in parsed.error


def test_year_and_vol_are_tag_syntax_but_a_colon_alone_is_not() -> None:
    assert has_tag_syntax("gyro year:1950")
    assert has_tag_syntax("vol:7 gyro")
    assert not has_tag_syntax("gyro")


def test_a_selection_with_years_and_volumes_describes_itself_as_typed() -> None:
    selection = TagSelection(("Gyro",), years=(1950, 1955), volumes=(5, 8))
    assert selection.describe() == "Gyro year:1950-55 vol:5-8"


@pytest.mark.parametrize(
    ("first_last", "years", "text"),
    [
        ((1951, 1951), True, "1951"),
        ((1950, 1955), True, "1950-55"),
        ((1999, 2001), True, "1999-2001"),
        ((7, 7), False, "7"),
        ((5, 8), False, "5-8"),
    ],
)
def test_range_text(first_last: tuple[int, int], years: bool, text: str) -> None:
    assert range_text(first_last, years=years) == text


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("", "No tag is named."),
        (" + ", "No tag is named."),  # separators only: no name, not a missing one
        ("scrooge, gyro | daisy", "Use + or | between tags, not both."),  # a comma is a +
        ("scrooge +", "A tag name is missing next to + , or |."),
        ("scrooge -", "A tag name is missing after -."),
    ],
)
def test_text_that_names_no_tags_says_exactly_why(text: str, error: str) -> None:
    parsed = parse_tag_query(text)
    assert (parsed.selection, parsed.error) == (None, error)


def test_a_range_in_one_century_shortens_its_last_year_in_any_century() -> None:
    assert range_text((1910, 1915), years=True) == "1910-15"
    assert range_text((1899, 1905), years=True) == "1899-1905"
