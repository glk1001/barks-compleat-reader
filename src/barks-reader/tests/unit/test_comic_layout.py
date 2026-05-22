from __future__ import annotations

from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.page_classes import (
    CleanPage,
    RequiredDimensions,
    SrceAndDestPages,
)
from barks_reader.core.comic_book_page_info import ComicLayout, ComicLayoutBuilder, PageInfo
from barks_reader.core.display_unit import DisplayUnit
from barks_reader.core.reader_consts_and_types import FIRST_BODY_PAGE


def _page(
    index: int,
    display_num: str,
    page_type: PageType = PageType.BODY,
    *,
    is_solo: bool = False,
) -> PageInfo:
    return PageInfo(
        page_index=index,
        display_page_num=display_num,
        page_type=page_type,
        srce_page=MagicMock(),
        dest_page=MagicMock(),
        is_solo=is_solo,
    )


def _layout(pages: list[PageInfo], last_body_page: str = "10") -> ComicLayout:
    page_map: OrderedDict[str, PageInfo] = OrderedDict((p.display_page_num, p) for p in pages)
    return ComicLayout(page_map=page_map, last_body_page=last_body_page)


class TestComicLayoutLookups:
    def test_page_by_display_and_index(self) -> None:
        p1 = _page(0, "1")
        p2 = _page(1, "2")
        layout = _layout([p1, p2])

        assert layout.page_by_display("1") is p1
        assert layout.page_by_index(1) is p2
        assert layout.page_by_index(999) is None


class TestIsInsideBody:
    def test_body_page_in_middle_is_inside(self) -> None:
        page = _page(5, "6")
        layout = _layout([page], last_body_page="10")
        assert layout.is_inside_body(page) is True

    def test_first_body_page_is_edge(self) -> None:
        page = _page(0, FIRST_BODY_PAGE)
        layout = _layout([page], last_body_page="10")
        assert layout.is_inside_body(page) is False

    def test_last_body_page_is_edge(self) -> None:
        page = _page(9, "10")
        layout = _layout([page], last_body_page="10")
        assert layout.is_inside_body(page) is False

    def test_non_body_page_is_not_inside(self) -> None:
        page = _page(0, "iii", page_type=PageType.FRONT)
        layout = _layout([page], last_body_page="10")
        assert layout.is_inside_body(page) is False


class TestDisplayUnits:
    def test_solo_pages_are_single_units(self) -> None:
        pages = [
            _page(0, "1", is_solo=True),
            _page(1, "2", is_solo=True),
        ]
        layout = _layout(pages)

        assert layout.display_units == [
            DisplayUnit(0, None),
            DisplayUnit(1, None),
        ]
        assert layout.unit_idx_for(0) == 0
        assert layout.unit_idx_for(1) == 1

    def test_non_solo_pages_pair_up(self) -> None:
        pages = [_page(i, str(i + 1)) for i in range(4)]
        layout = _layout(pages)

        assert layout.display_units == [
            DisplayUnit(0, 1),
            DisplayUnit(2, 3),
        ]
        # Both pages of a pair map to the same unit.
        assert layout.unit_idx_for(0) == 0
        assert layout.unit_idx_for(1) == 0
        assert layout.unit_idx_for(2) == 1
        assert layout.unit_idx_for(3) == 1

    def test_solo_breaks_pairing(self) -> None:
        pages = [
            _page(0, "1"),
            _page(1, "2", is_solo=True),
            _page(2, "3"),
            _page(3, "4"),
        ]
        layout = _layout(pages)

        # p0 cannot pair with solo p1, so p0 is solo; p1 is solo; p2+p3 pair.
        assert layout.display_units == [
            DisplayUnit(0, None),
            DisplayUnit(1, None),
            DisplayUnit(2, 3),
        ]

    def test_trailing_unpaired_page_is_solo(self) -> None:
        pages = [_page(0, "1"), _page(1, "2"), _page(2, "3")]
        layout = _layout(pages)

        assert layout.display_units == [DisplayUnit(0, 1), DisplayUnit(2, None)]


class TestResolveLastRead:
    def test_single_page_mode_returns_current(self) -> None:
        page_index = 4
        p5 = _page(page_index, "5")
        layout = _layout([p5], last_body_page="10")

        saved = layout.resolve_last_read("5", DisplayUnit(page_index, None), double_page_mode=False)

        assert saved.display_page_num == "5"
        assert saved.page_index == page_index
        assert saved.page_type == PageType.BODY
        assert saved.last_body_page == "10"

    def test_double_page_prefers_right(self) -> None:
        p3 = _page(2, "3")
        p4 = _page(3, "4")
        layout = _layout([p3, p4], last_body_page="10")

        saved = layout.resolve_last_read("3", DisplayUnit(2, 3), double_page_mode=True)

        # Furthest progress — right page (4).
        assert saved.display_page_num == "4"

    def test_double_page_picks_left_when_left_is_edge(self) -> None:
        # Left is last body page (edge), so pick left to let save reset to beginning.
        p_last = _page(9, "10")
        p_back = _page(10, "11", page_type=PageType.BACK_MATTER)
        layout = _layout([p_last, p_back], last_body_page="10")

        saved = layout.resolve_last_read("10", DisplayUnit(9, 10), double_page_mode=True)

        assert saved.display_page_num == "10"

    def test_double_page_solo_unit_returns_current(self) -> None:
        p1 = _page(0, "1")
        layout = _layout([p1], last_body_page="10")

        saved = layout.resolve_last_read("1", DisplayUnit(0, None), double_page_mode=True)

        assert saved.display_page_num == "1"

    def test_to_saved_sets_last_body_page(self) -> None:
        p5 = _page(4, "5")
        layout = _layout([p5], last_body_page="20")

        saved = layout.to_saved(p5)

        assert saved.last_body_page == "20"


# ------------------------------------------------------------------
# ComicLayoutBuilder + _build_page_map
# ------------------------------------------------------------------


def _srce_pages(specs: list[tuple[str, PageType]]) -> list[CleanPage]:
    return [CleanPage(page_filename=name, page_type=pt) for name, pt in specs]


def _srce_dest(
    specs: list[tuple[str, PageType]],
    dest_types: list[PageType] | None = None,
) -> SrceAndDestPages:
    """Build a SrceAndDestPages where dest types default to the same as srce types."""
    srce = _srce_pages(specs)
    if dest_types is None:
        dest = _srce_pages(specs)
    else:
        dest = [
            CleanPage(page_filename=name, page_type=dt)
            for (name, _), dt in zip(specs, dest_types, strict=True)
        ]
    return SrceAndDestPages(srce_pages=srce, dest_pages=dest)


def _comic(solo_page_keys: set[str] | None = None) -> object:
    """Minimal ComicBook stub — only solo_page_keys is read by _build_page_map."""
    return SimpleNamespace(solo_page_keys=solo_page_keys or set())


class FakeSortedPagesPort:
    def __init__(self, pages: SrceAndDestPages) -> None:
        self.pages = pages
        self.calls: list[object] = []

    def get_sorted_pages(self, comic: object) -> SrceAndDestPages:
        self.calls.append(comic)
        return self.pages


class FakeRequiredDimensionsPort:
    def __init__(self, dimensions: RequiredDimensions) -> None:
        self.dimensions = dimensions
        self.calls: list[object] = []

    def get_required_dimensions(self, comic: object) -> RequiredDimensions:
        self.calls.append(comic)
        return self.dimensions


class TestBuildPageMap:
    def test_starts_at_zero_when_first_is_front(self) -> None:
        pages = _srce_dest(
            [
                ("cover.jpg", PageType.FRONT),
                ("body1.jpg", PageType.BODY),
            ]
        )
        port = FakeSortedPagesPort(pages)
        builder = ComicLayoutBuilder(sorted_pages_port=port)

        layout = builder.build(_comic())  # ty: ignore[invalid-argument-type]

        assert "0" in layout.page_map
        assert "1" in layout.page_map
        assert layout.page_map["0"].page_type is PageType.FRONT

    def test_uses_roman_for_front_matter_then_arabic_for_body(self) -> None:
        pages = _srce_dest(
            [
                ("title.jpg", PageType.TITLE),
                ("cover.jpg", PageType.COVER),
                ("body1.jpg", PageType.BODY),
                ("body2.jpg", PageType.BODY),
            ]
        )
        port = FakeSortedPagesPort(pages)
        builder = ComicLayoutBuilder(sorted_pages_port=port)

        layout = builder.build(_comic())  # ty: ignore[invalid-argument-type]

        # No leading FRONT, so orig_page_num starts at 1 → "i" first.
        assert list(layout.page_map.keys()) == ["i", "ii", "1", "2"]

    def test_uses_arabic_when_first_page_is_body(self) -> None:
        pages = _srce_dest(
            [
                ("body1.jpg", PageType.BODY),
                ("body2.jpg", PageType.BODY),
            ]
        )
        port = FakeSortedPagesPort(pages)
        builder = ComicLayoutBuilder(sorted_pages_port=port)

        layout = builder.build(_comic())  # ty: ignore[invalid-argument-type]

        assert list(layout.page_map.keys()) == ["1", "2"]
        # No roman numerals were generated.
        assert "i" not in layout.page_map

    def test_tracks_last_body_page_excluding_back_matter(self) -> None:
        pages = _srce_dest(
            [
                ("body1.jpg", PageType.BODY),
                ("body2.jpg", PageType.BODY),
                ("back.jpg", PageType.BACK_MATTER),
            ]
        )
        port = FakeSortedPagesPort(pages)
        builder = ComicLayoutBuilder(sorted_pages_port=port)

        layout = builder.build(_comic())  # ty: ignore[invalid-argument-type]

        # last_body_page is the last page with type BODY, not the back-matter page.
        assert layout.last_body_page == "2"

    def test_marks_solo_for_solo_page_types(self) -> None:
        # BACK_MATTER is in SOLO_PAGE_TYPES but not in FRONT_MATTER_PAGES.
        pages = _srce_dest(
            [
                ("body1.jpg", PageType.BODY),
                ("back.jpg", PageType.BACK_MATTER),
            ]
        )
        port = FakeSortedPagesPort(pages)
        builder = ComicLayoutBuilder(sorted_pages_port=port)

        layout = builder.build(_comic())  # ty: ignore[invalid-argument-type]

        # "1" is BODY (not in SOLO_PAGE_TYPES), "2" is BACK_MATTER (in SOLO_PAGE_TYPES).
        assert layout.page_map["1"].is_solo is False
        assert layout.page_map["2"].is_solo is True

    def test_marks_solo_for_comic_solo_keys(self) -> None:
        pages = _srce_dest(
            [
                ("special.jpg", PageType.BODY),
                ("ordinary.jpg", PageType.BODY),
            ]
        )
        port = FakeSortedPagesPort(pages)
        builder = ComicLayoutBuilder(sorted_pages_port=port)

        layout = builder.build(_comic(solo_page_keys={"special"}))  # ty: ignore[invalid-argument-type]

        assert layout.page_map["1"].is_solo is True
        assert layout.page_map["2"].is_solo is False


class TestComicLayoutBuilder:
    def test_build_delegates_to_sorted_pages_port(self) -> None:
        pages = _srce_dest([("p.jpg", PageType.BODY)])
        port = FakeSortedPagesPort(pages)
        builder = ComicLayoutBuilder(sorted_pages_port=port)
        comic = _comic()

        builder.build(comic)  # ty: ignore[invalid-argument-type]

        assert port.calls == [comic]

    def test_get_required_dimensions_raises_when_port_missing(self) -> None:
        port = FakeSortedPagesPort(_srce_dest([("p.jpg", PageType.BODY)]))
        builder = ComicLayoutBuilder(sorted_pages_port=port, required_dimensions_port=None)

        with pytest.raises(RuntimeError, match="RequiredDimensionsPort was not wired"):
            builder.get_required_dimensions(MagicMock())

    def test_get_required_dimensions_delegates_to_port(self) -> None:
        dims = RequiredDimensions(panels_bbox_width=100, panels_bbox_height=200)
        srce_port = FakeSortedPagesPort(_srce_dest([("p.jpg", PageType.BODY)]))
        dims_port = FakeRequiredDimensionsPort(dims)
        builder = ComicLayoutBuilder(
            sorted_pages_port=srce_port,
            required_dimensions_port=dims_port,
        )
        comic = _comic()

        result = builder.get_required_dimensions(comic)  # ty: ignore[invalid-argument-type]

        assert result is dims
        assert dims_port.calls == [comic]
