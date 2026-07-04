# ruff: noqa: T201, PLC0415
"""CLI entry point that opens an OKF bundle in the standalone OKF reader.

Mirrors scripts/read_comic.py: a thin typer command over a workspace package —
here ``okf_reader`` (its own package) — that pins the window to the primary
monitor and runs the Kivy app.

The window is sized exactly as read_comic.py sizes the comic reader (comic-page
aspect ratio plus the action-bar height), so the standalone OKF window matches
the Barks reader it will eventually be embedded into. The Barks packages are
imported here in the launcher only — okf_reader itself stays independent of them
(import-linter contract) and sets no window geometry, since when embedded the
Barks reader owns the window.
"""

from pathlib import Path
from typing import Annotated

import typer
from barks_reader.core.reader_consts_and_types import RAW_ACTION_BAR_SIZE_Y
from barks_reader.core.reader_utils import get_win_dimensions
from barks_reader.core.screen_metrics import SCREEN_METRICS, get_best_window_height_fit
from okf_reader.ui.viewer import run

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
    """Set Kivy graphics config to pin the window before it is realised."""
    from kivy.config import Config

    win_left, win_top, win_width, win_height = _primary_monitor_window_geometry()
    Config.set("graphics", "left", win_left)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "top", win_top)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "width", win_width)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "height", win_height)  # ty: ignore[unresolved-attribute]


@app.command(help="Open an OKF knowledge bundle in the standalone reader.")
def main(
    bundle: Annotated[Path, typer.Argument(help="Path to the OKF bundle directory.")],
) -> None:
    if not bundle.is_dir():
        print(f"error: bundle {bundle} not found")
        raise typer.Exit(code=2)
    _pin_window_to_primary_monitor()
    run(bundle)


if __name__ == "__main__":
    app()
