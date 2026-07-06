# ruff: noqa: PLC0415
"""CLI entry point that opens an OKF bundle in the standalone OKF reader.

Mirrors scripts/read_comic.py: a thin typer command over a workspace package —
here ``okf_reader`` (its own package) — that pins the window to the primary
monitor and runs the Kivy app.

IMPORTANT: As in read_comic.py/main.py, nothing at module level may import kivy —
kivy reads its config and argv at import time, so it must only be imported after
the window Config has been decided (see ``_pin_window_to_primary_monitor`` and the
deferred ``okf_reader.ui.viewer`` import in ``main``). The module-level imports
below are all kivy-free: ``barks_reader.core`` by import-linter contract, and
``okf_reader.ui``'s package __init__ only sets KIVY_NO_ARGS (needed before the
first kivy import so typer, not kivy, owns the command line).

The window is sized exactly as read_comic.py sizes the comic reader (comic-page
aspect ratio plus the action-bar height), so the standalone OKF window matches
the Barks reader it will eventually be embedded into. The Barks packages are
imported here in the launcher only — okf_reader itself stays independent of them
(import-linter contract) and sets no window geometry, since when embedded the
Barks reader owns the window.
"""

import os
import re
import subprocess
import sys
from configparser import ConfigParser
from itertools import pairwise
from pathlib import Path
from typing import Annotated, ClassVar

import okf_reader.ui  # noqa: F401  — kivy-free: only sets KIVY_NO_ARGS for later kivy imports
import typer
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_reader.core.reader_consts_and_types import RAW_ACTION_BAR_SIZE_Y
from barks_reader.core.reader_utils import get_win_dimensions
from barks_reader.core.screen_metrics import SCREEN_METRICS, get_best_window_height_fit
from dotenv import load_dotenv
from okf_reader.core.actions import PageAction
from okf_reader.core.backgrounds import DirPerTitleImageProvider
from okf_reader.core.render import resolve_link

load_dotenv(Path(__file__).parent.parent / ".env.runtime")

BARKS_READER_SECTION = "Barks Reader"
DEFAULT_PANELS_DIR = "~/Books/Carl Barks/Barks Panels Pngs"

app = typer.Typer()


def _primary_monitor_window_geometry() -> tuple[int, int, int, int]:
    """Return ``(left, top, width, height)`` for a window pinned to the primary monitor.

    Mirrors scripts/read_comic.py:_primary_monitor_window_geometry so the standalone
    OKF window matches the comic reader's window.
    """
    primary = SCREEN_METRICS.get_primary_screen_info()
    margin = 20
    max_height = get_best_window_height_fit(primary.height_pixels) - margin
    win_width, content_h = get_win_dimensions(
        max_height - RAW_ACTION_BAR_SIZE_Y, primary.width_pixels
    )
    win_height = content_h + RAW_ACTION_BAR_SIZE_Y
    win_left = primary.monitor_x + round(primary.width_pixels / 2) - round(win_width / 2)
    win_top = primary.monitor_y + margin // 2
    return win_left, win_top, win_width, win_height


def _pin_window_to_primary_monitor() -> None:
    """Pin the Kivy window to the primary monitor.

    First kivy import of the process happens here, deliberately: the geometry is
    computed and written to Config before kivy can realize the window.

    Unlike read_comic.py (whose KIVY_HOME ini carries known-good values), the
    standalone launcher runs against whatever ~/.kivy/config.ini holds, so every
    graphics setting that affects placement is set explicitly. In particular
    ``resizable``: GNOME's Mutter clamps non-resizable windows to the focused
    monitor and refuses to move them across, silently defeating left/top
    (diagnosed on a two-monitor Wayland setup where a stale resizable=0 in
    ~/.kivy/config.ini kept the window off the primary).
    """
    win_left, win_top, win_width, win_height = _primary_monitor_window_geometry()

    from kivy.config import Config

    # Without position=custom, Kivy's SDL2 backend ignores left/top entirely.
    Config.set("graphics", "position", "custom")  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "resizable", "1")  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "left", win_left)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "top", win_top)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "width", win_width)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "height", win_height)  # ty: ignore[unresolved-attribute]


def _favourites_image_provider() -> DirPerTitleImageProvider | None:
    """Wire the Barks 'Favourites' panels tree as the background-image source.

    The panels root comes from barks-reader.ini's ``png_barks_panels_dir`` (the same
    key the Barks Reader uses), falling back to the stock location. Backgrounds are
    optional: no Favourites directory means the reader just runs without them.
    """
    panels_dir = DEFAULT_PANELS_DIR
    config_dir = os.environ.get("BARKS_READER_CONFIG_DIR")
    if config_dir:
        parser = ConfigParser()
        parser.read(Path(config_dir) / "barks-reader.ini")
        panels_dir = parser.get(BARKS_READER_SECTION, "png_barks_panels_dir", fallback=panels_dir)
    favourites = Path(os.path.expandvars(panels_dir)).expanduser() / "Favourites"
    return DirPerTitleImageProvider(favourites) if favourites.is_dir() else None


# Wiki story-page directory (under okf/concept/stories/) for each Fantagraphics
# series name, in candidate order — Gyro Gearloose and Misc material is filed
# across two dirs. "Extras" (introductions/appreciations) has no story pages.
_SERIES_TO_STORY_DIRS = {
    "Comics and Stories": ("comics-and-stories",),
    "Donald Duck Adventures": ("donald-duck-adventures",),
    "Donald Duck Short Stories": ("donald-duck-short-stories",),
    "Uncle Scrooge Adventures": ("uncle-scrooge-adventures",),
    "Uncle Scrooge Short Stories": ("uncle-scrooge-short-stories",),
    "Gyro Gearloose": ("gyro-gearloose-stories", "misc"),
    "Misc": ("misc", "gyro-gearloose-stories"),
    "One Pagers": ("one-pagers",),
}


def _story_slug(title: str) -> str:
    """Return a canonical title's wiki filename slug (CLAUDE.md wiki title convention).

    Lowercase; apostrophes dropped (not hyphenated); every other run of
    non-alphanumerics becomes a single hyphen; leading/trailing hyphens stripped.
    E.g. "You Can't Guess!" -> "you-cant-guess", 'Adventure "Down Under"' ->
    "adventure-down-under".
    """
    curly_apostrophe = chr(0x2019)  # U+2019 RIGHT SINGLE QUOTATION MARK
    lowered = title.lower().replace("'", "").replace(curly_apostrophe, "")
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")


def _canonical_title(text: str) -> Titles | None:
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


class ReadComicActionProvider:
    """Offer "Read Comic" on wiki story pages (an okf_reader PageActionProvider).

    A page qualifies when it lives under ``concept/stories/`` and its frontmatter
    title maps to a canonical Barks title with a Fantagraphics entry — the same
    gate scripts/read_comic.py itself applies. The comic reader is a separate
    Kivy app, so it launches as a subprocess; when the wiki reader is embedded
    in the Barks Reader this becomes an in-app screen switch instead.
    """

    def __init__(self) -> None:
        self._last_launch: subprocess.Popen | None = None

    def action_for(self, frontmatter: dict, page_path: Path) -> PageAction | None:
        """Return the "Read Comic" action for a story page, else None."""
        if ("concept", "stories") not in pairwise(page_path.parts):
            return None
        title = frontmatter.get("title")
        if not isinstance(title, str):
            return None
        title_enum = _canonical_title(title)
        if title_enum is None or title_enum not in ALL_FANTA_COMIC_BOOK_INFO:
            return None
        canonical = ENUM_TO_STR_TITLE[title_enum]
        return PageAction("Read Comic", lambda: self._launch(canonical))

    def _launch(self, canonical_title: str) -> None:
        if self._last_launch is not None and self._last_launch.poll() is None:
            return  # the comic reader we launched is still open; don't stack another
        script = Path(__file__).parent / "read_comic.py"
        self._last_launch = subprocess.Popen(  # noqa: S603
            [sys.executable, str(script), canonical_title],
            cwd=Path(__file__).parent.parent,
        )


def _resolve_start_page(bundle: Path, arg: str) -> tuple[Path | None, str]:
    """Resolve a CLI page argument — a bundle link or a canonical story title.

    Returns ``(page, "")`` on success, else ``(None, reason)``. A link is anything
    `resolve_link` accepts (bundle-relative or absolute, percent-encoded, bounded
    to the bundle). A title joins to its story page per the CLAUDE.md wiki title
    convention: series directory from our own ALL_FANTA_COMIC_BOOK_INFO entry,
    filename from `_story_slug`.
    """
    target = resolve_link(bundle / "index.md", arg, bundle)
    if target is not None:
        return target, ""
    title_enum = _canonical_title(arg)
    if title_enum is None:
        return None, f"no bundle page or canonical story title matches {arg!r}"
    fanta_info = ALL_FANTA_COMIC_BOOK_INFO.get(title_enum)
    if fanta_info is None:
        return None, f"{arg!r} is a known title but has no ALL_FANTA_COMIC_BOOK_INFO entry"
    story_dirs = _SERIES_TO_STORY_DIRS.get(fanta_info.series_name)
    if story_dirs is None:
        return None, f"{arg!r} is in series {fanta_info.series_name!r}, which has no story pages"
    slug = _story_slug(ENUM_TO_STR_TITLE[title_enum])  # slug the *canonical* form
    for story_dir in story_dirs:
        page = bundle / "concept" / "stories" / story_dir / f"{slug}.md"
        if page.is_file():
            return page, ""
    return None, f"{arg!r} is a known story but its wiki page is not written yet"


class BarksTableRewriter:
    """Decorate the wiki data tables per the CLAUDE.md wiki title convention.

    Non-Barks titles in a "Title" column are shown in parentheses, derived from
    **our own** ``is_barks_title`` in ``BARKS_TITLE_INFO`` — presentation applied
    at render time, never scraped from the wiki's markdown. Any "Barks?" flag
    column is dropped: it carries the same fact, and its check-mark glyph does
    not exist in the reader's monospace table font anyway. Lives in the launcher
    (the integration layer) so okf_reader stays free of Barks knowledge.
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


@app.command(help="Open an OKF knowledge bundle in the standalone reader.")
def main(
    bundle: Annotated[Path, typer.Argument(help="Path to the OKF bundle directory.")],
    page: Annotated[
        str | None,
        typer.Argument(
            help='Open at this bundle link (e.g. "reference/database.md") or at a'
            ' canonical story title (e.g. "Camera Crazy").'
        ),
    ] = None,
) -> None:
    if not bundle.is_dir():
        typer.echo(f"error: bundle {bundle} not found", err=True)
        raise typer.Exit(code=2)

    start_page: Path | None = None
    if page:
        start_page, error = _resolve_start_page(bundle, page)
        if start_page is None:
            typer.echo(f"error: {error}", err=True)
            raise typer.Exit(code=2)

    _pin_window_to_primary_monitor()

    # Deferred: okf_reader.ui.viewer imports kivy at module level, so it may only
    # be imported after _pin_window_to_primary_monitor has set the window Config.
    from okf_reader.ui.viewer import run

    run(
        bundle,
        image_provider=_favourites_image_provider(),
        table_rewriter=BarksTableRewriter(),
        start_page=start_page,
        action_provider=ReadComicActionProvider(),
    )


if __name__ == "__main__":
    app()
