import json
import statistics
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from loguru import logger
from PIL.Image import Image as PilImage

KUMIKO_LTR_NUMBERING = "ltr"

# A panel starts a new tier when its top is more than this fraction of the page's median
# panel height below the top of the tier being built.
TIER_TOLERANCE_FRACTION = 0.4

# Two panels whose intersection exceeds this percentage of the smaller panel's area are
# reported as overlapping. Kumiko's expanded bounds legitimately touch or overlap a little.
MAX_PANEL_OVERLAP_PERCENT = 10.0

NUM_PANEL_COORDS = 4

RawPanel = Sequence[int]


@dataclass(frozen=True, slots=True)
class KumikoBound:
    left: int
    top: int
    width: int
    height: int


def get_kumiko_panel_bound(raw_bound: tuple[int, int, int, int]) -> KumikoBound:
    return KumikoBound(raw_bound[0], raw_bound[1], raw_bound[2], raw_bound[3])


def get_min_max_panel_values(segment_info: dict[str, Any]) -> tuple[int, int, int, int]:
    """Return the inclusive bounding box enclosing every kumiko panel.

    Args:
        segment_info: Kumiko output with a ``"panels"`` list of ``[left, top, width, height]``.

    Returns:
        ``(x_min, y_min, x_max, y_max)`` with inclusive pixel coordinates.

    Raises:
        ValueError: If there are no panels, or a panel has a negative origin or a
            non-positive size.

    """
    x_min = y_min = x_max = y_max = -1

    for raw_kumiko_bound in segment_info["panels"]:
        kumiko_bound = get_kumiko_panel_bound(raw_kumiko_bound)

        if kumiko_bound.left < 0 or kumiko_bound.top < 0:
            msg = f"Kumiko panel has a negative origin: {kumiko_bound}."
            raise ValueError(msg)
        if kumiko_bound.width <= 0 or kumiko_bound.height <= 0:
            msg = f"Kumiko panel has a non-positive size: {kumiko_bound}."
            raise ValueError(msg)

        x0 = kumiko_bound.left
        y0 = kumiko_bound.top
        x1 = x0 + (kumiko_bound.width - 1)
        y1 = y0 + (kumiko_bound.height - 1)

        if x_min == -1:
            x_min, y_min, x_max, y_max = x0, y0, x1, y1
        else:
            x_min = min(x_min, x0)
            y_min = min(y_min, y0)
            x_max = max(x_max, x1)
            y_max = max(y_max, y1)

    if x_min == -1:
        msg = "Kumiko returned no panels."
        raise ValueError(msg)

    return x_min, y_min, x_max, y_max


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_raw_panel(panel: object) -> bool:
    return (
        isinstance(panel, Sequence)
        and not isinstance(panel, str)
        and len(panel) == NUM_PANEL_COORDS
        and all(_is_int(v) for v in panel)
    )


def sort_panels_in_reading_order(panels: Sequence[RawPanel]) -> list[list[int]]:
    """Order kumiko panels the way a Barks page is read: tier by tier, left to right.

    Panels are grouped into tiers by their top edge: walking the panels by ``(y, x)``, a
    panel starts a new tier when its top is more than ``TIER_TOLERANCE_FRACTION`` of the
    page's median panel height below the first panel of the current tier. A panel that
    spans two tiers is therefore read in the tier its top belongs to. Tiers are emitted
    top to bottom, and each tier left to right (``(x, y)``).

    Args:
        panels: Kumiko ``[x, y, w, h]`` panels in any order.

    Returns:
        The same panels, as new lists, in reading order. Stable for panels that tie.

    """
    if not panels:
        return []

    tolerance = TIER_TOLERANCE_FRACTION * statistics.median(p[3] for p in panels)

    tiers: list[list[RawPanel]] = []
    for panel in sorted(panels, key=lambda p: (p[1], p[0])):
        if tiers and (panel[1] - tiers[-1][0][1]) <= tolerance:
            tiers[-1].append(panel)
        else:
            tiers.append([panel])

    return [list(p) for tier in tiers for p in sorted(tier, key=lambda p: (p[0], p[1]))]


def apply_panel_order_override(panels: Sequence[RawPanel], order: Sequence[int]) -> list[list[int]]:
    """Re-emit panels in a hand-chosen order.

    Args:
        panels: Panels in automatic reading order.
        order: A permutation of the 1-based panel numbers of ``panels``.

    Returns:
        ``[panels[order[0] - 1], panels[order[1] - 1], ...]``.

    Raises:
        ValueError: If ``order`` is not a permutation of ``1..len(panels)``.

    """
    expected = list(range(1, len(panels) + 1))
    if not all(_is_int(n) for n in order) or sorted(order) != expected:
        msg = f"Panel order override {list(order)} is not a permutation of {expected}."
        raise ValueError(msg)

    return [list(panels[n - 1]) for n in order]


def read_panel_order_override(order_file: Path) -> list[int]:
    """Read a ``NNN-panel-order.json`` override: a JSON list of 1-based panel numbers.

    Args:
        order_file: The override file.

    Returns:
        The panel numbers in the wanted order.

    Raises:
        ValueError: If the file is not a JSON list of ints.

    """
    with order_file.open() as f:
        order = json.load(f)

    if not isinstance(order, list) or not all(_is_int(n) for n in order):
        msg = f'Panel order override "{order_file}" must be a JSON list of ints, not {order!r}.'
        raise ValueError(msg)

    return order


class PanelSegmentsFault(StrEnum):
    MISSING_KEY = "missing_key"
    BAD_PAGE_SIZE = "bad_page_size"
    NUMBERING_NOT_LTR = "numbering_not_ltr"
    NO_PANELS = "no_panels"
    BAD_PANEL_SHAPE = "bad_panel_shape"
    NON_POSITIVE_PANEL_SIZE = "non_positive_panel_size"
    PANEL_OUTSIDE_PAGE = "panel_outside_page"
    NOT_IN_READING_ORDER = "not_in_reading_order"
    BAD_ORDER_OVERRIDE = "bad_order_override"
    PANEL_OVERLAP = "panel_overlap"
    BAD_OVERALL_BOUNDS = "bad_overall_bounds"
    OVERALL_BOUNDS_MISMATCH = "overall_bounds_mismatch"
    PAGE_SIZE_MISMATCH = "page_size_mismatch"


@dataclass(frozen=True, slots=True)
class PanelSegmentsFinding:
    fault: PanelSegmentsFault
    panel_nums: tuple[int, ...] = ()  # 1-based: the public panel numbers.
    detail: str = ""


_FINDING_MSG_TEMPLATES: dict[PanelSegmentsFault, str] = {
    PanelSegmentsFault.MISSING_KEY: 'Missing key "{detail}".',
    PanelSegmentsFault.BAD_PAGE_SIZE: "Page size must be two positive ints, not {detail}.",
    PanelSegmentsFault.NUMBERING_NOT_LTR: (
        f'Numbering must be "{KUMIKO_LTR_NUMBERING}", not "{{detail}}".'
    ),
    PanelSegmentsFault.NO_PANELS: "There are no panels.",
    PanelSegmentsFault.BAD_PANEL_SHAPE: (
        "Panel {panels} must be four ints [x, y, w, h], not {detail}."
    ),
    PanelSegmentsFault.NON_POSITIVE_PANEL_SIZE: (
        "Panel {panels} has a non-positive width or height: {detail}."
    ),
    PanelSegmentsFault.PANEL_OUTSIDE_PAGE: "Panel {panels} lies outside the page: {detail}.",
    PanelSegmentsFault.NOT_IN_READING_ORDER: (
        "Panels are not in reading order - by their current numbers the reading order is"
        " {detail}. Re-running barks-batch-panel-bounds --force sorts them automatically;"
        " a NNN-panel-order.json is only for when that automatic order is wrong, and its"
        " numbers refer to the automatic order, not to these."
    ),
    PanelSegmentsFault.BAD_ORDER_OVERRIDE: "Bad panel order override: {detail}",
    PanelSegmentsFault.PANEL_OVERLAP: ("Panels {panels} overlap by {detail} of the smaller panel."),
    PanelSegmentsFault.BAD_OVERALL_BOUNDS: (
        "Overall bounds are malformed or outside the page: {detail}."
    ),
    PanelSegmentsFault.OVERALL_BOUNDS_MISMATCH: (
        "Overall bounds do not enclose the panels: {detail}."
    ),
    PanelSegmentsFault.PAGE_SIZE_MISMATCH: "Page size does not match the image: {detail}.",
}


def get_panel_segments_finding_msg(finding: PanelSegmentsFinding) -> str:
    """Format one validation finding as a sentence.

    Args:
        finding: The finding.

    Returns:
        A one-line description naming the panels involved.

    """
    panels = " and ".join(str(n) for n in finding.panel_nums)
    return _FINDING_MSG_TEMPLATES[finding.fault].format(panels=panels, detail=finding.detail)


def _page_size(size: object) -> tuple[int, int] | None:
    if (
        isinstance(size, Sequence)
        and not isinstance(size, str)
        and len(size) == 2  # noqa: PLR2004
        and all(_is_int(v) and v > 0 for v in size)
    ):
        return size[0], size[1]
    return None


def _overlap_percent(a: RawPanel, b: RawPanel) -> float:
    ix = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    iy = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    if ix <= 0 or iy <= 0:
        return 0.0
    smaller_area = min(a[2] * a[3], b[2] * b[3])
    return 100.0 * (ix * iy) / smaller_area


def _check_panels(
    panels: Sequence[object], page_size: tuple[int, int] | None
) -> tuple[list[PanelSegmentsFinding], list[tuple[int, RawPanel]], bool]:
    """Return per-panel findings, the geometrically usable panels, and whether all were valid."""
    findings: list[PanelSegmentsFinding] = []
    usable: list[tuple[int, RawPanel]] = []
    all_valid = True

    for num, panel in enumerate(panels, start=1):
        if not _is_raw_panel(panel):
            findings.append(
                PanelSegmentsFinding(PanelSegmentsFault.BAD_PANEL_SHAPE, (num,), repr(panel))
            )
            all_valid = False
            continue
        assert isinstance(panel, Sequence)
        x, y, w, h = panel
        if w <= 0 or h <= 0:
            findings.append(
                PanelSegmentsFinding(
                    PanelSegmentsFault.NON_POSITIVE_PANEL_SIZE, (num,), f"{list(panel)}"
                )
            )
            all_valid = False
            continue
        if x < 0 or y < 0 or (page_size and (x + w > page_size[0] or y + h > page_size[1])):
            where = f" on a {page_size[0]}x{page_size[1]} page" if page_size else ""
            findings.append(
                PanelSegmentsFinding(
                    PanelSegmentsFault.PANEL_OUTSIDE_PAGE, (num,), f"{list(panel)}{where}"
                )
            )
            all_valid = False
        usable.append((num, panel))

    return findings, usable, all_valid


def _check_reading_order(
    panels: Sequence[RawPanel], panel_order_override: Sequence[int] | None
) -> PanelSegmentsFinding | None:
    expected = sort_panels_in_reading_order(panels)
    if panel_order_override is not None:
        try:
            expected = apply_panel_order_override(expected, panel_order_override)
        except ValueError as e:
            return PanelSegmentsFinding(PanelSegmentsFault.BAD_ORDER_OVERRIDE, (), str(e))

    actual = [list(p) for p in panels]
    if actual == expected:
        return None

    expected_nums = [actual.index(p) + 1 for p in expected]
    return PanelSegmentsFinding(PanelSegmentsFault.NOT_IN_READING_ORDER, (), str(expected_nums))


def _check_overall_bounds(
    bounds: object,
    panels: Sequence[RawPanel],
    page_size: tuple[int, int] | None,
    *,
    all_panels_valid: bool,
    has_overall_bounds_override: bool,
) -> PanelSegmentsFinding | None:
    well_formed = _is_raw_panel(bounds)
    if well_formed:
        assert isinstance(bounds, Sequence)
        x0, y0, x1, y1 = bounds
        well_formed = x0 >= 0 and y0 >= 0 and x0 <= x1 and y0 <= y1
        if well_formed and page_size:
            well_formed = x1 < page_size[0] and y1 < page_size[1]
    if not well_formed:
        return PanelSegmentsFinding(PanelSegmentsFault.BAD_OVERALL_BOUNDS, (), repr(bounds))
    assert isinstance(bounds, Sequence)

    if has_overall_bounds_override or not all_panels_valid:
        return None

    expected = get_min_max_panel_values({"panels": panels})
    if tuple(bounds) != expected:
        return PanelSegmentsFinding(
            PanelSegmentsFault.OVERALL_BOUNDS_MISMATCH,
            (),
            f"expected {list(expected)}, got {list(bounds)}",
        )
    return None


def _check_header(
    segment_info: Mapping[str, Any], actual_page_size: tuple[int, int] | None
) -> tuple[list[PanelSegmentsFinding], tuple[int, int] | None]:
    """Check the keys, numbering and page size; return findings and the usable page size."""
    findings = [
        PanelSegmentsFinding(PanelSegmentsFault.MISSING_KEY, (), key)
        for key in ("panels", "size", "overall_bounds", "numbering")
        if key not in segment_info
    ]

    if "numbering" in segment_info and segment_info["numbering"] != KUMIKO_LTR_NUMBERING:
        findings.append(
            PanelSegmentsFinding(
                PanelSegmentsFault.NUMBERING_NOT_LTR, (), str(segment_info["numbering"])
            )
        )

    if "size" not in segment_info:
        return findings, None

    page_size = _page_size(segment_info["size"])
    if page_size is None:
        findings.append(
            PanelSegmentsFinding(PanelSegmentsFault.BAD_PAGE_SIZE, (), repr(segment_info["size"]))
        )
    elif actual_page_size is not None and page_size != tuple(actual_page_size):
        findings.append(
            PanelSegmentsFinding(
                PanelSegmentsFault.PAGE_SIZE_MISMATCH,
                (),
                f"image {actual_page_size[0]}x{actual_page_size[1]},"
                f" size {page_size[0]}x{page_size[1]}",
            )
        )

    return findings, page_size


def validate_panel_segments(
    segment_info: Mapping[str, Any],
    *,
    has_overall_bounds_override: bool,
    panel_order_override: Sequence[int] | None = None,
    actual_page_size: tuple[int, int] | None = None,
    max_overlap_percent: float = MAX_PANEL_OVERLAP_PERCENT,
) -> list[PanelSegmentsFinding]:
    """Check a panel segments file's content. Never raises; returns findings.

    Args:
        segment_info: The parsed segments JSON.
        has_overall_bounds_override: A ``NNN-overall-bounds-only.jpg`` fix exists, so
            ``overall_bounds`` legitimately need not enclose exactly the panels.
        panel_order_override: The ``NNN-panel-order.json`` fix for this page, if any.
        actual_page_size: When given, ``size`` must equal it.
        max_overlap_percent: Overlap tolerance, as a percentage of the smaller panel.

    Returns:
        The findings, empty when the file is good.

    """
    findings, page_size = _check_header(segment_info, actual_page_size)
    if "panels" not in segment_info:
        return findings

    panels = segment_info["panels"]
    if not panels:
        findings.append(PanelSegmentsFinding(PanelSegmentsFault.NO_PANELS))
        return findings

    panel_findings, usable, all_valid = _check_panels(panels, page_size)
    findings.extend(panel_findings)
    usable_panels = [p for _, p in usable]

    if all_valid:
        order_finding = _check_reading_order(usable_panels, panel_order_override)
        if order_finding:
            findings.append(order_finding)

    for i, (num_a, a) in enumerate(usable):
        for num_b, b in usable[i + 1 :]:
            pct = _overlap_percent(a, b)
            if pct > max_overlap_percent:
                findings.append(
                    PanelSegmentsFinding(
                        PanelSegmentsFault.PANEL_OVERLAP, (num_a, num_b), f"{pct:.1f}%"
                    )
                )

    if "overall_bounds" in segment_info:
        bounds_finding = _check_overall_bounds(
            segment_info["overall_bounds"],
            usable_panels,
            page_size,
            all_panels_valid=all_valid,
            has_overall_bounds_override=has_overall_bounds_override,
        )
        if bounds_finding:
            findings.append(bounds_finding)

    return findings


class KumikoPanelSegmentation:
    def __init__(
        self, work_dir: Path, comic_building_dir: Path, no_panel_expansion: bool = False
    ) -> None:
        self._work_dir = work_dir
        self._comic_building_dir = comic_building_dir
        self._no_panel_expansion = no_panel_expansion

    def get_panels_segment_info(self, srce_image: PilImage, srce_filename: Path) -> dict[str, Any]:
        logger.debug(f'Getting panel bounding box for "{srce_filename}" using kumiko.')

        work_filename = str(self._work_dir / (srce_filename.stem + "_orig.jpg"))
        srce_image.save(work_filename, optimize=True, compress_level=9)
        logger.debug(f'Saved srce image to work file "{work_filename}".')

        logger.debug(f'Getting segment info for "{work_filename}".')
        return self._run_kumiko(work_filename)

    def _run_kumiko(self, page_filename: str) -> dict[str, Any]:
        uv_cmd = "uv"
        kumiko_home_dir = Path.home() / "Prj/github/kumiko"
        kumiko_script_path = str(kumiko_home_dir / "kumiko")
        run_args = [
            uv_cmd,
            "run",
            "--directory",
            str(self._comic_building_dir),
            kumiko_script_path,
            "-i",
            page_filename,
        ]
        if self._no_panel_expansion:
            run_args.append("--no-panel-expansion")
        logger.debug(f"Running kumiko: {' '.join(run_args)}.")
        try:
            result = subprocess.run(  # noqa: S603
                run_args,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Kumiko failed with return code {e.returncode}")
            logger.error(f"STDOUT: {e.stdout}")
            logger.error(f"STDERR: {e.stderr}")
            raise

        segment_info = json.loads(result.stdout)
        assert len(segment_info) == 1

        return segment_info[0]
