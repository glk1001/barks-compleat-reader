"""Orchestration around panel bounding boxes.

Reads per-page panels-segments JSON from disk, extracts source box sizes from
:class:`CleanPage` objects, and delegates all arithmetic to
:mod:`.panel_geometry`. This module owns the I/O, logging, and page-type
filtering — the pure geometry lives in ``panel_geometry``.
"""

import json
from pathlib import Path
from typing import Literal

from loguru import logger

from .comics_consts import (
    DEST_TARGET_HEIGHT,
    DEST_TARGET_WIDTH,
    DEST_TARGET_X_MARGIN,
    PAGES_WITHOUT_PANELS,
    PANELS_BBOX_HEIGHT_SIMILARITY_MARGIN,
)
from .comics_utils import dest_file_is_older_than_srce, get_abbrev_path
from .page_classes import CleanPage, ComicDimensions, RequiredDimensions, SrceAndDestPages
from .panel_geometry import (
    BoundingBox,
    centered_bbox,
    compute_box_size_stats,
    compute_page_num_y_bottom,
    compute_required_panels_bbox_size,
    scale_height,
)

warn_on_panels_bbox_height_less_than_av: Literal[True, False] = True


def get_panels_bounding_box_from_file(panels_segments_file: Path) -> BoundingBox:
    """Read the overall panels bounding box from a panels-segments JSON file."""
    with panels_segments_file.open() as f:
        segment_info = json.load(f)

    x_min, y_min, x_max, y_max = segment_info["overall_bounds"]
    return BoundingBox(x_min, y_min, x_max, y_max)


def get_required_panels_bbox_width_height(
    srce_pages: list[CleanPage],
    required_page_height: int,
    required_page_number_height: int,
) -> tuple[ComicDimensions, RequiredDimensions]:
    """Compute source and required destination panel-bbox dimensions.

    Args:
        srce_pages: All source pages for a comic; pages without panels are skipped.
        required_page_height: Destination page height in pixels.
        required_page_number_height: Height of the rendered page-number text.

    """
    panel_sizes = [
        (p.panels_bbox.get_width(), p.panels_bbox.get_height())
        for p in srce_pages
        if p.page_type not in PAGES_WITHOUT_PANELS
    ]

    if not panel_sizes:
        # Every page is a full-page image with no panels (e.g. the "All Covers"
        # collection). There are no panel dimensions to compute, and a
        # PAGES_WITHOUT_PANELS page's dest bbox is the whole page (it ignores these
        # dimensions), so return the unset defaults rather than dividing by nothing.
        return ComicDimensions(), RequiredDimensions()

    stats = compute_box_size_stats(panel_sizes, PANELS_BBOX_HEIGHT_SIMILARITY_MARGIN)
    assert stats.avg_width > 0
    assert stats.avg_height > 0

    required_width, required_height = compute_required_panels_bbox_size(
        stats.avg_width,
        stats.avg_height,
        DEST_TARGET_WIDTH,
        DEST_TARGET_X_MARGIN,
    )
    page_num_y_bottom = compute_page_num_y_bottom(
        required_page_height,
        required_height,
        required_page_number_height,
    )

    return (
        ComicDimensions(
            stats.min_width,
            stats.max_width,
            stats.min_height,
            stats.max_height,
            stats.avg_width,
            stats.avg_height,
        ),
        RequiredDimensions(required_width, required_height, page_num_y_bottom),
    )


def set_srce_panel_bounding_boxes(
    srce_pages: list[CleanPage],
    srce_panels_segment_info_files: list[Path],
    check_srce_page_timestamps: bool,
) -> None:
    """Populate ``panels_bbox`` on each source page from its segments file."""
    logger.debug("Setting srce panel bounding boxes.")

    for srce_page, srce_panels_segment_info_file in zip(
        srce_pages, srce_panels_segment_info_files, strict=True
    ):
        if srce_page.page_type in PAGES_WITHOUT_PANELS:
            continue
        if not srce_panels_segment_info_file.is_file():
            msg = f'Could not find panels segments info file "{srce_panels_segment_info_file}".'
            raise FileNotFoundError(msg)
        if check_srce_page_timestamps and dest_file_is_older_than_srce(
            Path(srce_page.page_filename),
            srce_panels_segment_info_file,
        ):
            msg = (
                f'Panels segments info file "{srce_panels_segment_info_file}"'
                f' is older than srce image file "{srce_page.page_filename}".'
            )
            raise RuntimeError(msg)
        srce_page.panels_bbox = get_panels_bounding_box_from_file(srce_panels_segment_info_file)

    logger.debug("")


def set_dest_panel_bounding_boxes(
    srce_dim: ComicDimensions,
    required_dim: RequiredDimensions,
    pages: SrceAndDestPages,
) -> None:
    """Populate ``panels_bbox`` on each destination page from the source dimensions."""
    logger.debug("Setting dest panel bounding boxes.")

    for srce_page, dest_page in zip(pages.srce_pages, pages.dest_pages, strict=True):
        dest_page.panels_bbox = _get_dest_panels_bounding_box(srce_dim, required_dim, srce_page)

    logger.debug("")


def _get_dest_panels_bounding_box(
    srce_dim: ComicDimensions,
    required_dim: RequiredDimensions,
    srce_page: CleanPage,
) -> BoundingBox:
    if srce_page.page_type in PAGES_WITHOUT_PANELS:
        return BoundingBox(0, 0, DEST_TARGET_WIDTH - 1, DEST_TARGET_HEIGHT - 1)

    assert srce_dim.min_panels_bbox_width != -1
    assert required_dim.panels_bbox_width != -1
    assert srce_dim.av_panels_bbox_height > 0

    required_panels_width = required_dim.panels_bbox_width
    srce_panels_bbox_width = srce_page.panels_bbox.get_width()
    srce_panels_bbox_height = srce_page.panels_bbox.get_height()

    if srce_panels_bbox_height >= (
        srce_dim.av_panels_bbox_height - PANELS_BBOX_HEIGHT_SIMILARITY_MARGIN
    ):
        required_panels_height = required_dim.panels_bbox_height
    else:
        required_panels_height = scale_height(
            required_panels_width,
            srce_panels_bbox_width,
            srce_panels_bbox_height,
        )
        log_panel_warning = (
            logger.warning if warn_on_panels_bbox_height_less_than_av else logger.debug
        )
        log_panel_warning(
            f'For "{get_abbrev_path(srce_page.page_filename)}",'
            f" panels bbox height {srce_panels_bbox_height}"
            f" < {srce_dim.av_panels_bbox_height - PANELS_BBOX_HEIGHT_SIMILARITY_MARGIN}"
            f" (= average height:{srce_dim.av_panels_bbox_height}"
            f" - error:{PANELS_BBOX_HEIGHT_SIMILARITY_MARGIN})."
            f" So setting required bbox height to {required_panels_height},"
            f" not {required_dim.panels_bbox_height}.",
        )

    return centered_bbox(
        DEST_TARGET_WIDTH,
        DEST_TARGET_HEIGHT,
        required_panels_width,
        required_panels_height,
        DEST_TARGET_X_MARGIN,
    )
