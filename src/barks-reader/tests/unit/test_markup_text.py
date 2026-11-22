"""Kivy markup as the plain text it shows: tags gone, escapes undone, other brackets kept."""

from __future__ import annotations

import pytest
from barks_fantagraphics.speech_markup import escape_markup
from barks_reader.core.markup_text import plain_text


@pytest.mark.parametrize(
    ("markup", "expected"),
    [
        ("[b]Bold[/b] and [i]Italic[/i]", "Bold and Italic"),
        ("[color=#ff0000][size=20sp]Red Big[/size][/color]", "Red Big"),
        ("[font_name=Roboto][ref=story]Linked[/ref][/font_name]", "Linked"),
        ("no markup at all", "no markup at all"),
        ("", ""),
    ],
)
def test_tags_are_taken_out(markup: str, expected: str) -> None:
    assert plain_text(markup) == expected


def test_a_bracket_that_was_escaped_as_text_comes_back() -> None:
    line = "got items[i] & one of ['a', 'b']"
    assert plain_text(f"[b]Error:[/b] {escape_markup(line)}") == f"Error: {line}"


@pytest.mark.parametrize("text", ["[Cover]", "[Errno 2] No such file", "[actually, 1948]"])
def test_bracketed_text_that_is_no_tag_is_kept(text: str) -> None:
    """Kivy draws it as it is; a stripper that took every bracket run lost it from the log."""
    assert plain_text(f"[b]{text}[/b]") == text


def test_an_escaped_ampersand_does_not_start_another_escape() -> None:
    assert plain_text(escape_markup("&bl;")) == "&bl;"
