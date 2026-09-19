"""Who says an OCR speech group: the speaker vocabulary and its per-group record.

The vision pass in ``barks-ocr`` writes a **speaker call** onto each prelim OCR
group -- ``speaker``, ``speaker_confidence``, ``cap_colour``, ``identified_by``
-- and this module is the reader-side definition of that vocabulary.  It is
kept deliberately close to ``barks_ocr.utils.vision_schema`` (same names, same
values) so that repo can one day import from here instead of carrying its own
copy; ``barks_ocr`` depends on this package, never the reverse, which is why the
vocabulary has to live on this side.

## The ``speaker`` value

A single string, never a list.  Either a name from the closed roster
(:data:`SPEAKER_OPTIONS`), a story-cast name taken from the comics database
(``"Flintheart Glomgold"``, ``"The Beagle Boys"``), or free text behind the
:data:`OTHER_PREFIX` (``"other:Witch Hazel"``, ``"other:the crowd"``).  Three
roster entries are sentinels, not characters:

- ``narrator`` -- a caption box.
- ``none`` -- nobody speaks it: a sound effect, a sign, background lettering.
- ``unknown`` -- the speaker could not be placed at all.

A fourth, ``nephews``, is a collective: one of Huey, Dewey and Louie when the
art will not say which, or all three at once.  Several speakers at once are
written as free text (``"other:Donald and the nephews"``); nothing here tries
to split those.

## Coverage

Every key is optional.  Volumes 1 to 18 carry a call on all but a few hundred
groups, 19 and 20 are partial, and later volumes have none at all, so a
consumer must treat an absent call as ordinary.  ``speaker_confidence`` is
constant ``"high"`` across volumes 1 to 18 because a reviewed call is forced
to it; it carries no information there.  The evidence keys ``cap_colour`` and
``identified_by`` can be present-and-``null``, which is different from absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# The closed roster the vision pass chooses from. Story cast from the comics
# database extends it per title (see `is_valid_speaker` in barks-ocr), so a
# bare name outside this tuple is legitimate data, not an error.
SPEAKER_OPTIONS: tuple[str, ...] = (
    "Donald",
    "Huey",
    "Dewey",
    "Louie",
    "nephews",
    "Daisy",
    "Gladstone",
    "Scrooge",
    "Gyro",
    "narrator",
    "none",
    "unknown",
)
ROSTER: frozenset[str] = frozenset(SPEAKER_OPTIONS)
OTHER_PREFIX = "other:"

NARRATOR = "narrator"
NO_SPEAKER = "none"
UNKNOWN_SPEAKER = "unknown"
NON_CHARACTER_SPEAKERS: frozenset[str] = frozenset({NARRATOR, NO_SPEAKER, UNKNOWN_SPEAKER})

NEPHEWS_COLLECTIVE = "nephews"
NEPHEW_NAMES: frozenset[str] = frozenset({"Huey", "Dewey", "Louie"})

# The roster entries that name somebody, in the order the vision pass lists
# them. What a "filter by speaker" control offers.
CHARACTER_SPEAKER_OPTIONS: tuple[str, ...] = tuple(
    s for s in SPEAKER_OPTIONS if s not in NON_CHARACTER_SPEAKERS
)

CONFIDENCE_OPTIONS: tuple[str, ...] = ("high", "medium", "low")
CAP_COLOUR_OPTIONS: tuple[str, ...] = ("red", "blue", "green")
IDENTIFIED_BY_OPTIONS: tuple[str, ...] = (
    "balloon-tail",
    "cap-colour",
    "costume",
    "hat",
    "sole-figure",
    "dialogue",
    "caption",
    "off-panel",
)

# The group keys, as written to the prelim JSON.
SPEAKER_KEY = "speaker"
SPEAKER_CONFIDENCE_KEY = "speaker_confidence"
CAP_COLOUR_KEY = "cap_colour"
IDENTIFIED_BY_KEY = "identified_by"

# What the sentinels are shown as. `none` maps to nothing: a sound effect gets
# no speaker line at all.
_SENTINEL_DISPLAY: dict[str, str | None] = {
    NARRATOR: "Caption",
    UNKNOWN_SPEAKER: "Unknown",
    NO_SPEAKER: None,
}

# Words left lower-case inside a title-cased name: "Donald and the Nephews",
# not "Donald And The Nephews". Always capitalized when first.
_SMALL_WORDS: frozenset[str] = frozenset(
    {"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with"}
)


def _title_case(name: str) -> str:
    """Capitalize each word of a free-text name, leaving small words and apostrophes alone.

    ``str.title`` would give ``"The Quizmaster'S Assistant"``; this gives
    ``"The Quizmaster's Assistant"``.  A word already carrying a capital
    anywhere (``"McSue"``, ``"O'Gilt"``) is kept as written.
    """
    words = name.split()
    out: list[str] = []
    for i, word in enumerate(words):
        if any(c.isupper() for c in word) or (i > 0 and word in _SMALL_WORDS):
            out.append(word)
        else:
            out.append(word[0].upper() + word[1:])
    return " ".join(out)


def is_other_speaker(speaker: str) -> bool:
    """Whether a speaker value is free text behind the ``other:`` prefix.

    Args:
        speaker: A ``speaker`` value as stored.

    Returns:
        True for ``"other:..."`` values.

    """
    return speaker.startswith(OTHER_PREFIX)


def is_character_speaker(speaker: str) -> bool:
    """Whether a speaker value names somebody, rather than being a sentinel.

    Args:
        speaker: A ``speaker`` value as stored.

    Returns:
        False for ``narrator``, ``none`` and ``unknown``; True for everything
        else, including ``other:`` values and the ``nephews`` collective.

    """
    return speaker not in NON_CHARACTER_SPEAKERS


def speaker_display_name(speaker: str) -> str | None:
    """Return how a speaker value should read on screen, or None for no label.

    Presentation only, and case-preserving for names: the roster is already in
    display case, ``nephews`` and the sentinels are not.  A caller wanting the
    comic's all-caps lettering look upper-cases the result itself.

    Args:
        speaker: A ``speaker`` value as stored.

    Returns:
        ``None`` for ``none`` (nothing to show), ``"Caption"`` for ``narrator``,
        ``"Unknown"`` for ``unknown``, the text after ``other:`` in title case
        (``"The Juke Box"``, ``"Donald and the Nephews"``), and any other value
        title-cased the same way (so ``nephews`` reads ``"Nephews"``).

    """
    if speaker in _SENTINEL_DISPLAY:
        return _SENTINEL_DISPLAY[speaker]
    name = speaker.removeprefix(OTHER_PREFIX).strip()
    if not name:
        return None
    return _title_case(name)


@dataclass(frozen=True, slots=True)
class SpeakerCall:
    """One group's speaker call and the evidence it rests on.

    ``speaker`` is the value as stored -- roster name, cast name or
    ``other:`` text.  The rest is what the call was made from: ``cap_colour``
    is the nephew-cap evidence that makes a Huey/Dewey/Louie call reversible,
    and ``identified_by`` lists the cues (balloon tail, costume, sole figure,
    ...) from :data:`IDENTIFIED_BY_OPTIONS`.  Review bookkeeping
    (``speaker_was``, review dates and notes) is deliberately not carried; it
    stays in the page JSON for the tools that own it.
    """

    speaker: str
    confidence: str | None = None
    cap_colour: str | None = None
    identified_by: tuple[str, ...] = ()

    @property
    def is_other(self) -> bool:
        """Whether the speaker is free text behind ``other:``."""
        return is_other_speaker(self.speaker)

    @property
    def is_character(self) -> bool:
        """Whether the speaker names somebody rather than being a sentinel."""
        return is_character_speaker(self.speaker)

    @property
    def display_name(self) -> str | None:
        """The on-screen form of the speaker, or None when there is nothing to show."""
        return speaker_display_name(self.speaker)


def speaker_call_from_group(group: dict[str, Any]) -> SpeakerCall | None:
    """Read a group's speaker call out of its prelim JSON dict.

    Tolerant by design: the keys are absent on unprocessed groups and whole
    volumes, and the evidence keys are written as explicit ``null`` when there
    is nothing to record.  ``identified_by`` is sorted, because the two OCR
    engines' files list the same cues in different orders and nothing about the
    order is meaningful.

    Args:
        group: One entry of the page JSON's ``groups`` dict.

    Returns:
        The call, or ``None`` when the group has no (or an empty) ``speaker``.

    """
    speaker = group.get(SPEAKER_KEY)
    if not speaker:
        return None

    identified_by = group.get(IDENTIFIED_BY_KEY) or ()
    return SpeakerCall(
        speaker=str(speaker),
        confidence=group.get(SPEAKER_CONFIDENCE_KEY) or None,
        cap_colour=group.get(CAP_COLOUR_KEY) or None,
        identified_by=tuple(sorted(str(cue) for cue in identified_by)),
    )
