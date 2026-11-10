# ruff: noqa: SLF001
"""The goto-title overlay's caption: a title in italics, shown as text."""

from __future__ import annotations

from barks_reader.ui import goto_title_overlay


def test_a_title_is_set_in_italics() -> None:
    assert goto_title_overlay._italic("Lost in the Andes!") == "[i]Lost in the Andes![/i]"


def test_a_titles_own_brackets_and_ampersand_are_text_not_markup() -> None:
    assert goto_title_overlay._italic("Tom & [b]Jerry") == "[i]Tom &amp; &bl;b&br;Jerry[/i]"
