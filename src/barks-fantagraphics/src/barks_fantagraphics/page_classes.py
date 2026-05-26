from dataclasses import dataclass

from .comics_consts import PageType
from .panel_geometry import BoundingBox


@dataclass(frozen=True, slots=True)
class OriginalPage:
    page_filenames: str
    page_type: PageType
    # Fantagraphics volume this page is sourced from. ``None`` means "use the
    # comic's own (single) volume" - the normal case. It is set only for
    # multi-volume collection comics (e.g. the "All One-Pagers" collection)
    # whose pages are gathered from several different volumes.
    fanta_volume: int | None = None


class CleanPage:
    def __init__(
        self,
        page_filename: str,
        page_type: PageType,
        page_num: int = -1,
    ) -> None:
        self.page_filename = page_filename
        self.page_type = page_type
        self.page_num: int = page_num
        self.panels_bbox: BoundingBox = BoundingBox()


@dataclass(frozen=True, slots=True)
class SrceAndDestPages:
    srce_pages: list[CleanPage]
    dest_pages: list[CleanPage]


@dataclass(frozen=True, slots=True)
class RequiredDimensions:
    panels_bbox_width: int = -1
    panels_bbox_height: int = -1
    page_num_y_bottom: int = -1


@dataclass(frozen=True, slots=True)
class ComicDimensions:
    min_panels_bbox_width: int = -1
    max_panels_bbox_width: int = -1
    min_panels_bbox_height: int = -1
    max_panels_bbox_height: int = -1
    av_panels_bbox_width: int = -1
    av_panels_bbox_height: int = -1
