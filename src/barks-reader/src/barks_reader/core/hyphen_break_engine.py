"""Pure bookkeeping for rendering soft-hyphen-marked text with real hyphens.

Kivy has no soft-hyphen support: a marked word either always shows the hyphen or
never breaks on it. The workaround is a two-pass refinement driven by the UI layer
(``barks_reader.ui.hyphen_label.HyphenatingLabel``):

1. Each hyphenatable word is rendered as consecutive ``[ref=brk:fN]fragment[/ref]``
   runs. A markup run boundary is a legal Kivy wrap point, so the fragments give the
   layout its break opportunities, and the refs report where each fragment landed.
2. After a render, the ref bounding boxes reveal which fragment gaps coincide with an
   actual line break (adjacent fragments on different lines). A real ``-`` is inserted
   at exactly those gaps and the text is re-rendered, iterating to a fixpoint.
3. A gap that oscillates (hyphen doesn't fit, so the break moves away, then returns)
   is disabled: its fragments are merged into one run, removing the break opportunity.

This module is deliberately Kivy-free so the fixpoint logic is fully unit-testable;
only ``BreakRefinement.observe`` consumes ref boxes, as plain mappings.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum, auto
from itertools import pairwise
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

SOFT_HYPHEN = "\xad"
REF_PREFIX = "brk:f"

# Tokens containing markup or paragraph breaks must never gain break points:
# a hyphen (or a run split) inside a tag like [i] would corrupt the markup.
NO_BREAK_CHARS = ("\n", "[", "]", "&")

# Existing trailing dashes (hyphen-minus, Unicode hyphen, non-breaking hyphen) that a
# line-break hyphen must not be doubled onto.
_HYPHEN_CHARS = ("-", "\u2010", "\u2011")

MAX_ITERS = 8
TOGGLE_LIMIT = 2

# Ref boxes on the same layout line share an exact y, but compare with a small
# tolerance in case a text provider ever reports fractional pixels.
_SAME_LINE_Y_TOLERANCE = 0.5

type Box = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class Token:
    """One space-delimited token: its hyphenation fragments and global fragment ids."""

    fragments: tuple[str, ...]
    first_fragment_id: int


@dataclass(frozen=True, slots=True)
class ParsedText:
    """Soft-hyphen-marked text split into tokens and globally-numbered fragments.

    A gap is the position between two adjacent fragments of one token, identified
    by the global id of its left fragment.
    """

    tokens: tuple[Token, ...]
    gaps: frozenset[int]


class RefinementStatus(Enum):
    CONTINUE = auto()
    STABLE = auto()
    FAILED = auto()


def parse_marked_text(text: str) -> ParsedText:
    """Parse soft-hyphen-marked text into tokens/fragments with global ids.

    Args:
        text: Text with U+00AD soft hyphens marking hyphenation points.

    Returns:
        The parsed structure. Tokens containing markup characters or newlines are
        kept whole (any stray markers stripped), so they can never gain break points.

    """
    tokens: list[Token] = []
    gaps: set[int] = set()
    next_id = 0

    for raw_token in text.split(" "):
        fragments = tuple(f for f in raw_token.split(SOFT_HYPHEN) if f)
        if len(fragments) < 2 or any(c in raw_token for c in NO_BREAK_CHARS):  # noqa: PLR2004
            fragments = (raw_token.replace(SOFT_HYPHEN, ""),)

        tokens.append(Token(fragments=fragments, first_fragment_id=next_id))
        gaps.update(range(next_id, next_id + len(fragments) - 1))
        next_id += len(fragments)

    return ParsedText(tokens=tuple(tokens), gaps=frozenset(gaps))


def _token_runs(token: Token, disabled: frozenset[int]) -> list[tuple[int, str]]:
    """Group a token's fragments into runs, merging across disabled gaps.

    Returns:
        ``(first_fragment_id, run_text)`` pairs, in order.

    """
    runs: list[tuple[int, str]] = []
    current_id = token.first_fragment_id
    current_text = token.fragments[0]

    for i in range(1, len(token.fragments)):
        gap_id = token.first_fragment_id + i - 1
        if gap_id in disabled:
            current_text += token.fragments[i]
        else:
            runs.append((current_id, current_text))
            current_id = token.first_fragment_id + i
            current_text = token.fragments[i]

    runs.append((current_id, current_text))
    return runs


def build_markup(parsed: ParsedText, hyphens: frozenset[int], disabled: frozenset[int]) -> str:
    """Build the Kivy markup string for one refinement pass.

    Args:
        parsed: The parsed source text.
        hyphens: Gap ids that get a visible ``-`` (must be at line ends).
        disabled: Gap ids whose fragments are merged (no break opportunity).

    Returns:
        Markup where each multi-fragment token is a sequence of ``[ref=...]`` runs.

    """
    parts: list[str] = []

    for token in parsed.tokens:
        if len(token.fragments) == 1:
            parts.append(token.fragments[0])
            continue

        runs = _token_runs(token, disabled)
        if len(runs) == 1:
            parts.append(runs[0][1])
            continue

        pieces: list[str] = []
        for i, (first_id, run_text) in enumerate(runs):
            breaks_here = i < len(runs) - 1 and (runs[i + 1][0] - 1) in hyphens
            # Don't double a hyphen when the fragment already ends in one (e.g. the
            # pyphen point sits right beside the literal hyphen in "e-mail").
            hyphen = "-" if breaks_here and not run_text.endswith(_HYPHEN_CHARS) else ""
            pieces.append(f"[ref={REF_PREFIX}{first_id}]{run_text}{hyphen}[/ref]")
        parts.append("".join(pieces))

    return " ".join(parts)


def compute_breaks(
    parsed: ParsedText,
    disabled: frozenset[int],
    refs: Mapping[str, Sequence[Box]],
) -> frozenset[int] | None:
    """Determine which enabled gaps coincide with an actual line break.

    Args:
        parsed: The parsed source text.
        disabled: Gap ids with no break opportunity (merged fragments).
        refs: Rendered ref bounding boxes (name -> boxes, top-left origin).

    Returns:
        The breaking gap ids, or None if an expected ref is missing (detection failed).

    """
    breaks: set[int] = set()

    for token in parsed.tokens:
        if len(token.fragments) < 2:  # noqa: PLR2004
            continue
        for (left_id, _), (right_id, _) in pairwise(_token_runs(token, disabled)):
            left_boxes = refs.get(f"{REF_PREFIX}{left_id}")
            right_boxes = refs.get(f"{REF_PREFIX}{right_id}")
            if not left_boxes or not right_boxes:
                return None
            if abs(left_boxes[-1][1] - right_boxes[0][1]) > _SAME_LINE_Y_TOLERANCE:
                breaks.add(right_id - 1)

    return frozenset(breaks)


class BreakRefinement:
    """Fixpoint state machine: hyphens exactly at gaps where lines actually break.

    Usage: render ``markup()``, feed the resulting ref boxes to ``observe()``, and
    repeat while it returns CONTINUE. STABLE means the current markup is final;
    FAILED means detection broke down or the iteration cap was hit — render
    ``fallback_markup()`` (break opportunities, no visible hyphens).
    """

    def __init__(self, marked_text: str) -> None:
        self._parsed = parse_marked_text(marked_text)
        self._hyphens: frozenset[int] = frozenset()
        self._disabled: frozenset[int] = frozenset()
        self._toggles: Counter[int] = Counter()
        self._seen: set[tuple[frozenset[int], frozenset[int]]] = {(frozenset(), frozenset())}
        self._iterations = 0

    @property
    def has_gaps(self) -> bool:
        return bool(self._parsed.gaps)

    def markup(self) -> str:
        """Return the markup for the current (hyphens, disabled) state."""
        return build_markup(self._parsed, self._hyphens, self._disabled)

    def fallback_markup(self) -> str:
        """Return markup with all break opportunities but no visible hyphens."""
        return build_markup(self._parsed, frozenset(), frozenset())

    def final_markup(self) -> str:
        """Return the stable markup with all non-breaking gaps merged away.

        Adjacent runs are measured separately by Kivy, which pads each by a pixel
        or two (noticeably in italics), leaving hairline gaps inside words. Once
        the layout is stable, only the gaps that carry a hyphen need to stay run
        boundaries — those sit at line ends, where the padding is invisible.
        """
        return build_markup(self._parsed, self._hyphens, self._parsed.gaps - self._hyphens)

    def fallback_broken_words(self, refs: Mapping[str, Sequence[Box]]) -> list[str] | None:
        """Words that break across a line in the hyphen-less fallback markup.

        Diagnostic for the FAILED path: names which words wrapped without a visible
        hyphen, so a fallback can be reported specifically rather than silently.

        Args:
            refs: Rendered ref bounding boxes for the markup from ``fallback_markup()``.

        Returns:
            The offending whole words, or None if the breaks can't be determined
            (a ref is missing — typically the same reason refinement failed).

        """
        broken = compute_breaks(self._parsed, frozenset(), refs)
        if broken is None:
            return None

        words: list[str] = []
        for token in self._parsed.tokens:
            token_gaps = range(
                token.first_fragment_id, token.first_fragment_id + len(token.fragments) - 1
            )
            if broken.intersection(token_gaps):
                words.append("".join(token.fragments))
        return words

    def verify_final(self, refs: Mapping[str, Sequence[Box]]) -> bool:
        """Check that every hyphen still sits at a line break in the final markup.

        Args:
            refs: Rendered ref bounding boxes for the markup from ``final_markup()``.

        Returns:
            True if the merged layout still breaks at exactly the hyphen gaps.

        """
        observed = compute_breaks(self._parsed, self._parsed.gaps - self._hyphens, refs)
        return observed == self._hyphens

    def observe(self, refs: Mapping[str, Sequence[Box]]) -> RefinementStatus:
        """Advance the fixpoint from the ref boxes of the latest render.

        Args:
            refs: Rendered ref bounding boxes for the markup from ``markup()``.

        Returns:
            STABLE when every hyphen sits at a real line end and every breaking gap
            carries one; CONTINUE when another render pass is needed; FAILED when
            refs are unusable or MAX_ITERS is exhausted.

        """
        self._iterations += 1

        observed = compute_breaks(self._parsed, self._disabled, refs)
        if observed is None:
            return RefinementStatus.FAILED

        target = observed - self._disabled
        if target == self._hyphens:
            return RefinementStatus.STABLE
        if self._iterations >= MAX_ITERS:
            return RefinementStatus.FAILED

        # A gap whose hyphen keeps toggling (added, then the break moves away) can
        # never stabilize: disable it, merging its fragments for good.
        for gap in target ^ self._hyphens:
            self._toggles[gap] += 1
        disabled = self._disabled | frozenset(
            gap for gap, count in self._toggles.items() if count >= TOGGLE_LIMIT
        )
        hyphens = target - disabled

        if (hyphens, disabled) in self._seen:
            # Cycle backstop: kill every gap still in play and finish hyphen-less there.
            disabled = disabled | (hyphens ^ self._hyphens)
            hyphens = hyphens - disabled

        self._hyphens, self._disabled = hyphens, disabled
        self._seen.add((hyphens, disabled))
        return RefinementStatus.CONTINUE
