"""Tests for inline emphasis markup in OCR speech text."""

import pytest
from barks_fantagraphics.speech_markup import (
    escape_markup,
    has_markup,
    markup_from_spans,
    same_text_ignoring_markup,
    strip_markup,
    unescape_markup,
    validate_markup,
)

# Real corpus text. The bracket and ampersand cases are the ones that actually
# exist: Gemini's own annotations, and shop signage.
PLAIN_WITH_BRACKETS = "[Illegible Comic Covers]"
PLAIN_WITH_AMPERSAND = "GOLDSTEIN\n& CO.\nMARINE\nSUPPLIES"


@pytest.mark.parametrize(
    "plain",
    [
        "GET OUTTA\nHERE, YOU-YOU\nSABOTEURS!",
        PLAIN_WITH_BRACKETS,
        PLAIN_WITH_AMPERSAND,
        "CASH\nFEEDS & SEEDS",
        "",
        "&bl; is not special before escaping",
    ],
)
def test_escape_round_trips(plain: str) -> None:
    assert strip_markup(escape_markup(plain)) == plain
    assert unescape_markup(escape_markup(plain)) == plain


def test_ampersand_escaped_before_brackets() -> None:
    # The ordering bug this guards: escaping brackets first would produce
    # "&bl;" and the ampersand rule would then turn it into "&amp;bl;".
    assert escape_markup("[a & b]") == "&bl;a &amp; b&br;"
    assert strip_markup("&bl;a &amp; b&br;") == "[a & b]"


def test_strip_removes_tags() -> None:
    assert strip_markup("WELL, ROSCOE, YOU'RE\nA [b]SUCCESS[/b]!") == (
        "WELL, ROSCOE, YOU'RE\nA SUCCESS!"
    )


def test_strip_handles_one_character_span() -> None:
    # The most fragile case under the old offset scheme, and the reason the
    # migration happened: a 1-char span that drifts lands on some other letter
    # and looks entirely reasonable.
    assert strip_markup("THIS IS WHERE [b]I[/b] WANTED TO HIDE") == "THIS IS WHERE I WANTED TO HIDE"


def test_has_markup() -> None:
    assert has_markup("A [b]SUCCESS[/b]!")
    assert has_markup("[i]GYRO SOON FEELS[/i]")
    assert not has_markup("A SUCCESS!")
    assert not has_markup(PLAIN_WITH_BRACKETS)


def test_same_text_ignoring_markup() -> None:
    assert same_text_ignoring_markup("A [b]SUCCESS[/b]!", "A SUCCESS!")
    assert same_text_ignoring_markup("A [b]SUCCESS[/b]!", "A [i]SUCCESS[/i]!")
    assert not same_text_ignoring_markup("A [b]SUCCESS[/b]!", "A FAILURE!")


class TestValidate:
    def test_accepts_sound_markup(self) -> None:
        assert validate_markup("A [b]SUCCESS[/b]! WATCH THOSE [b]MUSCLES[/b], BOY!") == []
        assert validate_markup(escape_markup(PLAIN_WITH_BRACKETS)) == []

    def test_rejects_unbalanced(self) -> None:
        assert "closed 0 time(s)" in " ".join(validate_markup("A [b]SUCCESS!"))

    def test_rejects_closer_before_opener(self) -> None:
        assert "out of order" in " ".join(validate_markup("A [/b]SUCCESS[b]!"))

    def test_rejects_disallowed_tag(self) -> None:
        errors = " ".join(validate_markup("A [color=ff0000]SUCCESS[/color]!"))
        assert "unknown or disallowed tag" in errors

    def test_rejects_unescaped_bracket(self) -> None:
        assert "unescaped" in " ".join(validate_markup("A [b]SUCCESS[/b]! ]"))

    def test_rejects_unescaped_ampersand(self) -> None:
        assert 'unescaped "&"' in " ".join(validate_markup("GOLDSTEIN & CO."))

    def test_accepts_escaped_ampersand(self) -> None:
        assert validate_markup("GOLDSTEIN &amp; CO.") == []


class TestMarkupFromSpans:
    def test_converts_pilot_span(self) -> None:
        # The pilot's 077 g1 -- the group whose queued correction shortens the
        # text by two characters and would have slid this span off its word.
        text = "GET OUTTA\nHERE, YOU — YOU\nSABOTEURS!"
        # "bold" is the retired long form the stored data actually uses.
        assert markup_from_spans(text, [[26, 35, "bold"]]) == (
            "GET OUTTA\nHERE, YOU — YOU\n[b]SABOTEURS[/b]!"
        )

    def test_converts_multiple_spans(self) -> None:
        text = "WELL, ROSCOE, YOU'RE\nA SUCCESS! BUT WATCH\nTHOSE MUSCLES, BOY!"
        got = markup_from_spans(text, [[23, 30, "b"], [48, 55, "b"]])
        assert got == (
            "WELL, ROSCOE, YOU'RE\nA [b]SUCCESS[/b]! BUT WATCH\nTHOSE [b]MUSCLES[/b], BOY!"
        )
        assert strip_markup(got) == text

    def test_escapes_while_converting(self) -> None:
        assert markup_from_spans("A & B", [[0, 1, "b"]]) == "[b]A[/b] &amp; B"

    def test_rejects_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="outside text"):
            markup_from_spans("SHORT", [[0, 99, "b"]])

    def test_rejects_overlapping(self) -> None:
        with pytest.raises(ValueError, match="overlaps"):
            markup_from_spans("ABCDEFGH", [[0, 5, "b"], [3, 7, "b"]])

    def test_rejects_unknown_kind(self) -> None:
        with pytest.raises(ValueError, match="unknown emphasis kind"):
            markup_from_spans("ABCDEFGH", [[0, 5, "underline"]])
