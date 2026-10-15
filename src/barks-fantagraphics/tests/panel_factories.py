"""Panel-box factories the panel tests share.

Reached as a top-level module: ``conftest.py`` puts this directory on ``sys.path``.
"""

from __future__ import annotations

from barks_fantagraphics.panel_boxes import PagePanelBoxes, PanelBox


def make_panel_box(
    panel_num: int = 1, x0: int = 10, y0: int = 20, x1: int = 100, y1: int = 200
) -> PanelBox:
    """Make a panel box whose width and height follow from its corners."""
    return PanelBox(panel_num=panel_num, x0=x0, y0=y0, x1=x1, y1=y1, w=x1 - x0, h=y1 - y0)


def make_page_panel_boxes(
    panels: list[PanelBox] | None = None,
    overall: PanelBox | None = None,
    page_width: int = 800,
    page_height: int = 600,
) -> PagePanelBoxes:
    """Make page 001's panel boxes; the overall bound defaults to the whole page."""
    if overall is None:
        overall = make_panel_box(0, 0, 0, page_width - 1, page_height - 1)
    return PagePanelBoxes(
        page_num="001",
        page_width=page_width,
        page_height=page_height,
        overall_bounds=overall,
        panel_boxes=panels or [],
    )
