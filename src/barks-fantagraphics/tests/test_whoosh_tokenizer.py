"""The index's word tokens: apostrophes, dotted acronyms, hyphens and the stop words.

Through the schema's own ``unstemmed`` analyzer, so the chain under test is the one
the index is built with, not a copy of it.
"""

from barks_fantagraphics.testing.whoosh_index import schema_tokens


def test_basic_words() -> None:
    assert schema_tokens("hello world") == ["hello", "world"]


def test_comma_words() -> None:
    # 'OH' is a custom stop word. It won't be tokenized.
    assert schema_tokens("Oh, Yeah!") == ["yeah"]


def test_comma_numbers() -> None:
    assert schema_tokens("500,000,000.16") == ["500,000,000.16"]


def test_internal_apostrophe() -> None:
    assert schema_tokens("don't ain't") == ["don't", "ain't"]


def test_trailing_apostrophe() -> None:
    assert schema_tokens("knockin'") == ["knockin'"]


def test_leading_apostrophe() -> None:
    assert schema_tokens("'lo") == ["'lo"]


def test_quoted_word() -> None:
    assert schema_tokens("'hello'") == ["hello"]


def test_quoted_contraction() -> None:
    assert schema_tokens("'ain't'") == ["ain't"]


def test_dotted_acronym() -> None:
    assert schema_tokens("G.I.") == ["g.i."]


def test_dotted_possessive() -> None:
    assert schema_tokens("G.I.'s") == ["g.i.'s"]


def test_quoted_dotted_possessive() -> None:
    assert schema_tokens("'G.I.'s'") == ["g.i.'s"]


def test_stop_words() -> None:
    assert schema_tokens("help with that") == ["help"]


def test_mixed_sentence() -> None:
    text = "Don't use 'ain't' with G.I.'s knockin' 'lo"
    assert schema_tokens(text) == [
        "don't",
        "use",
        "ain't",
        "g.i.'s",
        "knockin'",
        "'lo",
    ]


def test_a_hyphen_before_a_space_joins_nothing() -> None:
    """A word broken off at a line's end ("well-") is not joined across the space."""
    assert schema_tokens("well- done") == ["well", "done"]


def test_apostrophes_with_no_word_are_no_token() -> None:
    assert schema_tokens("' '' don't") == ["don't"]
