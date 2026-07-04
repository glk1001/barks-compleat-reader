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

from pathlib import Path
from typing import Annotated

import okf_reader.ui  # noqa: F401  — kivy-free: only sets KIVY_NO_ARGS for later kivy imports
import typer
from barks_reader.core.reader_consts_and_types import RAW_ACTION_BAR_SIZE_Y
from barks_reader.core.reader_utils import get_win_dimensions
from barks_reader.core.screen_metrics import SCREEN_METRICS, get_best_window_height_fit

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

    Two-stage pinning. The create-time Config values reliably set the *size*, but
    the window manager is free to ignore SDL's create-time position hint and
    place the window itself (observed: requested (2763,10), WM placed it on the
    other monitor). So the position is re-asserted once the window is realised —
    assigning ``Window.left``/``Window.top`` calls SDL_SetWindowPosition on the
    live window, a post-map move most WMs honour (GNOME Wayland refuses both).
    """
    win_left, win_top, win_width, win_height = _primary_monitor_window_geometry()

    from kivy.config import Config

    # Without position=custom, Kivy's SDL2 backend ignores left/top entirely.
    Config.set("graphics", "position", "custom")  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "left", win_left)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "top", win_top)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "width", win_width)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "height", win_height)  # ty: ignore[unresolved-attribute]

    # Importing Window realizes the SDL window, so this must come after the
    # Config.set calls above (Config feeds the window's creation parameters).
    from kivy.core.window import Window

    def _reassert_position(*_args: object) -> None:
        Window.left = win_left
        Window.top = win_top

    # By on_draw the window is mapped, so the move sticks; unbind after one shot.
    def _once(*args: object) -> None:
        Window.unbind(on_draw=_once)
        _reassert_position(*args)

    Window.bind(on_draw=_once)


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

    run(bundle)


if __name__ == "__main__":
    app()
