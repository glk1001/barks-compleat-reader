"""Tests for the "By the Numbers" page metrics.

The page cannot scroll, so "does it all fit" is a correctness property rather than
a matter of taste. These tests are the guard: if someone adds a row or lengthens a
label later, they fail here instead of the page silently clipping in front of a
reader.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal
from unittest.mock import patch

import pytest
from barks_fantagraphics.search_ports import CorpusTextTotals
from barks_fantagraphics.testing.fake_search import InMemoryFullTextSearch
from barks_reader.core import corpus_stats as corpus_stats_module
from barks_reader.core import corpus_stats_layout as layout
from barks_reader.core.corpus_stats import (
    TEXT_SECTION_SHAPE,
    SectionShape,
    StatRow,
    StatSection,
    compute_static_stats,
    compute_text_stats,
)
from barks_reader.core.reader_utils import COMIC_PAGE_ASPECT_RATIO

# The page box is as tall as the comic-page aspect ratio makes it.
if TYPE_CHECKING:
    from pathlib import Path

_PAGE_HEIGHT = layout.REFERENCE_PAGE_WIDTH * COMIC_PAGE_ASPECT_RATIO


@pytest.fixture
def text_section(tmp_path: Path) -> StatSection:
    """Build the dialogue section the way `compute_text_stats` does, off a fake index."""
    fake = InMemoryFullTextSearch(corpus_text_totals=CorpusTextTotals(1, 2, 3, 4, 5))
    with patch.object(corpus_stats_module, "ComicSearch", return_value=fake):
        section = compute_text_stats(tmp_path)
    assert section is not None
    return section


def _columns_scope(fixture_name: str, config: pytest.Config) -> Literal["module", "function"]:  # noqa: ARG001
    """Once per module normally; once per test under mutmut (see test_corpus_stats)."""
    return "function" if os.environ.get("MUTANT_UNDER_TEST") else "module"


@pytest.fixture(scope=_columns_scope)
def columns(cpi_db: Path) -> tuple[list[StatSection], list[StatSection]]:
    left, right = layout.split_columns(compute_static_stats(cpi_db).sections)
    return list(left), list(right)


# How far the two columns may differ before the split stops looking balanced.
_COLUMN_BALANCE_TOLERANCE = 0.1


class TestItFitsOnOnePage:
    def test_the_real_page_fits_with_the_dialogue_slot_reserved(
        self, columns: tuple[list[StatSection], list[StatSection]]
    ) -> None:
        left, right = columns
        needed = layout.content_height(left, right, layout.reserved_height(TEXT_SECTION_SHAPE))
        assert needed <= _PAGE_HEIGHT

    def test_the_real_page_fits_when_the_dialogue_scan_never_lands(
        self, columns: tuple[list[StatSection], list[StatSection]]
    ) -> None:
        left, right = columns
        assert layout.content_height(left, right) <= _PAGE_HEIGHT

    def test_the_two_columns_balance(
        self, columns: tuple[list[StatSection], list[StatSection]]
    ) -> None:
        left, right = columns
        left_h = layout.column_height(left)
        right_h = layout.column_height(right, layout.reserved_height(TEXT_SECTION_SHAPE))
        assert abs(left_h - right_h) / max(left_h, right_h) < _COLUMN_BALANCE_TOLERANCE

    def test_an_overfull_page_is_reported_as_overfull(self) -> None:
        # The guard has to be able to fail, or it is guarding nothing.
        huge = StatSection(
            heading="Too much", rows=tuple(StatRow(f"Row {i}", "1") for i in range(60))
        )
        assert layout.content_height([huge], []) > _PAGE_HEIGHT


class TestHeightsAddUp:
    """The heights are the sums the page is laid out from, so they are checked as sums.

    The fit tests above only ask whether the real page fits, which every sign
    error in these sums still satisfies (mutmut, 2026-09-23).
    """

    @staticmethod
    def _sections() -> tuple[StatSection, StatSection]:
        one_row = StatSection(heading="A", rows=(StatRow("x", "1"),))
        two_rows_and_a_footnote = StatSection(
            heading="B", rows=(StatRow("y", "2"), StatRow("z", "3")), footnote="f"
        )
        return one_row, two_rows_and_a_footnote

    def test_the_opening_is_its_four_design_parts(self) -> None:
        d = layout.DESIGN
        assert layout.opening_height() == (
            d.headline_height + d.headline_gap + d.standfirst_height + d.opening_gap
        )

    def test_a_column_is_its_sections_each_with_a_gap_then_the_reserved_slot_with_its_gap(
        self,
    ) -> None:
        a, b = self._sections()
        gap = layout.DESIGN.section_gap
        assert layout.column_height([]) == 0.0
        assert layout.column_height([a, b]) == (
            layout.section_height(a) + layout.section_height(b) + 2 * gap
        )
        assert layout.column_height([a], reserved=50.0) == (
            layout.section_height(a) + gap + 50.0 + gap
        )

    def test_the_page_is_the_opening_the_taller_column_and_the_padding(self) -> None:
        a, b = self._sections()
        padding = 2.0 * layout.PAGE_VERTICAL_PADDING_FRACTION * layout.REFERENCE_PAGE_WIDTH
        taller = max(layout.column_height([a]), layout.column_height([b], 40.0))
        assert layout.content_height([a], [b], 40.0) == layout.opening_height() + taller + padding
        assert layout.content_height([], []) == layout.opening_height() + padding

    def test_nothing_is_reserved_unless_asked(self) -> None:
        a, b = self._sections()
        assert layout.content_height([a], [b]) == layout.content_height([a], [b], 0.0)
        assert layout.column_height([a]) == layout.column_height([a], 0.0)


class TestSectionHeights:
    def test_a_prose_row_is_taller_than_a_figure_row(self) -> None:
        figures = StatSection(heading="H", rows=(StatRow("a", "1"),))
        prose = StatSection(heading="H", rows=(StatRow("a", "A name", prose=True),))
        assert layout.section_height(prose) > layout.section_height(figures)

    def test_a_footnote_is_budgeted_at_two_lines(self) -> None:
        # A footnote that wraps must not be able to push a column past the fold.
        without = StatSection(heading="H", rows=(StatRow("a", "1"),))
        with_note = StatSection(heading="H", rows=(StatRow("a", "1"),), footnote="x")
        grew = layout.section_height(with_note) - layout.section_height(without)
        assert grew == pytest.approx(2 * layout.DESIGN.footnote_line_height)

    def test_the_reserved_slot_matches_the_section_it_stands_in_for(self) -> None:
        # What is reserved before the scan must equal what arrives after it, or the
        # page reflows - which a fixed page cannot do.
        arrived = StatSection(
            heading="The words",
            rows=tuple(StatRow(f"r{i}", "1") for i in range(TEXT_SECTION_SHAPE.num_rows)),
            footnote="a footnote",
        )
        assert layout.reserved_height(TEXT_SECTION_SHAPE) == pytest.approx(
            layout.section_height(arrived)
        )


class TestScale:
    def test_the_reference_width_scales_by_one(self) -> None:
        assert layout.scale_for(layout.REFERENCE_PAGE_WIDTH) == pytest.approx(1.0)

    def test_a_wider_page_scales_up_proportionally(self) -> None:
        assert layout.scale_for(2 * layout.REFERENCE_PAGE_WIDTH) == pytest.approx(2.0)

    def test_scale_is_floored_so_type_never_vanishes(self) -> None:
        assert layout.scale_for(1.0) == layout.MIN_SCALE

    def test_columns_split_the_page_width(self) -> None:
        width = layout.REFERENCE_PAGE_WIDTH
        two_columns = 2 * layout.column_width(width)
        padding = 2 * layout.PAGE_SIDE_PADDING_FRACTION * width
        gutter = layout.COLUMN_GUTTER_FRACTION * width
        assert two_columns + padding + gutter == pytest.approx(width)


class TestRowsFitTheColumnWidth:
    # The binding constraint is horizontal, not vertical: the longest label and its
    # value must sit side by side in one column. Measured with the real Roboto face,
    # the worst pair ("Submitted to Western" / "1942-1973", 29 characters) came to
    # 341px in a 360px column at the design body size. This character budget is the
    # cheap stand-in for that measurement - it will not catch a pathological string
    # of wide glyphs, but it does catch the realistic regression, which is someone
    # writing a label the way it reads in prose.
    _MAX_ROW_CHARS = 32

    def test_every_row_fits_its_column(self, cpi_db: Path) -> None:
        sections = list(compute_static_stats(cpi_db).sections)
        too_long = [
            (section.heading, row.label, row.value)
            for section in sections
            for row in section.rows
            if not row.prose and len(row.label) + len(row.value) > self._MAX_ROW_CHARS
        ]
        assert not too_long

    def test_the_dialogue_rows_fit_their_column(self, text_section: StatSection) -> None:
        too_long = [
            row.label
            for row in text_section.rows
            if len(row.label) + len(row.value) > self._MAX_ROW_CHARS
        ]
        assert not too_long


class TestDesignMatchesTheAppScale:
    # The page sets its own type sizes rather than reading FontManager, so nothing
    # stops the two drifting apart. These sizes sit a deliberate notch below the
    # app's equivalent roles, so pin the band rather than equality: a tweak stays
    # legal, a wholesale drift into a different scale does not.
    _MAX_DRIFT = 0.35
    _MIN_FOOTNOTE_RATIO = 0.55

    def test_design_sizes_stay_in_the_apps_ballpark(self) -> None:
        from barks_reader.ui.font_manager import LOW_RES_FONTS  # noqa: PLC0415
        from kivy.metrics import sp  # noqa: PLC0415

        one_sp = sp(1)
        for ours, theirs in (
            (layout.DESIGN.standfirst, LOW_RES_FONTS.title_info),
            (layout.DESIGN.heading, LOW_RES_FONTS.text_block_heading),
            (layout.DESIGN.footnote, LOW_RES_FONTS.about_box_fine_print),
        ):
            role = theirs / one_sp
            assert abs(ours - role) / role < self._MAX_DRIFT

    def test_the_type_hierarchy_holds(self) -> None:
        # Section headings are deliberately not the largest thing in their column -
        # they are set apart by weight and the accent colour, and sit just under the
        # body size. What must hold is the display line above and fine print below.
        assert layout.DESIGN.headline > layout.DESIGN.row > layout.DESIGN.footnote
        assert layout.DESIGN.heading < layout.DESIGN.row

    def test_the_footnote_stays_readable(self) -> None:
        # These lines carry the page's caveats. They may be fine print; they may not
        # shrink away from the body text that surrounds them. Stated as a proportion
        # rather than a pixel floor, so resizing the whole page keeps it meaningful -
        # an absolute floor would just get lowered every time it bound.
        assert layout.DESIGN.footnote / layout.DESIGN.row >= self._MIN_FOOTNOTE_RATIO


class TestTextSectionShape:
    def test_shape_matches_what_the_scan_actually_returns(self, text_section: StatSection) -> None:
        assert len(text_section.rows) == TEXT_SECTION_SHAPE.num_rows
        assert bool(text_section.footnote) == bool(TEXT_SECTION_SHAPE.footnote_lines)

    def test_shape_is_a_plain_declaration(self) -> None:
        assert SectionShape(num_rows=6, footnote_lines=2) == TEXT_SECTION_SHAPE
