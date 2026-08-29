# ruff: noqa: ANN401, PLR2004 - these tests deliberately feed malformed values to the validator.

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import comic_utils.panel_segmentation as panel_segmentation_module
import pytest
from comic_utils.panel_segmentation import (
    KumikoBound,
    KumikoPanelSegmentation,
    PanelSegmentsFault,
    PanelSegmentsFinding,
    apply_panel_order_override,
    get_kumiko_panel_bound,
    get_min_max_panel_values,
    get_panel_segments_finding_msg,
    read_panel_order_override,
    sort_panels_in_reading_order,
    validate_panel_segments,
)
from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path


class TestGetKumikoPanelBound:
    def test_maps_raw_list_positionally(self) -> None:
        assert get_kumiko_panel_bound((1, 2, 3, 4)) == KumikoBound(left=1, top=2, width=3, height=4)


class TestGetMinMaxPanelValues:
    def test_single_panel_uses_inclusive_extents(self) -> None:
        # width 100 starting at x=10 covers pixels 10..109 inclusive.
        result = get_min_max_panel_values({"panels": [[10, 20, 100, 200]]})
        assert result == (10, 20, 109, 219)

    def test_multiple_panels_take_overall_min_and_max(self) -> None:
        panels = [
            [50, 60, 100, 100],  # x: 50..149, y: 60..159
            [10, 300, 20, 20],  # x: 10..29,  y: 300..319
            [400, 5, 50, 10],  # x: 400..449, y: 5..14
        ]
        assert get_min_max_panel_values({"panels": panels}) == (10, 5, 449, 319)

    def test_panel_at_origin_is_valid(self) -> None:
        # Regression: the old implementation used 0 as an "unset" sentinel for the
        # maxima, so a 1x1 panel at the origin was rejected as "no panels".
        assert get_min_max_panel_values({"panels": [[0, 0, 1, 1]]}) == (0, 0, 0, 0)

    def test_no_panels_raises(self) -> None:
        with pytest.raises(ValueError, match="no panels"):
            get_min_max_panel_values({"panels": []})

    @pytest.mark.parametrize("panel", [[-1, 0, 10, 10], [0, -1, 10, 10]])
    def test_negative_origin_raises(self, panel: list[int]) -> None:
        with pytest.raises(ValueError, match="negative origin"):
            get_min_max_panel_values({"panels": [panel]})

    @pytest.mark.parametrize("panel", [[0, 0, 0, 10], [0, 0, 10, 0], [0, 0, -5, 10]])
    def test_non_positive_size_raises(self, panel: list[int]) -> None:
        with pytest.raises(ValueError, match="non-positive size"):
            get_min_max_panel_values({"panels": [panel]})


def _completed(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


class TestKumikoPanelSegmentation:
    def test_saves_work_image_and_returns_first_segment(self, tmp_path: Path) -> None:
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        seg = KumikoPanelSegmentation(work_dir, tmp_path / "building")
        image = Image.new("RGB", (4, 4))
        kumiko_out = json.dumps([{"panels": [[0, 0, 4, 4]], "processing_time": 1.5}])

        with patch.object(subprocess, "run", return_value=_completed(kumiko_out)) as run:
            result = seg.get_panels_segment_info(image, tmp_path / "pages" / "007.png")

        assert result == {"panels": [[0, 0, 4, 4]], "processing_time": 1.5}
        work_file = work_dir / "007_orig.jpg"
        assert work_file.is_file()
        args = run.call_args.args[0]
        assert args[:3] == ["uv", "run", "--directory"]
        assert args[3] == str(tmp_path / "building")
        assert args[-2:] == ["-i", str(work_file)]
        assert "--no-panel-expansion" not in args

    def test_no_panel_expansion_flag_is_passed(self, tmp_path: Path) -> None:
        seg = KumikoPanelSegmentation(tmp_path, tmp_path, no_panel_expansion=True)
        kumiko_out = json.dumps([{"panels": []}])

        with patch.object(subprocess, "run", return_value=_completed(kumiko_out)) as run:
            seg.get_panels_segment_info(Image.new("RGB", (4, 4)), tmp_path / "p.png")

        assert run.call_args.args[0][-1] == "--no-panel-expansion"

    def test_kumiko_failure_is_logged_and_re_raised(self, tmp_path: Path) -> None:
        seg = KumikoPanelSegmentation(tmp_path, tmp_path)
        error = subprocess.CalledProcessError(2, ["kumiko"], output="out", stderr="boom")
        logged: list[str] = []

        with (
            patch.object(subprocess, "run", side_effect=error),
            patch.object(panel_segmentation_module.logger, "error", side_effect=logged.append),
            pytest.raises(subprocess.CalledProcessError),
        ):
            seg.get_panels_segment_info(Image.new("RGB", (4, 4)), tmp_path / "p.png")

        assert any("return code 2" in m for m in logged)
        assert any("boom" in m for m in logged)

    def test_multiple_pages_in_output_is_rejected(self, tmp_path: Path) -> None:
        seg = KumikoPanelSegmentation(tmp_path, tmp_path)
        kumiko_out = json.dumps([{"panels": []}, {"panels": []}])

        with (
            patch.object(subprocess, "run", return_value=_completed(kumiko_out)),
            pytest.raises(AssertionError),
        ):
            seg.get_panels_segment_info(Image.new("RGB", (4, 4)), tmp_path / "p.png")


# ---------------------------------------------------------------------------
# Reading order
# ---------------------------------------------------------------------------

# Real page geometries (x, y, w, h) from the Fantagraphics segments files.
JOGGED_2X2_TIERS = [  # Vol 10 p020: kumiko emitted this column-wise.
    [222, 194, 965, 511],
    [222, 731, 994, 780],
    [1189, 194, 885, 648],
    [1218, 868, 856, 647],
]
TALL_RIGHT_PANEL = [  # Vol 28 p093: panel 4 spans tiers 1 and 2.
    [147, 232, 891, 560],
    [1104, 232, 442, 560],
    [147, 857, 880, 631],
    [1612, 232, 335, 1228],
    [1093, 857, 854, 603],
]
TALL_LEFT_PANEL = [  # Vol 10 p065, tiers 3-4: panel 1 is tall, 2 and 3 stack beside it.
    [155, 1537, 743, 1319],
    [923, 1534, 1075, 651],
    [923, 2212, 1075, 644],
]


def _order(panels: list[list[int]]) -> list[int]:
    return [panels.index(p) + 1 for p in sort_panels_in_reading_order(panels)]


class TestSortPanelsInReadingOrder:
    def test_clean_grid_is_unchanged(self) -> None:
        grid = [[x, y, 900, 600] for y in (0, 700, 1400, 2100) for x in (0, 1000)]
        assert _order(grid) == list(range(1, 9))

    def test_jogged_tiers_are_read_across_not_down(self) -> None:
        assert _order(JOGGED_2X2_TIERS) == [1, 3, 2, 4]

    def test_tall_panel_is_read_in_the_tier_it_starts_in(self) -> None:
        assert _order(TALL_RIGHT_PANEL) == [1, 2, 4, 3, 5]

    def test_tall_left_panel_then_stacked_neighbors(self) -> None:
        assert _order(TALL_LEFT_PANEL) == [1, 2, 3]

    def test_small_top_jitter_does_not_split_a_tier(self) -> None:
        panels = [[1000, 3, 900, 600], [0, 0, 900, 600]]
        assert _order(panels) == [2, 1]

    def test_single_panel(self) -> None:
        assert sort_panels_in_reading_order([[5, 6, 7, 8]]) == [[5, 6, 7, 8]]

    def test_empty(self) -> None:
        assert sort_panels_in_reading_order([]) == []

    def test_returns_new_lists(self) -> None:
        panels = [(0, 0, 10, 10)]
        result = sort_panels_in_reading_order(panels)
        assert result == [[0, 0, 10, 10]]
        assert isinstance(result[0], list)


class TestApplyPanelOrderOverride:
    def test_reorders(self) -> None:
        panels = [[1, 0, 1, 1], [2, 0, 1, 1], [3, 0, 1, 1]]
        assert apply_panel_order_override(panels, [3, 1, 2]) == [
            [3, 0, 1, 1],
            [1, 0, 1, 1],
            [2, 0, 1, 1],
        ]

    @pytest.mark.parametrize("order", [[1, 2], [1, 1, 2], [0, 1, 2], [1, 2, 4], [1, 2, True]])
    def test_non_permutation_raises(self, order: list[int]) -> None:
        panels = [[0, 0, 1, 1]] * 3
        with pytest.raises(ValueError, match="not a permutation"):
            apply_panel_order_override(panels, order)


class TestReadPanelOrderOverride:
    def test_reads_list(self, tmp_path: Path) -> None:
        f = tmp_path / "012-panel-order.json"
        f.write_text("[2, 1, 3]")
        assert read_panel_order_override(f) == [2, 1, 3]

    @pytest.mark.parametrize("text", ['{"a": 1}', '["1", 2]', "[1.5, 2]"])
    def test_rejects_non_int_list(self, tmp_path: Path, text: str) -> None:
        f = tmp_path / "012-panel-order.json"
        f.write_text(text)
        with pytest.raises(ValueError, match="JSON list of ints"):
            read_panel_order_override(f)


# ---------------------------------------------------------------------------
# validate_panel_segments
# ---------------------------------------------------------------------------

PAGE = (1000, 1500)
CLEAN_PANELS = [[0, 0, 400, 300], [500, 0, 400, 300], [0, 400, 400, 300], [500, 400, 400, 300]]


def _segments(
    panels: list[Any],
    *,
    size: Any = PAGE,
    overall: Any = None,
    numbering: Any = "ltr",
) -> dict[str, Any]:
    if overall is None and panels and all(_is_good_panel(p) for p in panels):
        overall = list(get_min_max_panel_values({"panels": panels}))
    return {
        "filename": "x.jpg",
        "size": list(size) if isinstance(size, tuple) else size,
        "numbering": numbering,
        "gutters": [0, 0],
        "license": None,
        "panels": panels,
        "overall_bounds": overall,
    }


def _is_good_panel(p: Any) -> bool:
    return isinstance(p, list) and len(p) == 4 and p[2] > 0 and p[3] > 0


def _faults(info: dict[str, Any], **kwargs: Any) -> list[PanelSegmentsFault]:
    kwargs.setdefault("has_overall_bounds_override", False)
    return [f.fault for f in validate_panel_segments(info, **kwargs)]


class TestValidatePanelSegments:
    def test_clean_page(self) -> None:
        assert _faults(_segments(CLEAN_PANELS)) == []

    def test_unsorted_panels(self) -> None:
        info = _segments(JOGGED_2X2_TIERS, size=(2216, 3056))
        findings = validate_panel_segments(info, has_overall_bounds_override=False)
        assert [f.fault for f in findings] == [PanelSegmentsFault.NOT_IN_READING_ORDER]
        assert findings[0].detail == "[1, 3, 2, 4]"

    def test_unsorted_panels_matching_override_are_fine(self) -> None:
        info = _segments(JOGGED_2X2_TIERS, size=(2216, 3056))
        # Tier order is 1,3,2,4; this override says "read the tier-sorted panels as 1,3,2,4",
        # which lands back on the kumiko order the file has.
        assert _faults(info, panel_order_override=[1, 3, 2, 4]) == []

    def test_bad_override(self) -> None:
        assert _faults(_segments(CLEAN_PANELS), panel_order_override=[1, 2]) == [
            PanelSegmentsFault.BAD_ORDER_OVERRIDE
        ]

    def test_touching_panels_are_fine(self) -> None:
        assert _faults(_segments([[0, 0, 100, 100], [100, 0, 100, 100]])) == []

    def test_overlap(self) -> None:
        info = _segments([[0, 0, 100, 100], [50, 0, 100, 100]])
        findings = validate_panel_segments(info, has_overall_bounds_override=False)
        assert [(f.fault, f.panel_nums, f.detail) for f in findings] == [
            (PanelSegmentsFault.PANEL_OVERLAP, (1, 2), "50.0%")
        ]

    def test_overlap_at_threshold_is_fine(self) -> None:
        assert _faults(_segments([[0, 0, 100, 100], [90, 0, 100, 100]])) == []

    def test_no_panels(self) -> None:
        assert _faults(_segments([], overall=[0, 0, 1, 1])) == [PanelSegmentsFault.NO_PANELS]

    @pytest.mark.parametrize("panel", [[950, 0, 100, 100], [0, 1450, 100, 100], [-1, 0, 10, 10]])
    def test_panel_outside_page(self, panel: list[int]) -> None:
        info = _segments([panel], overall=[0, 0, 1, 1])
        findings = validate_panel_segments(info, has_overall_bounds_override=True)
        assert [(f.fault, f.panel_nums) for f in findings] == [
            (PanelSegmentsFault.PANEL_OUTSIDE_PAGE, (1,))
        ]

    def test_non_positive_size_has_no_mismatch_cascade(self) -> None:
        info = _segments([[0, 0, 0, 10], [0, 20, 10, 10]], overall=[0, 20, 9, 29])
        assert _faults(info) == [PanelSegmentsFault.NON_POSITIVE_PANEL_SIZE]

    def test_bad_panel_shape(self) -> None:
        info = _segments([[0, 0, 10], [0, 20, 10, 10]], overall=[0, 20, 9, 29])
        findings = validate_panel_segments(info, has_overall_bounds_override=False)
        assert [(f.fault, f.panel_nums) for f in findings] == [
            (PanelSegmentsFault.BAD_PANEL_SHAPE, (1,))
        ]

    def test_overall_bounds_mismatch(self) -> None:
        info = _segments(CLEAN_PANELS, overall=[0, 0, 899, 700])
        findings = validate_panel_segments(info, has_overall_bounds_override=False)
        assert [f.fault for f in findings] == [PanelSegmentsFault.OVERALL_BOUNDS_MISMATCH]
        assert findings[0].detail == "expected [0, 0, 899, 699], got [0, 0, 899, 700]"

    def test_overall_bounds_mismatch_allowed_with_override(self) -> None:
        info = _segments(CLEAN_PANELS, overall=[0, 0, 899, 700])
        assert _faults(info, has_overall_bounds_override=True) == []

    @pytest.mark.parametrize(
        "overall", [[0, 0, 2000, 10], [10, 10, 5, 20], [-1, 0, 5, 5], [0, 0, 5], "x"]
    )
    def test_bad_overall_bounds(self, overall: Any) -> None:
        info = _segments(CLEAN_PANELS, overall=overall)
        assert _faults(info, has_overall_bounds_override=True) == [
            PanelSegmentsFault.BAD_OVERALL_BOUNDS
        ]

    def test_numbering_not_ltr(self) -> None:
        assert _faults(_segments(CLEAN_PANELS, numbering="rtl")) == [
            PanelSegmentsFault.NUMBERING_NOT_LTR
        ]

    def test_missing_size_still_checks_geometry(self) -> None:
        info = _segments([[0, 0, 100, 100], [50, 0, 100, 100]])
        del info["size"]
        findings = validate_panel_segments(info, has_overall_bounds_override=False)
        assert (findings[0].fault, findings[0].detail) == (PanelSegmentsFault.MISSING_KEY, "size")
        assert PanelSegmentsFault.PANEL_OVERLAP in [f.fault for f in findings]

    def test_missing_panels_is_the_only_finding(self) -> None:
        info = _segments(CLEAN_PANELS)
        del info["panels"]
        assert _faults(info) == [PanelSegmentsFault.MISSING_KEY]

    @pytest.mark.parametrize("size", [[0, 100], [100], ["a", 1], [True, 1], "big"])
    def test_bad_page_size(self, size: Any) -> None:
        assert _faults(_segments(CLEAN_PANELS, size=size)) == [PanelSegmentsFault.BAD_PAGE_SIZE]

    def test_page_size_mismatch(self) -> None:
        info = _segments(CLEAN_PANELS)
        assert _faults(info, actual_page_size=(1000, 1499)) == [
            PanelSegmentsFault.PAGE_SIZE_MISMATCH
        ]
        assert _faults(info, actual_page_size=(1000, 1500)) == []


class TestGetPanelSegmentsFindingMsg:
    @pytest.mark.parametrize("fault", list(PanelSegmentsFault))
    def test_every_fault_formats(self, fault: PanelSegmentsFault) -> None:
        msg = get_panel_segments_finding_msg(PanelSegmentsFinding(fault, (3, 4), "DETAIL"))
        assert msg
        assert "{" not in msg
        if fault != PanelSegmentsFault.NO_PANELS:
            assert "DETAIL" in msg

    def test_overlap_names_both_panels(self) -> None:
        finding = PanelSegmentsFinding(PanelSegmentsFault.PANEL_OVERLAP, (2, 3), "23.4%")
        assert get_panel_segments_finding_msg(finding) == (
            "Panels 2 and 3 overlap by 23.4% of the smaller panel."
        )
