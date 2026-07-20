"""Static guard: every BARKS_EXTRA_INFO entry produces leak-proof hyphen markup.

The Gladstone bug was a literal editorial bracket (``[actually, ...]``) swallowing an
injected ``[ref]`` tag under Kivy's non-greedy markup parsing, which silently dropped
hyphenation for the whole paragraph. This test renders the markup for every real entry
and fails, naming the entry, if any bracketed segment Kivy would parse is not a clean
tag — catching that class of failure before it ships, without needing a GUI.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from barks_fantagraphics.barks_extra_info import BARKS_EXTRA_INFO
from barks_reader.core.hyphen_break_engine import BreakRefinement
from barks_reader.core.reader_formatter import escape_editorial_brackets, hyphenate_text

if TYPE_CHECKING:
    from barks_fantagraphics.barks_titles import Titles

# Kivy isolates every ``[...]`` (non-greedy) as a potential tag; each must be one we own.
_KIVY_SEGMENT = re.compile(r"\[.*?\]")
_VALID_TAG = re.compile(r"\[/?[bi]\]|\[ref=brk:f\d+\]|\[/ref\]")


def _extra_info_markup(raw: str) -> str:
    # markup() with no hyphens/disabled is the maximum-ref-density state, so if it has
    # no leak, neither do the refined states (which only merge refs away).
    return BreakRefinement(hyphenate_text(escape_editorial_brackets(raw))).markup()


@pytest.mark.parametrize("title", list(BARKS_EXTRA_INFO), ids=lambda t: t.name)
def test_extra_info_markup_has_no_ref_leak(title: Titles) -> None:
    markup = _extra_info_markup(BARKS_EXTRA_INFO[title])
    bad = [seg for seg in _KIVY_SEGMENT.findall(markup) if not _VALID_TAG.fullmatch(seg)]
    assert not bad, f"{title.name}: Kivy would mis-parse bracket segment(s): {bad}"
