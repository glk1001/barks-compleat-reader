from __future__ import annotations

from collections import defaultdict
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
from .comic_issues import Issues
from .search_terms import SUBSTRING_MIN_CHARS
from .tag_query import TagMatch

if TYPE_CHECKING:
    from .barks_titles import Titles

PREFIX_LEN = 2

# How an alias matched a typed text, best first.
_EXACT, _PREFIX, _INSIDE = 0, 1, 2


class BarksTitleSearch:
    def __init__(self) -> None:
        self.title_prefix_dict: defaultdict[str, list[Titles]] = defaultdict(list)
        for info in BARKS_TITLE_INFO:
            if info.issue_name == Issues.EXTRAS:
                continue
            prefix = info.get_title_str()[:PREFIX_LEN].lower()
            self.title_prefix_dict[prefix].append(info.title)

        # Sort the lists for consistent return order
        for key in self.title_prefix_dict:
            self.title_prefix_dict[key].sort()

    @staticmethod
    def get_titles_as_strings(titles: list[Titles]) -> list[str]:
        return [BARKS_TITLE_INFO[title].get_display_title() for title in titles]

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
        if isinstance(item, TagGroups):
            titles: set[Titles] = set()
            for tag in get_all_tags_in_tag_group(item):
                titles.update(BARKS_TAGGED_TITLES.get(tag, []))
            return len(titles)
        return len(BARKS_TAGGED_TITLES.get(item, []))

    @staticmethod
    def get_titles_from_alias_tag(
        alias_tag_str: str,
    ) -> tuple[Tags | TagGroups | None, list[Titles]]:
        title_set: set[Titles] = set()

        if alias_tag_str in BARKS_TAG_ALIASES:
            tag = BARKS_TAG_ALIASES[alias_tag_str]
            title_set.update(BARKS_TAGGED_TITLES[tag])
            return tag, sorted(title_set)

        if alias_tag_str in BARKS_TAG_GROUPS_ALIASES:
            tag_group = BARKS_TAG_GROUPS_ALIASES[alias_tag_str]
            for tag in get_all_tags_in_tag_group(tag_group):
                title_set.update(BARKS_TAGGED_TITLES[tag])
            return tag_group, sorted(title_set)

        return None, []

    @staticmethod
    def get_direct_group_members(tag_group: TagGroups) -> list[Tags | TagGroups]:
        return list(BARKS_TAG_GROUPS.get(tag_group, []))
