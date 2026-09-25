"""Standalone validator for Barks Reader runtime files.

Aggregates every missing or invalid asset discovered across config, system
files, panel sources, intro/appendix documents, Fantagraphics archives,
prebuilt comics, per-title panel files, per-title layouts (with their
panel-segments JSONs) and the wiki story-page joins into a single report.
Exits non-zero on any failure.
"""

import os
import time
import zipfile
from collections.abc import Iterator
from configparser import ConfigParser
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePath

from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comic_book_info import (
    COVERS_SET,
    NON_COMIC_TITLES,
    ONE_PAGERS,
    get_filename_from_title,
    is_one_pager_collection,
    is_one_pager_located,
)
from barks_fantagraphics.comics_consts import PAGES_WITHOUT_PANELS
from barks_fantagraphics.comics_database import ComicsDatabase, TitleNotFoundError
from barks_fantagraphics.comics_utils import (
    get_dest_comic_zip_file_stem,
    get_timestamp_as_str,
)
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    FantaComicBookInfo,
    get_fanta_volume_from_str,
)
from barks_fantagraphics.page_classes import CleanPage
from barks_fantagraphics.pages import get_srce_and_dest_pages_in_order
from barks_reader.core.comic_book_page_info import ComicLayoutBuilder
from barks_reader.core.fantagraphics_volumes import (
    DuplicateArchiveFilesError,
    EmptyArchiveError,
    FantagraphicsArchive,
    FantagraphicsVolumeArchives,
    MissingArchiveFilesError,
    PageExtError,
    PageNumError,
    TooManyArchiveFilesError,
    TooManyOverrideDirsError,
)
from barks_reader.core.image_pipeline import load_pil as reader_load_pil
from barks_reader.core.page_info_adapters import FantagraphicsPanelSegmentsAdapter
from barks_reader.core.reader_utils import is_blank_page, is_title_page
from barks_reader.core.system_file_paths import SystemFilePaths
from barks_reader.core.wiki_integration import (
    SERIES_TO_STORY_DIRS,
    canonical_title,
    story_page_title,
    story_slug,
    title_can_have_wiki_page,
    wiki_page_for_title,
)
from comic_utils.comic_consts import (
    CBZ_FILE_EXT,
    JPG_FILE_EXT,
    JSON_FILE_EXT,
    PNG_FILE_EXT,
    PanelPath,
)
from comic_utils.decryption import DecryptionError
from dotenv import load_dotenv
from loguru import logger
from okf_reader.core.render import parse_frontmatter

# Load env vars (BARKS_READER_CONFIG_DIR, BARKS_READER_DATA_DIR, ...) before
# importing barks_reader.core.config_info, which constructs nothing at module
# load time but does set Kivy/SDL env vars defensively.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env.runtime")

from barks_reader.core.config_info import ConfigInfo, find_fanta_volumes_dirpath  # noqa: E402
from barks_reader.core.reader_consts_and_types import NO_OVERRIDES_SUFFIX  # noqa: E402
from barks_reader.core.reader_file_paths import (  # noqa: E402
    EDITED_SUBDIR,
    BarksPanelsExtType,
    PanelDirNames,
    ReaderFilePaths,
)
from barks_reader.core.reader_settings import (  # noqa: E402
    FANTA_DIR,
    JPG_BARKS_PANELS_ZIP,
    PNG_BARKS_PANELS_DIR,
    PREBUILT_COMICS_DIR,
    UNSET_WIKI_BUNDLE_DIR_MARKER,
    USE_LIVE_WIKI_BUNDLE,
    WIKI_BUNDLE_DIR,
    WIKI_BUNDLE_SUBDIR,
    read_setting_from_config,
)

_PAGE_EXTS = (JPG_FILE_EXT, PNG_FILE_EXT)
_CROSSCHECK_MIN_VARIANTS = 2

_INTRO_ARTICLE = Titles.DON_AULT___FANTAGRAPHICS_INTRODUCTION
_APPENDIX_ARTICLES: tuple[Titles, ...] = (
    Titles.RICH_TOMMASO___ON_COLORING_BARKS,
    Titles.DON_AULT___LIFE_AMONG_THE_DUCKS,
    Titles.MAGGIE_THOMPSON___COMICS_READERS_FIND_COMIC_BOOK_GOLD,
    Titles.GEORGE_LUCAS___AN_APPRECIATION,
)


# ---------------------------------------------------------------------------
# Error collection
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PhaseResult:
    """Aggregated outcome for a single validation phase."""

    name: str
    errors: list[str] = field(default_factory=list)
    items_checked: int = 0
    skipped: bool = False
    summary_extra: str = ""

    def add(self, msg: str) -> None:
        """Record an error message and emit it via loguru."""
        self.errors.append(msg)
        logger.error(f"[{self.name}] {msg}")

    @property
    def failed(self) -> bool:
        """Return True if this phase recorded any errors."""
        return bool(self.errors)


class ErrorCollector:
    """Owns the ordered list of phase results and prints the final report."""

    def __init__(self) -> None:
        self._phases: list[PhaseResult] = []

    def start_phase(self, name: str, num: str) -> PhaseResult:
        """Begin a new phase, log a banner, and return its result object."""
        logger.info("")
        logger.info(f"=== Phase {num}: {name} ===")
        phase = PhaseResult(name=name)
        self._phases.append(phase)
        return phase

    @staticmethod
    def finalize_phase(phase: PhaseResult) -> None:
        """Emit the per-phase summary line."""
        if phase.skipped:
            logger.info(f"[{phase.name}] SKIPPED")
            return
        status = "FAIL" if phase.failed else "OK"
        extra = f" {phase.summary_extra}" if phase.summary_extra else ""
        logger.info(
            f"[{phase.name}] {status} ({len(phase.errors)} errors,"
            f" {phase.items_checked} checked){extra}"
        )

    @property
    def any_failed(self) -> bool:
        """Return True if any phase recorded errors."""
        return any(p.failed for p in self._phases)

    @property
    def phases(self) -> list[PhaseResult]:
        """Return the ordered list of phase results."""
        return self._phases


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def build_reader_file_paths(cfg_info: ConfigInfo, reader_files_dir: Path) -> list[ReaderFilePaths]:
    """Construct one :class:`ReaderFilePaths` per resolvable panel source.

    Always tries the JPG zip (the canonical source). Additionally, tries the
    PNG dir when the INI configures one and that directory exists. Returns
    them in JPG-first order; an empty list means neither variant could be
    opened (Phase 3 will already have logged the underlying error).
    """
    barks_config = ConfigParser()
    barks_config.read(cfg_info.app_config_path)

    candidates: list[tuple[Path, BarksPanelsExtType]] = [
        (reader_files_dir / JPG_BARKS_PANELS_ZIP, BarksPanelsExtType.JPG),
    ]
    try:
        png_dir = read_setting_from_config(barks_config, PNG_BARKS_PANELS_DIR)
    except Exception:  # noqa: BLE001
        png_dir = None
    png_path = png_dir if isinstance(png_dir, Path) else Path(png_dir) if png_dir else None
    if png_path is not None and png_path.is_dir():
        candidates.append((png_path, BarksPanelsExtType.MOSTLY_PNG))

    result: list[ReaderFilePaths] = []
    for panels_source, ext_type in candidates:
        if not panels_source.exists():
            continue
        file_paths = ReaderFilePaths()
        try:
            file_paths.set_barks_panels_source(panels_source, ext_type)
        except FileNotFoundError:
            # Panels source incomplete; inset paths still resolve relative
            # to the configured INSETS dir, so keep the object.
            result.append(file_paths)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"build_reader_file_paths: skipping {panels_source}: {exc}")
            continue
        else:
            result.append(file_paths)
    return result


def _check_dir(phase: PhaseResult, label: str, path: Path) -> bool:
    """Record an error if ``path`` is not an existing directory."""
    phase.items_checked += 1
    if not path.is_dir():
        phase.add(f"{label}: missing directory {path}")
        return False
    return True


def _check_file(phase: PhaseResult, label: str, path: Path) -> bool:
    """Record an error if ``path`` is not an existing file."""
    phase.items_checked += 1
    if not path.is_file():
        phase.add(f"{label}: missing file {path}")
        return False
    return True


def _check_dir_has_pages(phase: PhaseResult, label: str, path: Path) -> bool:
    """Verify ``path`` is a directory containing >=1 ``page-NNN.{jpg,png}`` file."""
    if not _check_dir(phase, label, path):
        return False
    phase.items_checked += 1
    pages = [
        p
        for p in path.iterdir()
        if p.is_file() and p.suffix.lower() in _PAGE_EXTS and p.name.startswith("page-")
    ]
    if not pages:
        phase.add(f"{label}: no page-NNN.(jpg|png) files in {path}")
        return False
    return True


def _check_dir_has_pngs(phase: PhaseResult, label: str, path: Path) -> bool:
    """Verify ``path`` is a directory containing >=1 ``*.png`` file."""
    if not _check_dir(phase, label, path):
        return False
    phase.items_checked += 1
    pngs = [p for p in path.iterdir() if p.is_file() and p.suffix.lower() == PNG_FILE_EXT]
    if not pngs:
        phase.add(f"{label}: no PNG files in {path}")
        return False
    return True


# ---------------------------------------------------------------------------
# Phase 1 - Config
# ---------------------------------------------------------------------------


def phase1_config(
    collector: ErrorCollector,
    app_config_dir: Path | None,
    app_data_dir: Path | None,
) -> ConfigInfo | None:
    """Apply optional CLI overrides, build :class:`ConfigInfo`, and verify paths.

    Args:
        collector: Aggregator for phase errors.
        app_config_dir: CLI override for the app config directory.
        app_data_dir: CLI override for the app data directory.

    Returns:
        The constructed :class:`ConfigInfo` or ``None`` if construction failed.

    """
    phase = collector.start_phase("Config", "1")

    if app_config_dir is not None:
        os.environ["BARKS_READER_CONFIG_DIR"] = str(app_config_dir)
    if app_data_dir is not None:
        os.environ["BARKS_READER_DATA_DIR"] = str(app_data_dir)

    try:
        cfg_info = ConfigInfo()
    except Exception as exc:  # noqa: BLE001 - config errors should aggregate, not crash
        phase.add(f"failed to construct ConfigInfo: {exc}")
        collector.finalize_phase(phase)
        return None

    _check_dir(phase, "app_dir", cfg_info.app_dir)
    _check_dir(phase, "app_config_dir", cfg_info.app_config_dir)
    _check_file(phase, "app_config_path", cfg_info.app_config_path)
    _check_dir(phase, "app_data_dir", cfg_info.app_data_dir)
    _check_dir(phase, "kivy_config_dir", cfg_info.kivy_config_dir)

    collector.finalize_phase(phase)

    return cfg_info


# ---------------------------------------------------------------------------
# Phase 2 - SystemFilePaths
# ---------------------------------------------------------------------------


def phase2_system_file_paths(
    collector: ErrorCollector,
    sys_paths: SystemFilePaths,
) -> None:
    """Verify every directory and file populated by ``set_barks_reader_files_dir``.

    Replicates the dir + file lists from
    ``SystemFilePaths._check_reader_files_dirs`` (kept in sync manually) and
    appends each missing entry to the collector instead of raising.
    """
    phase = collector.start_phase("System File Paths", "2")

    # Mirror the lists in SystemFilePaths._check_reader_files_dirs (private but
    # intentionally duplicated here so this script stays decoupled from the
    # raise-on-first-error path used by the running app).
    dirs_to_check: list[tuple[str, Path | None]] = [
        ("barks_reader_files_dir", sys_paths._barks_reader_files_dir),  # noqa: SLF001
        ("reader_icon_files_dir", sys_paths._reader_icon_files_dir),  # noqa: SLF001
        ("action_bar_icons_dir", sys_paths._action_bar_icons_dir),  # noqa: SLF001
        ("various_files_dir", sys_paths._various_files_dir),  # noqa: SLF001
        ("indexes_dir", sys_paths._indexes_dir),  # noqa: SLF001
        (
            "fantagraphics_overrides_root_dir",
            sys_paths._fantagraphics_overrides_root_dir,  # noqa: SLF001
        ),
        ("intro_doc_dir", sys_paths._intro_doc_dir),  # noqa: SLF001
        ("censorship_fixes_doc_dir", sys_paths._censorship_fixes_doc_dir),  # noqa: SLF001
        ("how_to_doc_dir", sys_paths._how_to_doc_dir),  # noqa: SLF001
    ]
    for label, dir_path in dirs_to_check:
        assert dir_path is not None
        _check_dir(phase, label, dir_path)

    files_to_check: list[tuple[str, Path | None]] = [
        ("app_window_icon_path", sys_paths._app_window_icon_path),  # noqa: SLF001
        ("error_background_path", sys_paths._error_background_path),  # noqa: SLF001
        ("success_background_path", sys_paths._success_background_path),  # noqa: SLF001
        ("app_identity_image_path", sys_paths._app_identity_image_path),  # noqa: SLF001
        ("close_icon_path", sys_paths._close_icon_path),  # noqa: SLF001
        ("collapse_icon_path", sys_paths._collapse_icon_path),  # noqa: SLF001
        ("refresh_arrow_icon_path", sys_paths._refresh_arrow_icon_path),  # noqa: SLF001
        ("settings_icon_path", sys_paths._settings_icon_path),  # noqa: SLF001
        ("menu_dots_icon_path", sys_paths._menu_dots_icon_path),  # noqa: SLF001
        ("fullscreen_icon_path", sys_paths._fullscreen_icon_path),  # noqa: SLF001
        ("fullscreen_exit_icon_path", sys_paths._fullscreen_exit_icon_path),  # noqa: SLF001
        ("single_page_icon_path", sys_paths._single_page_icon_path),  # noqa: SLF001
        ("double_page_icon_path", sys_paths._double_page_icon_path),  # noqa: SLF001
        ("goto_icon_path", sys_paths._goto_icon_path),  # noqa: SLF001
        ("goto_start_icon_path", sys_paths._goto_start_icon_path),  # noqa: SLF001
        ("goto_end_icon_path", sys_paths._goto_end_icon_path),  # noqa: SLF001
        ("hamburger_menu_icon_path", sys_paths._hamburger_menu_icon_path),  # noqa: SLF001
        ("go_back_icon_path", sys_paths._go_back_icon_path),  # noqa: SLF001
        ("speech_bubble_icon_path", sys_paths._speech_bubble_icon_path),  # noqa: SLF001
        ("up_arrow_path", sys_paths._up_arrow_path),  # noqa: SLF001
        ("down_arrow_path", sys_paths._down_arrow_path),  # noqa: SLF001
        ("transparent_blank_path", sys_paths._transparent_blank_path),  # noqa: SLF001
        ("empty_page_path", sys_paths._empty_page_path),  # noqa: SLF001
        ("favourite_titles_path", sys_paths._favourite_titles_path),  # noqa: SLF001
        (
            "by_the_numbers_background_path",
            sys_paths._by_the_numbers_background_path,  # noqa: SLF001
        ),
    ]
    for label, file_path in files_to_check:
        assert file_path is not None
        _check_file(phase, label, file_path)

    # Plan extras.
    _check_dir_has_pages(phase, "how_to_doc_dir", sys_paths.get_how_to_doc_dir())
    _check_dir(
        phase,
        "fantagraphics_panel_segments_root_dir",
        sys_paths.get_barks_reader_fantagraphics_panel_segments_root_dir(),
    )
    _check_dir_has_pngs(phase, "statistics_dir", sys_paths.get_statistics_dir())

    collector.finalize_phase(phase)


# ---------------------------------------------------------------------------
# Phase 3 - ReaderFilePaths (panel sources)
# ---------------------------------------------------------------------------


def phase3_reader_file_paths(
    collector: ErrorCollector,
    cfg_info: ConfigInfo,
    reader_files_dir: Path,
) -> None:
    """Validate every panel source (JPG zip always, PNG dir if configured)."""
    phase = collector.start_phase("Reader File Paths", "3")

    sources = _resolve_panel_sources(phase, cfg_info, reader_files_dir)
    for panels_source, ext_type in sources:
        phase.items_checked += 1
        if not panels_source.exists():
            phase.add(f"panels_source: missing {panels_source}")
            continue

        file_paths = ReaderFilePaths()
        try:
            file_paths.set_barks_panels_source(panels_source, ext_type)
        except FileNotFoundError as exc:
            # The app's _check_panels_dirs raised on the first missing dir.
            # Re-enumerate below so we report every missing one.
            phase.add(f"panels_source check raised: {exc}")
        except Exception as exc:  # noqa: BLE001
            phase.add(f"set_barks_panels_source failed: {exc}")
            continue

        _enumerate_panel_dirs(phase, panels_source)

    collector.finalize_phase(phase)


def _resolve_panel_sources(
    phase: PhaseResult,
    cfg_info: ConfigInfo,
    reader_files_dir: Path,
) -> list[tuple[Path, BarksPanelsExtType]]:
    """Resolve every panel source the validator should check.

    Always includes the JPG zip (use_png_images=False). Additionally
    includes the PNG dir when the INI configures one and that directory
    exists on disk. The PNG variant is *additive*: missing or unconfigured
    PNG dirs are silently skipped, since the user-facing requirement is
    that the JPG zip is always present.
    """
    sources: list[tuple[Path, BarksPanelsExtType]] = [
        (reader_files_dir / JPG_BARKS_PANELS_ZIP, BarksPanelsExtType.JPG),
    ]

    if not cfg_info.app_config_path.is_file():
        phase.add(f"app config INI not readable: {cfg_info.app_config_path}")
        return sources

    barks_config = ConfigParser()
    barks_config.read(cfg_info.app_config_path)
    try:
        png_dir = read_setting_from_config(barks_config, PNG_BARKS_PANELS_DIR)
    except Exception:  # noqa: BLE001 - missing/unset PNG dir is fine; just skip it
        return sources

    png_path = png_dir if isinstance(png_dir, Path) else Path(png_dir) if png_dir else None
    if png_path is not None and png_path.is_dir():
        sources.append((png_path, BarksPanelsExtType.MOSTLY_PNG))
    return sources


def _enumerate_panel_dirs(phase: PhaseResult, panels_source: Path) -> None:
    """Enumerate every ``PanelDirNames.*`` entry under ``panels_source``."""
    is_zip = panels_source.suffix == ".zip"
    if is_zip:
        try:
            with zipfile.ZipFile(panels_source, "r") as panels_zip:
                names = panels_zip.namelist()
        except OSError as exc:
            phase.add(f"panels_zip: could not open {panels_source}: {exc}")
            return
        for dir_enum in PanelDirNames:
            phase.items_checked += 1
            prefix = f"{dir_enum.value}/"
            if not any(name.startswith(prefix) for name in names):
                phase.add(f"panels_zip: missing entry '{dir_enum.value}'")
        return

    for dir_enum in PanelDirNames:
        phase.items_checked += 1
        sub = panels_source / dir_enum.value
        if not sub.is_dir():
            phase.add(f"panels_dir: missing '{dir_enum.value}' under {panels_source}")
    edited = panels_source / PanelDirNames.INSETS.value / EDITED_SUBDIR
    phase.items_checked += 1
    if not edited.is_dir():
        phase.add(f"panels_dir: missing 'Insets/{EDITED_SUBDIR}' under {panels_source}")


# ---------------------------------------------------------------------------
# Phase 4/5/8 helpers — per-title file validation
# ---------------------------------------------------------------------------
#
# A title's on-disk presence is checked across many roots:
#
#   Insets/<title>.ext + Insets/edited/<title>.ext         (flat per-title files)
#   Covers/<title>.jpg + Covers/edited/<title>.<ext>       (flat per-title files)
#   <Category>/<title>/* + <Category>/<title>/edited/*     (per-title subdirs)
#       where <Category> in {AI, BW, Censorship, Closeups, Favourites,
#                            "Original Art", Search, Silhouettes, Splash}
#
# Existence requirements are deliberately sparse:
#   * Insets/<title>.<ext> must exist for every comic title not in ``NON_COMIC_TITLES``.
#   * Every comic title (not in ``NON_COMIC_TITLES``) must have at least one
#     file under one of {Closeups, Favourites, Silhouettes, Splash}.
#   * All other paths are optional — but every file that *is* present is
#     test-decoded (encrypted=True for the JPG zip variant, =False for the
#     PNG dir variant) so corrupt content fails this phase.


@dataclass(slots=True)
class _TitleCounts:
    """Per-category file counts for one (title, panel-source-variant) pair."""

    insets: int = 0
    covers: int = 0
    bw: int = 0
    ai: int = 0
    censorship: int = 0
    closeups: int = 0
    favourites: int = 0
    original_art: int = 0
    search: int = 0
    silhouettes: int = 0
    splash: int = 0

    @property
    def total(self) -> int:
        """Sum of every per-category count for the title."""
        return (
            self.insets
            + self.covers
            + self.bw
            + self.ai
            + self.censorship
            + self.closeups
            + self.favourites
            + self.original_art
            + self.search
            + self.silhouettes
            + self.splash
        )

    @property
    def has_required_panel_file(self) -> bool:
        """True iff at least one of the four required panel categories has a file."""
        return bool(self.closeups or self.favourites or self.silhouettes or self.splash)


def _load_test_image(panel_path: PanelPath, encrypted: bool) -> Exception | None:
    """Decode the image at ``panel_path``; return ``None`` on success, the exception on failure.

    Loads through the reader's OWN primitive ``image_pipeline.load_pil`` - the
    exact call ``panel_image_loader`` makes at read time - so this check stays
    faithful to the live reader and reproduces (rather than masks) a
    decryption-caller regression the compiled panel-key allow-list would reject.
    ``load_pil`` decrypts zip members when ``encrypted_zip=True`` and reads
    filesystem paths verbatim (the flag is ignored for them).
    """
    try:
        reader_load_pil(panel_path, encrypted_zip=encrypted)
    except DecryptionError as exc:
        return exc
    except (OSError, RuntimeError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        return exc
    return None


@dataclass(slots=True)
class _AuditCtx:
    """Per-variant state tracking which panel files the per-title sweep visited.

    A "visit" is recorded each time the sweep examines a specific file path
    (test-loads it, errors it as a non-image, or notes its existence). The
    :func:`phase_audit_panel_files` pass uses ``visited`` to find files the
    sweep never touched, which is how stray files outside the per-title
    naming scheme (e.g. typos in a title-named subdir, files dropped into
    the wrong category dir) get surfaced.
    """

    panel_source: Path
    is_zip: bool
    visited: set[str] = field(default_factory=set)

    def visit(self, panel_path: PanelPath) -> None:
        """Mark ``panel_path`` as inspected by the per-title sweep."""
        self.visited.add(_panel_key(self, panel_path))


def _panel_key(ctx: _AuditCtx, panel_path: PanelPath) -> str:
    """Return a stable key identifying ``panel_path`` within its variant.

    For zip variants the key is the member's ``at`` attribute (the path
    inside the archive). For filesystem variants it's the POSIX-style path
    relative to ``ctx.panel_source``.
    """
    if isinstance(panel_path, zipfile.Path):
        return panel_path.at
    return panel_path.relative_to(ctx.panel_source).as_posix()


def _validate_image_files_in(
    phase: PhaseResult,
    ctx: _AuditCtx,
    title_str: str,
    dir_path: PanelPath,
    encrypted: bool,
    *,
    label: str,
) -> int:
    """Inspect every file directly under ``dir_path``: test-load images, error non-images.

    Returns the count of image files found (regardless of load success —
    load failures are recorded on the phase, but the file is still counted
    so the JPG↔PNG cross-check sees a true count). Non-image files are
    recorded as errors with kind ``<label>_non_image_file`` and are not
    counted toward the image total. Every visited file (image or not) is
    added to ``ctx`` so the audit pass won't re-flag it as unvisited.
    """
    image_count = 0
    for f in dir_path.iterdir():
        if not f.is_file():
            continue
        ctx.visit(f)
        suffix = Path(f.name).suffix.lower()
        if suffix not in _PAGE_EXTS:
            phase.add(f"Title:{title_str} kind={label}_non_image_file path={f}")
            continue
        image_count += 1
        err = _load_test_image(f, encrypted)
        if err is not None:
            phase.add(
                f"Title:{title_str} kind={label}_load_failed path={f}"
                f" reason={type(err).__name__}: {err}"
            )
    return image_count


def _check_subdir_title(
    phase: PhaseResult,
    ctx: _AuditCtx,
    title_str: str,
    parent_dir: PanelPath,
    encrypted: bool,
    *,
    label: str,
) -> int:
    """Check ``<parent_dir>/<title_str>/*`` and optional ``<parent_dir>/<title_str>/edited/*``.

    Title-named subdirs are inherently optional — most titles do not have
    closeup/silhouette/etc files. Returns 0 silently when the title subdir
    is absent. Each present file is test-image-loaded; non-image files
    inside the subdir (or its ``edited`` subdir) are flagged as errors.
    """
    title_dir = parent_dir / title_str
    if not title_dir.is_dir():
        return 0
    count = _validate_image_files_in(phase, ctx, title_str, title_dir, encrypted, label=label)
    edited_dir = title_dir / EDITED_SUBDIR
    if edited_dir.is_dir():
        count += _validate_image_files_in(
            phase, ctx, title_str, edited_dir, encrypted, label=f"edited_{label}"
        )
    return count


def _check_flat_pair(
    phase: PhaseResult,
    ctx: _AuditCtx,
    title_str: str,
    parent_dir: PanelPath,
    encrypted: bool,
    *,
    label: str,
    main_filename: str,
    edited_filename: str,
    require_main: bool,
    also_check_no_overrides: bool = False,
) -> int:
    """Check a flat per-title file pair (main + optional edited) under ``parent_dir``.

    Used for flat per-title artifacts (insets and covers). Either may be
    absent: ``require_main`` flips the missing-main case from "ignore" to
    "report". Each present file is test-image-loaded and marked visited.

    When ``also_check_no_overrides`` is True, the optional
    ``<stem>-no-overrides<ext>`` sibling (in both the main and edited
    directories) is also test-image-loaded and marked visited if present.
    """
    count = 0
    main_path = parent_dir / main_filename
    if main_path.is_file():
        ctx.visit(main_path)
        err = _load_test_image(main_path, encrypted)
        if err is not None:
            phase.add(
                f"Title:{title_str} kind={label}_load_failed path={main_path}"
                f" reason={type(err).__name__}: {err}"
            )
        count += 1
    elif require_main:
        phase.add(f"Title:{title_str} kind=missing_{label} path={main_path}")

    if also_check_no_overrides:
        count += _check_no_overrides_variant(
            phase, ctx, title_str, parent_dir, main_filename, encrypted, label=label
        )

    edited_dir = parent_dir / EDITED_SUBDIR
    if edited_dir.is_dir():
        edited_path = edited_dir / edited_filename
        if edited_path.is_file():
            ctx.visit(edited_path)
            err = _load_test_image(edited_path, encrypted)
            if err is not None:
                phase.add(
                    f"Title:{title_str} kind=edited_{label}_load_failed path={edited_path}"
                    f" reason={type(err).__name__}: {err}"
                )
            count += 1
        if also_check_no_overrides:
            count += _check_no_overrides_variant(
                phase,
                ctx,
                title_str,
                edited_dir,
                edited_filename,
                encrypted,
                label=f"edited_{label}",
            )
    return count


def _check_no_overrides_variant(
    phase: PhaseResult,
    ctx: _AuditCtx,
    title_str: str,
    parent_dir: PanelPath,
    base_filename: str,
    encrypted: bool,
    *,
    label: str,
) -> int:
    """Load-check the ``<stem>-no-overrides<ext>`` sibling of ``base_filename`` if present.

    Returns 1 when the variant exists (and is therefore counted, regardless
    of load success — load failures are reported on the phase) and 0 when
    it is absent. The no-overrides variant is optional: only the four
    titles in :class:`SpecialFantaOverrides` ship one.
    """
    base = Path(base_filename)
    no_overrides_filename = f"{base.stem}{NO_OVERRIDES_SUFFIX}{base.suffix}"
    no_overrides_path = parent_dir / no_overrides_filename
    if not no_overrides_path.is_file():
        return 0
    ctx.visit(no_overrides_path)
    err = _load_test_image(no_overrides_path, encrypted)
    if err is not None:
        phase.add(
            f"Title:{title_str} kind={label}_load_failed path={no_overrides_path}"
            f" reason={type(err).__name__}: {err}"
        )
    return 1


def _validate_title_files(
    phase: PhaseResult,
    file_paths: ReaderFilePaths | None,
    ctx: _AuditCtx,
    title_str: str,
) -> _TitleCounts | None:
    """Validate inset, cover, and per-category subdir files for one title.

    Args:
        phase: Phase result to record errors against.
        file_paths: Resolved :class:`ReaderFilePaths` for one panel-source
            variant. ``None`` short-circuits (Phase 3 already reported the
            panels_source problem).
        ctx: Per-variant audit context. Each file the sweep visits is
            recorded so the audit pass can later report any unvisited file.
        title_str: The title identifier as keyed in ``STR_TITLE_TO_ENUM``.

    Returns:
        ``_TitleCounts`` summarising every file seen for this title across
        every category; ``None`` if the title is unknown or ``file_paths``
        is unavailable.

    """
    phase.items_checked += 1
    if file_paths is None:
        return None

    title = STR_TITLE_TO_ENUM.get(title_str)
    if title is None:
        return None

    is_article = title in NON_COMIC_TITLES
    is_one_pager = title in ONE_PAGERS
    is_cover = title in COVERS_SET
    encrypted = file_paths.barks_panels_are_encrypted
    inset_ext = file_paths.get_inset_file_ext()

    counts = _TitleCounts()

    # Insets — flat: Insets/<filename(title)>.ext + Insets/edited/<filename(title)>.ext.
    # Required for every comic title except articles. Individual one-pagers have no
    # standalone comic, prebuilt CBZ, or panel files of their own — they are read as a
    # page within the "All One-Pagers" collection. The one per-title asset they must
    # still ship is the inset thumbnail shown in the tree, and only when the one-pager
    # has a valid location (and therefore appears in the collection). The synthetic
    # collection itself has no inset of its own, so it is exempt too.
    #
    # Covers are read the same way - as a page within the "All Covers" collection -
    # but unlike one-pagers they ship no inset either: the tree falls back to the
    # emergency inset for them, so they are exempt outright.
    if is_one_pager_collection(title) or is_cover:
        inset_required = False
    elif is_one_pager:
        inset_required = is_one_pager_located(title)
    else:
        inset_required = not is_article
    inset_filename = get_filename_from_title(title, inset_ext)
    counts.insets = _check_flat_pair(
        phase,
        ctx,
        title_str,
        file_paths.get_comic_inset_files_dir(),
        encrypted,
        label="inset",
        main_filename=inset_filename,
        edited_filename=inset_filename,
        require_main=inset_required,
        also_check_no_overrides=True,
    )

    # Covers — flat: Covers/<title>.jpg (always JPG) + Covers/edited/<title>.<inset_ext>.
    counts.covers = _check_flat_pair(
        phase,
        ctx,
        title_str,
        file_paths.get_comic_cover_files_dir(),
        encrypted,
        label="cover",
        main_filename=title_str + JPG_FILE_EXT,
        edited_filename=title_str + inset_ext,
        require_main=False,
    )

    # Per-category subdirs.
    counts.bw = _check_subdir_title(
        phase, ctx, title_str, file_paths.get_comic_bw_files_dir(), encrypted, label="bw"
    )
    counts.ai = _check_subdir_title(
        phase, ctx, title_str, file_paths.get_comic_ai_files_dir(), encrypted, label="ai"
    )
    counts.censorship = _check_subdir_title(
        phase,
        ctx,
        title_str,
        file_paths.get_comic_censorship_files_dir(),
        encrypted,
        label="censorship",
    )
    counts.closeups = _check_subdir_title(
        phase, ctx, title_str, file_paths.get_comic_closeup_files_dir(), encrypted, label="closeup"
    )
    counts.favourites = _check_subdir_title(
        phase,
        ctx,
        title_str,
        file_paths.get_comic_favourite_files_dir(),
        encrypted,
        label="favourite",
    )
    counts.original_art = _check_subdir_title(
        phase,
        ctx,
        title_str,
        file_paths.get_comic_original_art_files_dir(),
        encrypted,
        label="original_art",
    )
    counts.search = _check_subdir_title(
        phase, ctx, title_str, file_paths.get_comic_search_files_dir(), encrypted, label="search"
    )
    counts.silhouettes = _check_subdir_title(
        phase,
        ctx,
        title_str,
        file_paths.get_comic_silhouette_files_dir(),
        encrypted,
        label="silhouette",
    )
    counts.splash = _check_subdir_title(
        phase, ctx, title_str, file_paths.get_comic_splash_files_dir(), encrypted, label="splash"
    )

    # One-pagers and covers carry no Closeups/Favourites/Silhouettes/Splash files of
    # their own (their large images are drawn from the "All One-Pagers" / "All Covers"
    # collection), so the required-panel-file rule does not apply to them.
    if not is_article and not is_one_pager and not is_cover and not counts.has_required_panel_file:
        phase.add(
            f"Title:{title_str} kind=no_panel_files"
            f" reason=no_files_in_(Closeups|Favourites|Silhouettes|Splash)"
        )

    return counts


# ---------------------------------------------------------------------------
# Phase 4 - Introduction node
# ---------------------------------------------------------------------------


def phase4_introduction(
    collector: ErrorCollector,
    sys_paths: SystemFilePaths,
    file_paths_variants: list[ReaderFilePaths],
) -> None:
    """Validate intro document pages and the intro article inset (per panel-source variant)."""
    phase = collector.start_phase("Introduction", "4")
    _check_dir_has_pages(phase, "intro_doc_dir", sys_paths.get_intro_doc_dir())
    title_str = ENUM_TO_STR_TITLE[_INTRO_ARTICLE]
    for file_paths in file_paths_variants:
        # Phase 4/5 use a throwaway ctx — only Phase 8 retains its ctx for the
        # audit pass. Visiting the intro/appendix files here is harmless: the
        # audit re-visits them in Phase 8 anyway.
        ctx = _build_audit_ctx(file_paths)
        _validate_title_files(phase, file_paths, ctx, title_str)
    collector.finalize_phase(phase)


def _build_audit_ctx(file_paths: ReaderFilePaths) -> _AuditCtx:
    """Construct an :class:`_AuditCtx` for one resolved panel-source variant."""
    panel_source = file_paths._barks_panels_source  # noqa: SLF001
    assert panel_source is not None
    return _AuditCtx(panel_source=panel_source, is_zip=panel_source.suffix == ".zip")


# ---------------------------------------------------------------------------
# Phase 5 - Appendices
# ---------------------------------------------------------------------------


def phase5_appendices(
    collector: ErrorCollector,
    sys_paths: SystemFilePaths,
    file_paths_variants: list[ReaderFilePaths],
) -> None:
    """Validate censorship-fixes pages and the four appendix article insets (per variant)."""
    phase = collector.start_phase("Appendices", "5")
    _check_dir_has_pages(
        phase,
        "censorship_fixes_doc_dir",
        sys_paths.get_censorship_fixes_doc_dir(),
    )
    for article in _APPENDIX_ARTICLES:
        title_str = ENUM_TO_STR_TITLE[article]
        for file_paths in file_paths_variants:
            ctx = _build_audit_ctx(file_paths)
            _validate_title_files(phase, file_paths, ctx, title_str)
    collector.finalize_phase(phase)


# ---------------------------------------------------------------------------
# Phase 6 - Per-volume Fantagraphics archives
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FantaState:
    """Cached Phase 6 outcome consumed by Phase 8."""

    archives: dict[int, FantagraphicsArchive] = field(default_factory=dict)
    error_volumes: set[int] = field(default_factory=set)


def phase6_fantagraphics(
    collector: ErrorCollector,
    cfg_info: ConfigInfo,
    sys_paths: SystemFilePaths,
) -> FantaState:
    """Replicate :meth:`FantagraphicsVolumeArchives.load` per-volume."""
    phase = collector.start_phase("Fantagraphics Volumes and Overrides", "6")
    state = FantaState()

    barks_config = ConfigParser()
    barks_config.read(cfg_info.app_config_path)

    archive_root = _resolve_archive_root(cfg_info, barks_config)
    if archive_root is None or not archive_root.is_dir():
        phase.add(f"archive_root: missing {archive_root}")
        collector.finalize_phase(phase)
        return state

    override_root = sys_paths.get_barks_reader_fantagraphics_overrides_root_dir()
    if not override_root.is_dir():
        phase.add(f"override_root: missing {override_root}")
        collector.finalize_phase(phase)
        return state

    volumes = list(range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1))
    archives_mgr = FantagraphicsVolumeArchives(archive_root, override_root, volumes)

    try:
        archive_filenames = sorted(
            archives_mgr.get_all_volume_filenames(),
            key=archives_mgr._get_fanta_volume,  # noqa: SLF001
        )
    except Exception as exc:  # noqa: BLE001
        phase.add(f"could not enumerate volume archives: {exc}")
        collector.finalize_phase(phase)
        return state

    try:
        override_archive_filenames = archives_mgr.get_all_volume_override_archives()
    except FileExistsError as exc:
        phase.add(f"override directory contains a non-file entry: {exc}")
        override_archive_filenames = {}
    except Exception as exc:  # noqa: BLE001
        phase.add(f"could not enumerate override archives: {exc}")
        override_archive_filenames = {}

    _check_volume_numbers(phase, state, archives_mgr, archive_filenames)

    if len(override_archive_filenames) > LAST_VOLUME_NUMBER - FIRST_VOLUME_NUMBER + 1:
        try:
            archives_mgr.check_archives_and_overrides(archive_filenames, override_archive_filenames)
        except TooManyOverrideDirsError as exc:
            phase.add(f"too many override archives: {exc}")

    _process_archive_filenames(
        phase, state, archives_mgr, archive_filenames, override_archive_filenames
    )

    phase.summary_extra = (
        f"({len(state.archives)} archives loaded, {len(state.error_volumes)} volumes flagged)"
    )
    collector.finalize_phase(phase)
    return state


def _resolve_archive_root(cfg_info: ConfigInfo, barks_config: ConfigParser) -> Path | None:
    """Resolve the Fantagraphics archive directory from config or fallback search."""
    try:
        configured = read_setting_from_config(barks_config, FANTA_DIR)
    except Exception:  # noqa: BLE001
        configured = None
    if isinstance(configured, Path) and configured.is_dir():
        return configured
    # Fall back to the same search the app uses when FANTA_DIR is the unset marker.
    candidate = find_fanta_volumes_dirpath(cfg_info, "Fantagraphics-original")
    if candidate is not None and candidate.is_dir():
        return candidate
    return None


def _check_volume_numbers(
    phase: PhaseResult,
    state: FantaState,
    archives_mgr: FantagraphicsVolumeArchives,
    archive_filenames: list[Path],
) -> None:
    """Run :meth:`check_correct_volume_numbers` and stamp errors per volume."""
    try:
        archives_mgr.check_correct_volume_numbers(archive_filenames)
    except MissingArchiveFilesError as exc:
        for vol in exc.missing_file_vols:
            state.error_volumes.add(vol)
            phase.add(f"Volume {vol}: missing archive file")
    except DuplicateArchiveFilesError as exc:
        for vol in exc.duplicates:
            state.error_volumes.add(vol)
            phase.add(f"Volume {vol}: duplicate archive files")
    except TooManyArchiveFilesError as exc:
        phase.add(f"too many archive files: {exc}")


def _process_archive_filenames(
    phase: PhaseResult,
    state: FantaState,
    archives_mgr: FantagraphicsVolumeArchives,
    archive_filenames: list[Path],
    override_archive_filenames: dict[int, Path],
) -> None:
    """Run the per-archive load() body, stamping errors per volume on failure."""
    for archive_filename in archive_filenames:
        phase.items_checked += 1
        try:
            fanta_volume = archives_mgr._get_fanta_volume(archive_filename)  # noqa: SLF001
        except ValueError as exc:
            phase.add(f"could not parse volume from {archive_filename}: {exc}")
            continue

        override_archive_filename = override_archive_filenames.get(fanta_volume)

        try:
            archive = _process_one_archive(
                archives_mgr, fanta_volume, archive_filename, override_archive_filename
            )
        except (
            EmptyArchiveError,
            PageNumError,
            PageExtError,
            RuntimeError,
            ValueError,
            OSError,
        ) as exc:
            state.error_volumes.add(fanta_volume)
            phase.add(f"Volume {fanta_volume}: {type(exc).__name__}: {exc}")
            continue
        state.archives[fanta_volume] = archive


def _process_one_archive(
    archives_mgr: FantagraphicsVolumeArchives,
    fanta_volume: int,
    archive_filename: Path,
    override_archive_filename: Path | None,
) -> FantagraphicsArchive:
    """Replicate the per-archive body of :meth:`FantagraphicsVolumeArchives.load`."""
    image_subdir, image_filenames = archives_mgr._get_archive_contents(archive_filename)  # noqa: SLF001
    if not image_filenames:
        raise EmptyArchiveError(archive_filename)
    image_ext = Path(image_filenames[0]).suffix
    if image_ext not in (JPG_FILE_EXT, PNG_FILE_EXT):
        msg = f'Unexpected image extension "{image_ext}" in {archive_filename}'
        raise PageExtError(msg)

    first_page, last_page = archives_mgr._get_first_and_last_page_nums(image_filenames)  # noqa: SLF001
    archives_mgr._check_image_names(image_filenames, first_page, last_page, image_ext)  # noqa: SLF001

    archive_images_page_map = archives_mgr._get_archive_image_page_map(  # noqa: SLF001
        image_subdir, image_filenames, first_page, last_page
    )
    override_images_page_map, extra_images_page_map = (
        archives_mgr._get_override_and_extra_images_page_maps(  # noqa: SLF001
            override_archive_filename, archive_images_page_map
        )
    )

    return FantagraphicsArchive(
        fanta_volume=fanta_volume,
        archive_filename=archive_filename,
        archive_image_subdir=image_subdir,
        image_ext=image_ext,
        first_page=first_page,
        last_page=last_page,
        archive_images_page_map=archive_images_page_map,
        override_images_page_map=override_images_page_map,
        extra_images_page_map=extra_images_page_map,
        override_archive_filename=override_archive_filename,
        is_missing=False,
    )


# ---------------------------------------------------------------------------
# Phase 7 - Per-volume prebuilt CBZs
# ---------------------------------------------------------------------------


def phase7_prebuilt_cbzs(collector: ErrorCollector, cfg_info: ConfigInfo) -> None:
    """Always-on check: every title's expected prebuilt CBZ must exist on disk."""
    phase = collector.start_phase("Prebuilt CBZs", "7")

    barks_config = ConfigParser()
    barks_config.read(cfg_info.app_config_path)

    try:
        prebuilt_dir_setting = read_setting_from_config(barks_config, PREBUILT_COMICS_DIR)
        prebuilt_dir = Path(prebuilt_dir_setting)
    except Exception:  # noqa: BLE001
        prebuilt_dir = ReaderFilePaths.get_default_prebuilt_comic_zips_dir()

    if not prebuilt_dir.is_dir():
        phase.add(f"Prebuilt: missing_dir {prebuilt_dir}")
        collector.finalize_phase(phase)
        return

    for title, fanta_info in ALL_FANTA_COMIC_BOOK_INFO.items():
        if title in ONE_PAGERS or title in COVERS_SET:
            # Individual one-pagers and covers have no prebuilt CBZ of their own — they
            # are read as a page within the "All One-Pagers" / "All Covers" collection,
            # whose CBZ is checked like any other title.
            continue
        title_str = ENUM_TO_STR_TITLE[title]
        phase.items_checked += 1
        cbz_stem = get_dest_comic_zip_file_stem(
            title_str,
            fanta_info.fanta_chronological_number,
            fanta_info.get_short_issue_title(),
        )
        cbz_path = prebuilt_dir / (cbz_stem + CBZ_FILE_EXT)
        if not cbz_path.is_file():
            phase.add(f"Prebuilt: missing {cbz_path}")

    collector.finalize_phase(phase)


# ---------------------------------------------------------------------------
# Phase 8 - Per-title
# ---------------------------------------------------------------------------


def phase8a_per_title_panel_files(
    collector: ErrorCollector,
    file_paths_variants: list[ReaderFilePaths],
    fanta_state: FantaState,
    titles_filter: list[str] | None = None,
) -> list[_AuditCtx]:
    """Per-title file + volume-binding sweep across ALL_FANTA_COMIC_BOOK_INFO.

    For each variant in ``file_paths_variants`` (JPG zip first, optional PNG
    dir second), every title is checked via :func:`_validate_title_files`,
    which test-image-loads every present file. When two variants are
    available the per-title totals are cross-checked: a mismatch flags a
    discrepancy between the JPG and PNG panel sources.

    Args:
        collector: Aggregator for phase results.
        file_paths_variants: Resolved panel-source variants (JPG zip first,
            optional PNG dir second).
        fanta_state: Cached Phase 6 outcome.
        titles_filter: Optional subset of titles to check (matches Phase 9's
            argument). ``None`` runs every title.

    Returns:
        Per-variant :class:`_AuditCtx` instances populated with every panel
        file the sweep visited. The audit pass consumes these to find files
        the sweep failed to visit.

    """
    phase = collector.start_phase("Per-title Panel Files", "8a")

    title_count_errors = 0
    invalid_volume_count = 0
    counts_by_variant: list[dict[str, _TitleCounts]] = [{} for _ in file_paths_variants]
    ctx_by_variant: list[_AuditCtx] = [_build_audit_ctx(fp) for fp in file_paths_variants]

    filter_set = set(titles_filter) if titles_filter is not None else None
    titles = [
        t
        for t in ALL_FANTA_COMIC_BOOK_INFO
        if filter_set is None or ENUM_TO_STR_TITLE[t] in filter_set
    ]
    total = len(titles)
    progress_step = max(5, total // 20)

    for idx, title in enumerate(titles, start=1):
        title_str = ENUM_TO_STR_TITLE[title]

        if total > 0 and (idx in (1, total) or idx % progress_step == 0):
            logger.info(f"[{idx}/{total}] {title_str}")

        before_files = len(phase.errors)
        for variant_idx, (file_paths, ctx) in enumerate(
            zip(file_paths_variants, ctx_by_variant, strict=True)
        ):
            counts = _validate_title_files(phase, file_paths, ctx, title_str)
            if counts is not None:
                counts_by_variant[variant_idx][title_str] = counts
        after_files = len(phase.errors)
        if after_files > before_files:
            title_count_errors += 1

        fanta_info = ALL_FANTA_COMIC_BOOK_INFO[title]
        _validate_title_volume_binding(phase, title_str, fanta_info, fanta_state)
        if len(phase.errors) > after_files:
            invalid_volume_count += 1

    mismatch_count = _crosscheck_variant_counts(phase, counts_by_variant)
    files_inspected_per_variant = [
        sum(c.total for c in variant.values()) for variant in counts_by_variant
    ]
    files_inspected = "+".join(str(n) for n in files_inspected_per_variant) or "0"

    phase.summary_extra = (
        f"({title_count_errors} titles with file errors,"
        f" {invalid_volume_count} broken volume bindings,"
        f" {mismatch_count} JPG/PNG count mismatches,"
        f" {files_inspected} files test-loaded)"
    )
    collector.finalize_phase(phase)
    return ctx_by_variant


def _crosscheck_variant_counts(
    phase: PhaseResult,
    counts_by_variant: list[dict[str, _TitleCounts]],
) -> int:
    """Compare per-title totals across panel-source variants; report mismatches.

    Only runs when two variants were validated (the JPG zip and the PNG
    dir). For each title present in both, the total across all categories
    (insets + covers + per-category subdir files, including ``edited``) must
    match — the PNG dir is meant to mirror the JPG zip, so a count
    discrepancy means one source is missing files the other has. Returns
    the number of mismatches reported.
    """
    if len(counts_by_variant) < _CROSSCHECK_MIN_VARIANTS:
        return 0
    jpg_counts, png_counts = counts_by_variant[0], counts_by_variant[1]
    mismatch_count = 0
    for title_str in jpg_counts.keys() & png_counts.keys():
        jpg_total = jpg_counts[title_str].total
        png_total = png_counts[title_str].total
        if jpg_total != png_total:
            mismatch_count += 1
            phase.add(
                f"Title:{title_str} kind=file_count_mismatch"
                f" jpg_total={jpg_total} png_total={png_total}"
            )
    return mismatch_count


def _validate_title_volume_binding(
    phase: PhaseResult,
    title_str: str,
    fanta_info: FantaComicBookInfo,
    fanta_state: FantaState,
) -> None:
    """Cross-link a title against its Fantagraphics volume archive."""
    phase.items_checked += 1
    try:
        volume = get_fanta_volume_from_str(fanta_info.fantagraphics_volume)
    except (AssertionError, ValueError) as exc:
        phase.add(f"Title:{title_str} kind=invalid_volume_str ({exc})")
        return

    archive = fanta_state.archives.get(volume)
    if archive is None or archive.is_missing:
        phase.add(f"Title:{title_str} kind=missing_volume volume={volume}")
        return
    if volume in fanta_state.error_volumes:
        phase.add(f"Title:{title_str} kind=volume_invalid volume={volume}")


# ---------------------------------------------------------------------------
# Phase 8b - Panel-files audit (post per-title sweep)
# ---------------------------------------------------------------------------


def phase8b_audit_panel_files(
    collector: ErrorCollector,
    file_paths_variants: list[ReaderFilePaths],
    ctx_by_variant: list[_AuditCtx],
    *,
    title_filter_active: bool = False,
) -> None:
    """Walk each panel source and flag files the per-title sweep didn't visit.

    For each panel-source variant this enumerates every file under the
    source (filesystem walk for PNG dirs, namelist scan for the JPG zip)
    and reports:

        * ``kind=non_image_file`` — the file's extension is not ``.jpg`` or
          ``.png``. Anything other than image data inside a panels source is
          suspicious (stray ``.DS_Store``, leftover ``.json`` indices, etc.).
          Files already flagged by the per-title sweep are not re-reported.
        * ``kind=unvisited_image_file`` — image file the sweep never
          inspected. Typical causes: typos in a title-named subdir (so the
          name doesn't match any entry in ``STR_TITLE_TO_ENUM``), files
          dropped into the wrong category dir, files at unexpected nesting
          depths.

    Files in the ``Nontitles/`` subtree are excluded from the
    unvisited-image error: the per-title sweep deliberately doesn't iterate
    that subtree because its files aren't keyed by title. Non-image files
    inside ``Nontitles/`` are still flagged.

    Image files whose stem ends with :data:`NO_OVERRIDES_SUFFIX` are also
    excluded from the unvisited-image error: those are the optional
    ``-no-overrides`` siblings used by :class:`SpecialFantaOverrides`, which
    the inset load check exercises directly.

    When ``title_filter_active`` is True the unvisited-image check is
    silenced (every file outside the filtered title set would otherwise be
    reported as unvisited, which is expected). The non-image-file check
    still runs since stray non-images are an error regardless of which
    titles are being validated.
    """
    phase = collector.start_phase("Panel Files Audit", "8b")
    nontitles_prefix = PanelDirNames.NONTITLES.value + "/"

    unvisited_image_count = 0
    non_image_count = 0
    for file_paths, ctx in zip(file_paths_variants, ctx_by_variant, strict=True):
        for key, panel_path in _enumerate_panel_files(file_paths, ctx):
            phase.items_checked += 1
            key_path = Path(key)
            suffix = key_path.suffix.lower()
            if suffix not in _PAGE_EXTS:
                if key not in ctx.visited:
                    non_image_count += 1
                    phase.add(
                        f"Source:{ctx.panel_source.name} kind=non_image_file path={panel_path}"
                    )
                continue
            if title_filter_active or key in ctx.visited:
                continue
            if key.startswith(nontitles_prefix):
                continue
            if key_path.stem.endswith(NO_OVERRIDES_SUFFIX):
                continue
            if key_path.parent.parent.stem.endswith("Paintings"):
                continue
            unvisited_image_count += 1
            phase.add(f"Source:{ctx.panel_source.name} kind=unvisited_image_file path={panel_path}")

    filter_note = (
        " — unvisited-image check skipped: title filter active" if title_filter_active else ""
    )
    phase.summary_extra = (
        f"({non_image_count} non-image files,"
        f" {unvisited_image_count} unvisited image files{filter_note})"
    )
    collector.finalize_phase(phase)


def _enumerate_panel_files(
    file_paths: ReaderFilePaths,
    ctx: _AuditCtx,
) -> Iterator[tuple[str, PanelPath]]:
    """Yield ``(key, panel_path)`` for every file under a variant's panel source.

    ``key`` is the same path representation used by :func:`_panel_key`, so
    membership in ``ctx.visited`` can be tested directly. For zip variants
    that's the member ``at`` string; for filesystem variants it's the POSIX
    path relative to the panel source.
    """
    if ctx.is_zip:
        panels_zip = file_paths._barks_panels_zip  # noqa: SLF001
        assert panels_zip is not None
        for name in panels_zip.namelist():
            if name.endswith("/"):
                continue
            yield name, zipfile.Path(panels_zip, at=name)
    else:
        for path in ctx.panel_source.rglob("*"):
            if path.is_file():
                yield path.relative_to(ctx.panel_source).as_posix(), path


# ---------------------------------------------------------------------------
# Phase 9 - Per-title full-load dry-run
# ---------------------------------------------------------------------------
#
# Phase 9 is the most demanding check: for every comic title, run a non-Kivy
# dry-run of the reader's non-prebuilt load path. For each source page that
# the title actually spans we:
#   1. Resolve the page source the same way ArchivePageImageSource does
#      (extra-overrides → main-overrides → archive original).
#   2. Decode the page bytes through ``image_pipeline.load_pil`` — the exact
#      function the reader uses, so PIL errors here are PIL errors the
#      reader would hit at runtime.
#
# It only decodes. The panel-segments JSON checks, which cost a stat and a zip
# directory lookup per page, live in the always-on Phase 10, so running both
# phases never reports one error twice.


@dataclass(slots=True)
class _Phase9Counts:
    """Per-phase counters used to populate ``phase.summary_extra``."""

    load_failed: int = 0
    page_load_failed: int = 0
    decryption_failed: int = 0


def phase9_per_title_load(
    collector: ErrorCollector,
    fanta_state: FantaState,
    titles_filter: list[str] | None = None,
) -> None:
    """Phase 9: dry-run the loader for every title, as if use_prebuilt_comics=0.

    Catches missing/unreadable source pages and ComicBook construction
    failures (per-title INI errors).

    Args:
        collector: Aggregator for phase results.
        fanta_state: Cached Phase 6 outcome.
        titles_filter: Optional subset of titles to check (from the CLI's
            ``--volume`` / ``--title``). ``None`` runs all titles.

    """
    phase = collector.start_phase("Per-title Image Loads", "9")
    logger.info(
        "Phase: per-title full-load dry-run."
        " Decodes every source page through image_pipeline.load_pil."
        " This may take a minute or two."
    )

    if not fanta_state.archives:
        phase.add(
            "Phase 6 produced no archives — skipping per-title load checks."
            " Resolve Fantagraphics volume errors first."
        )
        collector.finalize_phase(phase)
        return

    try:
        db = ComicsDatabase(for_building_comics=False)
    except Exception as exc:  # noqa: BLE001
        phase.add(f"could not construct ComicsDatabase: {exc}")
        collector.finalize_phase(phase)
        return

    counts = _Phase9Counts()

    # Individual one-pagers and covers have no standalone comic to load: they are read
    # as a page within the "All One-Pagers" / "All Covers" collection, which is itself
    # loaded here as a normal title — so their source pages are validated through it.
    candidates = _loadable_titles(titles_filter)
    total = len(candidates)
    progress_step = 5

    for idx, (title_str, fanta_info) in enumerate(candidates, start=1):
        if idx in (1, total) or idx % progress_step == 0:
            logger.info(f"[{idx}/{total}] {title_str}")

        try:
            volume = get_fanta_volume_from_str(fanta_info.fantagraphics_volume)
        except (AssertionError, ValueError):
            # Phase 8 already records this; skip silently here.
            continue

        archive = fanta_state.archives.get(volume)
        if archive is None or archive.is_missing:
            # Phase 8 already records this as missing_volume.
            continue

        try:
            comic = db.get_comic_book(title_str)
        except (
            TitleNotFoundError,
            FileNotFoundError,
            RuntimeError,
            KeyError,
            AssertionError,
        ) as exc:
            counts.load_failed += 1
            phase.add(
                f"Title:{title_str} kind=comic_book_load_failed reason={type(exc).__name__}: {exc}"
            )
            continue

        check_one_title_load(phase, counts, title_str, comic, archive)

    phase.summary_extra = (
        f"({counts.load_failed} load-failed,"
        f" {counts.page_load_failed} page-load-failed,"
        f" {counts.decryption_failed} decryption-failed)"
    )
    collector.finalize_phase(phase)


def _resolve_page_source(
    archive: FantagraphicsArchive,
    page_str: str,
) -> tuple[Path, str, bool] | None:
    """Mirror :meth:`ArchivePageImageSource._get_fanta_volume_image_path`.

    Returns ``(zip_member_path, source_label, is_encrypted)`` or ``None``
    if the page number isn't present in any of the page maps (which means
    the volume archive itself is missing this page — Phase 6 should have
    surfaced this, but the title-level loader would still raise here).
    """
    if page_str in archive.extra_images_page_map:
        return archive.extra_images_page_map[page_str], "extra", True
    if archive.has_overrides() and page_str in archive.override_images_page_map:
        return archive.override_images_page_map[page_str], "override", True
    if page_str in archive.archive_images_page_map:
        return archive.archive_images_page_map[page_str], "archive", False
    return None


@dataclass(slots=True)
class _VolumeZips:
    """A volume's open CBZ and override CBZ, or why either could not be opened."""

    main: zipfile.ZipFile | None
    main_error: Exception | None
    override: zipfile.ZipFile | None
    override_error: Exception | None


@contextmanager
def _open_volume_zips(archive: FantagraphicsArchive) -> Iterator[_VolumeZips]:
    """Open a volume's CBZ and, if it has one, its override CBZ; close both on exit.

    Nothing is raised for an archive that cannot be opened: its slot is ``None``
    and the error is handed back beside it, for the caller to report or ignore.
    """
    zips = _VolumeZips(main=None, main_error=None, override=None, override_error=None)
    try:
        try:
            zips.main = zipfile.ZipFile(archive.archive_filename, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            zips.main_error = exc
        if archive.has_overrides() and archive.override_archive_filename is not None:
            try:
                zips.override = zipfile.ZipFile(archive.override_archive_filename, "r")
            except (zipfile.BadZipFile, OSError) as exc:
                zips.override_error = exc
        yield zips
    finally:
        if zips.override is not None:
            zips.override.close()
        if zips.main is not None:
            zips.main.close()


def _page_member(
    archive: FantagraphicsArchive, zips: _VolumeZips, page_str: str
) -> tuple[zipfile.ZipFile | None, Path | None]:
    """Return the open zip holding a source page and its member path within it."""
    resolved = _resolve_page_source(archive, page_str)
    if resolved is None:
        return None, None
    member, _source_label, encrypted = resolved
    return (zips.override if encrypted else zips.main), member


def _check_one_source_page(
    phase: PhaseResult,
    counts: _Phase9Counts,
    title_str: str,
    archive: FantagraphicsArchive,
    zips: _VolumeZips,
    srce_page: CleanPage,
) -> None:
    """Decode one source page through the reader's own ``load_pil``."""
    page_filename = srce_page.page_filename

    # Skip the empty/title placeholders (the reader resolves these to the
    # in-memory empty_page_image, never opens a zip member).
    if is_title_page(srce_page) or is_blank_page(page_filename, srce_page.page_type):
        return

    page_str = Path(page_filename).stem
    phase.items_checked += 1

    resolved = _resolve_page_source(archive, page_str)
    if resolved is None:
        counts.page_load_failed += 1
        phase.add(
            f"Title:{title_str} kind=page_load_failed page={page_str} reason=page_not_in_volume"
        )
        return

    member, source_label, encrypted = resolved
    target_zip = zips.override if encrypted else zips.main
    if target_zip is None:
        counts.page_load_failed += 1
        phase.add(
            f"Title:{title_str} kind=page_load_failed page={page_str}"
            f" source={source_label} reason=override_archive_not_open"
        )
        return

    # Decode + decrypt through the reader's OWN primitive
    # (``barks_reader.core.image_pipeline.load_pil``), i.e. the exact
    # call ``ArchivePageImageSource`` makes at read time. Using the
    # reader's path - rather than a different decryptor entry point -
    # is what keeps Phase 9 faithful: if the reader's decryption ever
    # regresses (e.g. a caller the compiled panel-key allow-list
    # rejects), this phase reproduces the failure instead of masking it.
    try:
        reader_load_pil(
            # Zip member names always use '/', even on Windows (as the reader's own
            # ``ArchivePageImageSource._get_image_path`` makes them).
            zipfile.Path(target_zip, at=member.as_posix()),
            encrypted_zip=encrypted,
            use_ext_hint=True,
        )
    except DecryptionError as exc:
        counts.decryption_failed += 1
        phase.add(
            f"Title:{title_str} kind=decryption_failed page={page_str}"
            f" source={source_label} reason={exc}"
        )
    except (
        KeyError,
        zipfile.BadZipFile,
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        counts.page_load_failed += 1
        phase.add(
            f"Title:{title_str} kind=page_load_failed page={page_str}"
            f" source={source_label} reason={type(exc).__name__}: {exc}"
        )


def check_one_title_load(
    phase: PhaseResult,
    counts: _Phase9Counts,
    title_str: str,
    comic: ComicBook,
    archive: FantagraphicsArchive,
) -> None:
    """Open archives, enumerate source pages, and decode each one."""
    # Enumerate source pages. Use the private helper that produces the page
    # list without doing the JSON I/O the public ``get_sorted_srce_and_dest_pages_*``
    # variants would.
    try:
        srce_and_dest_pages = get_srce_and_dest_pages_in_order(comic, get_full_paths=False)
    except Exception as exc:  # noqa: BLE001
        counts.load_failed += 1
        phase.add(
            f"Title:{title_str} kind=comic_book_load_failed"
            f" reason=page_enum_failed: {type(exc).__name__}: {exc}"
        )
        return

    with _open_volume_zips(archive) as zips:
        if zips.main is None:
            counts.page_load_failed += len(srce_and_dest_pages.srce_pages)
            phase.add(
                f"Title:{title_str} kind=page_load_failed page=*"
                f" reason=cannot_open_volume_cbz: {zips.main_error}"
            )
            return
        if zips.override_error is not None:
            # Continue without overrides — per-page checks will then fail
            # on any page that needed an override.
            phase.add(
                f"Title:{title_str} kind=page_load_failed page=*"
                f" reason=cannot_open_override_cbz: {zips.override_error}"
            )

        for srce_page in srce_and_dest_pages.srce_pages:
            _check_one_source_page(phase, counts, title_str, archive, zips, srce_page)


# ---------------------------------------------------------------------------
# Phase 10 - Per-title layouts
# ---------------------------------------------------------------------------
#
# Always on. For every title Phase 9 would load, build the page layout the
# reader builds when it opens the comic — the same ComicLayoutBuilder and
# panel-segments adapter, so a raise here is a title the reader cannot open.
# Before the build, check the panel-segments JSONs it reads: each page with
# panels needs one, no older than its source page. These checks cost a stat
# and a zip directory lookup per page, no decoding.
#
# Timestamp interpretation: the build pipeline compares JSON mtime to the
# original on-disk source image, but on the reader machine the source
# images live INSIDE the volume CBZ — there is no separate filesystem
# mtime per page. So Phase 10 compares the JSON to the page's stored mtime in
# the volume CBZ. The reader itself sets ``check_srce_page_timestamps=False``,
# so a stale JSON does NOT block runtime loading; this validator is stricter
# on purpose, to catch stale builds.


@dataclass(slots=True)
class _Phase10Counts:
    """Per-phase counters used to populate ``phase.summary_extra``."""

    load_failed: int = 0
    layout_failed: int = 0
    missing_dir: int = 0
    missing_json: int = 0
    stale_json: int = 0


def phase10_layout(
    collector: ErrorCollector,
    sys_paths: SystemFilePaths,
    fanta_state: FantaState,
    titles_filter: list[str] | None = None,
) -> None:
    """Phase 10: check panel-segments JSONs and build each title's reader layout.

    Args:
        collector: Aggregator for phase results.
        sys_paths: Resolved :class:`SystemFilePaths`, for the panel-segments root.
        fanta_state: Cached Phase 6 outcome; a volume archive, when present, is
            what each JSON's staleness is measured against.
        titles_filter: Optional subset of titles to check. ``None`` runs all titles.

    """
    phase = collector.start_phase("Per-title Layouts", "10")

    try:
        db = ComicsDatabase(for_building_comics=False)
    except Exception as exc:  # noqa: BLE001
        phase.add(f"could not construct ComicsDatabase: {exc}")
        collector.finalize_phase(phase)
        return

    panel_segments_root = sys_paths.get_barks_reader_fantagraphics_panel_segments_root_dir()
    builder = ComicLayoutBuilder(
        sorted_pages_port=FantagraphicsPanelSegmentsAdapter(db, panel_segments_root)
    )
    counts = _Phase10Counts()

    for title_str, fanta_info in _loadable_titles(titles_filter):
        phase.items_checked += 1
        try:
            comic = db.get_comic_book(title_str)
        except (
            TitleNotFoundError,
            FileNotFoundError,
            RuntimeError,
            KeyError,
            AssertionError,
        ) as exc:
            counts.load_failed += 1
            phase.add(
                f"Title:{title_str} kind=comic_book_load_failed reason={type(exc).__name__}: {exc}"
            )
            continue

        panel_segments_dir = panel_segments_root / db.get_fantagraphics_volume_title(
            comic.get_fanta_volume()
        )
        archive = _volume_archive(fanta_state, fanta_info)
        if not _check_title_segments(phase, counts, title_str, comic, archive, panel_segments_dir):
            # The layout build reads those same JSONs: it could only fail again on
            # the file already reported.
            continue
        _check_title_layout(phase, counts, title_str, comic, builder)

    phase.summary_extra = (
        f"({counts.load_failed} load-failed,"
        f" {counts.layout_failed} layout-failed,"
        f" {counts.missing_dir} missing-dirs,"
        f" {counts.missing_json} missing-json,"
        f" {counts.stale_json} stale-json)"
    )
    collector.finalize_phase(phase)


def _loadable_titles(titles_filter: list[str] | None) -> list[tuple[str, FantaComicBookInfo]]:
    """Return the titles the reader opens as comics of their own, filtered.

    Individual one-pagers and covers are left out: they are read as a page of the
    "All One-Pagers" / "All Covers" collection, which is itself a title here.
    """
    filter_set = set(titles_filter) if titles_filter is not None else None
    return [
        (ENUM_TO_STR_TITLE[title], fanta_info)
        for title, fanta_info in ALL_FANTA_COMIC_BOOK_INFO.items()
        if (filter_set is None or ENUM_TO_STR_TITLE[title] in filter_set)
        and title not in ONE_PAGERS
        and title not in COVERS_SET
    ]


def _volume_archive(
    fanta_state: FantaState, fanta_info: FantaComicBookInfo
) -> FantagraphicsArchive | None:
    """Return a title's loaded volume archive, or None if Phase 6 has none for it."""
    try:
        volume = get_fanta_volume_from_str(fanta_info.fantagraphics_volume)
    except (AssertionError, ValueError):
        return None  # Phase 8 already records this.
    archive = fanta_state.archives.get(volume)
    if archive is None or archive.is_missing:
        return None  # Phase 8 already records this as missing_volume.
    return archive


def _check_title_segments(
    phase: PhaseResult,
    counts: _Phase10Counts,
    title_str: str,
    comic: ComicBook,
    archive: FantagraphicsArchive | None,
    panel_segments_dir: Path,
) -> bool:
    """Check every panel-segments JSON a title needs; return False if any is missing."""
    if STR_TITLE_TO_ENUM[title_str] in NON_COMIC_TITLES:
        return True

    if not panel_segments_dir.is_dir():
        counts.missing_dir += 1
        phase.add(f"Title:{title_str} kind=missing_segments_dir path={panel_segments_dir}")
        return False

    try:
        srce_and_dest_pages = get_srce_and_dest_pages_in_order(comic, get_full_paths=False)
    except Exception as exc:  # noqa: BLE001
        counts.load_failed += 1
        phase.add(
            f"Title:{title_str} kind=comic_book_load_failed"
            f" reason=page_enum_failed: {type(exc).__name__}: {exc}"
        )
        return False

    all_present = True
    with ExitStack() as stack:
        # Staleness is measured against the page's mtime in the volume archive.
        # Without the archive, only presence can be checked.
        zips = stack.enter_context(_open_volume_zips(archive)) if archive is not None else None
        for srce_page in srce_and_dest_pages.srce_pages:
            if (
                is_title_page(srce_page)
                or is_blank_page(srce_page.page_filename, srce_page.page_type)
                or srce_page.page_type in PAGES_WITHOUT_PANELS
            ):
                continue
            page_str = Path(srce_page.page_filename).stem
            target_zip, member = (
                _page_member(archive, zips, page_str)
                if archive is not None and zips is not None
                else (None, None)
            )
            all_present &= _check_segments_json(
                phase, counts, title_str, page_str, panel_segments_dir, target_zip, member
            )
    return all_present


def _check_segments_json(
    phase: PhaseResult,
    counts: _Phase10Counts,
    title_str: str,
    page_str: str,
    panel_segments_dir: Path,
    target_zip: zipfile.ZipFile | None,
    member: PurePath | None,
) -> bool:
    """Verify the panel-segments JSON exists and is no older than its source page.

    Returns:
        False if the JSON is missing; True otherwise, stale or not.

    """
    json_path = panel_segments_dir / (page_str + JSON_FILE_EXT)
    if not json_path.is_file():
        counts.missing_json += 1
        phase.add(f"Title:{title_str} kind=missing_segments_json page={page_str} path={json_path}")
        return False

    # Compare against the source image's stored mtime inside the zip, not the
    # zip file's own filesystem mtime — the archive is rewritten as a whole
    # whenever any page changes, so its mtime would flag every page in the
    # volume as stale after a single re-pack.
    if target_zip is None or member is None:
        return True
    try:
        # Zip member names always use '/', even on Windows.
        srce_zinfo = target_zip.getinfo(member.as_posix())
    except KeyError:
        return True
    # ZipInfo.date_time is naive local time; mktime interprets it the same way,
    # giving a Unix timestamp comparable to ``st_mtime``.
    srce_mtime = time.mktime((*srce_zinfo.date_time, 0, 0, -1))
    if json_path.stat().st_mtime < srce_mtime:
        counts.stale_json += 1
        logger.debug(
            f"Srce date: {get_timestamp_as_str(srce_mtime)},"
            f" json date: {get_timestamp_as_str(json_path.stat().st_mtime)}"
        )
        phase.add(f"Title:{title_str} kind=stale_segments_json page={page_str} path={json_path}")
    return True


def _check_title_layout(
    phase: PhaseResult,
    counts: _Phase10Counts,
    title_str: str,
    comic: ComicBook,
    builder: ComicLayoutBuilder,
) -> None:
    """Build a title's layout as the reader does, and sanity-check the result."""
    try:
        layout = builder.build(comic)
    except Exception as exc:  # noqa: BLE001 - any raise is a title the reader cannot open
        counts.layout_failed += 1
        phase.add(f"Title:{title_str} kind=layout_build_failed reason={type(exc).__name__}: {exc}")
        return

    page_map = layout.page_map
    if not page_map:
        counts.layout_failed += 1
        phase.add(f"Title:{title_str} kind=layout_empty")
        return
    if not layout.last_body_page and STR_TITLE_TO_ENUM[title_str] not in NON_COMIC_TITLES:
        counts.layout_failed += 1
        phase.add(f"Title:{title_str} kind=layout_no_body_page")
    indexes = [page.page_index for page in page_map.values()]
    if indexes != list(range(len(indexes))):
        counts.layout_failed += 1
        phase.add(f"Title:{title_str} kind=layout_index_gap indexes={indexes}")


# ---------------------------------------------------------------------------
# Phase 11 - Wiki joins
# ---------------------------------------------------------------------------
#
# Joins every title to its wiki story page and every story page back to its
# title, both ways through the app's own functions (wiki_integration). A title
# whose page is not written yet is counted, not failed, unless --strict-wiki:
# the bundle is written a page at a time. A story page the reader cannot reach
# is always a failure — the reader hides the page's "Read Comic" chip for it.


@dataclass(slots=True)
class _Phase11Counts:
    """Per-phase counters used to populate ``phase.summary_extra``."""

    joined: int = 0
    unwritten: int = 0
    no_location: int = 0
    outside_corpus: int = 0
    not_in_reader: int = 0


def resolve_wiki_bundle_dir(
    cfg_info: ConfigInfo, reader_files_dir: Path, override: Path | None
) -> Path | None:
    """Return the wiki bundle the reader would use, or None if there is none.

    Mirrors ``ReaderSettings.wiki_bundle_dir`` without building a
    ``ReaderSettings``: ``override`` (the CLI's ``--wiki-bundle``) wins; else the
    INI's ``wiki_bundle_dir`` when ``use_live_wiki_bundle`` is on; else the copy
    in Reader Files. A directory only counts when its root ``index.md`` exists.

    Args:
        cfg_info: Resolved config, for the INI path.
        reader_files_dir: The Reader Files directory holding the bundled copy.
        override: An explicit bundle directory, or None.

    Returns:
        The bundle root, or None if unset or not a bundle.

    """
    if override is not None:
        candidate = override
    else:
        barks_config = ConfigParser()
        barks_config.read(cfg_info.app_config_path)
        try:
            use_live = bool(read_setting_from_config(barks_config, USE_LIVE_WIKI_BUNDLE))
        except Exception:  # noqa: BLE001
            use_live = False  # the setting's default
        if use_live:
            try:
                value = read_setting_from_config(barks_config, WIKI_BUNDLE_DIR)
            except Exception:  # noqa: BLE001
                return None  # the setting's default is the unset marker
            if str(value) == UNSET_WIKI_BUNDLE_DIR_MARKER:
                return None
            candidate = Path(value)
        else:
            candidate = reader_files_dir / WIKI_BUNDLE_SUBDIR
    if not (candidate / "index.md").is_file():
        return None
    return candidate


def phase11_wiki(
    collector: ErrorCollector,
    bundle: Path | None,
    titles_filter: list[str] | None = None,
    strict: bool = False,
) -> None:
    """Phase 11: join titles to wiki story pages, and story pages to titles.

    Args:
        collector: Aggregator for phase results.
        bundle: The wiki bundle root (from :func:`resolve_wiki_bundle_dir`), or None.
        titles_filter: Optional subset of titles to check. ``None`` runs all
            titles, and then also reports story pages tied to no title.
        strict: Report a title with no page yet as an error, not a count.

    """
    phase = collector.start_phase("Wiki Joins", "11")
    if bundle is None:
        phase.add("Wiki: missing_bundle")
        collector.finalize_phase(phase)
        return
    logger.info(f"Checking the wiki bundle at {bundle}")

    filter_set = (
        {STR_TITLE_TO_ENUM[title_str] for title_str in titles_filter}
        if titles_filter is not None
        else None
    )
    counts = _Phase11Counts()

    pages_by_title = _check_story_pages(phase, counts, bundle, filter_set)
    for title_enum, pages in pages_by_title.items():
        _check_page_reachable(phase, bundle, title_enum, pages)

    for title_enum in ALL_FANTA_COMIC_BOOK_INFO:
        if filter_set is not None and title_enum not in filter_set:
            continue
        phase.items_checked += 1
        _check_title_page(phase, counts, bundle, title_enum, strict)

    phase.summary_extra = (
        f"({counts.joined} joined,"
        f" {counts.unwritten} unwritten,"
        f" {counts.no_location} no-location,"
        f" {counts.outside_corpus} outside-corpus,"
        f" {counts.not_in_reader} not-in-reader)"
    )
    collector.finalize_phase(phase)


def _read_frontmatter(phase: PhaseResult, page: Path, rel: str) -> dict | None:
    """Return a story page's frontmatter, or None once an unreadable page is reported.

    One page that cannot be read (not UTF-8, say) is that page's error: the rest of
    the bundle, and the final report, still get checked.
    """
    try:
        text = page.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        phase.add(f"Page:{rel} kind=story_page_unreadable error={exc!s}")
        return None
    frontmatter, _body = parse_frontmatter(text)
    return frontmatter


def _judge_unjoined_page(
    phase: PhaseResult,
    counts: _Phase11Counts,
    rel: str,
    raw_title: str,
    expected: Titles | None,
    filter_set: set[Titles] | None,
) -> None:
    """Count or report a story page whose title joins no title the reader shows.

    `expected` is the title the page's slug names, if any.
    """
    if canonical_title(raw_title) is not None:
        counts.not_in_reader += 1  # a canonical title the reader does not carry
        return
    if expected is None:
        counts.outside_corpus += 1  # a non-Disney or other non-corpus story
    elif filter_set is None or expected in filter_set:
        phase.add(
            f"Page:{rel} kind=story_page_title_mismatch title={raw_title!r}"
            f" expected={ENUM_TO_STR_TITLE[expected]!r}"
        )


def _check_story_pages(
    phase: PhaseResult,
    counts: _Phase11Counts,
    bundle: Path,
    filter_set: set[Titles] | None,
) -> dict[Titles, list[Path]]:
    """Resolve every story page to its title; return the pages found for each title."""
    slug_to_title = {
        story_slug(ENUM_TO_STR_TITLE[title_enum]): title_enum
        for title_enum in ALL_FANTA_COMIC_BOOK_INFO
    }
    pages_by_title: dict[Titles, list[Path]] = {}

    for page in sorted((bundle / "concept" / "stories").glob("*/*.md")):
        if page.name == "index.md":
            continue
        phase.items_checked += 1
        rel = page.relative_to(bundle).as_posix()
        frontmatter = _read_frontmatter(phase, page, rel)
        if frontmatter is None:
            continue
        raw_title = frontmatter.get("title")

        if not isinstance(raw_title, str):
            if filter_set is None:
                phase.add(f"Page:{rel} kind=story_page_no_title")
            continue

        title_enum = story_page_title(frontmatter, page)
        if title_enum is None:
            _judge_unjoined_page(
                phase, counts, rel, raw_title, slug_to_title.get(page.stem), filter_set
            )
            continue

        if filter_set is None or title_enum in filter_set:
            pages_by_title.setdefault(title_enum, []).append(page)

    return pages_by_title


def _check_page_reachable(
    phase: PhaseResult, bundle: Path, title_enum: Titles, pages: list[Path]
) -> None:
    """Check the reader's title-to-page join lands on this title's one story page."""
    title_str = ENUM_TO_STR_TITLE[title_enum]
    if len(pages) > 1:
        rel_paths = [page.relative_to(bundle).as_posix() for page in pages]
        phase.add(f"Title:{title_str} kind=duplicate_wiki_page pages={rel_paths}")
        return
    page = pages[0]
    if wiki_page_for_title(bundle, title_enum) != page:
        # The reader's chip for this story is hidden: it looks elsewhere.
        phase.add(
            f"Page:{page.relative_to(bundle).as_posix()} kind=wiki_page_unreachable"
            f" title={title_str!r} looked_in={_story_dirs(title_enum)}"
        )


def _check_title_page(
    phase: PhaseResult,
    counts: _Phase11Counts,
    bundle: Path,
    title_enum: Titles,
    strict: bool,
) -> None:
    """Join one title to its story page, counting the title if it has none."""
    if not title_can_have_wiki_page(title_enum):
        counts.no_location += 1
        return
    if wiki_page_for_title(bundle, title_enum) is not None:
        counts.joined += 1
        return

    counts.unwritten += 1
    title_str = ENUM_TO_STR_TITLE[title_enum]
    msg = (
        f"Title:{title_str} kind=missing_wiki_page slug={story_slug(title_str)}"
        f" dirs={_story_dirs(title_enum)}"
    )
    if strict:
        phase.add(msg)
    else:
        logger.warning(f"[{phase.name}] {msg}")


def _story_dirs(title_enum: Titles) -> str:
    """Return the story directories the reader looks in for a title, comma-joined."""
    series_name = ALL_FANTA_COMIC_BOOK_INFO[title_enum].series_name
    return ",".join(SERIES_TO_STORY_DIRS.get(series_name, ()))
