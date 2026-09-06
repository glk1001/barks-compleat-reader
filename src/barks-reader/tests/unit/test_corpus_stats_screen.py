"""Tests for the "By the Numbers" screen widget.

Kivy internals are patched out (the base layout's ``__init__`` injects a fake
``ids`` dict) so no ``.kv`` needs loading and no window is created.
"""
# ruff: noqa: SLF001, PLR2004

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core.corpus_stats import CorpusStats, HeroStat, StatRow, StatSection
from barks_reader.ui import corpus_stats_screen as corpus_stats_screen_module
from barks_reader.ui.corpus_stats_screen import CorpusStatsScreen
from barks_reader.ui.reader_keyboard_nav import KEY_ESCAPE, KEY_LEFT
from kivy.uix.floatlayout import FloatLayout

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

_STATS = CorpusStats(
    hero=(HeroStat("683", "stories"), HeroStat("6,591", "story pages")),
    sections=(
        StatSection(heading="The Corpus", rows=(StatRow("Stories", "683"),)),
        StatSection(
            heading="Payment",
            rows=(StatRow("Total paid", "$216,894"), StatRow("Paid pages", "6,250")),
            footnote="From 564 of 947 records.",
        ),
    ),
)

_TEXT_SECTION = StatSection(
    heading="The Words",
    rows=(StatRow("Words spoken", "574,699"),),
    footnote="Covers 407 of 683 stories.",
)


# Kivy validates colors and font sizes, so the stubs hand back real values
# rather than MagicMocks.
_COLOR = (1.0, 1.0, 1.0, 1.0)


class _FakeTheme:
    """Every palette field resolves to the same valid RGBA tuple."""

    def __getattr__(self, _name: str) -> tuple[float, float, float, float]:
        return _COLOR


def _fake_font_manager() -> MagicMock:
    font_manager = MagicMock()
    for name in (
        "main_title_font_size",
        "search_label_font_size",
        "text_block_heading_font_size",
        "main_index_item_font_size",
        "main_title_footnote_font_size",
    ):
        setattr(font_manager, name, 14.0)
    return font_manager


@pytest.fixture
def screen(tmp_path: Path) -> Iterator[CorpusStatsScreen]:
    with (
        patch.object(FloatLayout, "__init__", autospec=True) as mock_layout_init,
        patch.object(corpus_stats_screen_module, "dp", side_effect=lambda x: x),
        patch.object(corpus_stats_screen_module, "_fill_background"),
        patch.object(corpus_stats_screen_module, "_add_heading_hairline"),
        patch.object(corpus_stats_screen_module, "theme", return_value=_FakeTheme()),
    ):
        mock_ids = {"corpus_stats_rows": MagicMock(), "corpus_stats_scroll": MagicMock()}

        def side_effect(instance: CorpusStatsScreen, **_kwargs: object) -> None:
            instance.ids = mock_ids

        mock_layout_init.side_effect = side_effect
        yield CorpusStatsScreen(indexes_dir=tmp_path, font_manager=_fake_font_manager())


class TestBuildOnFirstShow:
    def test_nothing_computed_before_shown(self, screen: CorpusStatsScreen) -> None:
        assert screen._stats is None
        screen.ids["corpus_stats_rows"].clear_widgets.assert_not_called()

    def test_shown_builds_the_page(self, screen: CorpusStatsScreen) -> None:
        with (
            patch.object(corpus_stats_screen_module, "compute_static_stats", return_value=_STATS),
            patch.object(corpus_stats_screen_module, "threading") as mock_threading,
        ):
            screen.on_is_visible(None, visible=True)

        assert screen._stats is _STATS
        screen.ids["corpus_stats_rows"].clear_widgets.assert_called_once()
        mock_threading.Thread.assert_called_once()
        mock_threading.Thread.return_value.start.assert_called_once()

    def test_hidden_does_not_build(self, screen: CorpusStatsScreen) -> None:
        with patch.object(corpus_stats_screen_module, "compute_static_stats") as mock_compute:
            screen.on_is_visible(None, visible=False)
        mock_compute.assert_not_called()

    def test_second_show_reuses_the_cached_stats(self, screen: CorpusStatsScreen) -> None:
        with (
            patch.object(
                corpus_stats_screen_module, "compute_static_stats", return_value=_STATS
            ) as mock_compute,
            patch.object(corpus_stats_screen_module, "threading"),
        ):
            screen.on_is_visible(None, visible=True)
            screen.on_is_visible(None, visible=True)

        assert mock_compute.call_count == 1


class TestRowConstruction:
    def _widgets(self, screen: CorpusStatsScreen) -> list:
        return [c.args[0] for c in screen.ids["corpus_stats_rows"].add_widget.call_args_list]

    def test_widget_count_covers_hero_headings_rows_and_footnotes(
        self, screen: CorpusStatsScreen
    ) -> None:
        with (
            patch.object(corpus_stats_screen_module, "compute_static_stats", return_value=_STATS),
            patch.object(corpus_stats_screen_module, "threading"),
        ):
            screen.on_is_visible(None, visible=True)

        # 1 hero band + per section: 1 heading + N rows + optional footnote + 1 gap.
        # Section 1: 1 + 1 + 0 + 1 = 3. Section 2: 1 + 2 + 1 + 1 = 5.
        assert len(self._widgets(screen)) == 1 + 3 + 5

    def test_headings_are_upper_cased(self, screen: CorpusStatsScreen) -> None:
        heading = screen._make_heading("The Corpus")
        assert heading.text == "[b]THE CORPUS[/b]"

    def test_footnote_is_italicised(self, screen: CorpusStatsScreen) -> None:
        footnote = screen._make_footnote("From 564 of 947 records.")
        assert footnote.text == "[i]From 564 of 947 records.[/i]"

    def test_row_has_a_label_cell_and_a_value_cell(self, screen: CorpusStatsScreen) -> None:
        row = screen._make_row("Stories", "683", 0)
        assert len(row.children) == 2

    def test_value_cell_is_bold_and_right_aligned(self, screen: CorpusStatsScreen) -> None:
        cell = screen._make_cell("683", _COLOR, "right", bold=True)
        assert cell.text == "[b]683[/b]"
        assert cell.halign == "right"

    def test_label_cell_is_plain_and_left_aligned(self, screen: CorpusStatsScreen) -> None:
        cell = screen._make_cell("Stories", _COLOR, "left", bold=False)
        assert cell.text == "Stories"
        assert cell.halign == "left"


class TestBackgroundTextScan:
    def test_section_is_appended_when_the_scan_lands(self, screen: CorpusStatsScreen) -> None:
        with (
            patch.object(corpus_stats_screen_module, "compute_static_stats", return_value=_STATS),
            patch.object(corpus_stats_screen_module, "threading"),
        ):
            screen.on_is_visible(None, visible=True)

        with (
            patch.object(
                corpus_stats_screen_module, "compute_text_stats", return_value=_TEXT_SECTION
            ),
            patch.object(corpus_stats_screen_module, "Clock") as mock_clock,
        ):
            screen._scan_text_stats()
            # The rebuild is marshalled back onto the UI thread, not done here.
            assert screen._text_section is None
            mock_clock.schedule_once.call_args.args[0](0)

        assert screen._text_section is _TEXT_SECTION

    def test_no_index_leaves_the_page_alone(self, screen: CorpusStatsScreen) -> None:
        with (
            patch.object(corpus_stats_screen_module, "compute_text_stats", return_value=None),
            patch.object(corpus_stats_screen_module, "Clock") as mock_clock,
        ):
            screen._scan_text_stats()

        assert screen._text_section is None
        mock_clock.schedule_once.assert_not_called()

    def test_a_failing_scan_does_not_escape_the_thread(self, screen: CorpusStatsScreen) -> None:
        with (
            patch.object(
                corpus_stats_screen_module, "compute_text_stats", side_effect=RuntimeError("boom")
            ),
            patch.object(corpus_stats_screen_module, "Clock") as mock_clock,
        ):
            screen._scan_text_stats()

        assert screen._text_section is None
        mock_clock.schedule_once.assert_not_called()

    def test_scan_starts_only_once(self, screen: CorpusStatsScreen) -> None:
        with patch.object(corpus_stats_screen_module, "threading") as mock_threading:
            screen._start_text_scan()
            screen._start_text_scan()
        assert mock_threading.Thread.call_count == 1


class TestKeyboardNavigation:
    """The page must be drivable with only the remote's six keys."""

    def test_keys_ignored_until_focused(self, screen: CorpusStatsScreen) -> None:
        assert screen.handle_key(corpus_stats_screen_module.KEY_DOWN) is False

    def test_down_scrolls_towards_the_bottom(self, screen: CorpusStatsScreen) -> None:
        screen.enter_nav_focus(MagicMock())
        screen.ids["corpus_stats_scroll"].scroll_y = 1.0
        assert screen.handle_key(corpus_stats_screen_module.KEY_DOWN) is True
        assert screen.ids["corpus_stats_scroll"].scroll_y == pytest.approx(0.92)

    def test_up_scrolls_towards_the_top(self, screen: CorpusStatsScreen) -> None:
        screen.enter_nav_focus(MagicMock())
        screen.ids["corpus_stats_scroll"].scroll_y = 0.5
        assert screen.handle_key(corpus_stats_screen_module.KEY_UP) is True
        assert screen.ids["corpus_stats_scroll"].scroll_y == pytest.approx(0.58)

    def test_scroll_is_clamped_at_the_ends(self, screen: CorpusStatsScreen) -> None:
        screen.enter_nav_focus(MagicMock())
        screen.ids["corpus_stats_scroll"].scroll_y = 1.0
        screen.handle_key(corpus_stats_screen_module.KEY_UP)
        assert screen.ids["corpus_stats_scroll"].scroll_y == 1.0

        screen.ids["corpus_stats_scroll"].scroll_y = 0.0
        screen.handle_key(corpus_stats_screen_module.KEY_DOWN)
        assert screen.ids["corpus_stats_scroll"].scroll_y == 0.0

    @pytest.mark.parametrize("key", [KEY_ESCAPE, KEY_LEFT], ids=["escape", "left"])
    def test_escape_and_left_hand_focus_back(self, screen: CorpusStatsScreen, key: int) -> None:
        on_exit = MagicMock()
        screen.enter_nav_focus(on_exit)
        assert screen.handle_key(key) is True
        on_exit.assert_called_once()

    def test_unhandled_key_is_not_consumed(self, screen: CorpusStatsScreen) -> None:
        screen.enter_nav_focus(MagicMock())
        assert screen.handle_key(ord("q")) is False

    def test_exit_clears_focus(self, screen: CorpusStatsScreen) -> None:
        screen.enter_nav_focus(MagicMock())
        screen.exit_nav_focus()
        assert screen.handle_key(corpus_stats_screen_module.KEY_DOWN) is False
