# ruff: noqa: INP001
"""How long one part of a typed word query takes when it may look only in some stories.

Every part of an AND after the first searches only the stories found so far, passed
to the engine as a set of titles. Whoosh made an OR of title terms into its filter
by walking it document by document: "duck money" took a second on the real index,
its second word searched within the 170 stories of the first. Read from each title's
postings, and kept, the filter costs next to nothing. A synthetic index shaped like
the real one (hundreds of stories of some dozens of bubbles) keeps the benchmark free
of the data pack.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.search_query import AnyTerm
from barks_fantagraphics.whoosh_search_engine import SearchEngine, build_index_schema
from whoosh.index import create_in

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_benchmark.fixture import BenchmarkFixture

STORIES = 300
BUBBLES_PER_STORY = 60
WORDS_PER_BUBBLE = 8
VOCABULARY = [f"word{i}" for i in range(2_000)]
SEARCHED_IN = 200  # stories: as many as a common first word finds
BUDGET_SECS = 0.050


@pytest.fixture(scope="module")
def engine(tmp_path_factory: pytest.TempPathFactory) -> SearchEngine:
    index_dir: Path = tmp_path_factory.mktemp("bubbles-index")
    rng = random.Random(1951)  # fixed: the same index every run
    writer = create_in(str(index_dir), build_index_schema()).writer()
    for story in range(STORIES):
        for bubble in range(BUBBLES_PER_STORY):
            words = rng.choices(VOCABULARY, k=WORDS_PER_BUBBLE)
            if rng.random() < 0.1:  # noqa: PLR2004
                words.append("money")
            text = " ".join(words)
            writer.add_document(
                title=f"Story {story:03}",
                fanta_vol="1",
                fanta_page=f"{bubble // 6:03}",
                comic_page=str(bubble // 6),
                content_id=str(bubble),
                panel_num="1",
                speaker="",
                unstemmed=text,
                content_raw=text,
                entities_person="",
                entities_location="",
                entities_org="",
                entities_work="",
                entities_misc="",
            )
    writer.commit()
    return SearchEngine(index_dir)


def test_a_word_searched_within_many_stories_benchmark(
    benchmark: BenchmarkFixture, engine: SearchEngine
) -> None:
    titles = frozenset(f"Story {story:03}" for story in range(SEARCHED_IN))
    found = benchmark(engine.find_bubbles, AnyTerm(("money",)), titles=titles)
    assert set(found) <= titles
    assert len(found) > SEARCHED_IN // 2
    assert benchmark.stats is not None
    assert benchmark.stats["median"] < BUDGET_SECS, "the title filter is slow again"
