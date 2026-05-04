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
from barks_reader.core.reader_settings import READER_FILES_DIR, USE_PREBUILT_COMICS
from barks_reader.core.system_file_paths import SystemFilePaths
from dotenv import load_dotenv
from loguru import logger

# Load env vars (BARKS_READER_CONFIG_DIR, BARKS_READER_DATA_DIR, ...) before
# importing barks_reader.core.config_info, which constructs nothing at module
# load time but does set Kivy/SDL env vars defensively.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env.runtime")

from validate_barks_reader_core import (  # noqa: E402
    _ALLOW_LIST_FILENAME,
    ErrorCollector,
    _build_reader_file_paths,
    _load_inset_allow_list,
    _phase1_config,
    _phase2_system_file_paths,
    _phase3_reader_file_paths,
    _phase4_introduction,
    _phase5_appendices,
    _phase6_fantagraphics,
    _phase7_prebuilt_cbzs,
    _phase8_per_title,
    _phase9_per_title_load,
    _print_final_report,
)

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
    log_level: Annotated[
        str,
        typer.Option(help="Loguru log level (TRACE/DEBUG/INFO/WARNING/ERROR)."),
    ] = "INFO",
) -> None:
    """Validate every on-disk asset the Barks Reader expects at startup."""
    _setup_logging(log_level)
    started = time.time()

    collector = ErrorCollector()

    cfg_info = _phase1_config(collector, app_config_dir, app_data_dir)
    if cfg_info is None:
        _print_final_report(collector, time.time() - started)
        raise typer.Exit(code=1)

    if reader_files_dir is None:
        reader_files_dir = cfg_info.app_data_dir / READER_FILES_DIR

    sys_paths = SystemFilePaths()
    sys_paths.set_barks_reader_files_dir(reader_files_dir, check_files=False)

    allow_list = _load_inset_allow_list(_PROJECT_ROOT / "scripts" / _ALLOW_LIST_FILENAME)

    if not titles_only:
        _phase2_system_file_paths(collector, sys_paths)
        _phase3_reader_file_paths(collector, cfg_info, reader_files_dir)
        file_paths = _build_reader_file_paths(cfg_info, reader_files_dir)
        _phase4_introduction(collector, sys_paths, file_paths, allow_list)
        _phase5_appendices(collector, sys_paths, file_paths, allow_list)
    else:
        file_paths = _build_reader_file_paths(cfg_info, reader_files_dir)

    fanta_state = _phase6_fantagraphics(collector, cfg_info, sys_paths)
    _phase7_prebuilt_cbzs(collector, cfg_info)
    _phase8_per_title(collector, file_paths, fanta_state, allow_list)

    if full_load_check:
        _phase9_per_title_load(collector, sys_paths, fanta_state)

    _print_final_report(collector, time.time() - started)
    if collector.any_failed:
        raise typer.Exit(code=1)


# Silence the "use_prebuilt_archives" unused-import false positive: the symbol
# is part of the public API surface we mirror, but the validator never reads
# the flag (Phase 7 always runs).
_ = USE_PREBUILT_COMICS


if __name__ == "__main__":
    typer.run(main)
