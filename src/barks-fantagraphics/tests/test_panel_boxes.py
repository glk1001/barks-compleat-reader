# ruff: noqa: PLR2004, SLF001

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import barks_fantagraphics.panel_boxes as panel_boxes_module
import pytest
from barks_fantagraphics.barks_titles import Titles
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.panel_boxes import (
    PagePanelBoxes,
    PanelBox,
    TitlePanelBoxes,
    check_page_panel_boxes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_panel_box(
    panel_num: int = 1,
    x0: int = 10,
    y0: int = 20,
    x1: int = 100,
    y1: int = 200,
) -> PanelBox:
    return PanelBox(panel_num=panel_num, x0=x0, y0=y0, x1=x1, y1=y1, w=x1 - x0, h=y1 - y0)


def _make_page_panel_boxes(
    page_width: int = 800,
    page_height: int = 600,
) -> PagePanelBoxes:
    overall = _make_panel_box(0, 0, 0, page_width - 1, page_height - 1)
    return PagePanelBoxes(
        page_num="001",
        page_width=page_width,
        page_height=page_height,
        overall_bounds=overall,
        panel_boxes=[],
    )


def _make_panel_segments_json(
    width: int = 800,
    height: int = 600,
    panels: list[list[int]] | None = None,
    overall_bounds: list[int] | None = None,
) -> str:
    return json.dumps(
        {
            "size": [width, height],
            "panels": panels if panels is not None else [[10, 20, 90, 180]],
            "overall_bounds": overall_bounds if overall_bounds is not None else [0, 0, 799, 599],
        }
    )


# ---------------------------------------------------------------------------
# PanelBox
# ---------------------------------------------------------------------------


class TestPanelBox:
    def test_box_property_returns_coords(self) -> None:
        pb = PanelBox(panel_num=1, x0=10, y0=20, x1=100, y1=200, w=90, h=180)
        assert pb.box == (10, 20, 100, 200)

    def test_box_property_uses_stored_coords(self) -> None:
        pb = PanelBox(panel_num=3, x0=5, y0=15, x1=50, y1=150, w=45, h=135)
        assert pb.box == (5, 15, 50, 150)

    def test_is_frozen(self) -> None:
        pb = PanelBox(panel_num=1, x0=0, y0=0, x1=10, y1=10, w=10, h=10)
        with pytest.raises((AttributeError, TypeError)):
            pb.x0 = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TitlePanelBoxes._get_panel_box
# ---------------------------------------------------------------------------


class TestGetPanelBox:
    def test_converts_ocr_box_format(self) -> None:
        # OCR box format: [x0, y0, width, height]
        result = TitlePanelBoxes._get_panel_box(1, [10, 20, 90, 180])

        assert result.panel_num == 1
        assert result.x0 == 10
        assert result.y0 == 20
        assert result.w == 90
        assert result.h == 180
        assert result.x1 == 10 + 90 - 1  # x0 + w - 1
        assert result.y1 == 20 + 180 - 1  # y0 + h - 1

    def test_panel_num_assigned_correctly(self) -> None:
        result = TitlePanelBoxes._get_panel_box(5, [0, 0, 100, 100])
        assert result.panel_num == 5


# ---------------------------------------------------------------------------
# TitlePanelBoxes._get_overall_bounds_box
# ---------------------------------------------------------------------------


class TestGetOverallBoundsBox:
    def test_converts_bounds_format(self) -> None:
        # Overall bounds format: [x0, y0, x1, y1]
        result = TitlePanelBoxes._get_overall_bounds_box(0, [0, 0, 799, 599])

        assert result.panel_num == 0
        assert result.x0 == 0
        assert result.y0 == 0
        assert result.x1 == 799
        assert result.y1 == 599
        assert result.w == 799 - 0 + 1  # x1 - x0 + 1
        assert result.h == 599 - 0 + 1  # y1 - y0 + 1

    def test_non_zero_origin(self) -> None:
        result = TitlePanelBoxes._get_overall_bounds_box(0, [10, 20, 110, 220])

        assert result.x0 == 10
        assert result.y0 == 20
        assert result.x1 == 110
        assert result.y1 == 220
        assert result.w == 101  # 110 - 10 + 1
        assert result.h == 201  # 220 - 20 + 1


# ---------------------------------------------------------------------------
# TitlePanelBoxes.get_panel_boxes
# ---------------------------------------------------------------------------


class TestGetPanelBoxes:
    def _make_tpb(self) -> TitlePanelBoxes:
        return TitlePanelBoxes(_comics_database=MagicMock())

    def test_raises_when_file_not_found(self, tmp_path: pytest.TempPathFactory) -> None:
        tpb = self._make_tpb()
        missing = tmp_path / "nonexistent.json"  # type: ignore[operator]

        with pytest.raises(FileNotFoundError, match="panel segments file"):
            tpb.get_panel_boxes(missing, "001")

    def test_parses_size_correctly(self, tmp_path: pytest.TempPathFactory) -> None:
        tpb = self._make_tpb()
        f = tmp_path / "panels.json"  # type: ignore[operator]
        f.write_text(_make_panel_segments_json(width=1024, height=768))

        result = tpb.get_panel_boxes(f, "001")

        assert result.page_width == 1024
        assert result.page_height == 768
        assert result.page_num == "001"

    def test_parses_single_panel(self, tmp_path: pytest.TempPathFactory) -> None:
        tpb = self._make_tpb()
        f = tmp_path / "panels.json"  # type: ignore[operator]
        f.write_text(_make_panel_segments_json(panels=[[5, 10, 80, 160]]))

        result = tpb.get_panel_boxes(f, "002")

        assert len(result.panel_boxes) == 1
        pb = result.panel_boxes[0]
        assert pb.panel_num == 1
        assert pb.x0 == 5
        assert pb.y0 == 10
        assert pb.w == 80
        assert pb.h == 160
        assert pb.x1 == 5 + 80 - 1
        assert pb.y1 == 10 + 160 - 1

    def test_parses_multiple_panels_in_order(self, tmp_path: pytest.TempPathFactory) -> None:
        tpb = self._make_tpb()
        f = tmp_path / "panels.json"  # type: ignore[operator]
        f.write_text(
            _make_panel_segments_json(panels=[[0, 0, 50, 50], [50, 50, 50, 50], [100, 100, 50, 50]])
        )

        result = tpb.get_panel_boxes(f, "003")

        assert len(result.panel_boxes) == 3
        assert result.panel_boxes[0].panel_num == 1
        assert result.panel_boxes[1].panel_num == 2
        assert result.panel_boxes[2].panel_num == 3

    def test_parses_overall_bounds(self, tmp_path: pytest.TempPathFactory) -> None:
        tpb = self._make_tpb()
        f = tmp_path / "panels.json"  # type: ignore[operator]
        f.write_text(_make_panel_segments_json(overall_bounds=[5, 10, 795, 590]))

        result = tpb.get_panel_boxes(f, "001")

        ob = result.overall_bounds
        assert ob.panel_num == 0
        assert ob.x0 == 5
        assert ob.y0 == 10
        assert ob.x1 == 795
        assert ob.y1 == 590

    def test_empty_panels_list(self, tmp_path: pytest.TempPathFactory) -> None:
        tpb = self._make_tpb()
        f = tmp_path / "panels.json"  # type: ignore[operator]
        f.write_text(_make_panel_segments_json(panels=[]))

        result = tpb.get_panel_boxes(f, "001")

        assert result.panel_boxes == []


# ---------------------------------------------------------------------------
# TitlePanelBoxes._get_srce_page_nums
# ---------------------------------------------------------------------------


class TestGetSrcePageNums:
    def test_returns_restorable_pages_only(self) -> None:
        body_page = MagicMock(page_num=1, page_type=PageType.BODY)
        cover_page = MagicMock(page_num=2, page_type=PageType.COVER)
        front_page = MagicMock(page_num=3, page_type=PageType.FRONT_MATTER)
        back_page = MagicMock(page_num=4, page_type=PageType.BACK_MATTER)

        srce_dest = MagicMock()
        srce_dest.srce_pages = [body_page, cover_page, front_page, back_page]

        comic = MagicMock()
        with patch.object(
            panel_boxes_module, "get_sorted_srce_and_dest_pages", return_value=srce_dest
        ):
            result = TitlePanelBoxes._get_srce_page_nums(comic)

        # COVER is not in RESTORABLE_PAGE_TYPES; BODY, FRONT_MATTER, BACK_MATTER are
        assert result == ["001", "003", "004"]

    def test_empty_srce_pages(self) -> None:
        srce_dest = MagicMock()
        srce_dest.srce_pages = []

        comic = MagicMock()
        with patch.object(
            panel_boxes_module, "get_sorted_srce_and_dest_pages", return_value=srce_dest
        ):
            result = TitlePanelBoxes._get_srce_page_nums(comic)

        assert result == []

    def test_page_num_formatted_with_leading_zeros(self) -> None:
        page = MagicMock(page_num=5, page_type=PageType.BODY)
        srce_dest = MagicMock()
        srce_dest.srce_pages = [page]

        comic = MagicMock()
        with patch.object(
            panel_boxes_module, "get_sorted_srce_and_dest_pages", return_value=srce_dest
        ):
            result = TitlePanelBoxes._get_srce_page_nums(comic)

        assert result == ["005"]


# ---------------------------------------------------------------------------
# TitlePanelBoxes._get_panel_boxes
# ---------------------------------------------------------------------------


class TestPrivateGetPanelBoxes:
    def test_delegates_to_get_panel_boxes(self, tmp_path: pytest.TempPathFactory) -> None:
        db = MagicMock()
        tpb = TitlePanelBoxes(_comics_database=db)

        panel_file = tmp_path / "001.json"  # type: ignore[operator]
        panel_file.write_text(_make_panel_segments_json())

        comic = MagicMock()
        comic.get_srce_panel_segments_file.return_value = panel_file

        result = tpb._get_panel_boxes(comic, "001")

        comic.get_srce_panel_segments_file.assert_called_once_with("001")
        assert isinstance(result, PagePanelBoxes)
        assert result.page_num == "001"


# ---------------------------------------------------------------------------
# TitlePanelBoxes.get_page_panel_boxes
# ---------------------------------------------------------------------------


class TestGetPagePanelBoxes:
    def test_returns_title_pages_panel_boxes(self, tmp_path: pytest.TempPathFactory) -> None:
        db = MagicMock()
        db.get_fanta_volume_int.return_value = 3

        panel_file = tmp_path / "001.json"  # type: ignore[operator]
        panel_file.write_text(_make_panel_segments_json())

        comic = MagicMock()
        comic.get_srce_panel_segments_file.return_value = panel_file
        db.get_comic_book.return_value = comic

        body_page = MagicMock(page_num=1, page_type=PageType.BODY)
        srce_dest = MagicMock()
        srce_dest.srce_pages = [body_page]

        tpb = TitlePanelBoxes(_comics_database=db)
        title = Titles.DONALD_DUCK_FINDS_PIRATE_GOLD

        with patch.object(
            panel_boxes_module, "get_sorted_srce_and_dest_pages", return_value=srce_dest
        ):
            result = tpb.get_page_panel_boxes(title)

        assert result.title == title
        assert result.volume == 3
        assert "001" in result.pages
        assert isinstance(result.pages["001"], PagePanelBoxes)


# ---------------------------------------------------------------------------
# check_page_panel_boxes
# ---------------------------------------------------------------------------


class TestCheckPagePanelBoxes:
    def test_matching_dimensions_no_error(self) -> None:
        ppb = _make_page_panel_boxes(page_width=800, page_height=600)
        check_page_panel_boxes((800, 600), ppb)  # should not raise

    def test_width_mismatch_raises(self) -> None:
        ppb = _make_page_panel_boxes(page_width=800, page_height=600)
        with pytest.raises(RuntimeError, match="width"):
            check_page_panel_boxes((900, 600), ppb)

    def test_height_mismatch_raises(self) -> None:
        ppb = _make_page_panel_boxes(page_width=800, page_height=600)
        with pytest.raises(RuntimeError, match="height"):
            check_page_panel_boxes((800, 700), ppb)

    def test_both_mismatch_raises_on_width_first(self) -> None:
        ppb = _make_page_panel_boxes(page_width=800, page_height=600)
        with pytest.raises(RuntimeError, match="width"):
            check_page_panel_boxes((900, 700), ppb)
