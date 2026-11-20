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
    get_panels_bounding_box_from_file,
    get_required_panels_bbox_width_height,
    set_dest_panel_bounding_boxes,
    set_srce_panel_bounding_boxes,
)
from barks_fantagraphics.panel_geometry import BoundingBox

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
# get_panels_bounding_box_from_file
# ---------------------------------------------------------------------------


class TestGetPanelsBoundingBoxFromFile:
    def test_reads_overall_bounds(self, tmp_path: Path) -> None:
        f = tmp_path / "segments.json"
        f.write_text(_make_panel_segments_json([5, 10, 800, 1400]))

        result = get_panels_bounding_box_from_file(f)

        assert result.x_min == 5
        assert result.y_min == 10
        assert result.x_max == 800
        assert result.y_max == 1400


# ---------------------------------------------------------------------------
# _get_min_max helpers (tested indirectly via get_required_panels_bbox_width_height)
# ---------------------------------------------------------------------------


class TestGetRequiredPanelsBboxWidthHeight:
    def test_every_dimension_of_two_unlike_pages(self) -> None:
        pages = [
            _body_page("a.jpg", BoundingBox(0, 0, 799, 1199)),  # w=800, h=1200
            _body_page("b.jpg", BoundingBox(0, 0, 999, 1499)),  # w=1000, h=1500
        ]
        srce_dim, required_dim = get_required_panels_bbox_width_height(pages, 3200, 20)

        # Page a is more than the margin shorter than b, so the averages are b's alone.
        assert srce_dim == ComicDimensions(
            min_panels_bbox_width=800,
            max_panels_bbox_width=1000,
            min_panels_bbox_height=1200,
            max_panels_bbox_height=1500,
            av_panels_bbox_width=1000,
            av_panels_bbox_height=1500,
        )
        # Height: 1500 * 1920 / 1000. Page number: the 320 pixels left over put the
        # centre of the top margin's top half at 80, and half the number's 20 comes off.
        assert required_dim == RequiredDimensions(
            panels_bbox_width=REQUIRED_WIDTH, panels_bbox_height=2880, page_num_y_bottom=70
        )

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

    def test_all_pages_without_panels_returns_defaults(self) -> None:
        # A collection of full-page images only (e.g. "All Covers") has no panel
        # pages, so there is nothing to compute - return the unset defaults rather
        # than dividing by an empty list.
        pages = [CleanPage("500.jpg", PageType.COVER), CleanPage("501.jpg", PageType.COVER)]
        srce_dim, required_dim = get_required_panels_bbox_width_height(pages, 3200, 20)

        assert srce_dim == ComicDimensions()
        assert required_dim == RequiredDimensions()


# ---------------------------------------------------------------------------
# set_srce_panel_bounding_boxes
# ---------------------------------------------------------------------------


class TestSetSrcePanelBoundingBoxes:
    def test_sets_bbox_from_file(self, tmp_path: Path) -> None:
        f = tmp_path / "001.json"
        f.write_text(_make_panel_segments_json([5, 10, 800, 1400]))

        page = _body_page()
        set_srce_panel_bounding_boxes([page], [f], check_srce_page_timestamps=False)

        assert page.panels_bbox.x_min == 5
        assert page.panels_bbox.y_min == 10
        assert page.panels_bbox.x_max == 800
        assert page.panels_bbox.y_max == 1400

    def test_skips_pages_without_panels(self, tmp_path: Path) -> None:
        page = _front_page()
        missing = tmp_path / "nonexistent.json"
        # Should not raise even though file is missing — FRONT pages are skipped
        set_srce_panel_bounding_boxes([page], [missing], check_srce_page_timestamps=False)

    def test_raises_when_segment_file_missing(self, tmp_path: Path) -> None:
        page = _body_page()
        missing = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError, match="panels segments info file"):
            set_srce_panel_bounding_boxes([page], [missing], check_srce_page_timestamps=False)

    def test_raises_on_stale_timestamp(self, tmp_path: Path) -> None:
        f = tmp_path / "001.json"
        f.write_text(_make_panel_segments_json())
        page = _body_page()

        with (
            patch.object(panel_bounding_module, "dest_file_is_older_than_srce", return_value=True),
            pytest.raises(RuntimeError, match="older than srce"),
        ):
            set_srce_panel_bounding_boxes([page], [f], check_srce_page_timestamps=True)

    def test_no_timestamp_check_skips_stale_check(self, tmp_path: Path) -> None:
        f = tmp_path / "001.json"
        f.write_text(_make_panel_segments_json())
        page = _body_page()

        with patch.object(panel_bounding_module, "dest_file_is_older_than_srce", return_value=True):
            # Should not raise because check_srce_page_timestamps=False
            set_srce_panel_bounding_boxes([page], [f], check_srce_page_timestamps=False)


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

        # 1920 x 2880 on the 2120 x 3200 page: 100 at each side, 160 above and below.
        assert dest_page.panels_bbox == BoundingBox(100, 160, 2019, 3039)

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

        # Its own height at the required width, 1300 * 1920 / 1000 = 2496, centred.
        assert dest_page.panels_bbox == BoundingBox(100, 352, 2019, 2847)

    @pytest.mark.parametrize(
        ("srce_height", "dest_height"),
        [
            pytest.param(1400, 2880, id="at the margin: the required height"),
            pytest.param(1399, 2686, id="one pixel under: its own scaled height"),
        ],
    )
    def test_the_margin_below_the_average_is_inclusive(
        self, srce_height: int, dest_height: int
    ) -> None:
        av_h = 1400 + PANELS_BBOX_HEIGHT_SIMILARITY_MARGIN
        srce_page = _body_page(bbox=BoundingBox(0, 0, 999, srce_height - 1))
        dest_page = CleanPage("1-01.jpg", PageType.BODY)
        pages = SrceAndDestPages([srce_page], [dest_page])

        set_dest_panel_bounding_boxes(
            _make_srce_dim(av_h=av_h, max_h=av_h), _make_required_dim(h=2880), pages
        )

        assert dest_page.panels_bbox.get_height() == dest_height

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
