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

import hashlib
import re
import zipfile
from itertools import pairwise
from typing import TYPE_CHECKING, Any, ClassVar

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_book_info import BARKS_TITLE_INFO
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO, SERIES_EXTRAS
from okf_reader.core.backgrounds import PageBackground
from okf_reader.core.theme import ViewerThemeSpec
from okf_reader.core.top_bar import TopBarSpec

from .image_pipeline import encode_png_stream
from .image_selector import ImageSelector
from .panel_image_loader import load_panel_pil
from .reader_consts_and_types import (
    ACTION_BAR_BG_COLOR,
    ACTION_BAR_SEPARATOR_COLOR,
    RAW_ACTION_BAR_ICON_WIDTH,
    RAW_ACTION_BAR_SIZE_Y,
    RAW_QUIT_FENCE_WIDTH,
)
from .reader_file_paths import ALL_TYPES
from .reader_file_paths_resolver import ReaderFilePathsResolver
from .reader_formatter import escape_kivy_markup, get_action_bar_title
from .reader_palette import color_to_markup_hex, theme

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from .reader_formatter import FontManagerProtocol
    from .reader_settings import ReaderSettings
    from .system_file_paths import SystemFilePaths

WIKI_TITLE = "Carl Barks Wiki"


def wiki_session_path(app_data_dir: Path, bundle: Path) -> Path:
    """Return the wiki session file for ``bundle``, under the app data dir.

    One join for both hosts: the embedded wiki screen and scripts/read_okf.py
    resume from the same file for the same bundle. The name is keyed by the
    resolved bundle path so opening a *different* OKF bundle with the CLI can
    never clobber the Barks wiki's resume point (the session payload itself is
    only a bundle-relative page path).
    """
    digest = hashlib.sha256(str(bundle.resolve()).encode("utf-8")).hexdigest()[:12]
    return app_data_dir / f"okf-reader-session-{digest}.json"


def wiki_top_bar_spec(
    font_manager: FontManagerProtocol,
    sys_paths: SystemFilePaths,
    on_close: Callable[[], None] | None = None,
) -> TopBarSpec:
    """Dress the okf viewer's bar like the Barks screens' action bars.

    The one builder both hosts use: the Carl Barks-font title markup, the app
    window icon, the stock go-back/close icons, and the shared action-bar
    style constants (reader_consts_and_types), so the wiki bar can't drift
    from the kv bars. ``on_close`` is the Quit button's action — the embedded
    screen passes its leave-this-screen handler; the standalone launcher
    leaves the default (stop the app).
    """
    return TopBarSpec(
        title_markup=get_action_bar_title(font_manager, WIKI_TITLE),
        title_color=theme().app_title,
        icon_path=sys_paths.get_barks_reader_app_window_icon_path(),
        back_icon_path=sys_paths.get_barks_reader_go_back_icon_file(),
        contrast_on_icon_path=sys_paths.get_barks_reader_contrast_on_icon_file(),
        contrast_off_icon_path=sys_paths.get_barks_reader_contrast_off_icon_file(),
        close_icon_path=sys_paths.get_barks_reader_close_icon_file(),
        height=RAW_ACTION_BAR_SIZE_Y,
        on_close=on_close,
        bg_color=ACTION_BAR_BG_COLOR,
        separator_color=ACTION_BAR_SEPARATOR_COLOR,
        icon_width=RAW_ACTION_BAR_ICON_WIDTH,
        quit_fence_width=RAW_QUIT_FENCE_WIDTH,
    )


def wiki_theme_spec() -> ViewerThemeSpec:
    """Color the okf viewer from the app's active palette (reader_palette.theme()).

    The `ViewerThemeSpec` counterpart of `wiki_top_bar_spec`: maps the app's
    `ReaderTheme` roles onto the viewer's themable colors so the wiki screen
    wears the same palette as the rest of the app — selection band from
    `accent_selection`, tree/heading/search-title gold from `text_title`, quiet
    text from `text_secondary`, striping and focus ring from their roles.
    Read lazily at build time (the viewer is built on first open, after the
    theme is set). Hyperlinks keep the viewer's default blue (`link_hex`
    unset) — links are recognizable working parts, not a themed accent. The
    tree directory rows stay the default white (`dir_text` unset).
    """
    title_hex = color_to_markup_hex(theme().text_title).lstrip("#")
    return ViewerThemeSpec(
        selection=theme().accent_selection,
        title_text=theme().text_title,
        secondary_text=theme().text_secondary,
        row_stripe_even=theme().row_stripe_even,
        row_stripe_odd=theme().row_stripe_odd,
        focus_ring=theme().focus_ring,
        heading_hex=title_hex,
        title_hex=title_hex,
        crumb_hex=color_to_markup_hex(theme().text_secondary).lstrip("#"),
        icon_tint=theme().icon_tint,
    )


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


def story_page_title(frontmatter: dict[str, Any], page_path: Path) -> Titles | None:
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


def tree_navigable_title(frontmatter: dict[str, Any], page_path: Path) -> Titles | None:
    """Like `story_page_title`, but only titles with a place in the main tree.

    Extras (the non-comic articles) are in ``ALL_FANTA_COMIC_BOOK_INFO`` but
    have no chronological tree position — navigating to one would fail — so the
    wiki's "Goto Title" action gates on this instead of the plain story gate.
    """
    title_enum = story_page_title(frontmatter, page_path)
    if title_enum is None:
        return None
    if ALL_FANTA_COMIC_BOOK_INFO[title_enum].series_name == SERIES_EXTRAS:
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


def title_can_have_wiki_page(title_enum: Titles) -> bool:
    """Whether a wiki story-page location exists for ``title_enum`` at all.

    False when the title has no Fantagraphics entry or its series has no story
    directory — `wiki_page_for_title` can never find those, as opposed to a
    page that simply is not written yet.
    """
    fanta_info = ALL_FANTA_COMIC_BOOK_INFO.get(title_enum)
    return fanta_info is not None and fanta_info.series_name in SERIES_TO_STORY_DIRS


class BarksPanelsImageProvider:
    """Back wiki pages with the Barks Reader's panel imagery (an okf ImageProvider).

    Wraps the app's own ``ImageSelector``: a story page draws from that title's
    panel images across every panel directory (favourites, insets, covers,
    splash, silhouettes, closeups, original art, B/W, AI, censorship); any other
    page gets a random image across all Fantagraphics titles, with the
    selector's recently-used tracking avoiding repeats. Panels may live in an
    encrypted zip, whose members kivy cannot open by filename — those are
    decrypted and re-encoded to PNG bytes here (``panel_image_loader.
    load_panel_pil`` is the allow-listed decrypt path).

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

    def background_for(self, frontmatter: dict[str, Any], page_path: Path) -> PageBackground | None:
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
            pil = load_panel_pil(panel, encrypted_zip=self._file_paths.barks_panels_are_encrypted)
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

    # Per-table wraps, keyed by the table's full (rewritten) header row — for
    # columns whose name is too generic to narrow globally. The "in Color"
    # series-overview table (concept/production/carl-barks-library-in-color)
    # holds full series titles in both its Series and Wiki columns; wrapping
    # those and the Span dates sooner fits the six-series table in the page
    # without touching the other tables' "Series" columns (covers, colorists).
    _TABLE_WRAP_WIDTHS: ClassVar[dict[tuple[str, ...], dict[str, int]]] = {
        ("Series", "INDUCKS", "Issues", "Span", "Contents", "Wiki"): {
            "Series": 22,
            "Span": 10,
            "Wiki": 20,
        },
    }

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
                # Cells arrive Kivy-markup-escaped (okf_reader.core.render._esc);
                # match that form of a title too — escape_kivy_markup mirrors it.
                self._non_barks_titles.add(escape_kivy_markup(title))

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
        per_table = self._TABLE_WRAP_WIDTHS.get(tuple(header), {})
        return [per_table.get(cell, self._WRAP_WIDTHS.get(cell)) for cell in header]
