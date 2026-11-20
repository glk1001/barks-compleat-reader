"""The shape of `BARKS_EXTRA_INFO`: a note for a title, in the markup the reader shows.

The reader's own tests render every note; these hold what this package can say of them
without the reader, so the table is guarded where it lives.
"""

from __future__ import annotations

import re

import pytest
from barks_fantagraphics.barks_extra_info import BARKS_EXTRA_INFO
from barks_fantagraphics.barks_titles import Titles

_TAG = re.compile(r"\[(/?)([bi])\]")


def test_there_are_notes() -> None:
    # Guards the parametrize source below against collecting nothing.
    assert BARKS_EXTRA_INFO


def test_every_key_is_a_title() -> None:
    assert [key for key in BARKS_EXTRA_INFO if not isinstance(key, Titles)] == []


@pytest.mark.parametrize("title", list(BARKS_EXTRA_INFO), ids=lambda t: t.name)
def test_a_note_is_text_with_no_stray_space_around_it(title: Titles) -> None:
    note = BARKS_EXTRA_INFO[title]
    assert note
    assert note == note.strip()


@pytest.mark.parametrize("title", list(BARKS_EXTRA_INFO), ids=lambda t: t.name)
def test_a_note_closes_each_bold_and_italic_it_opens(title: Titles) -> None:
    is_open = {"b": False, "i": False}
    for closing, tag in _TAG.findall(BARKS_EXTRA_INFO[title]):
        # An opening tag must find its kind closed, and a closing tag find it open.
        assert is_open[tag] is bool(closing), f"[{closing}{tag}] out of turn"
        is_open[tag] = not closing
    assert is_open == {"b": False, "i": False}
