"""The page number printed in the book for a Fantagraphics scan image.

A scan's file name is not its printed page: image `040` of volume 18 carries the folio
33. The two differ by a fixed offset through a volume, because the scans include the
book's cover and front matter, so this module only has to record that offset.

The numbers began as INDUCKS printed pages, in the barks-wiki `ccbdl-contents.md` table.
They live here so that nothing has to reach into another repo to read one, and
`barks-comic-building`'s `test_printed_pages_match_wiki.py` holds the two in step.

The contents table lists stories only, so the offset is cross-checked up to each volume's
last story and extrapolated past it into the cover galleries. A full-page cover carries
no folio of its own, so a number given for one is its position in the page sequence.
"""

from typing import Final

from .barks_covers import COVER_COLLECTION_PAGE_BASE
from .comic_book import ComicBook, get_page_str

# Volume to image number minus printed page.
_PRINTED_PAGE_OFFSETS: Final[dict[int, int]] = {
    1: 7,
    2: 6,
    3: 9,
    4: 6,
    5: 5,
    6: 5,
    7: 13,
    8: 6,
    9: 5,
    10: 5,
    11: 5,
    12: 7,
    13: 5,
    14: 5,
    15: 5,
    16: 7,
    17: 6,
    18: 7,
    19: 6,
    20: 6,
    21: 6,
    22: 7,
    23: 6,
    24: 5,
    25: 5,
    26: 6,
    27: 6,
    28: 7,
    29: 7,
    30: 7,
}

# Volume to (first image, new offset), where a volume's offset changes part way through.
# Volume 7's "The Short Stories" divider is image 120: image 119 is printed page 106, and
# image 121 is printed page 109.
_PRINTED_PAGE_OFFSET_STEPS: Final[dict[int, tuple[int, int]]] = {7: (121, 12)}

# Pages whose printed number is not a plain number.
_PRINTED_FOLIOS: Final[dict[tuple[int, str], str]] = {
    (4, "227"): "188a",  # "The Bill Collectors" page restored between 188 and 189.
}

# Scanned pages that carry no page number.
_UNNUMBERED_IMAGES: Final[frozenset[tuple[int, str]]] = frozenset(
    {
        (7, "120"),  # The "The Short Stories" divider.
    }
)

# Volume to the images of the stories Fantagraphics censored out of it: they are restored
# here, but the book never printed them.
_CENSORED_OUT_STORIES: Final[dict[int, range]] = {
    1: range(258, 268),  # "Good Deeds"
    3: range(250, 260),  # "Silent Night"
}


def get_printed_page(volume: int, image: str) -> str | None:
    """Return the page number printed in the book for a scan image.

    Args:
        volume: The Fantagraphics volume number.
        image: The scan image stem, such as "040".

    Returns:
        The printed page, which can be a folio such as "188a", or None if the image has no
        printed page: front matter before page 1, an unnumbered divider, a page added to
        the volume, a story censored out of it, or a collection's own page numbering.

    """
    if not image.isdigit():
        return None

    page = int(image)
    stem = get_page_str(page)

    if (volume, stem) in _PRINTED_FOLIOS:
        return _PRINTED_FOLIOS[(volume, stem)]

    offset = _PRINTED_PAGE_OFFSETS.get(volume)
    if (
        offset is None
        or page >= COVER_COLLECTION_PAGE_BASE
        or (volume, stem) in _UNNUMBERED_IMAGES
        or page in _CENSORED_OUT_STORIES.get(volume, ())
        or ComicBook.is_fixes_special_case_added(volume, stem)
    ):
        return None

    step = _PRINTED_PAGE_OFFSET_STEPS.get(volume)
    if step is not None and page >= step[0]:
        offset = step[1]

    printed_page = page - offset

    return str(printed_page) if printed_page >= 1 else None
