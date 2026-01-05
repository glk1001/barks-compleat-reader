import pytest
from barks_fantagraphics.whoosh_punct_tokenizer import WordWithPunctTokenizer
from barks_fantagraphics.whoosh_search_engine import MY_STOP_WORDS
from whoosh.analysis import LowercaseFilter, StopFilter, Tokenizer


@pytest.fixture
def analyzer() -> Tokenizer:
    return WordWithPunctTokenizer() | LowercaseFilter() | StopFilter(stoplist=MY_STOP_WORDS)


def tokens(analyzer: Tokenizer, text: str) -> list[str]:
    # noinspection PyCallingNonCallable
    return [t.text for t in analyzer(text)]  # ty:ignore[call-non-callable]


def test_basic_words(analyzer: Tokenizer) -> None:
    assert tokens(analyzer, "hello world") == ["hello", "world"]


def test_comma_words(analyzer: Tokenizer) -> None:
    # 'OH' is a custom stop word. It won't be tokenized.
    assert tokens(analyzer, "Oh, Yeah!") == ["yeah"]


def test_comma_numbers(analyzer: Tokenizer) -> None:
    assert tokens(analyzer, "500,000,000.16") == ["500,000,000.16"]


def test_internal_apostrophe(analyzer: Tokenizer) -> None:
    assert tokens(analyzer, "don't ain't") == ["don't", "ain't"]


def test_trailing_apostrophe(analyzer: Tokenizer) -> None:
    assert tokens(analyzer, "knockin'") == ["knockin'"]


def test_leading_apostrophe(analyzer: Tokenizer) -> None:
    assert tokens(analyzer, "'lo") == ["'lo"]


def test_quoted_word(analyzer: Tokenizer) -> None:
    assert tokens(analyzer, "'hello'") == ["hello"]


def test_quoted_contraction(analyzer: Tokenizer) -> None:
    assert tokens(analyzer, "'ain't'") == ["ain't"]


def test_dotted_acronym(analyzer: Tokenizer) -> None:
    assert tokens(analyzer, "G.I.") == ["g.i."]


def test_dotted_possessive(analyzer: Tokenizer) -> None:
    assert tokens(analyzer, "G.I.'s") == ["g.i.'s"]


def test_quoted_dotted_possessive(analyzer: Tokenizer) -> None:
    assert tokens(analyzer, "'G.I.'s'") == ["g.i.'s"]


def test_stop_words(analyzer: Tokenizer) -> None:
    assert tokens(analyzer, "help with that") == ["help"]


def test_mixed_sentence(analyzer: Tokenizer) -> None:
    text = "Don't use 'ain't' with G.I.'s knockin' 'lo"
    assert tokens(analyzer, text) == [
        "don't",
        "use",
        "ain't",
        "g.i.'s",
        "knockin'",
        "'lo",
    ]
