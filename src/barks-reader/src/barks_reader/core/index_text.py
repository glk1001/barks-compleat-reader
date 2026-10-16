"""How the index screens write a title or tag: sorted by its word after "The" or "A".

Kivy-free, so the GUI tests can tell which index entries are titles by the text the
index shows, rather than by knowing its layout.
"""

from __future__ import annotations

import re
import textwrap

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles

# The tag aliases (search shorthands) the index spells its own way: those found nowhere in
# their tag's name, and a surname the name's last word would cut short. Every other alias
# the index lists takes its spelling from its tag's name.
ALIAS_INDEX_NAMES = {
    "car 313": "car 313",
    "glittering goldie": "Glittering Goldie",
    "mount demon tooth": "Mount Demon Tooth",
    "south pole": "South Pole",
    "spell": "De Spell",
}

# The tag aliases that serve the search only: no reader looks the tag up under them in the
# index. Half or part of a name known whole (Zoola, Morganbilt, Carver, Dorado of "El
# Dorado"), one another entry already covers (Demon), or a misleading pointer ("Scrooge"
# lists only the Uncle Scrooge stories outside the US series).
SEARCH_ONLY_ALIASES = frozenset(
    {"carver", "demon", "dorado", "helper", "morganbilt", "scrooge", "zombie", "zoola"}
)

# The longest title an index row shows with its pages, before it is shortened.
MAX_TITLE_AND_PAGES_LEN = 34 + 8  # len(", 11,...") == 8


def sortable_string(text: str) -> str:
    """Return `text` with a leading "The" or "A" moved to the end: "Ghost of the Grotto, The".

    Args:
        text: A title or tag name.

    Returns:
        The text as the index lists it, so it sorts by its first real word.

    """
    text_upper = text.upper()
    if text_upper.startswith("THE "):
        return text[4:] + ", The"
    if text_upper.startswith("A "):
        return text[2:] + ", A"
    return text


def indexable_title_from_str(title_str: str) -> str:
    """Return a title as an index row shows it: shortened to fit, then made sortable."""
    return sortable_string(
        textwrap.shorten(title_str, width=MAX_TITLE_AND_PAGES_LEN, placeholder="...")
    )


def indexable_title(title: Titles) -> str:
    """Return `title` as an index row shows it."""
    return indexable_title_from_str(ENUM_TO_STR_TITLE[title])


def alias_index_name(alias: str, tag_name: str) -> str | None:
    """Return a tag alias as the index lists it, or None when it would only repeat the tag.

    An alias the tag's name starts with ("amnesia" for "amnesia stories", "gyro" for "Gyro
    Gearloose", or its plural, "utopias") would sit beside the tag in the index, and so is
    left out, as is one that is the whole name run together ("pjmcbrine") or is in
    `SEARCH_ONLY_ALIASES`. Any other alias is a cross-reference, spelled as
    `ALIAS_INDEX_NAMES` gives it, or else as the tag's name spells it ("mcbrine" is
    "McBrine" in "P.J.McBrine").

    Args:
        alias: A lower-case search alias of the tag.
        tag_name: The tag's name.

    Returns:
        The alias's index entry, or None for no entry.

    """
    if alias in SEARCH_ONLY_ALIASES:
        return None
    tag_lower = tag_name.lower()
    stems = {alias, alias.removesuffix("s"), alias.removesuffix("es")}
    if any(tag_lower.startswith(stem) for stem in stems):
        return None
    if _squashed(alias) == _squashed(tag_name):
        return None
    if alias in ALIAS_INDEX_NAMES:
        return ALIAS_INDEX_NAMES[alias]
    return _spelled_as_in(alias, tag_name)


def _squashed(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


def _spelled_as_in(alias: str, tag_name: str) -> str | None:
    """Return the words of `tag_name` that `alias` matches, ignoring case and apostrophes.

    A full stop separates words, so "mcbrine" is a word of "P.J.McBrine".
    """
    kept = [(i, " " if c == "." else c.lower()) for i, c in enumerate(tag_name) if c != "'"]
    plain = "".join(c for _, c in kept)
    match = re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", plain)
    if match is None:
        return None
    return tag_name[kept[match.start()][0] : kept[match.end() - 1][0] + 1]
