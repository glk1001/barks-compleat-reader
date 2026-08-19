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
from dataclasses import dataclass
from pathlib import Path

from .comics_consts import INTERNAL_DATA_DIR

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


class CensorshipFixesError(Exception):
    """The censorship-fixes CSV could not be read."""


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
            or a row's volume is not a number.

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
