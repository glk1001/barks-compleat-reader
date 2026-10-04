"""The search result types, and the set operations the query evaluator combines them with."""

from __future__ import annotations

import copy

import pytest
from barks_fantagraphics import search_results, whoosh_search_engine
from barks_fantagraphics.search_results import (
    PageInfo,
    SpeechInfo,
    TitleDict,
    TitleInfo,
    hit_counts,
    intersect_titles,
    merge_title_dicts,
    restrict_titles,
    subtract_titles,
)


def _speech(group_id: str, *entity_types: str) -> SpeechInfo:
    return SpeechInfo(
        group_id=group_id,
        panel_num=1,
        speech_text=f"text {group_id}",
        speech_text_markup=f"text {group_id}",
        entity_types=entity_types,
    )


def _result(stories: dict[str, dict[str, list[str]]], vol: int = 5) -> TitleDict:
    """Build a result: story -> fanta page -> its matching group ids (comic page = "c" + page)."""
    return {
        title: TitleInfo(
            fanta_vol=vol,
            fanta_pages={
                page: PageInfo(f"c{page}", [_speech(g) for g in groups])
                for page, groups in pages.items()
            },
        )
        for title, pages in stories.items()
    }


def _groups(result: TitleDict) -> dict[str, dict[str, list[str]]]:
    """Return a result as story -> page -> group ids, in the result's order."""
    return {
        title: {
            page: [s.group_id for s in info.speech_info_list]
            for page, info in ti.fanta_pages.items()
        }
        for title, ti in result.items()
    }


GOLD = _result({"Lost in the Andes": {"101": ["3"]}, "Pirate Gold": {"12": ["2", "7"]}})
MINE = _result({"Pirate Gold": {"12": ["7", "9"], "14": ["1"]}, "The Gold Mine": {"40": ["5"]}})


def test_the_engine_re_exports_the_very_same_types() -> None:
    """Old imports (the reader's screens, ../barks-ocr) must get these objects, not copies."""
    for name in ("SpeechInfo", "PageInfo", "TitleInfo", "TitleDict"):
        assert getattr(whoosh_search_engine, name) is getattr(search_results, name)


class TestMerge:
    """OR: every story either found, with both sets of bubbles."""

    def test_every_story_and_bubble_once(self) -> None:
        assert _groups(merge_title_dicts(GOLD, MINE)) == {
            "Lost in the Andes": {"101": ["3"]},
            "Pirate Gold": {"12": ["2", "7", "9"], "14": ["1"]},
            "The Gold Mine": {"40": ["5"]},
        }

    def test_a_bubble_both_found_keeps_both_entity_types(self) -> None:
        first = {"S": TitleInfo(1, {"1": PageInfo("c1", [_speech("4", "person")])})}
        second = {"S": TitleInfo(1, {"1": PageInfo("c1", [_speech("4", "person", "place")])})}
        [speech] = merge_title_dicts(first, second)["S"].fanta_pages["1"].speech_info_list
        assert speech.entity_types == ("person", "place")

    def test_in_the_engine_order(self) -> None:
        """Stories and pages by name; bubbles by number, a malformed id after them."""
        unordered = _result({"Zebra": {"9": ["10", "x", "2"]}, "Apple": {"2": ["1"], "10": ["1"]}})
        result = merge_title_dicts(unordered)
        assert list(result) == ["Apple", "Zebra"]
        assert list(result["Apple"].fanta_pages) == ["10", "2"]
        assert _groups(result)["Zebra"]["9"] == ["2", "10", "x"]

    def test_a_page_at_two_comic_pages_is_an_index_inconsistency(self) -> None:
        other = {"Pirate Gold": TitleInfo(5, {"12": PageInfo("elsewhere", [_speech("1")])})}
        with pytest.raises(ValueError, match="Index inconsistency"):
            merge_title_dicts(GOLD, other)

    def test_nothing_is_nothing(self) -> None:
        assert merge_title_dicts() == {}
        assert merge_title_dicts({}, {}) == {}


class TestIntersect:
    """AND: the same story, not the same bubble."""

    def test_the_shared_stories_with_every_result_s_bubbles(self) -> None:
        assert _groups(intersect_titles(GOLD, MINE)) == {
            "Pirate Gold": {"12": ["2", "7", "9"], "14": ["1"]}
        }

    def test_three_ways(self) -> None:
        andes = _result({"Pirate Gold": {"20": ["1"]}})
        assert list(intersect_titles(GOLD, MINE, andes)) == ["Pirate Gold"]
        assert intersect_titles(GOLD, MINE, _result({"Elsewhere": {"1": ["1"]}})) == {}

    def test_alone_it_is_a_copy(self) -> None:
        assert _groups(intersect_titles(GOLD)) == _groups(GOLD)


class TestSubtract:
    """NOT: whole stories go."""

    def test_stories_the_other_found_are_dropped_whole(self) -> None:
        assert _groups(subtract_titles(GOLD, MINE)) == {"Lost in the Andes": {"101": ["3"]}}

    def test_only_the_kept_result_s_bubbles(self) -> None:
        assert _groups(subtract_titles(MINE, GOLD)) == {"The Gold Mine": {"40": ["5"]}}


class TestRestrict:
    def test_keeps_only_the_named_stories(self) -> None:
        assert list(restrict_titles(merge_title_dicts(GOLD, MINE), {"The Gold Mine", "Nope"})) == [
            "The Gold Mine"
        ]


def test_hit_counts_are_bubbles_per_story() -> None:
    assert hit_counts(merge_title_dicts(GOLD, MINE)) == {
        "Lost in the Andes": 1,
        "Pirate Gold": 4,
        "The Gold Mine": 1,
    }


@pytest.mark.parametrize(
    "operation",
    [
        merge_title_dicts,
        intersect_titles,
        subtract_titles,
        lambda a, _b: restrict_titles(a, {"Pirate Gold"}),
    ],
    ids=["merge", "intersect", "subtract", "restrict"],
)
def test_no_operation_changes_its_arguments(operation) -> None:  # noqa: ANN001
    """TitleInfo is mutable and a result may be cached, so the inputs must survive intact."""
    gold, mine = copy.deepcopy(GOLD), copy.deepcopy(MINE)
    result = operation(gold, mine)
    assert gold == GOLD
    assert mine == MINE
    for info in result.values():  # and the result shares no mutable part with them
        for page in info.fanta_pages.values():
            page.speech_info_list.append(_speech("99"))
    assert gold == GOLD
    assert mine == MINE


def test_one_speech_group_found_twice_keeps_both_finds_entity_types() -> None:
    def found(entity: str) -> TitleDict:
        speech = SpeechInfo("3", 1, "Duckburg!", "Duckburg!", entity_types=(entity,))
        return {"A Story": TitleInfo(5, {"010": PageInfo("10", [speech])})}

    merged = merge_title_dicts(found("location"), found("person"))
    [speech] = merged["A Story"].fanta_pages["010"].speech_info_list
    assert speech.entity_types == ("location", "person")
