from __future__ import annotations

from collections import defaultdict

from .barks_tags import (
    BARKS_TAG_ALIASES,
    BARKS_TAG_GROUPS,
    BARKS_TAG_GROUPS_ALIASES,
    BARKS_TAGGED_TITLES,
    TagGroups,
    Tags,
)
from .barks_titles import BARKS_ISSUE_DICT, BARKS_TITLE_INFO, Titles
from .comic_issues import Issues

PREFIX_LEN = 2


class BarksTitleSearch:
    def __init__(self) -> None:
        self.title_prefix_dict: defaultdict[str, list[Titles]] = defaultdict(list)
        for info in BARKS_TITLE_INFO:
            if info.issue_name == Issues.EXTRAS:
                continue
            prefix = info.get_title_str()[:PREFIX_LEN].lower()
            self.title_prefix_dict[prefix].append(info.title)

        self.tag_prefix_dict: defaultdict[str, list[str]] = defaultdict(list)
        for tag_alias_str in BARKS_TAG_ALIASES:
            prefix = tag_alias_str[:PREFIX_LEN].lower()
            self.tag_prefix_dict[prefix].append(tag_alias_str)

        for tag_alias_str in BARKS_TAG_GROUPS_ALIASES:
            prefix = tag_alias_str[:PREFIX_LEN].lower()
            self.tag_prefix_dict[prefix].append(tag_alias_str)

        # Sort the lists for consistent return order
        for key in self.title_prefix_dict:
            self.title_prefix_dict[key].sort()
        for key in self.tag_prefix_dict:
            # Sorting here might be good for determinism if needed, but not strictly necessary
            self.tag_prefix_dict[key].sort()

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

    def get_tags_matching_prefix(self, prefix: str) -> list[Tags | TagGroups]:
        prefix = prefix.lower()
        if not prefix:
            return []

        if len(prefix) == 1:
            return self._get_titles_with_one_char_tag_search(prefix)

        short_prefix = prefix[:PREFIX_LEN]
        candidate_aliases = self.tag_prefix_dict.get(short_prefix, [])

        tag_list = self._get_tags_from_aliases(prefix, candidate_aliases)

        return list(set(tag_list))

    @staticmethod
    def get_titles_from_alias_tag(alias_tag_str: str) -> tuple[Tags | None, list[Titles]]:
        title_set: set[Titles] = set()

        if alias_tag_str in BARKS_TAG_ALIASES:
            tag = BARKS_TAG_ALIASES[alias_tag_str]
            title_set.update(BARKS_TAGGED_TITLES[tag])
            return tag, sorted(title_set)

        if alias_tag_str in BARKS_TAG_GROUPS_ALIASES:
            tag_group = BARKS_TAG_GROUPS_ALIASES[alias_tag_str]
            tags = BARKS_TAG_GROUPS[tag_group]
            for tag in tags:
                title_set.update(BARKS_TAGGED_TITLES[tag])
            return tag_group, sorted(title_set)

        return None, []

    def _get_titles_with_one_char_tag_search(self, prefix: str) -> list[Tags]:
        assert len(prefix) == 1
        all_aliases = list(BARKS_TAG_ALIASES.keys()) + list(BARKS_TAG_GROUPS_ALIASES.keys())
        return self._get_tags_from_aliases(prefix, all_aliases)

    def _get_tags_from_aliases(self, prefix: str, aliases: list[str]) -> list[Tags | TagGroups]:
        prefix = prefix.lower()

        if len(prefix) == 0:
            return []

        if len(prefix) == 1:
            return self._get_titles_with_one_char_tag_search(prefix)

        tag_list = []
        for alias_tag_str in aliases:
            if not alias_tag_str.startswith(prefix):
                continue
            if alias_tag_str in BARKS_TAG_ALIASES:
                tag_list.append(BARKS_TAG_ALIASES[alias_tag_str])
            if alias_tag_str in BARKS_TAG_GROUPS_ALIASES:
                tag_list.append(BARKS_TAG_GROUPS_ALIASES[alias_tag_str])

        return tag_list
