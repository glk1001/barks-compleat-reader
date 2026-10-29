"""The pages a document shows at a time on the two-page spread."""

from __future__ import annotations

import pytest
from barks_reader.core.display_unit import DisplayUnit, build_document_units


class TestBuildDocumentUnits:
    def test_the_first_page_stands_alone_then_the_rest_pair_off(self) -> None:
        units, unit_for = build_document_units(5)
        assert units == [DisplayUnit(0, None), DisplayUnit(1, 2), DisplayUnit(3, 4)]
        assert unit_for == {0: 0, 1: 1, 2: 1, 3: 2, 4: 2}

    def test_an_odd_last_page_stands_alone(self) -> None:
        units, unit_for = build_document_units(4)
        assert units == [DisplayUnit(0, None), DisplayUnit(1, 2), DisplayUnit(3, None)]
        assert units[unit_for[3]] == DisplayUnit(3, None)

    @pytest.mark.parametrize(
        ("page_count", "expected"),
        [(0, []), (1, [DisplayUnit(0, None)]), (2, [DisplayUnit(0, None), DisplayUnit(1, None)])],
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
