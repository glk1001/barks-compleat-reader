from dataclasses import dataclass

from .comics_consts import PageType
from .panel_geometry import BoundingBox


@dataclass(frozen=True, slots=True)
class OriginalPage:
    page_filenames: str
    page_type: PageType


def get_collection_pages(
    first_page: int, num_pages: int, page_type: PageType
) -> list[OriginalPage]:
    """Return the pages of a synthetic collection, numbered in a row.

    The "All One-Pagers" and "All Covers" collections are staged as extra pages of a
    nominal volume, one page per located item, numbered from a base above any real page.

    Args:
        first_page: The first page's number in the nominal volume.
        num_pages: How many pages the collection has.
        page_type: The type every page has.

    Returns:
        The pages, in order; empty for an empty collection.

    """
    return [OriginalPage(f"{first_page + i:03d}", page_type) for i in range(num_pages)]


class CleanPage:
    def __init__(
        self,
        page_filename: str,
        page_type: PageType,
        page_num: int = -1,
        use_arabic_page_num: bool = False,
    ) -> None:
        self.page_filename = page_filename
        self.page_type = page_type
        self.page_num: int = page_num
        self.panels_bbox: BoundingBox = BoundingBox()
        # Front-matter pages normally take roman numerals, which only run to "x". The
        # synthetic collections are hundreds of cover pages long, so they are numbered
        # as an ordinary book instead.
        self.use_arabic_page_num = use_arabic_page_num


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
