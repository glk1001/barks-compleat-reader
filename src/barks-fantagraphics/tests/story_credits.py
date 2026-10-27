"""Read the role credits in a story ini's ``extra_pub_info``: who wrote it, and who drew it.

Three checks ask the credits a question: whether a Misc story names any credit at all
(``test_misc_series_ini``), whether a story another scriptwriter wrote is bylined as wholly
Barks's (``test_story_bylines``), and whether the credits agree with Barks's role in
Barrier's bibliography (``test_story_credits``). They read the credits here, one way.

Each line of ``extra_pub_info`` is read on its own, and a credit must be the whole line:

* "Script not by Barks" - someone else wrote it.
* "[Pages 1-3, ]<role> by <who>" or "<role>: <who>", where the role is "script",
  "script and layout", "script and finished art", "pencils and inks" or "art". A "script"
  role credits the script, an "art" or "pencils and inks" role the art; "layout" alone is
  not art. ``who`` is Barks when it starts with "Barks" or "Carl Barks", so "Script by Bob
  Gregory and Barks" credits another writer.

Anything else is not a credit: restoration notes ("Original art and dialogue ... restored
by GLK"), "Layout and restoration by Kim Weston", and Silent Night's "and Unn
Printz-Pahlsom, art by Daan Jippes", which credits only its added opening half-page. A line
that names a script, pencils or inks but is none of the forms above is kept as
unrecognised, so a new wording is reported rather than silently missed. (Bare "art" is no
sign of a credit: restoration notes say it too.)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NOT_BY_BARKS_RE = re.compile(r"script not by barks\.?", re.IGNORECASE)
_ROLE_RE = re.compile(
    r"(?:pages?\s+[\d\s,-]+?,?\s+)?"
    r"(?P<role>script and finished art|script and layout|script|pencils and inks|art)"
    r"(?:\s+by\s+|\s*:\s*)(?P<who>.+)",
    re.IGNORECASE,
)
_BARKS_RE = re.compile(r"(?:carl\s+)?barks\b", re.IGNORECASE)
_ROLE_WORD_RE = re.compile(r"\b(?:script|pencils|inks)\b", re.IGNORECASE)


@dataclass(frozen=True)
class StoryCredits:
    """The script and art credits read from one story's ``extra_pub_info``."""

    barks_script: bool = False
    other_script: bool = False
    barks_art: bool = False
    other_art: bool = False
    unrecognised: tuple[str, ...] = ()

    @property
    def any(self) -> bool:
        """Whether the credits name anyone's script or art."""
        return self.barks_script or self.other_script or self.barks_art or self.other_art


def read_credits(extra_pub_info: str) -> StoryCredits:
    """Read the script and art credits from a story's ``extra_pub_info``.

    Args:
        extra_pub_info: The ini's ``extra_pub_info`` value, one note per line.

    Returns:
        Whether Barks, and whether someone else, is credited with the script and with
        the art, and any line that looks like a credit but is not one of the known forms.

    """
    found: set[tuple[str, bool]] = set()
    unrecognised: list[str] = []
    for line in (raw.strip() for raw in extra_pub_info.splitlines()):
        if _NOT_BY_BARKS_RE.fullmatch(line):
            found.add(("script", False))
        elif match := _ROLE_RE.fullmatch(line):
            role = match["role"].lower()
            by_barks = bool(_BARKS_RE.match(match["who"]))
            if role.startswith("script"):
                found.add(("script", by_barks))
            if role.endswith("art") or role == "pencils and inks":
                found.add(("art", by_barks))
        elif _ROLE_WORD_RE.search(line):
            unrecognised.append(line)
    return StoryCredits(
        barks_script=("script", True) in found,
        other_script=("script", False) in found,
        barks_art=("art", True) in found,
        other_art=("art", False) in found,
        unrecognised=tuple(unrecognised),
    )
