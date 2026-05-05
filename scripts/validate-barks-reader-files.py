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
from barks_reader.core.reader_settings import READER_FILES_DIR
from barks_reader.core.system_file_paths import SystemFilePaths
from comic_utils.common_typer_options import LogLevelArg, TitleArg, VolumesArg  # noqa: TC002
from intspan import intspan
from loguru import logger
from validate_barks_reader_core import (
    ErrorCollector,
    build_reader_file_paths,
    phase1_config,
    phase2_system_file_paths,
    phase3_reader_file_paths,
    phase4_introduction,
    phase5_appendices,
    phase6_fantagraphics,
    phase7_prebuilt_cbzs,
    phase8_per_title,
    phase9_per_title_load,
    phase_audit_panel_files,
)


def resolve_title_filter(volumes_str: str, title_str: str) -> list[str] | None:
    """Resolve ``--volume`` / ``--title`` CLI args to a Phase 8/9 title filter.

    Args:
        volumes_str: ``intspan`` expression (e.g. ``"1-10"``); empty for no
            volume filter.
        title_str: Single comic title; empty for no title filter.

    Returns:
        ``None`` if neither argument is provided (every title is checked).
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


def _print_final_report(
    collector: ErrorCollector, elapsed: float, titles_filter: list[str] | None
) -> None:
    """Emit the summary block and the overall result line."""
    total_filtered_titles = len(titles_filter) if titles_filter else 0
    filter_note = (
        "(No title filter active.)"
        if total_filtered_titles == 0
        else f"(Filtered to {total_filtered_titles} titles.)"
    )

    logger.info("")
    logger.info(f"Validation complete in {elapsed:.1f}s. {filter_note}")
    width = max(len(p.name) for p in collector.phases) + 2
    for phase in collector.phases:
        status = "SKIPPED" if phase.skipped else ("FAIL" if phase.failed else "OK")
        label = (phase.name + ":").ljust(width)
        extra = f" {phase.summary_extra}" if phase.summary_extra else ""
        logger.info(
            f"  {label}{status:7s} ({len(phase.errors)} errors,"
            f" {phase.items_checked:4d} checked){extra}"
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


AppDataDirArg = Annotated[
    Path | None,
    typer.Option(help="Override BARKS_READER_DATA_DIR for this run."),
]
AppConfigDirArg = Annotated[
    Path | None,
    typer.Option(help="Override BARKS_READER_CONFIG_DIR for this run."),
]
ReaderFilesDirArg = Annotated[
    Path | None,
    typer.Option(
        help=(
            "Override the Reader Files directory location."
            f" Defaults to <app-data-dir>/{READER_FILES_DIR}."
        )
    ),
]
TitlesOnlyArg = Annotated[
    bool,
    typer.Option("--titles-only", help="Skip non-title phases (config / system / panels)."),
]
FullLoadCheckArg = Annotated[
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
]


def main(
    app_data_dir: AppDataDirArg = None,
    app_config_dir: AppConfigDirArg = None,
    reader_files_dir: ReaderFilesDirArg = None,
    titles_only: TitlesOnlyArg = False,
    full_load_check: FullLoadCheckArg = False,
    volume: VolumesArg = "",
    title: TitleArg = "",
    log_level: LogLevelArg = "INFO",
) -> None:
    """Validate every on-disk asset the Barks Reader expects at startup."""
    _setup_logging(log_level)
    started = time.time()

    # Resolve the optional title filter early so a bad --volume / --title
    # combination fails before any phase work is done. The same filter is
    # applied to Phase 8 and Phase 9.
    titles_filter = resolve_title_filter(volume, title)

    collector = ErrorCollector()

    cfg_info = phase1_config(collector, app_config_dir, app_data_dir)
    if cfg_info is None:
        _print_final_report(collector, time.time() - started, titles_filter)
        raise typer.Exit(code=1)

    if reader_files_dir is None:
        reader_files_dir = cfg_info.app_data_dir / READER_FILES_DIR

    sys_paths = SystemFilePaths()
    sys_paths.set_barks_reader_files_dir(reader_files_dir, check_files=False)

    if titles_only:
        file_paths_variants = build_reader_file_paths(cfg_info, reader_files_dir)
    else:
        phase2_system_file_paths(collector, sys_paths)
        phase3_reader_file_paths(collector, cfg_info, reader_files_dir)
        file_paths_variants = build_reader_file_paths(cfg_info, reader_files_dir)
        phase4_introduction(collector, sys_paths, file_paths_variants)
        phase5_appendices(collector, sys_paths, file_paths_variants)

    fanta_state = phase6_fantagraphics(collector, cfg_info, sys_paths)
    phase7_prebuilt_cbzs(collector, cfg_info)
    ctx_by_variant = phase8_per_title(collector, file_paths_variants, fanta_state, titles_filter)
    phase_audit_panel_files(
        collector,
        file_paths_variants,
        ctx_by_variant,
        title_filter_active=titles_filter is not None,
    )

    if full_load_check:
        phase9_per_title_load(collector, sys_paths, fanta_state, titles_filter)

    _print_final_report(collector, time.time() - started, titles_filter)
    if collector.any_failed:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
