"""Tests for the "By the Numbers" screen widget.

Kivy internals are patched out (the base screen's ``__init__`` injects a fake
``ids`` dict) so no ``.kv`` needs loading and no window is created.
"""
# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.corpus_stats import (
    TEXT_SECTION_SHAPE,
    CorpusStats,
    Opening,
    StatRow,
    StatSection,
)
from barks_reader.ui import corpus_stats_screen as corpus_stats_screen_module
from barks_reader.ui.corpus_stats_screen import CorpusStatsScreen
from barks_reader.ui.reader_keyboard_nav import KEY_ESCAPE, KEY_LEFT, KEY_RIGHT, KEY_UP
from barks_reader.ui.reader_screens import ReaderScreen

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_STATS = CorpusStats(
    opening=Opening(headline="683 stories, 1942-1973", standfirst="6,591 pages."),
    sections=(
        StatSection(heading="The corpus", rows=(StatRow("Stories", "683"),)),
        StatSection(heading="Barks's hand", rows=(StatRow("Script and art", "561", share=0.82),)),
        StatSection(heading="Length", rows=(StatRow("Longest story", "A Title", prose=True),)),
        StatSection(
            heading="Payment",
            rows=(StatRow("Total paid", "$216,894"), StatRow("Paid pages", "6,250")),
            footnote="From 564 of 947 records.",
        ),
        StatSection(heading="The cast", rows=(StatRow("Places", "62"),)),
    ),
)

_TEXT_SECTION = StatSection(
    heading="The words",
    rows=tuple(StatRow(f"Row {i}", "1") for i in range(TEXT_SECTION_SHAPE.num_rows)),
    footnote="Covers 407 of 683 stories.",
)

# Kivy validates colors and font sizes, so the stubs hand back real values
# rather than MagicMocks.
_COLOR = (1.0, 1.0, 1.0, 1.0)


class _FakeTheme:
    """Every palette field resolves to the same valid RGBA tuple."""

    def __getattr__(self, _name: str) -> tuple[float, float, float, float]:
        return _COLOR


class _FakeBox:
    """Stands in for a kv-declared layout: records what was added to it."""

    def __init__(self, width: float = 0.0) -> None:
        self.width = width
        self.height = 0.0
        self.padding: list[float] = []
        self.spacing = 0.0
        self.children: list[object] = []

    def clear_widgets(self) -> None:
        self.children.clear()

    def add_widget(self, widget: object) -> None:
        self.children.append(widget)

    def bind(self, **_kwargs: object) -> None:
        pass


@pytest.fixture
def screen(tmp_path: Path) -> Iterator[CorpusStatsScreen]:
    with (
        patch.object(ReaderScreen, "__init__", autospec=True) as mock_screen_init,
        patch.object(corpus_stats_screen_module, "_add_share_bar"),
        patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()),
        patch.object(CorpusStatsScreen, "_setup_action_bar_nav"),
    ):
        mock_ids = {
            "stats_page": _FakeBox(width=corpus_stats_screen_module.layout.REFERENCE_PAGE_WIDTH),
            "stats_opening": _FakeBox(),
            "stats_columns": _FakeBox(),
            "stats_left": _FakeBox(),
            "stats_right": _FakeBox(),
            "close_button": MagicMock(),
        }

        def side_effect(instance: CorpusStatsScreen, **_kwargs: object) -> None:
            instance.ids = mock_ids

        mock_screen_init.side_effect = side_effect
        built = CorpusStatsScreen(
            indexes_dir=tmp_path,
            font_manager=MagicMock(),
            on_close_screen=MagicMock(),
        )
        built._menu_mode = False
        yield built


def _open(screen: CorpusStatsScreen) -> None:
    with (
        patch.object(corpus_stats_screen_module, "compute_static_stats", return_value=_STATS),
        patch.object(corpus_stats_screen_module, "threading"),
        patch.object(corpus_stats_screen_module, "get_action_bar_title", return_value="t"),
        patch.object(corpus_stats_screen_module, "Window"),
        patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()),
    ):
        screen.open()


def _rebuild(screen: CorpusStatsScreen) -> None:
    with patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()):
        screen._rebuild()


class TestBuildOnOpen:
    def test_nothing_computed_before_opening(self, screen: CorpusStatsScreen) -> None:
        assert screen._stats is None
        assert not screen.ids["stats_left"].children

    def test_opening_builds_the_page(self, screen: CorpusStatsScreen) -> None:
        _open(screen)
        assert screen._stats is _STATS
        assert screen.ids["stats_left"].children
        assert screen.ids["stats_right"].children

    def test_reopening_reuses_the_cached_stats(self, screen: CorpusStatsScreen) -> None:
        with (
            patch.object(
                corpus_stats_screen_module, "compute_static_stats", return_value=_STATS
            ) as mock_compute,
            patch.object(corpus_stats_screen_module, "threading"),
            patch.object(corpus_stats_screen_module, "get_action_bar_title", return_value="t"),
            patch.object(corpus_stats_screen_module, "Window"),
            patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()),
        ):
            screen.open()
            screen.open()
        assert mock_compute.call_count == 1

    def test_the_scan_starts_only_once(self, screen: CorpusStatsScreen) -> None:
        with (
            patch.object(corpus_stats_screen_module, "compute_static_stats", return_value=_STATS),
            patch.object(corpus_stats_screen_module, "threading") as mock_threading,
            patch.object(corpus_stats_screen_module, "get_action_bar_title", return_value="t"),
            patch.object(corpus_stats_screen_module, "Window"),
            patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()),
        ):
            screen.open()
            screen.open()
        assert mock_threading.Thread.call_count == 1


class TestTwoColumns:
    def test_the_sections_are_split_between_the_columns(self, screen: CorpusStatsScreen) -> None:
        _open(screen)
        # Three sections plus a gap each on the left; two sections, the reserved
        # dialogue slot, their gaps, and the trailing spacer on the right.
        assert len(screen.ids["stats_left"].children) == 3 * 2 + 1
        assert len(screen.ids["stats_right"].children) == 3 * 2 + 1

    def test_the_opening_spans_the_page(self, screen: CorpusStatsScreen) -> None:
        _open(screen)
        # Headline, standfirst and the gap beneath them.
        assert len(screen.ids["stats_opening"].children) == 3

    def test_the_columns_are_gutter_spaced(self, screen: CorpusStatsScreen) -> None:
        _open(screen)
        assert screen.ids["stats_columns"].spacing > 0


class TestTheReservedDialogueSlot:
    def _right_heights(self, screen: CorpusStatsScreen) -> list[float]:
        return [getattr(c, "height", 0.0) for c in screen.ids["stats_right"].children]

    def test_the_slot_is_reserved_before_the_scan_lands(self, screen: CorpusStatsScreen) -> None:
        _open(screen)
        reserved = corpus_stats_screen_module.layout.reserved_height(TEXT_SECTION_SHAPE)
        assert reserved in self._right_heights(screen)

    def test_the_page_does_not_reflow_when_the_scan_lands(self, screen: CorpusStatsScreen) -> None:
        # The whole point of reserving the slot: a page that cannot scroll must be
        # exactly as tall after the background scan as it was before.
        _open(screen)
        before = self._right_heights(screen)

        screen._text_section = _TEXT_SECTION
        _rebuild(screen)

        assert self._right_heights(screen) == before

    def test_the_landed_section_fills_the_slot(self, screen: CorpusStatsScreen) -> None:
        _open(screen)
        screen._text_section = _TEXT_SECTION
        _rebuild(screen)

        reserved = corpus_stats_screen_module.layout.reserved_height(TEXT_SECTION_SHAPE)
        slot = next(
            c for c in screen.ids["stats_right"].children if getattr(c, "height", 0.0) == reserved
        )
        # Heading, six rows and a footnote, rather than the placeholder heading.
        assert len(slot.children) == 1 + TEXT_SECTION_SHAPE.num_rows + 1

    def test_a_failing_scan_does_not_escape_the_thread(self, screen: CorpusStatsScreen) -> None:
        with patch.object(
            corpus_stats_screen_module, "compute_text_stats", side_effect=RuntimeError("boom")
        ):
            screen._scan_text_stats()
        assert screen._text_section is None

    def test_no_index_leaves_the_section_empty(self, screen: CorpusStatsScreen) -> None:
        with patch.object(corpus_stats_screen_module, "compute_text_stats", return_value=None):
            screen._scan_text_stats()
        assert screen._text_section is None


class TestRowShapes:
    def test_a_row_without_a_share_gets_no_bar(self, screen: CorpusStatsScreen) -> None:
        with (
            patch.object(corpus_stats_screen_module, "_add_share_bar") as mock_bar,
            patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()),
        ):
            screen._row(StatRow("Stories", "683"), 1.0)
        mock_bar.assert_not_called()

    def test_a_row_with_a_share_gets_a_bar(self, screen: CorpusStatsScreen) -> None:
        with (
            patch.object(corpus_stats_screen_module, "_add_share_bar") as mock_bar,
            patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()),
        ):
            row = screen._row(StatRow("Script and art", "561", share=0.82), 1.0)
        mock_bar.assert_called_once_with(row, 0.82)

    def test_a_prose_row_stacks_its_label_above_its_value(self, screen: CorpusStatsScreen) -> None:
        with patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()):
            row = screen._row(StatRow("Longest story", "Pirate Gold, 64 pages", prose=True), 1.0)
        assert row.orientation == "vertical"
        # Kivy lists children back to front, so the value was added last.
        value, label = row.children
        assert label.text == "Longest story"
        assert value.text == "[b]Pirate Gold, 64 pages[/b]"
        assert value.halign == "left"

    def test_headings_are_set_as_written(self, screen: CorpusStatsScreen) -> None:
        with patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()):
            assert screen._heading("The corpus", 1.0).text == "[b]The corpus[/b]"

    def test_footnote_is_italicised(self, screen: CorpusStatsScreen) -> None:
        with patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()):
            footnote = screen._footnote("From 564 of 947 records.", 1.0)
        assert footnote.text == "[i]From 564 of 947 records.[/i]"


class TestScaling:
    def test_type_scales_with_the_page(self, screen: CorpusStatsScreen) -> None:
        with patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()):
            small = screen._heading("The corpus", 1.0).font_size
            large = screen._heading("The corpus", 2.0).font_size
        assert large == pytest.approx(2 * small)

    def test_row_heights_scale_with_the_page(self, screen: CorpusStatsScreen) -> None:
        # Heights must ride the same scalar as the type, or the page falls apart.
        with patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()):
            small = screen._row(StatRow("Stories", "683"), 1.0).height
            large = screen._row(StatRow("Stories", "683"), 2.0).height
        assert large == pytest.approx(2 * small)


class TestKeyboard:
    def test_escape_closes_the_page(self, screen: CorpusStatsScreen) -> None:
        # Not the mixin's default, which would open the action-bar menu instead.
        with patch.object(corpus_stats_screen_module, "Window"):
            assert screen._handle_reading_key(KEY_ESCAPE)
        screen._on_close_screen.assert_called_once()

    def test_left_closes_the_page(self, screen: CorpusStatsScreen) -> None:
        with patch.object(corpus_stats_screen_module, "Window"):
            assert screen._handle_reading_key(KEY_LEFT)
        screen._on_close_screen.assert_called_once()

    def test_up_reaches_the_action_bar(self, screen: CorpusStatsScreen) -> None:
        with patch.object(screen, "_enter_menu_mode") as mock_menu:
            assert screen._handle_reading_key(KEY_UP)
        mock_menu.assert_called_once()

    def test_an_unhandled_key_is_not_consumed(self, screen: CorpusStatsScreen) -> None:
        assert not screen._handle_reading_key(KEY_RIGHT)


class TestLifecycle:
    def test_opening_rebinds_rather_than_double_binding(self, screen: CorpusStatsScreen) -> None:
        with (
            patch.object(corpus_stats_screen_module, "compute_static_stats", return_value=_STATS),
            patch.object(corpus_stats_screen_module, "threading"),
            patch.object(corpus_stats_screen_module, "get_action_bar_title", return_value="t"),
            patch.object(corpus_stats_screen_module, "Window") as mock_window,
            patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()),
        ):
            screen.open()
            screen.open()
        assert mock_window.unbind.call_count == mock_window.bind.call_count

    def test_closing_unbinds_and_hands_the_window_back(self, screen: CorpusStatsScreen) -> None:
        with patch.object(corpus_stats_screen_module, "Window") as mock_window:
            screen.close()
        mock_window.unbind.assert_called_once()
        screen._on_close_screen.assert_called_once()
