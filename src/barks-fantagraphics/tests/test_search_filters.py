# cspell:ignore ande clasics zzzzqqq glomgo storie
"""Story filters for a word search: tags, submitted years, Fantagraphics volumes."""

from __future__ import annotations

from barks_fantagraphics.barks_tags import BARKS_TAGGED_TITLES, Tags
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO
from barks_fantagraphics.search_filters import (
    AllFilters,
    AnyFilter,
    NotFilter,
    SearchFilter,
    apply_filter,
    closest_tags,
    submitted_year,
    tag_titles,
    titles_in_years,
    unknown_tag_notice,
)
from barks_fantagraphics.search_results import TitleInfo

ANDES = ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]  # 1948
POOR = ENUM_TO_STR_TITLE[Titles.ONLY_A_POOR_OLD_MAN]  # 1951
PIRATE = ENUM_TO_STR_TITLE[Titles.DONALD_DUCK_FINDS_PIRATE_GOLD]  # 1942


def test_a_story_has_its_submitted_year() -> None:
    assert submitted_year(ANDES) == BARKS_TITLE_INFO[Titles.LOST_IN_THE_ANDES].submitted_year
    assert submitted_year("No Such Story") is None


def test_the_stories_in_years_are_every_story_submitted_then() -> None:
    expected = {
        ENUM_TO_STR_TITLE[info.title]
        for info in BARKS_TITLE_INFO
        if 1948 <= info.submitted_year <= 1951  # noqa: PLR2004
    }
    assert titles_in_years(1948, 1951) == expected
    assert {ANDES, POOR} <= expected
    assert PIRATE not in expected


def test_a_tag_or_group_names_its_stories() -> None:
    assert tag_titles("andes") == frozenset(
        ENUM_TO_STR_TITLE[t] for t in BARKS_TAGGED_TITLES[Tags.ANDES]
    )
    assert tag_titles("  ANDES ") == tag_titles("andes")
    africa = tag_titles("africa")  # a group: every story its members tag
    assert africa
    assert tag_titles("no such tag") is None


def test_the_closest_tags_hold_the_text_or_are_spelled_alike() -> None:
    assert closest_tags("clasics") == ["the classics"]
    assert "andes" in closest_tags("ande")
    assert len(closest_tags("a")) <= 3  # noqa: PLR2004
    assert closest_tags("zzzzqqq") == []


def test_an_unknown_tag_s_notice_names_the_closest_tags_if_any() -> None:
    assert unknown_tag_notice("clasics") == 'No tag is called "clasics". Closest: the classics.'
    assert unknown_tag_notice("zzzzqqq") == 'No tag is called "zzzzqqq".'


def test_an_empty_filter_allows_everything_and_lists_nothing() -> None:
    empty = SearchFilter()
    assert empty.is_empty
    assert empty.allows("No Such Story", 99)
    assert empty.candidates is None


def test_a_filter_allows_a_story_only_when_every_part_does() -> None:
    f = SearchFilter(years=(1948, 1951), volumes=(7, 7), tag_titles=frozenset({ANDES, POOR}))
    assert f.allows(ANDES, 7)
    assert not f.allows(ANDES, 8)  # volume
    assert not f.allows(POOR, 12)  # volume
    assert not SearchFilter(years=(1948, 1948)).allows(POOR, 12)  # year
    assert not f.allows(PIRATE, 7)  # tags, year
    assert not SearchFilter(years=(1948, 1951)).allows("No Such Story", 7)
    assert f.candidates == frozenset({ANDES, POOR})


def test_combined_filters() -> None:
    in_1948 = SearchFilter(years=(1948, 1948))
    vol_12 = SearchFilter(volumes=(12, 12))
    assert NotFilter(in_1948).allows(POOR, 12)
    assert not NotFilter(in_1948).allows(ANDES, 7)
    assert NotFilter(in_1948).candidates is None

    assert AnyFilter((in_1948, vol_12)).allows(POOR, 12)
    assert AnyFilter((in_1948, vol_12)).allows(ANDES, 7)
    assert not AnyFilter((in_1948, vol_12)).allows(PIRATE, 1)
    assert AnyFilter((in_1948, vol_12)).candidates is None  # a volume cannot list its stories
    in_1951 = SearchFilter(years=(1951, 1951))
    assert AnyFilter((in_1948, in_1951)).candidates == titles_in_years(
        1948, 1948
    ) | titles_in_years(1951, 1951)

    assert not AllFilters((in_1948, vol_12)).allows(ANDES, 7)
    assert AllFilters((in_1948, SearchFilter(volumes=(7, 7)))).allows(ANDES, 7)
    assert AllFilters((in_1948, vol_12)).candidates == titles_in_years(1948, 1948)
    assert AllFilters(()).candidates is None


def test_applying_a_filter_keeps_the_allowed_stories_in_order() -> None:
    found = {PIRATE: TitleInfo(1), ANDES: TitleInfo(7), POOR: TitleInfo(12)}
    kept = apply_filter(SearchFilter(volumes=(5, 12)), found)
    assert list(kept) == [ANDES, POOR]
    assert kept[ANDES] is found[ANDES]


def test_the_closest_tags_put_names_holding_the_text_before_close_spellings() -> None:
    assert closest_tags("glomgo") == [
        "Flintheart Glomgold",
        "first Flintheart Glomgold appearance",
        "glomgold",
    ]


def test_the_closest_tags_go_up_to_the_limit_asked_for() -> None:
    limit = 6  # more than difflib's own default of 3
    assert len(closest_tags("alien storie", limit=limit)) == limit


def test_the_notice_lists_the_closest_tags_comma_separated() -> None:
    assert unknown_tag_notice("glomgo") == (
        'No tag is called "glomgo". Closest: Flintheart Glomgold,'
        " first Flintheart Glomgold appearance, glomgold."
    )
