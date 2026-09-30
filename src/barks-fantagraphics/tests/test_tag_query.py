"""Tags picked together, typed: names with + , | and a leading - between them."""

from __future__ import annotations

import pytest
from barks_fantagraphics.search_query import Combine
from barks_fantagraphics.tag_query import TagSelection, has_tag_syntax, parse_tag_query

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
