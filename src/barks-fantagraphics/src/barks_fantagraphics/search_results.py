"""The shape of a word search's result, and the set operations that combine results.

A result is a `TitleDict`: each story found, its Fantagraphics volume, and on each
of its pages the speech groups (bubbles) that matched. Kivy-free and Whoosh-free,
so the query evaluator and the fake search engine combine results without either.
`whoosh_search_engine` re-exports the types under their old names.

The operations follow the search plan's rules (docs/plans/advanced-search.md in the
reader): AND and NOT work at story level, so `intersect_titles` keeps the stories
every result found, with every result's bubbles in them, and `subtract_titles`
drops whole stories. None of them changes its arguments: `TitleInfo` is mutable,
and a result may be cached. Every result comes back in the engine's order: stories
and pages by name, bubbles by group number.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection


@dataclass(frozen=True, slots=True)
class SpeechInfo:
    """One matching speech group in a search result.

    ``speech_text`` is plain and ``speech_text_markup`` carries the ``[b]``/``[i]``
    emphasis tags, the same split as ``SpeechText`` and for the same reason: a
    caller that has not heard of emphasis gets correct text from the obvious
    attribute.  Only the reader's bubble list, which renders Kivy markup, wants
    the other one.

    ``speaker`` mirrors ``SpeechText.speaker``, reduced to the stored value --
    ``"Scrooge"``, ``"other:Witch Hazel"``, ``"none"`` -- because that is all
    the index keeps.  ``None`` when the group had no call, and always ``None``
    from an index built before the field existed.  Turn it into a label with
    ``speech_speakers.speaker_display_name``.
    """

    group_id: str
    panel_num: int
    speech_text: str
    speech_text_markup: str
    entity_types: tuple[str, ...] = ()
    speaker: str | None = None


@dataclass(frozen=True, slots=True)
class PageInfo:
    comic_page: str
    speech_info_list: list[SpeechInfo]


@dataclass(slots=True)
class TitleInfo:
    fanta_vol: int = 0
    fanta_pages: dict[str, PageInfo] = field(default_factory=dict)


type TitleDict = dict[str, TitleInfo]


def speech_sort_key(speech_info: SpeechInfo) -> tuple[int, str]:
    """Order speech groups on a page numerically, tolerating non-numeric group ids.

    Group ids are numeric strings in a well-formed index. A malformed one must not
    take down the whole search, so it sorts after the numbered groups by its text.
    """
    if speech_info.group_id.isdigit():
        return (int(speech_info.group_id), "")
    return (sys.maxsize, speech_info.group_id)


def _merged_speech(first: SpeechInfo, second: SpeechInfo) -> SpeechInfo:
    """Return one speech group found by two searches: their entity types together."""
    extra = tuple(t for t in second.entity_types if t not in first.entity_types)
    return replace(first, entity_types=first.entity_types + extra) if extra else first


def merge_title_dicts(*title_dicts: TitleDict) -> TitleDict:
    """Return every story any of `title_dicts` found, with all their bubbles: OR.

    A bubble found by more than one search appears once, with the entity types
    they gave it together.

    Args:
        *title_dicts: The results to combine.

    Returns:
        A new result, in the engine's order.

    Raises:
        ValueError: If two results map the same page of a story to different comic
            pages - an inconsistent index, as the engine itself reports it.

    """
    volumes: dict[str, int] = {}
    comic_pages: dict[tuple[str, str], str] = {}
    speeches: dict[tuple[str, str], dict[str, SpeechInfo]] = {}
    for title_dict in title_dicts:
        for title, title_info in title_dict.items():
            volumes.setdefault(title, title_info.fanta_vol)
            for fanta_page, page_info in title_info.fanta_pages.items():
                key = (title, fanta_page)
                known = comic_pages.setdefault(key, page_info.comic_page)
                if known != page_info.comic_page:
                    msg = (
                        f'Index inconsistency for "{title}": fanta page {fanta_page}'
                        f" maps to both comic page {known} and {page_info.comic_page}."
                    )
                    raise ValueError(msg)
                on_page = speeches.setdefault(key, {})
                for speech in page_info.speech_info_list:
                    earlier = on_page.get(speech.group_id)
                    on_page[speech.group_id] = (
                        speech if earlier is None else _merged_speech(earlier, speech)
                    )

    merged: TitleDict = {title: TitleInfo(fanta_vol=volumes[title]) for title in sorted(volumes)}
    for title, fanta_page in sorted(comic_pages):
        merged[title].fanta_pages[fanta_page] = PageInfo(
            comic_pages[(title, fanta_page)],
            sorted(speeches[(title, fanta_page)].values(), key=speech_sort_key),
        )
    return merged


def restrict_titles(title_dict: TitleDict, titles: Collection[str]) -> TitleDict:
    """Return the part of `title_dict` about the stories in `titles`: a filter.

    Args:
        title_dict: A result.
        titles: The stories to keep.

    Returns:
        A new result, in the engine's order.

    """
    return merge_title_dicts({t: info for t, info in title_dict.items() if t in titles})


def intersect_titles(first: TitleDict, *others: TitleDict) -> TitleDict:
    """Return the stories every result found, with every result's bubbles in them: AND.

    The same story, not the same bubble: a story is kept when each search found
    something in it, and all of what they found is kept, so each word's matches
    can be shown.

    Args:
        first: A result.
        *others: The results it must share stories with.

    Returns:
        A new result, in the engine's order.

    """
    common = set(first).intersection(*others)
    return merge_title_dicts(*(restrict_titles(d, common) for d in (first, *others)))


def subtract_titles(kept: TitleDict, removed: TitleDict) -> TitleDict:
    """Return the stories of `kept` that `removed` did not find: NOT, at story level.

    Args:
        kept: A result.
        removed: The result whose stories are dropped from it.

    Returns:
        A new result with `kept`'s bubbles, in the engine's order.

    """
    return restrict_titles(kept, set(kept) - set(removed))


def hit_counts(title_dict: TitleDict) -> dict[str, int]:
    """Return how many bubbles matched in each story.

    Args:
        title_dict: A result.

    Returns:
        Each story's count of matching speech groups, in the result's order.

    """
    return {
        title: sum(len(page.speech_info_list) for page in info.fanta_pages.values())
        for title, info in title_dict.items()
    }
