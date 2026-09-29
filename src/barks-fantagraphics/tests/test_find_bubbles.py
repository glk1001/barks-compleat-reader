"""find_bubbles, one leaf of a typed word query: the Whoosh engine and the fake, case for case.

Both search the same corpus, the fake with the index's own analyzer, so a test the
fake passes and Whoosh fails (or the other way) is a fake that no longer stands in
for the engine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.search_query import AnyTerm, Near, Phrase, SearchLeaf
from barks_fantagraphics.testing.fake_search import FakeBubble, InMemoryFullTextSearch
from barks_fantagraphics.whoosh_search_engine import SearchEngine, build_index_schema

if TYPE_CHECKING:
    from pathlib import Path

    from barks_fantagraphics.search_ports import FullTextSearchPort
    from barks_fantagraphics.search_results import TitleDict

GOLD_STORY, ANDES, MONEY, HELMET = "Gold Story", "Andes Story", "Money Story", "Helmet Story"
QUACK = "Quack Story"


def _bubble(
    title: str, text: str, vol: int, page: str, group: str, speaker: str = ""
) -> FakeBubble:
    return FakeBubble(title, text, vol, page, str(int(page)), group, speaker=speaker or None)


CORPUS = [
    _bubble(GOLD_STORY, "Pirate gold! A mine of gold in the old mine!", 1, "001", "1", "Donald"),
    _bubble(GOLD_STORY, "The ducks are ducking the parrot.", 1, "002", "2", "Huey"),
    _bubble(ANDES, "Square eggs! Gold is nowhere in the Andes.", 7, "010", "1", "Donald"),
    # gold ... mine: five words apart once the stop words are gone.
    _bubble(ANDES, "Gold far away from here is buried in the mine", 7, "011", "2", "Scrooge"),
    _bubble(MONEY, "My money! My gold coins!", 12, "020", "1", "Scrooge"),
    _bubble(HELMET, "The golden helmet belongs to the finder", 11, "030", "1"),
    # a word twice, and once: NEAR with a term on both sides needs two of it
    _bubble(QUACK, "Quack! Quack!", 2, "040", "1"),
    _bubble(QUACK, "Just one quack and a duck", 2, "041", "2"),
]


def _analyzer_tokens(text: str) -> list[str]:
    analyzer = build_index_schema()["unstemmed"].analyzer
    return [token.text for token in analyzer(text)]


def _build_index(tmp_path: Path) -> Path:
    from whoosh.index import create_in  # noqa: PLC0415

    index = create_in(str(tmp_path), build_index_schema())
    writer = index.writer()
    for bubble in CORPUS:
        writer.add_document(
            title=bubble.title,
            fanta_vol=str(bubble.fanta_vol),
            fanta_page=bubble.fanta_page,
            comic_page=bubble.comic_page,
            content_id=bubble.group_id,
            panel_num=str(bubble.panel_num),
            speaker=bubble.speaker or "",
            unstemmed=bubble.text,
            content_raw=bubble.text,
            entities_person="",
            entities_location="",
            entities_org="",
            entities_work="",
            entities_misc="",
        )
    writer.commit()
    return tmp_path


@pytest.fixture(params=["whoosh", "fake"])
def engine(request: pytest.FixtureRequest, tmp_path: Path) -> FullTextSearchPort:
    if request.param == "whoosh":
        return SearchEngine(_build_index(tmp_path))
    return InMemoryFullTextSearch(bubbles=list(CORPUS), tokenize=_analyzer_tokens)


def _found(title_dict: TitleDict) -> dict[str, tuple[int, dict[str, list[str]]]]:
    """Each story's volume, and each page's matching group ids."""
    return {
        title: (
            info.fanta_vol,
            {
                page: [s.group_id for s in p.speech_info_list]
                for page, p in info.fanta_pages.items()
            },
        )
        for title, info in title_dict.items()
    }


@pytest.mark.parametrize(
    ("leaf", "expected"),
    [
        (
            AnyTerm(("gold",)),
            {
                ANDES: (7, {"010": ["1"], "011": ["2"]}),
                GOLD_STORY: (1, {"001": ["1"]}),
                MONEY: (12, {"020": ["1"]}),
            },
        ),
        (AnyTerm(("ducks", "ducking")), {GOLD_STORY: (1, {"002": ["2"]})}),
        (AnyTerm(("golden", "coins")), {HELMET: (11, {"030": ["1"]}), MONEY: (12, {"020": ["1"]})}),
        (AnyTerm(("nothing",)), {}),
        # a phrase: next to each other, in order, one bubble; stop words dropped both sides
        (Phrase(("pirate", "gold")), {GOLD_STORY: (1, {"001": ["1"]})}),
        (Phrase(("gold", "pirate")), {}),
        (Phrase(("mine", "of", "gold")), {GOLD_STORY: (1, {"001": ["1"]})}),
        (Phrase(("gold", "mine")), {GOLD_STORY: (1, {"001": ["1"]})}),
        # NEAR: either order, at most the distance apart, one bubble
        (
            Near(AnyTerm(("gold",)), AnyTerm(("mine",)), 5),
            {ANDES: (7, {"011": ["2"]}), GOLD_STORY: (1, {"001": ["1"]})},
        ),
        (Near(AnyTerm(("gold",)), AnyTerm(("mine",)), 4), {GOLD_STORY: (1, {"001": ["1"]})}),
        (Near(AnyTerm(("mine",)), AnyTerm(("gold",)), 1), {GOLD_STORY: (1, {"001": ["1"]})}),
        (Near(AnyTerm(("square",)), AnyTerm(("andes",)), 4), {ANDES: (7, {"010": ["1"]})}),
        (Near(AnyTerm(("square",)), AnyTerm(("andes",)), 3), {}),
        (
            Near(AnyTerm(("money", "helmet")), AnyTerm(("coins", "finder")), 3),
            {HELMET: (11, {"030": ["1"]}), MONEY: (12, {"020": ["1"]})},
        ),
        (Near(AnyTerm(("quack",)), AnyTerm(("quack",)), 2), {QUACK: (2, {"040": ["1"]})}),
        (
            Near(AnyTerm(("quack", "quacking")), AnyTerm(("quack",)), 2),
            {QUACK: (2, {"040": ["1"]})},
        ),
        (
            Near(AnyTerm(("quack",)), AnyTerm(("quack", "duck")), 5),
            {QUACK: (2, {"040": ["1"], "041": ["2"]})},
        ),
    ],
)
def test_a_leaf_finds_its_bubbles(
    engine: FullTextSearchPort, leaf: SearchLeaf, expected: dict[str, object]
) -> None:
    assert _found(engine.find_bubbles(leaf)) == expected


def test_a_speaker_keeps_only_that_speakers_bubbles(engine: FullTextSearchPort) -> None:
    found = engine.find_bubbles(AnyTerm(("gold",)), speaker="Scrooge")
    assert _found(found) == {ANDES: (7, {"011": ["2"]}), MONEY: (12, {"020": ["1"]})}


def test_titles_restrict_the_search_to_those_stories(engine: FullTextSearchPort) -> None:
    found = engine.find_bubbles(AnyTerm(("gold",)), titles=frozenset({ANDES, "No Such Story"}))
    assert list(found) == [ANDES]


def test_no_titles_find_nothing(engine: FullTextSearchPort) -> None:
    assert engine.find_bubbles(AnyTerm(("gold",)), titles=frozenset()) == {}


def test_a_bubble_carries_its_text_and_speaker(engine: FullTextSearchPort) -> None:
    found = engine.find_bubbles(AnyTerm(("coins",)))
    (speech,) = found[MONEY].fanta_pages["020"].speech_info_list
    assert (speech.speech_text, speech.speaker, speech.panel_num) == (
        "My money! My gold coins!",
        "Scrooge",
        1,
    )
    assert found[MONEY].fanta_pages["020"].comic_page == "20"


def test_the_fakes_own_tokenizer_keeps_a_words_hyphens_and_apostrophes() -> None:
    fake = InMemoryFullTextSearch(bubbles=[FakeBubble("S", "Don't go to Indo-China, Unca!")])
    assert list(fake.find_bubbles(AnyTerm(("indo-china",)))) == ["S"]
    assert list(fake.find_bubbles(AnyTerm(("don't",)))) == ["S"]
    assert fake.find_bubbles(AnyTerm(("china",))) == {}


def test_the_fake_records_what_it_was_asked() -> None:
    fake = InMemoryFullTextSearch()
    leaf = AnyTerm(("gold",))
    fake.find_bubbles(leaf, speaker="Scrooge", titles=frozenset({"S"}))
    assert fake.bubble_calls == [(leaf, "Scrooge", frozenset({"S"}))]
