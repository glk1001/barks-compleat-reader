"""The Barks side of the OKF wiki reader — kivy-free integration providers.

Everything here fills an ``okf_reader.core`` port with Barks knowledge, per
the CLAUDE.md wiki title convention: identity is the plain canonical title
(join via frontmatter ``title`` or the filename slug); parentheses are
presentation applied at render time from **our own** ``is_barks_title``;
okf_reader itself stays generic. Shared by the standalone launcher
(scripts/read_okf.py) and the embedded wiki screen. UI-side pieces (fonts,
icons, screen switching) do not belong here — barks_reader.core may not
import okf_reader.ui or kivy (import-linter contract 1).
"""

from __future__ import annotations

import re
import zipfile
from itertools import pairwise
from typing import TYPE_CHECKING, ClassVar

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from okf_reader.core.backgrounds import PageBackground

from barks_reader.core.image_pipeline import encode_png_stream, load_pil
from barks_reader.core.image_selector import ImageSelector
from barks_reader.core.reader_file_paths import ALL_TYPES
from barks_reader.core.reader_file_paths_resolver import ReaderFilePathsResolver

if TYPE_CHECKING:
    from pathlib import Path

    from barks_reader.core.reader_settings import ReaderSettings

WIKI_TITLE = "Carl Barks Wiki"

# Wiki story-page directory (under okf/concept/stories/) for each Fantagraphics
# series name, in candidate order — Gyro Gearloose and Misc material is filed
# across two dirs. "Extras" (introductions/appreciations) has no story pages.
SERIES_TO_STORY_DIRS = {
    "Comics and Stories": ("comics-and-stories",),
    "Donald Duck Adventures": ("donald-duck-adventures",),
    "Donald Duck Short Stories": ("donald-duck-short-stories",),
    "Uncle Scrooge Adventures": ("uncle-scrooge-adventures",),
    "Uncle Scrooge Short Stories": ("uncle-scrooge-short-stories",),
    "Gyro Gearloose": ("gyro-gearloose-stories", "misc"),
    "Misc": ("misc", "gyro-gearloose-stories"),
    "One Pagers": ("one-pagers",),
}


def story_slug(title: str) -> str:
    """Return a canonical title's wiki filename slug (CLAUDE.md wiki title convention).

    Lowercase; apostrophes dropped (not hyphenated); every other run of
    non-alphanumerics becomes a single hyphen; leading/trailing hyphens stripped.
    E.g. "You Can't Guess!" -> "you-cant-guess", 'Adventure "Down Under"' ->
    "adventure-down-under".
    """
    curly_apostrophe = chr(0x2019)  # U+2019 RIGHT SINGLE QUOTATION MARK
    lowered = title.lower().replace("'", "").replace(curly_apostrophe, "")
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")


def canonical_title(text: str) -> Titles | None:
    """Map a display title to its Titles enum, tolerating quoted display forms.

    Canonical titles are quote-free; the wiki pages show forms like
    'Adventure "Down Under"'.
    """
    title_enum = STR_TITLE_TO_ENUM.get(text)
    if title_enum is None:
        for quote in ('"', chr(0x201C), chr(0x201D)):  # straight/curly double quotes
            text = text.replace(quote, "")
        title_enum = STR_TITLE_TO_ENUM.get(text.strip())
    return title_enum


def story_page_title(frontmatter: dict, page_path: Path) -> Titles | None:
    """Return the canonical title of a wiki story page, or None for any other page.

    A story page lives under ``concept/stories/`` and its frontmatter title maps
    to a canonical Barks title with a Fantagraphics entry. The shared gate for
    everything keyed to "the story this page is about" (Read Comic button,
    title-specific backgrounds).
    """
    if ("concept", "stories") not in pairwise(page_path.parts):
        return None
    title = frontmatter.get("title")
    if not isinstance(title, str):
        return None
    title_enum = canonical_title(title)
    if title_enum is None or title_enum not in ALL_FANTA_COMIC_BOOK_INFO:
        return None
    return title_enum


def wiki_page_for_title(bundle: Path, title_enum: Titles) -> Path | None:
    """Return a title's wiki story page in ``bundle``, or None if not written yet.

    The reverse join of `story_page_title`: series directory from our own
    ALL_FANTA_COMIC_BOOK_INFO entry, filename from `story_slug` of the
    canonical title.
    """
    fanta_info = ALL_FANTA_COMIC_BOOK_INFO.get(title_enum)
    if fanta_info is None:
        return None
    story_dirs = SERIES_TO_STORY_DIRS.get(fanta_info.series_name)
    if story_dirs is None:
        return None
    slug = story_slug(ENUM_TO_STR_TITLE[title_enum])  # slug the *canonical* form
    for story_dir in story_dirs:
        page = bundle / "concept" / "stories" / story_dir / f"{slug}.md"
        if page.is_file():
            return page
    return None


class BarksPanelsImageProvider:
    """Back wiki pages with the Barks Reader's panel imagery (an okf ImageProvider).

    Wraps the app's own ``ImageSelector``: a story page draws from that title's
    panel images across every panel directory (favourites, insets, covers,
    splash, silhouettes, closeups, original art, B/W, AI, censorship); any other
    page gets a random image across all Fantagraphics titles, with the
    selector's recently-used tracking avoiding repeats. Panels may live in an
    encrypted zip, whose members kivy cannot open by filename — those are
    decrypted and re-encoded to PNG bytes here (``image_pipeline.load_pil`` is
    the allow-listed decrypt path).

    Pass the app's existing ``ImageSelector`` when embedding, so the wiki
    shares its no-repeat memory; the standalone launcher lets one be built.
    """

    def __init__(
        self, reader_settings: ReaderSettings, image_selector: ImageSelector | None = None
    ) -> None:
        self._file_paths = reader_settings.file_paths
        self._selector = image_selector or ImageSelector(
            ReaderFilePathsResolver(self._file_paths), reader_settings
        )
        self._all_titles = list(ALL_FANTA_COMIC_BOOK_INFO.values())

    def background_for(self, frontmatter: dict, page_path: Path) -> PageBackground | None:
        """Return a title-specific image for a story page, else a random one."""
        title_enum = story_page_title(frontmatter, page_path)
        if title_enum is not None:
            panel = self._selector.get_random_image_for_title(
                ENUM_TO_STR_TITLE[title_enum], ALL_TYPES
            )
        else:
            panel = self._selector.get_random_image(self._all_titles).filename
        if panel is None:
            return None
        if isinstance(panel, zipfile.Path):
            pil = load_pil(panel, encrypted_zip=self._file_paths.barks_panels_are_encrypted)
            return PageBackground(ext=".png", data=encode_png_stream(pil).getvalue())
        return PageBackground(ext=panel.suffix, path=panel)


class BarksTableRewriter:
    """Decorate the wiki data tables per the CLAUDE.md wiki title convention.

    Non-Barks titles in a "Title" column are shown in parentheses, derived from
    **our own** ``is_barks_title`` in ``BARKS_TITLE_INFO`` — presentation applied
    at render time, never scraped from the wiki's markdown. Any "Barks?" flag
    column is dropped: it carries the same fact, and its check-mark glyph does
    not exist in the reader's monospace table font anyway.
    """

    # Columns holding canonical story titles, whatever the table calls them
    # (chronology/payments/bibliography use "Title", tags "Story", covers
    # "Illustrates").
    _TITLE_COLUMNS = ("Title", "Story", "Illustrates")

    # Tighter per-column wraps for the wide tag-vocabulary table: Tag and Story
    # cells wrap sooner than the global default, and the mostly-empty
    # "Orig. pages" column may not inflate to the width of its one long
    # page-list cell.
    _WRAP_WIDTHS: ClassVar[dict[str, int]] = {"Tag": 20, "Story": 24, "Orig. pages": 12}

    # Shorter display names for headers wider than their column's values — the
    # chronology's "Issue date" header (10 chars over 7-char YYYY-MM values)
    # was the few characters that pushed the table past a comic-page-width
    # window.
    _HEADER_RENAMES: ClassVar[dict[str, str]] = {"Issue date": "Date"}

    def __init__(self) -> None:
        self._non_barks_titles = set()
        for cbi in BARKS_TITLE_INFO:
            if not cbi.is_barks_title:
                title = cbi.get_title_str()
                self._non_barks_titles.add(title)
                # Cells arrive Kivy-markup-escaped; match that form of a title too.
                self._non_barks_titles.add(
                    title.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")
                )

    def rewrite(
        self, header: list[str], body: list[list[str]]
    ) -> tuple[list[str], list[list[str]]]:
        """Parenthesize non-Barks titles and drop a "Barks?" column, if present."""
        title_cols = {c for c, cell in enumerate(header) if cell in self._TITLE_COLUMNS}
        if title_cols:
            body = [
                [
                    f"({cell})" if c in title_cols and cell in self._non_barks_titles else cell
                    for c, cell in enumerate(row)
                ]
                for row in body
            ]
        if "Barks?" in header:
            flag_col = header.index("Barks?")
            header = [cell for c, cell in enumerate(header) if c != flag_col]
            body = [[cell for c, cell in enumerate(row) if c != flag_col] for row in body]
        header = [self._HEADER_RENAMES.get(cell, cell) for cell in header]
        return header, body

    def wrap_widths(self, header: list[str]) -> list[int | None]:
        """Return the per-column wrap overrides for the known wide wiki tables."""
        return [self._WRAP_WIDTHS.get(cell) for cell in header]
