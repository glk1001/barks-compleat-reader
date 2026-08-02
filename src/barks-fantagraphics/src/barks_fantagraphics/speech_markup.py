"""Inline emphasis markup for OCR speech text.

Emphasis detected by the vision pass is stored **inside** ``ai_text`` as Kivy
markup — ``[b]WORD[/b]`` — rather than as character offsets held in a separate
field.

The reason is drift.  Offsets index a string that other tools edit: the kivy
editor rewrites ``ai_text``, ``string_replacer`` runs bulk regex substitutions
over it, and applying a queued vision correction changes its length.  Every one
of those silently moves the text out from under a stored offset, and the result
stays *in range*, so a bounds check cannot see it.  The pilot's ``077 g1``
carries a bold span ``[26, 35]`` over the last word, and a queued correction
that shortens the text by two characters; applying it would have slid the bold
two characters along, off the word it marks, with nothing raising an error --
the offsets are still in range.  Inline tags travel with the characters they
mark, so that class of bug cannot occur.

What inline markup costs instead is that every consumer must now strip it.  That
is a *visible* failure — a stray ``[b]`` in a search result is noticed the first
time anyone looks — where a drifted offset is invisible forever, which is why the
trade is worth making.  It is still a trap, so the default is arranged to be
safe: ``SpeechText.ai_text`` returns stripped text and callers must ask for
``ai_text_markup`` to get the tags.  Only the reader, which renders Kivy markup
natively, needs to.

## Escaping

Kivy's markup parser gives ``[`` and ``]`` meaning, and ``&`` introduces its
escape sequences, so literal occurrences in the comic text must be escaped.
They are not hypothetical: across 148,614 corpus groups, 31 contain brackets --
including Gemini's own ``[Illegible Comic Covers]`` and ``[Chinese Characters]``
annotations -- and 59 contain an ampersand, from signage like ``GOLDSTEIN & CO.``
and ``FEEDS & SEEDS``.

Text is stored **escaped**, because escaping at render time is impossible: once
a literal ``[`` and a real ``[b]`` are both sitting in the string there is no way
to tell them apart without having recorded which was which.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# The emphasis tags a group may carry. Kivy understands more (`u`, `s`, `sub`,
# `font`, `color`, ...), but widening this set would let the vision pass write
# presentation choices into what is supposed to be a record of the lettering.
# Bold is what Barks's letterer varies; italic is here for captions set in a
# slanted face, which page 176's yellow box is.
EMPHASIS_TAGS = ("b", "i")

# What the retired `emphasis_spans` field called them. Only the migration needs
# this; nothing writes the long forms any more.
_LEGACY_KINDS = {"bold": "b", "italic": "i"}

# `[`, `]` and `&` in the comic text itself, in the form Kivy expects.
# `&` is listed first on purpose: it must be escaped before the bracket rules
# run, or the `&` each of them introduces would be escaped a second time.
_ESCAPES = (("&", "&amp;"), ("[", "&bl;"), ("]", "&br;"))

_TAG_RE = re.compile(r"\[/?(" + "|".join(EMPHASIS_TAGS) + r")\]")

# Any bracketed run, so that a tag Kivy would act on but we do not allow --
# `[color=ff0000]`, `[ref=x]` -- is reported rather than passed through.
_ANY_TAG_RE = re.compile(r"\[[^\[\]]*\]")

# Everything in a stored string that is *not* the comic's own lettering: the
# emphasis tags, and the escape sequences standing in for a literal `[`, `]`
# or `&`. Built from the two definitions above so it cannot fall out of step.
_MARKUP_TOKEN_RE = re.compile(
    r"\[/?(?:"
    + "|".join(EMPHASIS_TAGS)
    + r")\]|"
    + "|".join(re.escape(escaped) for _literal, escaped in _ESCAPES)
)


def escape_markup(text: str) -> str:
    """Escape ``[``, ``]`` and ``&`` so they survive as literal characters.

    Args:
        text: Plain comic text, with no markup tags in it.

    Returns:
        The text with its markup-significant characters escaped.

    """
    for literal, escaped in _ESCAPES:
        text = text.replace(literal, escaped)
    return text


def unescape_markup(text: str) -> str:
    """Turn Kivy's escape sequences back into the literal characters.

    Args:
        text: Text that may contain ``&bl;``, ``&br;`` or ``&amp;``.

    Returns:
        The text with those sequences replaced by ``[``, ``]`` and ``&``.

    """
    # Reversed, for the same reason `_ESCAPES` is ordered the way it is: `&amp;`
    # has to be substituted last or it would re-introduce an ampersand that the
    # bracket rules then read as the start of their own escape.
    for literal, escaped in reversed(_ESCAPES):
        text = text.replace(escaped, literal)
    return text


def strip_markup(text: str) -> str:
    """Return the plain text: emphasis tags removed, escapes resolved.

    This is what every consumer other than the reader wants -- the search index,
    the entity tagger, ``ocr_check``'s width-fit measurement, the capitalization
    map.  It is the inverse of :func:`escape_markup` for text carrying no tags.

    Args:
        text: Text that may contain emphasis markup.

    Returns:
        The text as it is lettered in the comic, with no markup in it.

    """
    return unescape_markup(_TAG_RE.sub("", text))


def has_markup(text: str) -> bool:
    """Whether the text carries any emphasis tag.

    Args:
        text: Text to test.

    Returns:
        True if at least one ``[b]``/``[i]`` tag pair opener or closer is present.

    """
    return _TAG_RE.search(text) is not None


def same_text_ignoring_markup(left: str, right: str) -> bool:
    """Whether two strings differ only in their emphasis markup.

    The distinction the correction-rate measurement rests on: a re-run that
    changes only which words are bold must not be counted as a text correction,
    because the baseline it is compared against (1.5% on the pilot) counts
    readings the art disagreed with.

    Args:
        left: First string.
        right: Second string.

    Returns:
        True if both strip to the same plain text.

    """
    return strip_markup(left) == strip_markup(right)


def transform_lettering_only(text: str, transform: Callable[[str], str]) -> str:
    """Apply ``transform`` to the comic's lettering, leaving markup untouched.

    For anything that rewrites a stored string in place -- search highlighting is
    the case this exists for -- rather than reading it.  A plain
    ``re.sub`` over the whole string reaches inside the markup: searching for
    ``b`` matches the ``b`` in ``[b]`` and wraps it, and searching for ``amp``
    matches inside ``&amp;``.  Either produces a tag Kivy cannot parse, so the
    reader shows broken text on screen rather than the line.

    Stripping first is not an option here, because the result has to keep its
    markup.  So the string is cut at every tag and escape sequence and the
    transform is applied only to what lies between.

    A consequence worth knowing: a match cannot span a markup token.  Searching
    "really sharp" against ``REALLY [b]SHARP[/b]`` finds nothing, because the two
    words are in different segments.  That is a missed highlight, which is
    visible and harmless, and the alternative is mapping offsets across the tags
    -- the thing inline markup was adopted to avoid.

    Args:
        text: A stored string, possibly carrying markup.
        transform: Applied to each run of lettering between markup tokens.

    Returns:
        The text with ``transform`` applied to its lettering and every markup
        token preserved exactly.

    """
    out: list[str] = []
    cursor = 0
    for match in _MARKUP_TOKEN_RE.finditer(text):
        out.append(transform(text[cursor : match.start()]))
        out.append(match.group())
        cursor = match.end()
    out.append(transform(text[cursor:]))
    return "".join(out)


def validate_markup(text: str) -> list[str]:
    """Check that a string's emphasis markup is well formed.

    Catches the three ways hand-written or model-written markup goes wrong:
    a tag Kivy would act on that is not in :data:`EMPHASIS_TAGS`, a closer with
    no opener (or the reverse), and a bare ``[``, ``]`` or ``&`` that should have
    been escaped and will otherwise be eaten by Kivy's parser.

    Args:
        text: The marked-up text to check.

    Returns:
        A list of human-readable problems; empty when the markup is sound.

    """
    errors: list[str] = []

    allowed = ", ".join(f"[{t}]" for t in EMPHASIS_TAGS)
    errors.extend(
        f'unknown or disallowed tag "{match.group()}"; only {allowed} are allowed,'
        " and a literal bracket must be written &bl; or &br;"
        for match in _ANY_TAG_RE.finditer(text)
        if not _TAG_RE.fullmatch(match.group())
    )

    for tag in EMPHASIS_TAGS:
        opens = text.count(f"[{tag}]")
        closes = text.count(f"[/{tag}]")
        if opens != closes:
            errors.append(f"[{tag}] opened {opens} time(s) but closed {closes} time(s)")
        if opens and not _tags_are_nested(text, tag):
            errors.append(f"[{tag}] tags are out of order: a closer appears before its opener")

    # Whatever `_ANY_TAG_RE` did not account for is a stray bracket. Checking the
    # residue rather than the original avoids reporting the brackets that belong
    # to the tags themselves.
    residue = _ANY_TAG_RE.sub("", text)
    for literal, escaped in _ESCAPES:
        if literal == "&":
            # A bare `&` is only wrong when it is not already starting an escape.
            if re.search(r"&(?!amp;|bl;|br;)", residue):
                errors.append('unescaped "&"; write it as &amp;')
        elif literal in residue:
            errors.append(f'unescaped "{literal}"; write it as {escaped}')

    return errors


def _tags_are_nested(text: str, tag: str) -> bool:
    """Whether every closer for ``tag`` is preceded by a matching opener."""
    depth = 0
    for match in re.finditer(rf"\[(/?){tag}\]", text):
        depth += -1 if match.group(1) else 1
        if depth < 0:
            return False
    return depth == 0


def markup_from_spans(text: str, spans: list[list]) -> str:
    """Convert legacy ``emphasis_spans`` offsets into inline markup.

    Used once, by the migration that retired the spans field.  Kept here rather
    than in the migration script because it is the only place that records how
    the two representations line up, and a later reader of the git history will
    want it next to the format it produced.

    Args:
        text: The plain ``ai_text`` the spans were computed against.
        spans: ``[[start, end, kind], ...]`` offsets into ``text``.  ``kind`` may
            be a tag name or one of the retired long forms, ``bold``/``italic``.

    Returns:
        ``text`` escaped, with a tag pair wrapped around each span.

    Raises:
        ValueError: If a span is out of range or the spans overlap.

    """
    ordered = sorted(spans, key=lambda s: (s[0], s[1]))
    resolved: list[tuple[int, int, str]] = []
    last_end = 0
    for start, end, kind in ordered:
        if not 0 <= start < end <= len(text):
            msg = f"span [{start}, {end}] is outside text of length {len(text)}"
            raise ValueError(msg)
        if start < last_end:
            msg = f"span [{start}, {end}] overlaps the previous one"
            raise ValueError(msg)
        tag = _LEGACY_KINDS.get(kind, kind)
        if tag not in EMPHASIS_TAGS:
            msg = f'unknown emphasis kind "{kind}"'
            raise ValueError(msg)
        resolved.append((start, end, tag))
        last_end = end

    out: list[str] = []
    cursor = 0
    for start, end, tag in resolved:
        out.append(escape_markup(text[cursor:start]))
        out.append(f"[{tag}]{escape_markup(text[start:end])}[/{tag}]")
        cursor = end
    out.append(escape_markup(text[cursor:]))
    return "".join(out)
