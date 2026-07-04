# ruff: noqa: T201, PLC0415
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
from configparser import ConfigParser
from pathlib import Path
from typing import Annotated

import okf_reader.ui  # noqa: F401  — kivy-free: only sets KIVY_NO_ARGS for later kivy imports
import typer
from barks_reader.core.reader_consts_and_types import RAW_ACTION_BAR_SIZE_Y
from barks_reader.core.reader_utils import get_win_dimensions
from barks_reader.core.screen_metrics import SCREEN_METRICS, get_best_window_height_fit
from dotenv import load_dotenv
from okf_reader.core.backgrounds import DirPerTitleImageProvider

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


@app.command(help="Open an OKF knowledge bundle in the standalone reader.")
def main(
    bundle: Annotated[Path, typer.Argument(help="Path to the OKF bundle directory.")],
) -> None:
    if not bundle.is_dir():
        print(f"error: bundle {bundle} not found")
        raise typer.Exit(code=2)

    _pin_window_to_primary_monitor()

    # Deferred: okf_reader.ui.viewer imports kivy at module level, so it may only
    # be imported after _pin_window_to_primary_monitor has set the window Config.
    from okf_reader.ui.viewer import run

    run(bundle, image_provider=_favourites_image_provider())


if __name__ == "__main__":
    app()
