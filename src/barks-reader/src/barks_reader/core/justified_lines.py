"""Bring back the end of a justified line that Kivy's markup layout pushed past its edge.

When a justified line's spaces cannot fill it exactly, Kivy (2.3.1, ``MarkupLabel``) pushes
the line's last space and what follows to the right edge: it splits that run in two, left
and right of the space. But it measures the halves in the font of the run it last added a
space to, which on a line mixing roman and italic may be a different one. The widths come
out wrong, the end of the line lands past the label's edge, and the texture cuts it off.

Lines with no split can overrun too, by a few pixels: a line's runs are measured one by one
and rounded, more of them where hyphenation points divide its words.

This module is Kivy-free so that it can be unit tested: it takes the laid-out lines and a
way to measure a word. It moves words sideways only, so the line breaks are not touched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence


class JustifiedWord(Protocol):
    """One run of a laid-out line: its text, its width and the style it is drawn in."""

    lw: float

    @property
    def text(self) -> str: ...

    @property
    def options(self) -> object: ...


class JustifiedLine(Protocol):
    """One laid-out line."""

    @property
    def words(self) -> Sequence[JustifiedWord]: ...

    @property
    def is_last_line(self) -> bool: ...


def _last_spaced_run_index(words: Sequence[JustifiedWord]) -> int | None:
    for index in range(len(words) - 1, -1, -1):
        if " " in words[index].text:
            return index
    return None


def _is_split(words: Sequence[JustifiedWord], index: int) -> bool:
    """Say whether a run is the right half of a run Kivy split.

    A split's halves hold the very same options, where each run of the markup has its own.
    """
    word = words[index]
    return index > 0 and word.text.startswith(" ") and words[index - 1].options is word.options


def _run_giving_way(words: Sequence[JustifiedWord], spaced: int) -> JustifiedWord | None:
    """Find the run that can be narrowed, so that what gets drawn over is only a space.

    Returns:
        The run itself if it ends in a space, the one before it if it starts with one, or
        None if its spaces are all inside it: narrowing anything would overlap letters.

    """
    if words[spaced].text.endswith(" "):
        return words[spaced]
    if spaced > 0 and words[spaced].text.startswith(" "):
        return words[spaced - 1]
    return None


def repair_justified_lines(
    lines: Iterable[JustifiedLine],
    usable_width: float,
    measure: Callable[[JustifiedWord], float],
) -> None:
    """Bring the end of each justified line back to the right edge.

    A pushed end goes flush with the edge, past it or short of it. Any other line's end only
    comes back if it is past the edge. The run giving way may end up a pixel or two narrower
    than its text measures, which is safe: what it gives up is a space.

    Args:
        lines: The lines as laid out, changed in place.
        usable_width: The width lines fill: the label's less its side padding.
        measure: Gives a word's width in its own font.

    """
    for line in lines:
        words = line.words
        spaced = _last_spaced_run_index(words) if not line.is_last_line else None
        if spaced is None:
            continue

        split = _is_split(words, spaced)
        if split:
            words[spaced].lw = measure(words[spaced])
        giving_way = words[spaced - 1] if split else _run_giving_way(words, spaced)
        if giving_way is None:
            continue

        past_edge = sum(word.lw for word in words[:-1]) + measure(words[-1]) - usable_width
        if split or past_edge > 0:
            giving_way.lw = max(0, giving_way.lw - past_edge)
