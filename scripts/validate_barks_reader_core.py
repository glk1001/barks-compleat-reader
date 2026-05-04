"""Standalone validator for Barks Reader runtime files.

Aggregates every missing or invalid asset discovered across config, system
files, panel sources, intro/appendix documents, Fantagraphics archives,
prebuilt comics, and per-title insets into a single report. Exits non-zero
on any failure.
"""

import os
import zipfile
from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path

from barks_fantagraphics.barks_titles import BARKS_TITLES, Titles
from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comic_book_info import (
    BARKS_TITLE_DICT,
    NON_COMIC_TITLES,
    get_filename_from_title,
)
from barks_fantagraphics.comics_consts import PAGES_WITHOUT_PANELS
from barks_fantagraphics.comics_database import ComicsDatabase, TitleNotFoundError
from barks_fantagraphics.comics_utils import (
    dest_file_is_older_than_srce,
    get_dest_comic_zip_file_stem,
)
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
    FantaComicBookInfo,
    get_fanta_volume_from_str,
)
from barks_fantagraphics.page_classes import CleanPage
from barks_fantagraphics.pages import _get_srce_and_dest_pages_in_order
from barks_reader.core.config_info import ConfigInfo, find_fanta_volumes_dirpath
from barks_reader.core.fantagraphics_volumes import (
    DuplicateArchiveFilesError,
    FantagraphicsArchive,
    FantagraphicsVolumeArchives,
    MissingArchiveFilesError,
    PageExtError,
    PageNumError,
    TooManyArchiveFilesError,
    TooManyOverrideDirsError,
)
from barks_reader.core.reader_file_paths import (
    EDITED_SUBDIR,
    BarksPanelsExtType,
    PanelDirNames,
    ReaderFilePaths,
)
from barks_reader.core.reader_settings import (
    FANTA_DIR,
    JPG_BARKS_PANELS_ZIP,
    PNG_BARKS_PANELS_DIR,
    PREBUILT_COMICS_DIR,
    USE_PNG_IMAGES,
    read_setting_from_config,
)
from barks_reader.core.reader_utils import is_blank_page, is_title_page
from barks_reader.core.system_file_paths import SystemFilePaths
from comic_utils.comic_consts import (
    CBZ_FILE_EXT,
    JPG_FILE_EXT,
    JSON_FILE_EXT,
    PNG_FILE_EXT,
)
from comic_utils.decryption import DecryptionError
from comic_utils.pil_image_utils import load_pil_image_from_zip
from loguru import logger

ALLOW_MISSING_INSETS_LIST_FILENAME = "known-missing-insets.txt"
_PAGE_EXTS = (JPG_FILE_EXT, PNG_FILE_EXT)

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

    def start_phase(self, name: str) -> PhaseResult:
        """Begin a new phase, log a banner, and return its result object."""
        logger.info("")
        logger.info(f"=== Phase: {name} ===")
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


def load_inset_allow_list(path: Path) -> set[str]:
    """Parse the known-missing-insets file into a set of title strings.

    Args:
        path: Path to the allow-list file. Missing file is treated as empty.

    Returns:
        Set of title strings whose missing-inset failures should be suppressed.

    """
    if not path.is_file():
        logger.info(f"Inset allow-list not found ({path}); treating as empty.")
        return set()

    titles: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        titles.add(line)
    logger.info(f"Loaded {len(titles)} title(s) from inset allow-list {path}.")
    return titles


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
    phase = collector.start_phase("Config")

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
    phase = collector.start_phase("SystemFilePaths")

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
        ("about_background_path", sys_paths._about_background_path),  # noqa: SLF001
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


def _resolve_panels_source(
    phase: PhaseResult,
    cfg_info: ConfigInfo,
    reader_files_dir: Path,
) -> tuple[Path, BarksPanelsExtType] | None:
    """Read panel-source settings from the INI and resolve to (path, ext_type).

    Returns ``None`` (after recording an error on ``phase``) if the INI is
    unreadable or the panel-source setting cannot be parsed.
    """
    if not cfg_info.app_config_path.is_file():
        phase.add(f"app config INI not readable: {cfg_info.app_config_path}")
        return None
    barks_config = ConfigParser()
    barks_config.read(cfg_info.app_config_path)
    try:
        use_png_images = bool(read_setting_from_config(barks_config, USE_PNG_IMAGES))
    except Exception as exc:  # noqa: BLE001
        phase.add(f"could not read {USE_PNG_IMAGES} from config: {exc}")
        return None

    if not use_png_images:
        return reader_files_dir / JPG_BARKS_PANELS_ZIP, BarksPanelsExtType.JPG

    try:
        png_dir = read_setting_from_config(barks_config, PNG_BARKS_PANELS_DIR)
    except Exception as exc:  # noqa: BLE001
        phase.add(f"could not read {PNG_BARKS_PANELS_DIR} from config: {exc}")
        return None
    return Path(png_dir), BarksPanelsExtType.MOSTLY_PNG


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


def phase3_reader_file_paths(
    collector: ErrorCollector,
    cfg_info: ConfigInfo,
    reader_files_dir: Path,
) -> None:
    """Validate panel sources (zip or PNG dir + every ``PanelDirNames.*`` entry)."""
    phase = collector.start_phase("ReaderFilePaths")

    resolved = _resolve_panels_source(phase, cfg_info, reader_files_dir)
    if resolved is None:
        collector.finalize_phase(phase)
        return
    panels_source, ext_type = resolved

    phase.items_checked += 1
    if not panels_source.exists():
        phase.add(f"panels_source: missing {panels_source}")
        collector.finalize_phase(phase)
        return

    file_paths = ReaderFilePaths()
    try:
        file_paths.set_barks_panels_source(panels_source, ext_type)
    except FileNotFoundError as exc:
        # The app's _check_panels_dirs raised on the first missing dir.
        # Re-enumerate below so we report every missing one.
        phase.add(f"panels_source check raised: {exc}")
    except Exception as exc:  # noqa: BLE001
        phase.add(f"set_barks_panels_source failed: {exc}")
        collector.finalize_phase(phase)
        return

    _enumerate_panel_dirs(phase, panels_source)
    collector.finalize_phase(phase)


# ---------------------------------------------------------------------------
# Phase 4/5 helpers
# ---------------------------------------------------------------------------


def _validate_title_inset(
    phase: PhaseResult,
    file_paths: ReaderFilePaths | None,
    title_str: str,
    allow_list: set[str],
) -> None:
    """Check that the inset for ``title_str`` exists or is allow-listed."""
    phase.items_checked += 1
    if file_paths is None:
        # Phase 3 already reported the panels_source problem; nothing to do.
        return
    if title_str in allow_list:
        return

    title = BARKS_TITLE_DICT.get(title_str)
    if title in NON_COMIC_TITLES:
        return
    if title is None:
        phase.add(f"Title:{title_str} kind=unknown_title")
        return

    inset_dir = file_paths.get_comic_inset_files_dir()
    inset_filename = get_filename_from_title(title, file_paths.get_inset_file_ext())
    computed = inset_dir / inset_filename
    if not computed.is_file():
        phase.add(f"Title:{title_str} kind=missing_inset path={computed}")


# ---------------------------------------------------------------------------
# Phase 4 - Introduction node
# ---------------------------------------------------------------------------


def phase4_introduction(
    collector: ErrorCollector,
    sys_paths: SystemFilePaths,
    file_paths: ReaderFilePaths | None,
    allow_list: set[str],
) -> None:
    """Validate intro document pages and the intro article inset."""
    phase = collector.start_phase("Introduction")
    _check_dir_has_pages(phase, "intro_doc_dir", sys_paths.get_intro_doc_dir())
    title_str = BARKS_TITLES[_INTRO_ARTICLE]
    _validate_title_inset(phase, file_paths, title_str, allow_list)
    collector.finalize_phase(phase)


# ---------------------------------------------------------------------------
# Phase 5 - Appendices
# ---------------------------------------------------------------------------


def phase5_appendices(
    collector: ErrorCollector,
    sys_paths: SystemFilePaths,
    file_paths: ReaderFilePaths | None,
    allow_list: set[str],
) -> None:
    """Validate censorship-fixes pages and the four appendix article insets."""
    phase = collector.start_phase("Appendices")
    _check_dir_has_pages(
        phase,
        "censorship_fixes_doc_dir",
        sys_paths.get_censorship_fixes_doc_dir(),
    )
    for article in _APPENDIX_ARTICLES:
        _validate_title_inset(phase, file_paths, BARKS_TITLES[article], allow_list)
    collector.finalize_phase(phase)


# ---------------------------------------------------------------------------
# Phase 6 - Per-volume Fantagraphics archives
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class FantaState:
    """Cached Phase 6 outcome consumed by Phase 8."""

    archives: dict[int, FantagraphicsArchive] = field(default_factory=dict)
    error_volumes: set[int] = field(default_factory=set)


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
        except (PageNumError, PageExtError, RuntimeError, ValueError, OSError) as exc:
            state.error_volumes.add(fanta_volume)
            phase.add(f"Volume {fanta_volume}: {type(exc).__name__}: {exc}")
            continue
        state.archives[fanta_volume] = archive


def phase6_fantagraphics(
    collector: ErrorCollector,
    cfg_info: ConfigInfo,
    sys_paths: SystemFilePaths,
) -> FantaState:
    """Replicate :meth:`FantagraphicsVolumeArchives.load` per-volume."""
    phase = collector.start_phase("Fantagraphics")
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


def _process_one_archive(
    archives_mgr: FantagraphicsVolumeArchives,
    fanta_volume: int,
    archive_filename: Path,
    override_archive_filename: Path | None,
) -> FantagraphicsArchive:
    """Replicate the per-archive body of :meth:`FantagraphicsVolumeArchives.load`."""
    image_subdir, image_filenames = archives_mgr._get_archive_contents(archive_filename)  # noqa: SLF001
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
    phase = collector.start_phase("Prebuilt CBZs")

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

    for title_str, fanta_info in ALL_FANTA_COMIC_BOOK_INFO.items():
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


def phase8_per_title(
    collector: ErrorCollector,
    file_paths: ReaderFilePaths | None,
    fanta_state: FantaState,
    allow_list: set[str],
) -> None:
    """Per-title inset + volume-binding sweep across ALL_FANTA_COMIC_BOOK_INFO."""
    phase = collector.start_phase("Per-title")

    missing_inset_count = 0
    invalid_volume_count = 0

    for title_str, fanta_info in ALL_FANTA_COMIC_BOOK_INFO.items():
        before_inset = len(phase.errors)
        _validate_title_inset(phase, file_paths, title_str, allow_list)
        after_inset = len(phase.errors)
        if after_inset > before_inset:
            missing_inset_count += 1

        _validate_title_volume_binding(phase, title_str, fanta_info, fanta_state)
        if len(phase.errors) > after_inset:
            invalid_volume_count += 1

    phase.summary_extra = (
        f"({missing_inset_count} missing insets, {invalid_volume_count} broken volume bindings)"
    )
    collector.finalize_phase(phase)


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
#   3. For pages with panels, verify the per-page panel-segments JSON
#      exists, and is no older than its containing volume CBZ.
#
# Timestamp interpretation: the build pipeline compares JSON mtime to the
# original on-disk source image, but on the reader machine the source
# images live INSIDE the volume CBZ — there is no separate filesystem
# mtime per page. So Phase 9 compares the JSON to the volume CBZ. The
# reader itself sets ``check_srce_page_timestamps=False``, so a stale
# JSON does NOT block runtime loading; this validator is stricter on
# purpose, to catch stale builds.


@dataclass(slots=True)
class _Phase9Counts:
    """Per-phase counters used to populate ``phase.summary_extra``."""

    load_failed: int = 0
    missing_dir: int = 0
    page_load_failed: int = 0
    decryption_failed: int = 0
    missing_json: int = 0
    stale_json: int = 0


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


def _check_one_source_page(
    phase: PhaseResult,
    counts: _Phase9Counts,
    title_str: str,
    archive: FantagraphicsArchive,
    main_zip: zipfile.ZipFile,
    override_zip: zipfile.ZipFile | None,
    panel_segments_dir: Path,
    srce_page: CleanPage,
) -> None:
    """Decode one source page (load_pil) + check its panel-segments JSON."""
    page_filename = srce_page.page_filename
    page_type = srce_page.page_type

    # Skip the empty/title placeholders (the reader resolves these to the
    # in-memory empty_page_image, never opens a zip member).
    if is_title_page(srce_page) or is_blank_page(page_filename, page_type):
        return

    page_str = Path(page_filename).stem
    phase.items_checked += 1

    resolved = _resolve_page_source(archive, page_str)
    if resolved is None:
        counts.page_load_failed += 1
        phase.add(
            f"Title:{title_str} kind=page_load_failed page={page_str} reason=page_not_in_volume"
        )
    else:
        member, source_label, encrypted = resolved
        target_zip = override_zip if encrypted else main_zip
        if target_zip is None:
            counts.page_load_failed += 1
            phase.add(
                f"Title:{title_str} kind=page_load_failed page={page_str}"
                f" source={source_label} reason=override_archive_not_open"
            )
        else:
            # Call the canonical loader inside ``comic_utils.pil_image_utils``;
            # ``image_pipeline.load_pil`` is functionally equivalent but the
            # compiled Cython panel-key module restricts the encrypted-decrypt
            # path to a fixed allow-list of callers (``comic_utils.pil_image_utils``
            # is on it; ``barks_reader.core.image_pipeline`` is not). Using the
            # allowed entry point keeps Phase 9 honest without bypassing the
            # caller check.
            try:
                load_pil_image_from_zip(
                    zipfile.Path(target_zip, at=str(member)),
                    encrypted=encrypted,
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

    # Panel-segments JSON only required for pages with panels.
    if page_type in PAGES_WITHOUT_PANELS:
        return

    json_path = panel_segments_dir / (page_str + JSON_FILE_EXT)
    if not json_path.is_file():
        counts.missing_json += 1
        phase.add(f"Title:{title_str} kind=missing_segments_json page={page_str} path={json_path}")
        return
    if dest_file_is_older_than_srce(
        archive.archive_filename, json_path, include_missing_dest=False
    ):
        counts.stale_json += 1
        phase.add(f"Title:{title_str} kind=stale_segments_json page={page_str} path={json_path}")


def check_one_title_load(
    phase: PhaseResult,
    counts: _Phase9Counts,
    sys_paths: SystemFilePaths,
    title_str: str,
    comic: ComicBook,
    archive: FantagraphicsArchive,
) -> None:
    """Open archives, enumerate source pages, and check each one."""
    volume = archive.fanta_volume
    panel_segments_root = sys_paths.get_barks_reader_fantagraphics_panel_segments_root_dir()
    vol_dir_name = ComicsDatabase.get_fantagraphics_volume_title(volume)
    panel_segments_dir = panel_segments_root / vol_dir_name

    if not panel_segments_dir.is_dir():
        counts.missing_dir += 1
        phase.add(f"Title:{title_str} kind=missing_segments_dir path={panel_segments_dir}")
        return

    # Enumerate source pages. Use the private helper that produces the page
    # list without doing the JSON I/O the public ``get_sorted_srce_and_dest_pages_*``
    # variants would. Phase 9 does that I/O itself, error-collected.
    try:
        srce_and_dest_pages = _get_srce_and_dest_pages_in_order(comic, get_full_paths=False)
    except Exception as exc:  # noqa: BLE001
        counts.load_failed += 1
        phase.add(
            f"Title:{title_str} kind=comic_book_load_failed"
            f" reason=page_enum_failed: {type(exc).__name__}: {exc}"
        )
        return

    main_zip: zipfile.ZipFile | None = None
    override_zip: zipfile.ZipFile | None = None
    try:
        try:
            main_zip = zipfile.ZipFile(archive.archive_filename, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            counts.page_load_failed += len(srce_and_dest_pages.srce_pages)
            phase.add(
                f"Title:{title_str} kind=page_load_failed page=*"
                f" reason=cannot_open_volume_cbz: {exc}"
            )
            return

        if archive.has_overrides() and archive.override_archive_filename is not None:
            try:
                override_zip = zipfile.ZipFile(archive.override_archive_filename, "r")
            except (zipfile.BadZipFile, OSError) as exc:
                phase.add(
                    f"Title:{title_str} kind=page_load_failed page=*"
                    f" reason=cannot_open_override_cbz: {exc}"
                )
                # continue without overrides — per-page checks will then fail
                # on any page that needed an override

        for srce_page in srce_and_dest_pages.srce_pages:
            _check_one_source_page(
                phase,
                counts,
                title_str,
                archive,
                main_zip,
                override_zip,
                panel_segments_dir,
                srce_page,
            )
    finally:
        if override_zip is not None:
            override_zip.close()
        if main_zip is not None:
            main_zip.close()


def phase9_per_title_load(
    collector: ErrorCollector,
    sys_paths: SystemFilePaths,
    fanta_state: FantaState,
    titles_filter: list[str] | None = None,
) -> None:
    """Phase 9: dry-run the loader for every title, as if use_prebuilt_comics=0.

    Catches missing/unreadable source pages, missing/stale panel-segments
    JSONs, and ComicBook construction failures (per-title INI errors).

    Args:
        collector: Aggregator for phase results.
        sys_paths: Resolved :class:`SystemFilePaths` from Phase 2.
        fanta_state: Cached Phase 6 outcome.
        titles_filter: Optional subset of titles to check (from
            :func:`resolve_phase9_title_filter`). ``None`` runs all titles.

    """
    phase = collector.start_phase("PerTitleLoad")
    logger.info(
        "Phase 9: per-title full-load dry-run."
        " Decodes every source page through image_pipeline.load_pil"
        " and checks each panel-segments JSON exists + is no older than"
        " its volume CBZ. This may take a minute or two."
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
    filter_set = set(titles_filter) if titles_filter is not None else None

    candidates = [
        (title_str, fanta_info)
        for title_str, fanta_info in ALL_FANTA_COMIC_BOOK_INFO.items()
        if filter_set is None or title_str in filter_set
    ]
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

        check_one_title_load(phase, counts, sys_paths, title_str, comic, archive)

    phase.summary_extra = (
        f"({counts.load_failed} load-failed,"
        f" {counts.missing_dir} missing-dirs,"
        f" {counts.page_load_failed} page-load-failed,"
        f" {counts.decryption_failed} decryption-failed,"
        f" {counts.missing_json} missing-json,"
        f" {counts.stale_json} stale-json)"
    )
    collector.finalize_phase(phase)


def build_reader_file_paths(cfg_info: ConfigInfo, reader_files_dir: Path) -> ReaderFilePaths | None:
    """Construct a :class:`ReaderFilePaths` for inset lookups, or return ``None``.

    Phase 3 already reported any structural error; this helper only succeeds if
    the panel source can be opened. Failures are silent so callers can fall back
    to skipping inset checks rather than re-reporting the same error.
    """
    barks_config = ConfigParser()
    barks_config.read(cfg_info.app_config_path)
    try:
        use_png_images = bool(read_setting_from_config(barks_config, USE_PNG_IMAGES))
    except Exception:  # noqa: BLE001
        return None

    if use_png_images:
        try:
            png_dir = read_setting_from_config(barks_config, PNG_BARKS_PANELS_DIR)
        except Exception:  # noqa: BLE001
            return None
        panels_source = Path(png_dir)
        ext_type = BarksPanelsExtType.MOSTLY_PNG
    else:
        panels_source = reader_files_dir / JPG_BARKS_PANELS_ZIP
        ext_type = BarksPanelsExtType.JPG

    if not panels_source.exists():
        return None

    file_paths = ReaderFilePaths()
    try:
        file_paths.set_barks_panels_source(panels_source, ext_type)
    except FileNotFoundError:
        # Panels source incomplete; inset paths still resolve relative to the
        # configured INSETS dir, so keep the object.
        return file_paths
    except Exception:  # noqa: BLE001
        return None
    else:
        return file_paths
