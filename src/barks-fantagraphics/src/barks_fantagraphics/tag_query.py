"""What the tag search box finds: each tag or tag group a typed text matches, with its count.

Kivy-free. The search plan (docs/plans/advanced-search.md in the reader) grows this
module into tag selections combined with AND, OR and NOT; for now it holds what one
typed text matches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .barks_tags import TagGroups, Tags


@dataclass(frozen=True, slots=True)
class TagMatch:
    """A tag or tag group a typed text matched.

    Attributes:
        item: The tag or tag group.
        label: Its display name, the chip's text (and one of its aliases, lower-cased).
        title_count: How many stories it tags; a group's, every story its members tag.
        exact: Whether the text was one of its aliases, whole.

    """

    item: Tags | TagGroups
    label: str
    title_count: int
    exact: bool = False
