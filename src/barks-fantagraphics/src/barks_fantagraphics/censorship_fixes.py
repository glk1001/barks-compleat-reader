"""The censorship-fixes CSV: the record of every fix made to a Fantagraphics scan.

Fantagraphics censored and mis-printed a fair amount of Barks, and the Compleat Barks
Reader puts it back. Each row here is one such correction - a line of dialogue restored,
a hat recoloured, a glitch cleaned - located by the Fantagraphics volume, the scan image
it lands on, and the panel within it. GLK maintains the file by hand; the volume, image
and printed-page columns are derived from the comics database by
`barks-ocr-censorship-csv`.

The rows are not one-to-one with the fix images on disk: several panels of one page each
get their own row, so `censorship_fix_pages` is the way to ask which *pages* were fixed.
"""

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from .barks_titles import ENUM_TO_STR_TITLE
from .comic_book_info import COVERS_SET
from .comics_consts import INTERNAL_DATA_DIR, PageType
from .comics_database import ComicsDatabase
from .pages import get_page_num_str, get_srce_and_dest_pages_in_order

CENSORSHIP_FIXES_CSV = INTERNAL_DATA_DIR / "censorship-fixes.csv"

CENSORSHIP_FIXES_HEADER = [
    "Volume",
    "Image",
    "Fanta_page",
    "Comic_page",
    "Panel",
    "Story",
    "Error_type",
    "Change_From",
    "Change_To",
]


# Story names in the CSV that predate the canonical title spellings. The curly
# apostrophe is the CSV's, and has to be matched exactly.
TITLE_ALIASES = {
    "The Mummy’s Ring": "Donald Duck and the Mummy's Ring",  # noqa: RUF001
    "Race to the South Seas": "Race to the South Seas!",
}


class CensorshipFixesError(Exception):
    """The censorship-fixes CSV could not be read, or one of its rows does not resolve."""


@dataclass(frozen=True, slots=True)
class CensorshipFixRow:
    """One row of the censorship-fixes CSV.

    Attributes:
        volume: The Fantagraphics volume number.
        image: The scan image stem the fix lands on, or "" for a whole-story row.
        fanta_page: The printed book page, or "" where the page has none.
        comic_page: The page within the story, or "" for a whole-story row.
        panel: The panel within that page - "6", "7,8", or "" for a whole page.
        story: The story, as an issue string ("WDCS 71") or a title ("Frozen Gold").
        error_type: "censorship" or "error".
        change_from: The text or artwork as Fantagraphics printed it.
        change_to: The text or artwork as restored.

    """

    volume: int
    image: str
    fanta_page: str
    comic_page: str
    panel: str
    story: str
    error_type: str
    change_from: str
    change_to: str

    def as_cells(self) -> list[str]:
        """Return the row as strings, in `CENSORSHIP_FIXES_HEADER` order.

        Returns:
            One cell per header column.

        """
        return [
            str(self.volume),
            self.image,
            self.fanta_page,
            self.comic_page,
            self.panel,
            self.story,
            self.error_type,
            self.change_from,
            self.change_to,
        ]


def read_censorship_fixes(file: Path = CENSORSHIP_FIXES_CSV) -> list[CensorshipFixRow]:
    """Read the censorship-fixes CSV.

    Args:
        file: The CSV to read. Defaults to the copy shipped with this package.

    Returns:
        One row per fix, in file order.

    Raises:
        CensorshipFixesError: If the file is missing, its header is not the expected one,
            or a row is the wrong width or does not start with a volume number.

    """
    if not file.is_file():
        msg = f'Censorship fixes file not found: "{file}".'
        raise CensorshipFixesError(msg)

    with file.open("r", newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)
        if header != CENSORSHIP_FIXES_HEADER:
            msg = f'Unexpected header in "{file}": {header}.'
            raise CensorshipFixesError(msg)

        rows = []
        for line_num, row in enumerate(reader, start=2):
            if not row:
                continue
            if len(row) != len(CENSORSHIP_FIXES_HEADER):
                # Every caller guards on CensorshipFixesError alone, so a hand-added row
                # with a column missing - or a stray unquoted comma splitting one in two -
                # has to be reported here rather than left to raise TypeError out of the
                # dataclass and past every handler.
                msg = (
                    f"Expected {len(CENSORSHIP_FIXES_HEADER)} columns on line {line_num} of"
                    f' "{file}", found {len(row)}: {row}.'
                )
                raise CensorshipFixesError(msg)
            volume, *rest = row
            if not volume.isdigit():
                msg = f'Volume is not a number on line {line_num} of "{file}": "{volume}".'
                raise CensorshipFixesError(msg)
            rows.append(CensorshipFixRow(int(volume), *rest))

    return rows


def censorship_fix_pages(rows: list[CensorshipFixRow]) -> dict[int, set[str]]:
    """Return the scan pages the CSV records a fix for, by volume.

    Whole-story rows are skipped: a story censored out of its volume entirely has no one
    page to point at, so it names no image.

    Args:
        rows: The rows, from `read_censorship_fixes`.

    Returns:
        Volume number to the set of image stems fixed in it.

    """
    pages: dict[int, set[str]] = {}
    for row in rows:
        if row.image:
            pages.setdefault(row.volume, set()).add(row.image)

    return pages


def resolve_censorship_story(comics_database: ComicsDatabase, story: str) -> str:
    """Resolve a `Story` cell to its canonical database title.

    Handles the CSV's padded issue strings ("WDCS  34"), issue strings that match both a
    story and that issue's cover, and the story names that predate a title's spelling.

    Args:
        comics_database: The comics database.
        story: The `Story` cell as written in the CSV.

    Returns:
        The canonical database title.

    Raises:
        CensorshipFixesError: If the story does not resolve to exactly one title.

    """
    if story in TITLE_ALIASES:
        return TITLE_ALIASES[story]

    covers = {ENUM_TO_STR_TITLE[title] for title in COVERS_SET}
    issue = re.sub(r"\s+", " ", story).strip()
    found, titles, _closest = comics_database.get_story_title_from_issue(issue)
    if found:
        story_titles = [t for t in titles if t not in covers]
        if len(story_titles) == 1:
            return story_titles[0]
        msg = f'Issue "{story}" matches {len(story_titles)} stories: {story_titles}.'
        raise CensorshipFixesError(msg)

    is_title, closest = comics_database.is_story_title(story)
    if is_title:
        return story

    msg = f'Story "{story}" is not a known title or issue. Closest match: "{closest}".'
    raise CensorshipFixesError(msg)


@dataclass(frozen=True, slots=True)
class CensorshipStoryPages:
    """Where a story's pages live in its volume's scans.

    Attributes:
        volume: The Fantagraphics volume number.
        body_images: Each comic page number's scan image stem.
        unnumbered_images: The stems of the story's pages that carry no comic page
            number - its cover, splash, front and back matter. A fix to one of those is
            recorded with an image and no page, since there is no page to name.

    """

    volume: int
    body_images: dict[str, str]
    unnumbered_images: frozenset[str]


def censorship_story_pages(comics_database: ComicsDatabase, title: str) -> CensorshipStoryPages:
    """Map a story's pages to the scan images they were printed on.

    `comics_helpers.get_volume_and_page` is not used here: it derives the image stem
    arithmetically as `first_stem + page - 1`, which is wrong wherever a story's BODY
    stems are not contiguous - `The Bill Collectors` maps page 3 to `227` and page 4
    to `195`.

    Args:
        comics_database: The comics database.
        title: The canonical database title.

    Returns:
        The story's volume and its numbered and unnumbered pages.

    """
    comic = comics_database.get_comic_book(title)
    srce_and_dest = get_srce_and_dest_pages_in_order(comic, get_full_paths=False)

    body_images = {}
    unnumbered_images = set()
    for srce, dest in zip(srce_and_dest.srce_pages, srce_and_dest.dest_pages, strict=True):
        stem = Path(srce.page_filename).stem
        if dest.page_type == PageType.BODY:
            body_images[get_page_num_str(dest)] = stem
        else:
            unnumbered_images.add(stem)

    return CensorshipStoryPages(comic.get_fanta_volume(), body_images, frozenset(unnumbered_images))


def story_page_offsets(page_pairs: list[tuple[str, str]]) -> set[int]:
    """Return the distinct steps a story's rows imply between its two page numbers.

    Both numbers advance one per page, so `Fanta_page - Comic_page` is one fixed offset
    for a whole story - its printed start page. More than one offset means a row names a
    page it does not belong to, and that can be seen without knowing where any story
    starts. Pairs that are not both plain numbers are skipped: a restored page carries a
    printed folio such as "188a", which sits between two pages rather than on one.

    Args:
        page_pairs: One story's `(comic_page, fanta_page)` cells.

    Returns:
        Every distinct offset the pairs imply. One offset - or none, when no pair is
        usable - means the rows agree.

    """
    return {
        int(fanta_page) - int(comic_page)
        for comic_page, fanta_page in page_pairs
        if comic_page.isdigit() and fanta_page.isdigit()
    }


def story_page_offsets_disagree(page_pairs: list[tuple[str, str]]) -> bool:
    """Return whether a story's rows contradict each other about where it starts.

    One offset means the rows agree. More than one usually means a row names a page it
    does not belong to - but not always: a page restored into the middle of a story is
    printed on a folio such as "188a", between two pages rather than on one, so every
    page after it sits one printed page lower than the pages before. `The Bill
    Collectors` is exactly that, and its rows are right. So one extra offset is allowed
    per folio the story carries.

    Distinct folios, not folio rows: several panels of one restored page each get their
    own row, and counting those would widen the allowance a page at a time until it
    covered a genuinely mis-numbered row.

    Args:
        page_pairs: One story's `(comic_page, fanta_page)` cells.

    Returns:
        True if the rows cannot all be describing the same story.

    """
    folios = {
        fanta_page
        for _comic_page, fanta_page in page_pairs
        if fanta_page and not fanta_page.isdigit()
    }

    return len(story_page_offsets(page_pairs)) > 1 + len(folios)
