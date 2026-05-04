"""Standalone validator for Barks Reader runtime files.

Aggregates every missing or invalid asset discovered across config, system
files, panel sources, intro/appendix documents, Fantagraphics archives,
prebuilt comics, and per-title insets into a single report. Exits non-zero
on any failure.

Run via ``uv run scripts/validate-barks-reader-files.py``. The script never
imports Kivy or any UI module: it reads the same on-disk layout as the
running app but without touching the GUI stack, so it can be wired into
post-install / post-deploy checks.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Annotated

import typer
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.comics_helpers import get_titles
from barks_reader.core.reader_settings import READER_FILES_DIR, USE_PREBUILT_COMICS
from barks_reader.core.system_file_paths import SystemFilePaths
from dotenv import load_dotenv
from intspan import intspan
from loguru import logger

# Load env vars (BARKS_READER_CONFIG_DIR, BARKS_READER_DATA_DIR, ...) before
# importing barks_reader.core.config_info, which constructs nothing at module
# load time but does set Kivy/SDL env vars defensively.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env.runtime")

from comic_utils.common_typer_options import TitleArg, VolumesArg  # noqa: E402, TC002
from validate_barks_reader_core import (  # noqa: E402
    ALLOW_MISSING_INSETS_LIST_FILENAME,
    ErrorCollector,
    build_reader_file_paths,
    load_inset_allow_list,
    phase1_config,
    phase2_system_file_paths,
    phase3_reader_file_paths,
    phase4_introduction,
    phase5_appendices,
    phase6_fantagraphics,
    phase7_prebuilt_cbzs,
    phase8_per_title,
    phase9_per_title_load,
)


def resolve_phase9_title_filter(volumes_str: str, title_str: str) -> list[str] | None:
    """Resolve ``--volume`` / ``--title`` CLI args to a Phase 9 title filter.

    Args:
        volumes_str: ``intspan`` expression (e.g. ``"1-10"``); empty for no
            volume filter.
        title_str: Single comic title; empty for no title filter.

    Returns:
        ``None`` if neither argument is provided (Phase 9 runs every title).
        Otherwise, the list of titles matching the filter.

    Raises:
        typer.BadParameter: If both arguments are provided together.

    """
    if volumes_str and title_str:
        msg = "Options --volume and --title are mutually exclusive."
        raise typer.BadParameter(msg)
    if not volumes_str and not title_str:
        return None
    volumes = list(intspan(volumes_str))
    db = ComicsDatabase(for_building_comics=False)
    return get_titles(db, volumes, title_str)


def _print_final_report(collector: ErrorCollector, elapsed: float) -> None:
    """Emit the summary block and the overall result line."""
    logger.info("")
    logger.info(f"Validation complete in {elapsed:.1f}s.")
    width = max(len(p.name) for p in collector.phases) + 2
    for phase in collector.phases:
        status = "SKIPPED" if phase.skipped else ("FAIL" if phase.failed else "OK")
        label = (phase.name + ":").ljust(width)
        extra = f" {phase.summary_extra}" if phase.summary_extra else ""
        logger.info(
            f"  {label}{status:7s} ({len(phase.errors)} errors,"
            f" {phase.items_checked} checked){extra}"
        )
    overall = "FAIL" if collector.any_failed else "OK"
    logger.info(f"Result: {overall}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _setup_logging(log_level: str) -> None:
    """Configure loguru to emit a single, predictable stream to stdout."""
    logger.remove()
    logger.add(
        sys.stdout,
        level=log_level.upper(),
        format=(
            "<green>{time:HH:mm:ss}</green> <level>{level:<7}</level> <level>{message}</level>"
        ),
    )


def main(
    app_data_dir: Annotated[
        Path | None,
        typer.Option(help="Override BARKS_READER_DATA_DIR for this run."),
    ] = None,
    app_config_dir: Annotated[
        Path | None,
        typer.Option(help="Override BARKS_READER_CONFIG_DIR for this run."),
    ] = None,
    reader_files_dir: Annotated[
        Path | None,
        typer.Option(
            help=(
                "Override the Reader Files directory location."
                f" Defaults to <app-data-dir>/{READER_FILES_DIR}."
            )
        ),
    ] = None,
    titles_only: Annotated[
        bool,
        typer.Option("--titles-only", help="Skip non-title phases (config / system / panels)."),
    ] = False,
    full_load_check: Annotated[
        bool,
        typer.Option(
            "--full-load-check",
            help=(
                "Run Phase 9: dry-run the comic loader for every title (as if"
                " use_prebuilt_comics=0). Reads each source page from its"
                " volume / override CBZ via the same image_pipeline.load_pil"
                " call the reader uses, and verifies every required"
                " panel-segments JSON exists and is no older than its volume CBZ."
                " Adds ~30-90s of wall time."
            ),
        ),
    ] = False,
    volume: VolumesArg = "",
    title: TitleArg = "",
    log_level: Annotated[
        str,
        typer.Option(help="Loguru log level (TRACE/DEBUG/INFO/WARNING/ERROR)."),
    ] = "INFO",
) -> None:
    """Validate every on-disk asset the Barks Reader expects at startup."""
    _setup_logging(log_level)
    started = time.time()

    # Resolve the optional Phase 9 title filter early so a bad --volume / --title
    # combination fails before any phase work is done.
    titles_filter = resolve_phase9_title_filter(volume, title)

    collector = ErrorCollector()

    cfg_info = phase1_config(collector, app_config_dir, app_data_dir)
    if cfg_info is None:
        _print_final_report(collector, time.time() - started)
        raise typer.Exit(code=1)

    if reader_files_dir is None:
        reader_files_dir = cfg_info.app_data_dir / READER_FILES_DIR

    sys_paths = SystemFilePaths()
    sys_paths.set_barks_reader_files_dir(reader_files_dir, check_files=False)

    allow_list = load_inset_allow_list(
        _PROJECT_ROOT / "scripts" / ALLOW_MISSING_INSETS_LIST_FILENAME
    )

    if not titles_only:
        phase2_system_file_paths(collector, sys_paths)
        phase3_reader_file_paths(collector, cfg_info, reader_files_dir)
        file_paths = build_reader_file_paths(cfg_info, reader_files_dir)
        phase4_introduction(collector, sys_paths, file_paths, allow_list)
        phase5_appendices(collector, sys_paths, file_paths, allow_list)
    else:
        file_paths = build_reader_file_paths(cfg_info, reader_files_dir)

    fanta_state = phase6_fantagraphics(collector, cfg_info, sys_paths)
    phase7_prebuilt_cbzs(collector, cfg_info)
    phase8_per_title(collector, file_paths, fanta_state, allow_list)

    if full_load_check:
        phase9_per_title_load(collector, sys_paths, fanta_state, titles_filter)

    _print_final_report(collector, time.time() - started)
    if collector.any_failed:
        raise typer.Exit(code=1)


# Silence the "use_prebuilt_archives" unused-import false positive: the symbol
# is part of the public API surface we mirror, but the validator never reads
# the flag (Phase 7 always runs).
_ = USE_PREBUILT_COMICS


if __name__ == "__main__":
    typer.run(main)
