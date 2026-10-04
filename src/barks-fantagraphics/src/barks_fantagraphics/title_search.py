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
from .barks_titles import US_1_FC_ISSUE_NUM, US_2_FC_ISSUE_NUM, US_3_FC_ISSUE_NUM
from .comic_book_info import BARKS_ISSUE_DICT, BARKS_TITLE_INFO, COVERS_SET
from .comic_issues import ISSUE_NAME, SHORT_ISSUE_NAME, Issues
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


# What a text typed alone finds: every cover.
_COVER_WORDS = frozenset({"cover", "covers"})

# A submission date, or part of one, that is not known.
_NO_DATE = -1


def _when_submitted(title: Titles) -> tuple[int, int, int, int]:
    """Return a title's place in time: when Barks handed it in, then its chronological number.

    Stories and covers are each numbered in the order they were handed in, but every
    cover after every story, so the date is what places a cover among the stories. The
    few with no known date go by when they came out.
    """
    info = BARKS_TITLE_INFO[title]
    if info.submitted_year == _NO_DATE:
        return info.issue_year, info.issue_month, _NO_DATE, title
    return info.submitted_year, info.submitted_month, info.submitted_day, title


# Uncle Scrooge 1 to 3 came out as these Four Color issues.
_US_AS_FC = ((1, US_1_FC_ISSUE_NUM), (2, US_2_FC_ISSUE_NUM), (3, US_3_FC_ISSUE_NUM))


@cache
def _issue_numbers(issue: Issues) -> frozenset[int]:
    """Return the numbers of an issue's comics that hold something Barks did."""
    return frozenset(info.issue_number for info in BARKS_TITLE_INFO if info.issue_name == issue)


@dataclass(frozen=True, slots=True)
class _SearchableTitle:
    title: Titles
    text: str  # as `_words_only` reads it
    bare: str  # the same without a leading "the", "a" or "an"
    words: tuple[str, ...]
    stems: frozenset[str]  # every stem each word may be a form of: fleecing, fleece

    def is_found_by(self, text: str, typed_words: list[str]) -> bool:
        """Whether a typed text, as `_words_only` reads it, finds this title.

        See `BarksTitleSearch.find_titles` for the rules.
        """
        return (
            self.text.startswith(text)
            or self.bare.startswith(text)
            or (len(text) >= PREFIX_LEN and all(map(self.has_word_for, typed_words)))
            or (
                len(text) >= SUBSTRING_MIN_CHARS
                and all(typed in self.text for typed in typed_words)
            )
        )

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
        """Return the titles a typed text finds, in the order Barks handed them in.

        A text naming an issue ("CS 100", "wdcs100", "Four Color #223") finds what Barks did
        in it, as `get_titles_in_issues` reads it, covers too, and nothing else. "Cover" or
        "covers" alone finds every cover. Any other text finds the stories, not the covers,
        where:

        - it starts with the text, with or without its leading "The", "A" or "An";
        - from two letters, each typed word starts one of the title's words, or is another
          form of one, in any order ("gold fleece" finds "The Golden Fleecing");
        - from three letters, each typed word is anywhere in the title ("ost" finds
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

        found = self.get_titles_in_issues(query)
        if found is not None:
            return found
        if text in _COVER_WORDS:
            covers = [s.title for s in self._searchable if s.title in COVERS_SET]
            return sorted(covers, key=_when_submitted)
        return [
            s.title
            for s in self._searchable
            if s.title not in COVERS_SET and s.is_found_by(text, typed_words)
        ]

    @staticmethod
    def get_titles_in_issues(text: str) -> list[Titles] | None:
        """Return what Barks did in each issue a text names, or None when it names none.

        The issue is its code, short name or full name, then the start of its number, in
        any case, with or without spaces, punctuation or "#": "CS 100", "wdcs100", "Four
        Color #223". "CS 10" names CS 10 and CS 100 to 109, as the number is typed; a
        leading 0 is passed over.
        Uncle Scrooge 1 to 3 are the Four Color issues they came out as.

        Args:
            text: The typed text.

        Returns:
            Each story, one-pager and cover in those issues, in the order Barks handed
            them in.

        """
        match = _ISSUE.fullmatch(_issue_name_key(text))
        if match is None:
            return None
        issue = _issue_names().get(match[1])
        if issue is None:
            return None
        digits = str(int(match[2]))  # "CS 010" is CS 10
        numbers = {(issue, n) for n in _issue_numbers(issue) if str(n).startswith(digits)}
        if issue == Issues.US:
            numbers |= {(Issues.FC, fc) for us, fc in _US_AS_FC if str(us).startswith(digits)}
        in_issues = [
            info.title
            for info in BARKS_TITLE_INFO
            if (info.issue_name, info.issue_number) in numbers
        ]
        return sorted(in_issues, key=_when_submitted)

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
