# ruff: noqa: PLR2004

from __future__ import annotations

import pytest
from barks_fantagraphics.panel_geometry import (
    BoundingBox,
    BoxSizeStats,
    centered_bbox,
    compute_box_size_stats,
    compute_page_num_y_bottom,
    compute_required_panels_bbox_size,
    scale_height,
)

# ---------------------------------------------------------------------------
# BoundingBox
# ---------------------------------------------------------------------------


class TestBoundingBox:
    def test_get_box(self) -> None:
        bb = BoundingBox(10, 20, 100, 200)
        assert bb.get_box() == (10, 20, 100, 200)

    def test_get_width_and_height_are_inclusive(self) -> None:
        bb = BoundingBox(10, 20, 109, 219)
        assert bb.get_width() == 100
        assert bb.get_height() == 200

    def test_defaults_to_sentinel(self) -> None:
        bb = BoundingBox()
        assert bb.x_min == -1
        assert bb.y_min == -1
        assert bb.x_max == -1
        assert bb.y_max == -1

    def test_is_frozen(self) -> None:
        bb = BoundingBox(0, 0, 10, 10)
        with pytest.raises((AttributeError, TypeError)):
            # noinspection PyDataclass
            bb.x_min = 99  # ty: ignore[invalid-assignment]


# ---------------------------------------------------------------------------
# scale_height
# ---------------------------------------------------------------------------


class TestScaleHeight:
    def test_doubling_width_doubles_height(self) -> None:
        assert scale_height(2000, 1000, 1500) == 3000

    def test_identity(self) -> None:
        assert scale_height(1000, 1000, 1500) == 1500

    def test_rounds_to_nearest(self) -> None:
        # 1500 * 1001 / 1000 = 1501.5 → 1502
        assert scale_height(1001, 1000, 1500) == 1502


# ---------------------------------------------------------------------------
# compute_box_size_stats
# ---------------------------------------------------------------------------


class TestComputeBoxSizeStats:
    def test_single_box(self) -> None:
        stats = compute_box_size_stats([(1000, 1500)], height_similarity_margin=100)

        assert stats == BoxSizeStats(
            min_width=1000,
            max_width=1000,
            min_height=1500,
            max_height=1500,
            avg_width=1000,
            avg_height=1500,
        )

    def test_min_and_max_cover_all_boxes(self) -> None:
        stats = compute_box_size_stats(
            [(800, 1200), (1000, 1500), (900, 1400)],
            height_similarity_margin=200,
        )

        assert stats.min_width == 800
        assert stats.max_width == 1000
        assert stats.min_height == 1200
        assert stats.max_height == 1500

    def test_short_boxes_excluded_from_average(self) -> None:
        # max_h = 1500, margin = 100 → threshold = 1400. The 1000-high box is excluded.
        stats = compute_box_size_stats(
            [(1000, 1500), (1000, 1450), (500, 1000)],
            height_similarity_margin=100,
        )

        # Only the first two (1000 wide x 1500 and 1000 wide x 1450) contribute to the average.
        assert stats.avg_width == 1000
        assert stats.avg_height == round((1500 + 1450) / 2)  # 1475

    def test_empty_sizes_raises(self) -> None:
        with pytest.raises(ValueError, match="empty list"):
            compute_box_size_stats([], height_similarity_margin=100)

    def test_no_box_qualifies_for_average_raises(self) -> None:
        # Impossible given `max_h - margin <= max_h` is always true for the max-height box,
        # but a negative margin creates the pathological case.
        with pytest.raises(ValueError, match="qualify"):
            compute_box_size_stats([(1000, 1500)], height_similarity_margin=-1)


# ---------------------------------------------------------------------------
# compute_required_panels_bbox_size
# ---------------------------------------------------------------------------


class TestComputeRequiredPanelsBboxSize:
    def test_width_is_target_minus_two_margins(self) -> None:
        w, _ = compute_required_panels_bbox_size(
            avg_box_width=1000,
            avg_box_height=1500,
            target_page_width=2120,
            target_x_margin=100,
        )
        assert w == 1920

    def test_height_preserves_average_aspect_ratio(self) -> None:
        w, h = compute_required_panels_bbox_size(
            avg_box_width=1000,
            avg_box_height=1500,
            target_page_width=2120,
            target_x_margin=100,
        )
        # w = 1920, so h = 1500 * 1920 / 1000 = 2880
        assert w == 1920
        assert h == 2880


# ---------------------------------------------------------------------------
# compute_page_num_y_bottom
# ---------------------------------------------------------------------------


class TestComputePageNumYBottom:
    def test_centered_in_top_margin_half(self) -> None:
        # page_h = 3200, panels_h = 2880 → top margin = 160, quarter = 80 → centre y = 80
        # page_num_h = 20 → y_bottom = 80 - 10 = 70
        assert compute_page_num_y_bottom(3200, 2880, 20) == 70


# ---------------------------------------------------------------------------
# centered_bbox
# ---------------------------------------------------------------------------


class TestCenteredBbox:
    def test_horizontally_symmetric(self) -> None:
        bb = centered_bbox(
            target_page_width=2120,
            target_page_height=3200,
            bbox_width=1920,
            bbox_height=2880,
            x_margin=100,
        )
        assert bb.x_min == 100
        assert bb.x_max == 100 + 1920 - 1

    def test_vertically_centered(self) -> None:
        bb = centered_bbox(
            target_page_width=2120,
            target_page_height=3200,
            bbox_width=1920,
            bbox_height=2880,
            x_margin=100,
        )
        # (3200 - 2880) / 2 = 160
        assert bb.y_min == 160
        assert bb.y_max == 160 + 2880 - 1

    def test_exact_width_and_height(self) -> None:
        bb = centered_bbox(
            target_page_width=2120,
            target_page_height=3200,
            bbox_width=1920,
            bbox_height=2880,
            x_margin=100,
        )
        assert bb.get_width() == 1920
        assert bb.get_height() == 2880

    def test_asserts_bbox_fits_horizontally(self) -> None:
        with pytest.raises(AssertionError):
            centered_bbox(
                target_page_width=1000,
                target_page_height=1000,
                bbox_width=900,
                bbox_height=500,
                x_margin=100,  # 900 + 200 > 1000
            )
