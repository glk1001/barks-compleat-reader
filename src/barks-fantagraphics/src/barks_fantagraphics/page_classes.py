from dataclasses import dataclass

from .comics_consts import PageType
from .panel_bounding_boxes import BoundingBox


@dataclass(frozen=True, slots=True)
class OriginalPage:
    page_filenames: str
    page_type: PageType


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
