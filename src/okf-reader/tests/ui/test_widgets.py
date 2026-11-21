# ruff: noqa: SLF001
# cspell:ignore pytestmark
"""The viewer's own widgets: a link found under a point, and the table that builds lazily."""

from __future__ import annotations

import gc
import weakref
from unittest.mock import MagicMock, patch

import pytest
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from okf_reader.ui import widgets
from okf_reader.ui.widgets import LAZY_TABLE_MARGIN, TABLE_FONT_NAME, LazyTable
from viewer_test_helpers import LONG_TABLE_ROWS, NEEDS_A_WINDOW, eager_heights

pytestmark = NEEDS_A_WINDOW


class TestRefUnder:
    """The hit test behind the hand cursor: which of a label's links is under a point."""

    @pytest.fixture
    def label(self) -> Label:
        lbl = Label(size=(200, 40), pos=(0, 0))
        lbl.texture_size = (100, 20)  # centred: spans x 50..150, y 10..30
        lbl.refs = {"here": [(0, 0, 50, 20)], "there": [(50, 0, 100, 20)]}
        return lbl

    def test_each_link_by_where_the_point_is(self, label: Label) -> None:
        assert widgets.ref_under(label, 60, 20) == "here"
        assert widgets.ref_under(label, 140, 20) == "there"

    def test_outside_the_label_is_no_link(self, label: Label) -> None:
        assert widgets.ref_under(label, 500, 20) is None

    def test_inside_the_label_but_off_its_text_is_no_link(self, label: Label) -> None:
        assert widgets.ref_under(label, 10, 20) is None


class TestLazyTable:
    """A long, link-free table builds Labels only for the rows near the viewport."""

    FONT_SIZE = 13

    @pytest.fixture
    def viewport(self) -> ScrollView:
        return ScrollView(size_hint=(None, None), size=(400, 300), pos=(0, 0))

    @pytest.fixture
    def table(self, viewport: ScrollView) -> LazyTable:
        table = LazyTable(LONG_TABLE_ROWS, self.FONT_SIZE, viewport)
        table.y = viewport.top - table.height  # the table's top at the viewport's top
        table._update()
        return table

    def test_it_takes_the_eager_tables_size_at_once(self, table: LazyTable) -> None:
        heights = eager_heights(LONG_TABLE_ROWS, self.FONT_SIZE)
        assert table.height == sum(heights)
        widths = []
        for row in LONG_TABLE_ROWS:
            lbl = Label(text=row, markup=True, font_name=TABLE_FONT_NAME, font_size=self.FONT_SIZE)
            lbl.texture_update()
            widths.append(lbl.texture_size[0])
        assert table.width == max(widths)

    def test_only_the_rows_near_the_viewport_are_built(
        self, table: LazyTable, viewport: ScrollView
    ) -> None:
        heights = eager_heights(LONG_TABLE_ROWS, self.FONT_SIZE)
        reach = viewport.height * (1 + LAZY_TABLE_MARGIN)
        expected = next(i for i in range(len(heights)) if sum(heights[:i]) >= reach)
        assert table.built_rows == list(range(expected))
        assert len(table.children) == expected < len(LONG_TABLE_ROWS)

    def test_each_built_row_sits_where_the_eager_table_puts_it(self, table: LazyTable) -> None:
        heights = eager_heights(LONG_TABLE_ROWS, self.FONT_SIZE)
        for index in table.built_rows[:20]:
            label = table._built[index]
            assert label.top == table.height - sum(heights[:index])
            assert label.size == label.texture_size

    def test_a_second_look_from_the_same_place_keeps_the_rows_it_has(
        self, table: LazyTable
    ) -> None:
        built = dict(table._built)
        table._update()
        assert table._built == built
        assert all(table._built[i] is label for i, label in built.items())

    def test_scrolling_to_the_end_builds_the_last_rows_and_reuses_labels(
        self, table: LazyTable, viewport: ScrollView
    ) -> None:
        labels_before = set(table.children)  # the labels, kept: a freed one's id is reused
        table.y = viewport.y  # the table's bottom at the viewport's bottom
        table._update()
        assert table.built_rows[-1] == len(LONG_TABLE_ROWS) - 1
        assert 0 not in table.built_rows
        assert table.children  # some built, and
        assert set(table.children) <= labels_before  # each one reused, none new

    def test_a_row_of_another_height_than_reserved_is_logged_once(
        self, viewport: ScrollView
    ) -> None:
        table = LazyTable(LONG_TABLE_ROWS, self.FONT_SIZE, viewport)
        table._tops = [top * 2 for top in table._tops]  # every row's slot twice its height
        table.y = viewport.top - table.height
        with patch.object(widgets.trace, "lazy_row_height_differs") as logged:
            table._update()
        logged.assert_called_once()
        row, real, reserved = logged.call_args.args
        assert (row, reserved) == (0, 2 * real)

    def test_rows_of_the_reserved_height_log_nothing(self, viewport: ScrollView) -> None:
        table = LazyTable(LONG_TABLE_ROWS, self.FONT_SIZE, viewport)
        table.y = viewport.top - table.height
        with patch.object(widgets.trace, "lazy_row_height_differs") as logged:
            table._update()
        logged.assert_not_called()

    def test_the_page_scroll_view_does_not_keep_a_table_alive(self, viewport: ScrollView) -> None:
        table = weakref.ref(LazyTable(LONG_TABLE_ROWS, self.FONT_SIZE, viewport))
        gc.collect()
        assert table() is None
        viewport.scroll_y = 0.5  # its dead binding must not break the scroll view


def test_a_white_tint_leaves_an_icon_as_it_is() -> None:
    button = MagicMock()
    widgets.tint_bar_icon(button, (1.0, 1.0, 1.0, 1.0))
    button.add_widget.assert_not_called()
