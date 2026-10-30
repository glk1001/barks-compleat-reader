"""The pages a comic or a document shows at a time: solo, or a pair."""

from __future__ import annotations

from collections import OrderedDict
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_reader.core.comic_book_page_info import PageInfo
from barks_reader.core.display_unit import DisplayUnit, build_display_units, build_document_units


def _page_map(page_count: int, solo: tuple[int, ...] = ()) -> OrderedDict[str, PageInfo]:
    """Draw a comic's pages, the ones at `solo` solo; the page images are stand-ins."""
    pages: OrderedDict[str, PageInfo] = OrderedDict()
    for index in range(page_count):
        pages[str(index + 1)] = PageInfo(
            page_index=index,
            display_page_num=str(index + 1),
            page_type=PageType.BODY,
            srce_page=MagicMock(),
            dest_page=MagicMock(),
            is_solo=index in solo,
        )
    return pages


class TestBuildDisplayUnits:
    def test_the_pages_pair_off_in_reading_order(self) -> None:
        units, unit_for = build_display_units(_page_map(4))
        assert units == [DisplayUnit(0, 1), DisplayUnit(2, 3)]
        assert unit_for == {0: 0, 1: 0, 2: 1, 3: 1}

    def test_a_solo_page_stands_alone_and_so_does_the_page_before_it(self) -> None:
        units, unit_for = build_display_units(_page_map(4, solo=(1,)))
        assert units == [DisplayUnit(0, None), DisplayUnit(1, None), DisplayUnit(2, 3)]
        assert unit_for == {0: 0, 1: 1, 2: 2, 3: 2}

    def test_the_last_page_stands_alone_when_odd(self) -> None:
        units, unit_for = build_display_units(_page_map(3))
        assert units == [DisplayUnit(0, 1), DisplayUnit(2, None)]
        assert units[unit_for[2]] == DisplayUnit(2, None)

    def test_no_pages_make_no_units(self) -> None:
        assert build_display_units(_page_map(0)) == ([], {})


class TestBuildDocumentUnits:
    def test_the_pages_pair_off_from_the_first(self) -> None:
        """A document has no cover: its first page is the left of the first pair."""
        units, unit_for = build_document_units(4)
        assert units == [DisplayUnit(0, 1), DisplayUnit(2, 3)]
        assert unit_for == {0: 0, 1: 0, 2: 1, 3: 1}

    def test_an_odd_last_page_stands_alone(self) -> None:
        units, unit_for = build_document_units(5)
        assert units == [DisplayUnit(0, 1), DisplayUnit(2, 3), DisplayUnit(4, None)]
        assert unit_for == {0: 0, 1: 0, 2: 1, 3: 1, 4: 2}

    @pytest.mark.parametrize(
        ("page_count", "expected"),
        [(0, []), (1, [DisplayUnit(0, None)]), (2, [DisplayUnit(0, 1)])],
    )
    def test_the_short_documents(self, page_count: int, expected: list[DisplayUnit]) -> None:
        units, unit_for = build_document_units(page_count)
        assert units == expected
        assert sorted(unit_for) == list(range(page_count))

    def test_every_page_is_in_exactly_one_unit(self) -> None:
        units, unit_for = build_document_units(13)
        shown = [i for unit in units for i in (unit.left_page_index, unit.right_page_index)]
        assert sorted(i for i in shown if i is not None) == list(range(13))
        for index, unit_idx in unit_for.items():
            assert index in (units[unit_idx].left_page_index, units[unit_idx].right_page_index)
