# ruff: noqa: PLR2004, B008

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import barks_fantagraphics.panel_bounding as panel_bounding_module
import pytest
from barks_fantagraphics.comics_consts import (
    DEST_TARGET_HEIGHT,
    DEST_TARGET_WIDTH,
    DEST_TARGET_X_MARGIN,
    PANELS_BBOX_HEIGHT_SIMILARITY_MARGIN,
    PageType,
)
from barks_fantagraphics.page_classes import (
    CleanPage,
    ComicDimensions,
    RequiredDimensions,
    SrceAndDestPages,
)
from barks_fantagraphics.panel_bounding import (
    get_required_panels_bbox_width_height,
    get_scaled_panels_bbox_height,
    set_dest_panel_bounding_boxes,
    set_srce_panel_bounding_boxes,
)
from barks_fantagraphics.panel_bounding_boxes import BoundingBox, get_panels_bounding_box_from_file

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_WIDTH = DEST_TARGET_WIDTH - (2 * DEST_TARGET_X_MARGIN)  # 1920


def _body_page(
    filename: str = "001.jpg", bbox: BoundingBox = BoundingBox(0, 0, 999, 1499)
) -> CleanPage:
    page = CleanPage(filename, PageType.BODY)
    page.panels_bbox = bbox
    return page


def _front_page(filename: str = "front.jpg") -> CleanPage:
    return CleanPage(filename, PageType.FRONT)


def _make_srce_dim(
    av_w: int = 1000,
    av_h: int = 1500,
    min_w: int = 900,
    max_w: int = 1100,
    min_h: int = 1400,
    max_h: int = 1600,
) -> ComicDimensions:
    return ComicDimensions(min_w, max_w, min_h, max_h, av_w, av_h)


def _make_required_dim(w: int = REQUIRED_WIDTH, h: int = 2880, y: int = 50) -> RequiredDimensions:
    return RequiredDimensions(w, h, y)


def _make_panel_segments_json(overall_bounds: list[int] | None = None) -> str:
    return json.dumps({"overall_bounds": overall_bounds or [10, 20, 800, 1400]})


# ---------------------------------------------------------------------------
# BoundingBox
# ---------------------------------------------------------------------------


class TestBoundingBox:
    def test_get_box(self) -> None:
        bb = BoundingBox(10, 20, 100, 200)
        assert bb.get_box() == (10, 20, 100, 200)

    def test_get_width(self) -> None:
        bb = BoundingBox(10, 0, 109, 0)
        assert bb.get_width() == 100  # (109 - 10) + 1

    def test_get_height(self) -> None:
        bb = BoundingBox(0, 20, 0, 219)
        assert bb.get_height() == 200  # (219 - 20) + 1

    def test_default_values(self) -> None:
        bb = BoundingBox()
        assert bb.x_min == -1
        assert bb.y_min == -1
        assert bb.x_max == -1
        assert bb.y_max == -1

    def test_is_frozen(self) -> None:
        bb = BoundingBox(0, 0, 10, 10)
        # noinspection PyTypeChecker
        with pytest.raises((AttributeError, TypeError)):
            # noinspection PyDataclass
            bb.x_min = 99  # ty: ignore[invalid-assignment]


# ---------------------------------------------------------------------------
# get_panels_bounding_box_from_file
# ---------------------------------------------------------------------------


class TestGetPanelsBoundingBoxFromFile:
    def test_reads_overall_bounds(self, tmp_path: Path) -> None:
        f = tmp_path / "segments.json"  # type: ignore[operator]
        f.write_text(_make_panel_segments_json([5, 10, 800, 1400]))

        result = get_panels_bounding_box_from_file(f)  # type: ignore[arg-type]

        assert result.x_min == 5
        assert result.y_min == 10
        assert result.x_max == 800
        assert result.y_max == 1400


# ---------------------------------------------------------------------------
# get_scaled_panels_bbox_height
# ---------------------------------------------------------------------------


class TestGetScaledPanelsBboxHeight:
    def test_basic_scaling(self) -> None:
        # If width doubles, height doubles
        result = get_scaled_panels_bbox_height(
            scaled_panels_bbox_width=2000,
            panels_bbox_width=1000,
            panels_bbox_height=1500,
        )
        assert result == 3000

    def test_identity_scaling(self) -> None:
        result = get_scaled_panels_bbox_height(1000, 1000, 1500)
        assert result == 1500

    def test_rounds_result(self) -> None:
        # 1500 * 1001 / 1000 = 1501.5 → rounds to 1502
        result = get_scaled_panels_bbox_height(1001, 1000, 1500)
        assert result == 1502


# ---------------------------------------------------------------------------
# _get_min_max helpers (tested indirectly via get_required_panels_bbox_width_height)
# ---------------------------------------------------------------------------


class TestGetRequiredPanelsBboxWidthHeight:
    def test_returns_comic_and_required_dimensions(self) -> None:
        pages = [_body_page(bbox=BoundingBox(0, 0, 999, 1499))]
        srce_dim, required_dim = get_required_panels_bbox_width_height(pages, 3200, 20)

        assert isinstance(srce_dim, ComicDimensions)
        assert isinstance(required_dim, RequiredDimensions)

    def test_min_max_computed_correctly(self) -> None:
        pages = [
            _body_page("a.jpg", BoundingBox(0, 0, 799, 1199)),  # w=800, h=1200
            _body_page("b.jpg", BoundingBox(0, 0, 999, 1499)),  # w=1000, h=1500
        ]
        srce_dim, _ = get_required_panels_bbox_width_height(pages, 3200, 20)

        assert srce_dim.min_panels_bbox_width == 800
        assert srce_dim.max_panels_bbox_width == 1000

    def test_required_width_uses_target_minus_margins(self) -> None:
        pages = [_body_page(bbox=BoundingBox(0, 0, 999, 1499))]
        _, required_dim = get_required_panels_bbox_width_height(pages, 3200, 20)

        assert required_dim.panels_bbox_width == REQUIRED_WIDTH

    def test_pages_without_panels_skipped(self) -> None:
        pages = [
            _front_page(),
            _body_page(bbox=BoundingBox(0, 0, 999, 1499)),
        ]
        srce_dim, _ = get_required_panels_bbox_width_height(pages, 3200, 20)

        # Only the body page contributes
        assert srce_dim.max_panels_bbox_width == 1000


# ---------------------------------------------------------------------------
# set_srce_panel_bounding_boxes
# ---------------------------------------------------------------------------


class TestSetSrcePanelBoundingBoxes:
    def test_sets_bbox_from_file(self, tmp_path: Path) -> None:
        f = tmp_path / "001.json"  # type: ignore[operator]
        f.write_text(_make_panel_segments_json([5, 10, 800, 1400]))

        page = _body_page()
        set_srce_panel_bounding_boxes([page], [f], check_srce_page_timestamps=False)  # type: ignore[list-item]

        assert page.panels_bbox.x_min == 5
        assert page.panels_bbox.y_min == 10
        assert page.panels_bbox.x_max == 800
        assert page.panels_bbox.y_max == 1400

    def test_skips_pages_without_panels(self, tmp_path: Path) -> None:
        page = _front_page()
        missing = tmp_path / "nonexistent.json"  # type: ignore[operator]
        # Should not raise even though file is missing — FRONT pages are skipped
        set_srce_panel_bounding_boxes([page], [missing], check_srce_page_timestamps=False)  # type: ignore[list-item]

    def test_raises_when_segment_file_missing(self, tmp_path: Path) -> None:
        page = _body_page()
        missing = tmp_path / "nonexistent.json"  # type: ignore[operator]

        with pytest.raises(FileNotFoundError, match="panels segments info file"):
            set_srce_panel_bounding_boxes([page], [missing], check_srce_page_timestamps=False)  # type: ignore[list-item]

    def test_raises_on_stale_timestamp(self, tmp_path: Path) -> None:
        f = tmp_path / "001.json"  # type: ignore[operator]
        f.write_text(_make_panel_segments_json())
        page = _body_page()

        with (
            patch.object(panel_bounding_module, "dest_file_is_older_than_srce", return_value=True),
            pytest.raises(RuntimeError, match="older than srce"),
        ):
            set_srce_panel_bounding_boxes([page], [f], check_srce_page_timestamps=True)  # type: ignore[list-item]

    def test_no_timestamp_check_skips_stale_check(self, tmp_path: Path) -> None:
        f = tmp_path / "001.json"  # type: ignore[operator]
        f.write_text(_make_panel_segments_json())
        page = _body_page()

        with patch.object(panel_bounding_module, "dest_file_is_older_than_srce", return_value=True):
            # Should not raise because check_srce_page_timestamps=False
            set_srce_panel_bounding_boxes([page], [f], check_srce_page_timestamps=False)  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# set_dest_panel_bounding_boxes
# ---------------------------------------------------------------------------


class TestSetDestPanelBoundingBoxes:
    def test_sets_bbox_on_dest_pages(self) -> None:
        srce_page = _body_page(bbox=BoundingBox(0, 0, 999, 1499))
        dest_page = CleanPage("1-01.jpg", PageType.BODY)
        pages = SrceAndDestPages([srce_page], [dest_page])
        srce_dim = _make_srce_dim(av_w=1000, av_h=1500, max_h=1500)
        required_dim = _make_required_dim()

        set_dest_panel_bounding_boxes(srce_dim, required_dim, pages)

        bb = dest_page.panels_bbox
        assert bb.x_min >= 0
        assert bb.y_min >= 0
        assert bb.x_max > bb.x_min
        assert bb.y_max > bb.y_min

    def test_full_page_bbox_for_no_panels_page(self) -> None:
        srce_page = _front_page()
        dest_page = CleanPage("1-01.jpg", PageType.FRONT)
        pages = SrceAndDestPages([srce_page], [dest_page])
        srce_dim = _make_srce_dim()
        required_dim = _make_required_dim()

        set_dest_panel_bounding_boxes(srce_dim, required_dim, pages)

        bb = dest_page.panels_bbox
        assert bb.x_min == 0
        assert bb.y_min == 0
        assert bb.x_max == DEST_TARGET_WIDTH - 1
        assert bb.y_max == DEST_TARGET_HEIGHT - 1


# ---------------------------------------------------------------------------
# _get_dest_panels_bounding_box (tested via set_dest_panel_bounding_boxes)
# ---------------------------------------------------------------------------


class TestGetDestPanelsBoundingBox:
    def test_normal_page_uses_required_height_when_similar(self) -> None:
        # Page height == average height → use required_dim.panels_bbox_height
        av_h = 1500
        srce_page = _body_page(bbox=BoundingBox(0, 0, 999, av_h - 1))  # h = 1500
        dest_page = CleanPage("1-01.jpg", PageType.BODY)
        pages = SrceAndDestPages([srce_page], [dest_page])
        srce_dim = _make_srce_dim(av_h=av_h, max_h=av_h)
        required_dim = _make_required_dim(h=2880)

        set_dest_panel_bounding_boxes(srce_dim, required_dim, pages)

        bb = dest_page.panels_bbox
        assert bb.get_height() == 2880

    def test_short_page_uses_scaled_height(self) -> None:
        # Page height much less than average → gets its own scaled height
        av_h = 1500
        short_h = av_h - PANELS_BBOX_HEIGHT_SIMILARITY_MARGIN - 100  # well below threshold
        srce_page = _body_page(bbox=BoundingBox(0, 0, 999, short_h - 1))
        dest_page = CleanPage("1-01.jpg", PageType.BODY)
        pages = SrceAndDestPages([srce_page], [dest_page])
        srce_dim = _make_srce_dim(av_h=av_h, max_h=av_h)
        required_dim = _make_required_dim(h=2880)

        set_dest_panel_bounding_boxes(srce_dim, required_dim, pages)

        # Short page gets a different (smaller) required height
        bb = dest_page.panels_bbox
        assert bb.get_height() != 2880

    def test_dest_bbox_centered_horizontally(self) -> None:
        srce_page = _body_page(bbox=BoundingBox(0, 0, 999, 1499))
        dest_page = CleanPage("1-01.jpg", PageType.BODY)
        pages = SrceAndDestPages([srce_page], [dest_page])
        srce_dim = _make_srce_dim(av_h=1500, max_h=1500)
        required_dim = _make_required_dim()

        set_dest_panel_bounding_boxes(srce_dim, required_dim, pages)

        bb = dest_page.panels_bbox
        assert bb.x_min == DEST_TARGET_X_MARGIN
        assert bb.x_max == DEST_TARGET_X_MARGIN + REQUIRED_WIDTH - 1
