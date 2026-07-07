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
first kivy import so typer, not kivy, owns the command line). The
``barks_reader.core.config_info`` import redirects KIVY_HOME to the app's config
directory (its guard requires it to precede any kivy import), so this launcher
reads the same known-good kivy ini as read_comic.py/main.py rather than
``~/.kivy/config.ini``.

The window is sized exactly as read_comic.py sizes the comic reader (comic-page
aspect ratio plus the action-bar height), so the standalone OKF window matches
the Barks reader it will eventually be embedded into. The Barks packages are
imported here in the launcher only — okf_reader itself stays independent of them
(import-linter contract) and sets no window geometry, since when embedded the
Barks reader owns the window.
"""

import subprocess
import sys
from configparser import ConfigParser
from pathlib import Path
from typing import Annotated

import okf_reader.ui  # noqa: F401  — kivy-free: only sets KIVY_NO_ARGS for later kivy imports
import typer
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE
from barks_fantagraphics.comic_book_info import is_one_pager_located
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_reader.core.config_info import ConfigInfo
from barks_reader.core.reader_consts_and_types import RAW_ACTION_BAR_SIZE_Y
from barks_reader.core.reader_settings import ReaderSettings
from barks_reader.core.reader_setup import bootstrap_reader_environment
from barks_reader.core.reader_utils import get_win_dimensions
from barks_reader.core.screen_metrics import SCREEN_METRICS, get_best_window_height_fit
from barks_reader.core.wiki_integration import (
    WIKI_TITLE,
    BarksPanelsImageProvider,
    BarksTableRewriter,
    canonical_title,
    story_page_title,
    title_can_have_wiki_page,
    wiki_page_for_title,
    wiki_session_path,
    wiki_top_bar_spec,
)
from cli_setup import init_logging
from comic_utils.common_typer_options import LogLevelArg
from dotenv import load_dotenv
from loguru import logger
from okf_reader.core.actions import PageAction
from okf_reader.core.render import resolve_link
from okf_reader.core.top_bar import TopBarSpec

load_dotenv(Path(__file__).parent.parent / ".env.runtime")

APP_LOGGING_NAME = "okf"

app = typer.Typer()


def _primary_monitor_window_geometry() -> tuple[int, int, int, int]:
    """Return ``(left, top, width, height)`` for a window pinned to the primary monitor.

    Mirrors scripts/read_comic.py:_primary_monitor_window_geometry so the standalone
    OKF window matches the comic reader's window.
    """
    primary = SCREEN_METRICS.get_primary_screen_info()
    margin = 60
    max_height = get_best_window_height_fit(primary.height_pixels) - margin
    win_width, content_h = get_win_dimensions(
        max_height - RAW_ACTION_BAR_SIZE_Y, primary.width_pixels
    )
    win_height = content_h + RAW_ACTION_BAR_SIZE_Y
    win_left = primary.monitor_x + round(primary.width_pixels / 2) - round(win_width / 2)
    win_top = primary.monitor_y + margin // 2
    return win_left, win_top, win_width, win_height


def _pin_window_to_primary_monitor() -> int:
    """Pin the Kivy window to the primary monitor; return the window height.

    First kivy import of the process happens here, deliberately: the geometry is
    computed and written to Config before kivy can realize the window.

    KIVY_HOME points at the app's config directory (redirected by the module's
    ``config_info`` import), but every graphics setting that affects placement
    is still set explicitly rather than trusted from any ini. In particular
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
    logger.info(
        f"OKF window pinned to primary monitor: ({win_left},{win_top}) {win_width}x{win_height}."
    )

    return win_height


def _barks_top_bar_spec(reader_settings: ReaderSettings | None, win_height: int) -> TopBarSpec:
    """Dress the okf action bar like the Barks Reader's.

    The shared `wiki_top_bar_spec` builder, with the default ``on_close`` (stop
    the app). Deferred kivy import: ``FontManager`` may only be imported once
    the window Config is decided, so this must be called after
    ``_pin_window_to_primary_monitor``. Without a bootstrapped environment the
    bar degrades to a plain-text title with no icons.
    """
    if reader_settings is None:
        return TopBarSpec(title_markup=WIKI_TITLE, height=RAW_ACTION_BAR_SIZE_Y)

    from barks_reader.ui.font_manager import FontManager

    # Seeded with the window height, exactly as read_comic.py does — without it
    # the title's [size=...] markup expands to size=0 and renders invisibly.
    font_manager = FontManager()
    font_manager.update_font_sizes(win_height)

    return wiki_top_bar_spec(font_manager, reader_settings.sys_file_paths)


def _bootstrap_barks_reader() -> tuple[ReaderSettings, ComicsDatabase, ConfigInfo] | None:
    """Wire ``ReaderSettings`` + ``ComicsDatabase`` to the on-disk config.

    The same boot sequence as scripts/read_comic.py. Returns None if the
    environment isn't configured (missing ini, panels source, comics dir…) —
    reading the wiki must survive that, just without backgrounds, Read Comic
    buttons, or session restore.
    """
    try:
        config_info = ConfigInfo()
        parser = ConfigParser()
        parser.read(config_info.app_config_path)
        reader_settings = ReaderSettings()
        comics_database = ComicsDatabase(for_building_comics=False)
        bootstrap_reader_environment(reader_settings, comics_database, parser, config_info)
    except Exception:  # noqa: BLE001 — reading the wiki must survive this
        logger.exception("Barks reader environment unavailable:")
        return None
    return reader_settings, comics_database, config_info


class ReadComicActionProvider:
    """Offer "Read Comic" on wiki story pages (an okf_reader PageActionProvider).

    A page qualifies when it lives under ``concept/stories/``, its frontmatter
    title maps to a canonical Barks title with a Fantagraphics entry, **and**
    read_comic.py can serve it: either the comics database knows the title, or
    it is a located one-pager (read_comic.py opens those via the synthetic
    "All One-Pagers" collection at the right page; unlocated ones get no
    button). The comic reader is a separate Kivy app, so it launches as a
    subprocess; when the wiki reader is embedded in the Barks Reader this
    becomes an in-app screen switch instead.
    """

    def __init__(self, comics_database: ComicsDatabase | None = None) -> None:
        self._last_launch: subprocess.Popen | None = None
        self._comics_database = comics_database
        self._database_unavailable = False

    def _story_in_database(self, canonical_title: str) -> bool:
        """Whether the comics database can serve ``canonical_title`` as a comic.

        If no database was injected, one is built lazily on the first story page
        viewed; if it cannot be built at all (e.g. an unconfigured environment),
        the wiki reader keeps working and simply offers no Read Comic buttons.
        """
        if self._comics_database is None and not self._database_unavailable:
            try:
                self._comics_database = ComicsDatabase(for_building_comics=False)
            except Exception:  # noqa: BLE001 — reading the wiki must survive this
                logger.exception("Comics database unavailable:")
                self._database_unavailable = True
        if self._comics_database is None:
            return False
        found, _close = self._comics_database.is_story_title(canonical_title)
        return found

    def action_for(self, frontmatter: dict, page_path: Path) -> PageAction | None:
        """Return the "Read Comic" action for a story page, else None."""
        title_enum = story_page_title(frontmatter, page_path)
        if title_enum is None:
            return None
        canonical = ENUM_TO_STR_TITLE[title_enum]
        if not (is_one_pager_located(title_enum) or self._story_in_database(canonical)):
            return None
        return PageAction("Read Comic", lambda: self._launch(canonical))

    def _launch(self, canonical_title: str) -> None:
        if self._last_launch is not None and self._last_launch.poll() is None:
            logger.info("Comic reader already open; not launching another.")
            return
        logger.info(f'Launching comic reader for "{canonical_title}"...')
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
    title_enum = canonical_title(arg)
    if title_enum is None:
        return None, f"no bundle page or canonical story title matches {arg!r}"
    if not title_can_have_wiki_page(title_enum):
        return None, f"{arg!r} is a known title but not one with a wiki story page"
    page = wiki_page_for_title(bundle, title_enum)
    if page is None:
        return None, f"{arg!r} is a known story but its wiki page is not written yet"
    return page, ""


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
    log_level_str: LogLevelArg = "INFO",
) -> None:
    init_logging(APP_LOGGING_NAME, "read-okf.log", log_level_str)

    if not bundle.is_dir():
        typer.echo(f"error: bundle {bundle} not found", err=True)
        raise typer.Exit(code=2)

    start_page: Path | None = None
    if page:
        start_page, error = _resolve_start_page(bundle, page)
        if start_page is None:
            typer.echo(f"error: {error}", err=True)
            raise typer.Exit(code=2)

    logger.info(f'Opening OKF bundle "{bundle}"' + (f' at "{start_page}".' if start_page else "."))

    # Bootstrap the Barks reader environment before any window appears, so a
    # misconfiguration warning prints while the terminal still has the user's eye.
    barks_env = _bootstrap_barks_reader()
    reader_settings = None
    comics_database = None
    state_path = None
    if barks_env is not None:
        reader_settings, comics_database, config_info = barks_env
        # Resume where the last session left off; the state lives beside the
        # app's other per-user data, keyed by bundle path (the same file the
        # embedded wiki screen uses for the same bundle — and a different one
        # for any other bundle, so reading elsewhere can't clobber the wiki's
        # resume point).
        state_path = wiki_session_path(Path(config_info.app_data_dir), bundle)
    image_provider = (
        BarksPanelsImageProvider(reader_settings) if reader_settings is not None else None
    )

    win_height = _pin_window_to_primary_monitor()

    # Deferred: okf_reader.ui.viewer imports kivy at module level, so it may only
    # be imported after _pin_window_to_primary_monitor has set the window Config.
    from okf_reader.ui.viewer import run

    run(
        bundle,
        image_provider=image_provider,
        table_rewriter=BarksTableRewriter(),
        start_page=start_page,
        action_provider=ReadComicActionProvider(comics_database),
        top_bar=_barks_top_bar_spec(reader_settings, win_height),
        state_path=state_path,
    )


if __name__ == "__main__":
    app()
