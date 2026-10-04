from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

from .barks_tags import (
    BARKS_TAG_ALIASES,
    BARKS_TAG_GROUPS,
    BARKS_TAG_GROUPS_ALIASES,
    BARKS_TAGGED_TITLES,
    TagGroups,
    Tags,
    get_all_tags_in_tag_group,
)
from .comic_book_info import BARKS_ISSUE_DICT, BARKS_TITLE_INFO
from .comic_issues import ISSUE_NAME, SHORT_ISSUE_NAME, Issues, _get_shortest_issue_name
from .fanta_comics_info import FANTA_SOURCE_COMICS, get_fanta_info
from .search_query import Combine
from .search_terms import SUBSTRING_MIN_CHARS, _stems_of
from .tag_query import TagMatch

if TYPE_CHECKING:
    from .barks_titles import Titles
    from .tag_query import TagSelection

PREFIX_LEN = 2


def _fanta_volume(title: Titles) -> int | None:
    """Return the Fantagraphics volume a story is in, or None for one in none."""
    info = get_fanta_info(title)
    return None if info is None else FANTA_SOURCE_COMICS[info.fantagraphics_volume].volume


@cache
def _titles_tagged_by(item: Tags | TagGroups) -> tuple[Titles, ...]:
    """Return the stories a tag tags, sorted; a group's, every story its members tag.

    Read once per tag: the tag box counts every tag it lists, on every keystroke.
    """
    tags = get_all_tags_in_tag_group(item) if isinstance(item, TagGroups) else {item}
    return tuple(sorted({title for tag in tags for title in BARKS_TAGGED_TITLES.get(tag, [])}))


# How an alias matched a typed text, best first.
_EXACT, _PREFIX, _INSIDE = 0, 1, 2

_APOSTROPHES = re.compile("['\u2019]")  # straight and curly
_NOT_A_WORD = re.compile(r"[\W_]+")
_ARTICLES = ("the ", "a ", "an ")
_ISSUE = re.compile(r"([a-z]+)(\d+)")

# The other names an issue goes by, beside its code and its names in comic_issues.
_MORE_ISSUE_NAMES = {"Walt Disney's Comics and Stories": Issues.CS}


def _words_only(text: str) -> str:
    """Return the text lowercased, with apostrophes dropped and other punctuation as spaces.

    So "The Gold-Finder" reads "the gold finder" and "The Rabbit's Foot" "the rabbits foot".
    """
    return " ".join(_NOT_A_WORD.sub(" ", _APOSTROPHES.sub("", text.lower())).split())


def _issue_name_key(name: str) -> str:
    """Return a text as `_words_only` reads it, run together with no spaces.

    So "Four Color #223", "four-color 223" and "FourColor223" all read the same.
    """
    return _words_only(name).replace(" ", "")


@cache
def _issue_names() -> dict[str, Issues]:
    """Return each name an issue goes by, as `_issue_name_key` reads it."""
    names: dict[str, Issues] = {}
    for issue in Issues:
        if issue != Issues.EXTRAS:
            for name in (issue.name, SHORT_ISSUE_NAME[issue], ISSUE_NAME[issue]):
                names[_issue_name_key(name)] = issue
    for name, issue in _MORE_ISSUE_NAMES.items():
        names[_issue_name_key(name)] = issue
    return names


@dataclass(frozen=True, slots=True)
class _SearchableTitle:
    title: Titles
    text: str  # as `_words_only` reads it
    bare: str  # the same without a leading "the", "a" or "an"
    words: tuple[str, ...]
    stems: frozenset[str]  # every stem each word may be a form of: fleecing, fleece

    def has_word_for(self, typed: str) -> bool:
        """Whether a typed word starts one of the title's words or shares a stem with one."""
        return any(word.startswith(typed) for word in self.words) or bool(
            _stems_of(typed) & self.stems
        )


class BarksTitleSearch:
    def __init__(self) -> None:
        self._searchable: list[_SearchableTitle] = []
        self.title_prefix_dict: defaultdict[str, list[Titles]] = defaultdict(list)
        for info in BARKS_TITLE_INFO:
            if info.issue_name == Issues.EXTRAS:
                continue
            prefix = info.get_title_str()[:PREFIX_LEN].lower()
            self.title_prefix_dict[prefix].append(info.title)

            text = _words_only(info.get_title_str())
            article = next((a for a in _ARTICLES if text.startswith(a)), "")
            words = tuple(text.split())
            stems = frozenset(stem for word in words for stem in _stems_of(word))
            self._searchable.append(
                _SearchableTitle(info.title, text, text[len(article) :], words, stems)
            )

        # Sort the lists for consistent return order
        for key in self.title_prefix_dict:
            self.title_prefix_dict[key].sort()

    @staticmethod
    def get_titles_as_strings(titles: list[Titles]) -> list[str]:
        return [BARKS_TITLE_INFO[title].get_display_title() for title in titles]

    def find_titles(self, query: str) -> list[Titles]:
        """Return the titles a typed text finds, best matches first.

        An issue the text names ("CS 100", "wdcs100", "Four Color #223") comes first, with
        its stories. Then, in publication order within each:

        1. titles starting with the text, with or without their leading "The", "A" or "An";
        2. from two letters, titles where each typed word starts one of the title's words,
           or is another form of one, in any order ("gold fleece" finds "The Golden
           Fleecing");
        3. from three letters, titles holding each typed word anywhere ("ost" finds
           "Lost in the Andes!").

        Case, apostrophes and other punctuation are ignored.

        Args:
            query: The text typed into the title box.

        Returns:
            Each title found, once.

        """
        text = _words_only(query)
        if not text:
            return []
        typed_words = text.split()

        ranks: tuple[list[Titles], list[Titles], list[Titles]] = ([], [], [])
        for searchable in self._searchable:
            if searchable.text.startswith(text) or searchable.bare.startswith(text):
                ranks[0].append(searchable.title)
            elif len(text) >= PREFIX_LEN and all(map(searchable.has_word_for, typed_words)):
                ranks[1].append(searchable.title)
            elif len(text) >= SUBSTRING_MIN_CHARS and all(
                typed in searchable.text for typed in typed_words
            ):
                ranks[2].append(searchable.title)

        found = dict.fromkeys(self.get_titles_in_issue(query))
        for rank in ranks:
            found.update(dict.fromkeys(rank))
        return list(found)

    @staticmethod
    def get_titles_in_issue(text: str) -> list[Titles]:
        """Return the stories in the issue a text names, or none when it names none.

        The issue is its code, short name or full name, then its number, in any case, with
        or without spaces, punctuation or "#": "CS 100", "wdcs100", "Four Color #223".

        Args:
            text: The typed text.

        Returns:
            The issue's stories, as `get_titles_from_issue_num` gives them, in a new list.

        """
        match = _ISSUE.fullmatch(_issue_name_key(text))
        if match is None:
            return []
        issue = _issue_names().get(match[1])
        if issue is None:
            return []
        number = int(match[2])
        return list(BARKS_ISSUE_DICT.get(f"{_get_shortest_issue_name(issue)} {number}", []))

    def get_titles_matching_prefix(self, prefix: str) -> list[Titles]:
        prefix = prefix.lower()

        if len(prefix) == 0:
            return []

        if len(prefix) == 1:
            # For a single character, we check all titles starting with it.
            return [
                info.title
                for info in BARKS_TITLE_INFO
                if info.issue_name != Issues.EXTRAS
                and info.get_title_str().lower().startswith(prefix)
            ]

        short_prefix = prefix[:PREFIX_LEN]
        candidate_titles = self.title_prefix_dict.get(short_prefix, [])
        return [
            t
            for t in candidate_titles
            if BARKS_TITLE_INFO[t].get_title_str().lower().startswith(prefix)
        ]

    @staticmethod
    def get_titles_from_issue_num(issue_num: str) -> list[Titles]:
        issue_num = issue_num.upper()
        if issue_num not in BARKS_ISSUE_DICT:
            return []
        return BARKS_ISSUE_DICT[issue_num]

    @staticmethod
    def get_titles_containing(word: str) -> list[Titles]:
        if len(word) <= 1:
            return []

        word = word.lower()
        return [
            info.title
            for info in BARKS_TITLE_INFO
            if info.issue_name != Issues.EXTRAS and word in info.get_title_str().lower()
        ]

    @staticmethod
    def get_tags_matching(text: str) -> list[TagMatch]:
        """Return the tags and tag groups `text` matches, best first, with their story counts.

        An alias the text is, whole, first (its tag is `exact`); then aliases starting
        with it; then, from three letters, aliases with it inside. Each tag appears
        once, at its best match; each group is sorted by display name.

        Args:
            text: What was typed, in any case.

        Returns:
            The matches; empty when nothing is typed.

        """
        query = text.strip().lower()
        if not query:
            return []
        inside = len(query) >= SUBSTRING_MIN_CHARS
        best: dict[Tags | TagGroups, int] = {}
        for alias, item in (*BARKS_TAG_ALIASES.items(), *BARKS_TAG_GROUPS_ALIASES.items()):
            if alias == query:
                rank = _EXACT
            elif alias.startswith(query):
                rank = _PREFIX
            elif inside and query in alias:
                rank = _INSIDE
            else:
                continue
            best[item] = min(rank, best.get(item, rank))
        ranked = sorted(best, key=lambda item: (best[item], str(item.value)))
        return [
            TagMatch(
                item=item,
                label=str(item.value),
                title_count=BarksTitleSearch.get_tag_title_count(item),
                exact=best[item] == _EXACT,
            )
            for item in ranked
        ]

    @staticmethod
    def get_tag_title_count(item: Tags | TagGroups) -> int:
        """Return how many stories a tag tags; for a group, every story its members tag."""
        return len(_titles_tagged_by(item))

    @staticmethod
    def get_titles_for_selection(selection: TagSelection) -> list[Titles]:
        """Return the stories a tag selection lists, in chronological order.

        Those every included tag tags (ALL) or any does (ANY), less those any
        excluded tag tags, and of those, the ones submitted in its years and in its
        Fantagraphics volumes, if it gives them. A group tags every story its
        members tag. Nothing is listed without an included tag, and a name that is
        no tag tags nothing.

        Args:
            selection: The tags, by name or alias, in any case.

        Returns:
            The stories.

        """
        included = [
            set(BarksTitleSearch.get_titles_from_alias_tag(n.lower())[1])
            for n in selection.included
        ]
        if not included:
            return []
        if selection.combine is Combine.ALL:
            titles = set.intersection(*included)
        else:
            titles = set.union(*included)
        for name in selection.excluded:
            titles -= set(BarksTitleSearch.get_titles_from_alias_tag(name.lower())[1])
        if selection.years is not None:
            first, last = selection.years
            titles = {t for t in titles if first <= BARKS_TITLE_INFO[t].submitted_year <= last}
        if selection.volumes is not None:
            first, last = selection.volumes
            titles = {t for t in titles if first <= (_fanta_volume(t) or 0) <= last}
        return sorted(titles)

    @staticmethod
    def get_titles_from_alias_tag(
        alias_tag_str: str,
    ) -> tuple[Tags | TagGroups | None, list[Titles]]:
        item: Tags | TagGroups | None = BARKS_TAG_ALIASES.get(alias_tag_str)
        if item is None:
            item = BARKS_TAG_GROUPS_ALIASES.get(alias_tag_str)
        if item is None:
            return None, []
        return item, list(_titles_tagged_by(item))

    @staticmethod
    def get_direct_group_members(tag_group: TagGroups) -> list[Tags | TagGroups]:
        return list(BARKS_TAG_GROUPS.get(tag_group, []))
