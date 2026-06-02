# ruff: noqa: PLC0415, T201
"""CLI entry point that opens a single Barks comic title in the comic reader.

Mirrors the relevant slice of ``main.py`` / ``BarksReaderApp``: imports
``barks_reader.core.config_info`` before any kivy import, sets up
``ReaderSettings``, looks up the requested title, and hands off to a minimal
single-screen Kivy app hosting ``ComicBookReaderScreen``.
"""

from configparser import ConfigParser
from pathlib import Path

import typer
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM
from barks_fantagraphics.comic_book import ComicBook
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    FantaComicBookInfo,
)

# IMPORTANT: ``barks_reader.core.config_info`` must be imported before any kivy
# import. A runtime guard inside that module enforces this.
from barks_reader.core.comic_book_page_info import ComicLayoutBuilder
from barks_reader.core.config_info import ConfigInfo
from barks_reader.core.fantagraphics_volumes import MissingVolumeError
from barks_reader.core.page_info_adapters import FantagraphicsPanelSegmentsAdapter
from barks_reader.core.reader_consts_and_types import COMIC_BEGIN_PAGE, RAW_ACTION_BAR_SIZE_Y
from barks_reader.core.reader_settings import ReaderSettings
from barks_reader.core.reader_setup import bootstrap_reader_environment, prepare_comic_for_reading
from barks_reader.core.reader_utils import get_win_dimensions
from barks_reader.core.screen_metrics import SCREEN_METRICS, get_best_window_height_fit
from cli_setup import init_logging
from comic_utils.common_typer_options import LogLevelArg
from dotenv import load_dotenv
from loguru import logger

APP_LOGGING_NAME = "read"

load_dotenv(Path(__file__).parent.parent / ".env.runtime")


app = typer.Typer()


@app.command(help="Open a single Barks comic title in the comic reader.")
def main(
    title: str = typer.Argument(..., help="Exact comic title (e.g. 'Lost in the Andes')."),
    log_level_str: LogLevelArg = "INFO",
) -> None:
    init_logging(APP_LOGGING_NAME, "read-comic.log", log_level_str)

    title_enum = STR_TITLE_TO_ENUM.get(title)
    fanta_info = ALL_FANTA_COMIC_BOOK_INFO.get(title_enum) if title_enum is not None else None
    if fanta_info is None:
        _print_title_not_found(title)
        raise typer.Exit(code=2)

    config_info = ConfigInfo()
    parser = ConfigParser()
    parser.read(config_info.app_config_path)

    reader_settings = ReaderSettings()
    comics_database = ComicsDatabase(for_building_comics=False)
    bootstrap_reader_environment(reader_settings, comics_database, parser, config_info)

    comic = comics_database.get_comic_book(title)

    _run_cli_reader(reader_settings, comics_database, fanta_info, comic)


def _print_title_not_found(title_str: str) -> None:
    needle = title_str.lower()
    title_strs = [ENUM_TO_STR_TITLE[t] for t in ALL_FANTA_COMIC_BOOK_INFO]
    suggestions = [t for t in title_strs if needle in t.lower()]
    print(f'Title not found: "{title_str}".')
    if suggestions:
        print("Did you mean one of:")
        for suggestion in suggestions[:20]:
            print(f"  - {suggestion}")
    else:
        print("Use an exact title string. Some examples:")
        for suggestion in title_strs[:5]:
            print(f"  - {suggestion}")


def _primary_monitor_window_geometry() -> tuple[int, int, int, int]:
    """Return ``(left, top, width, height)`` for a window pinned to the primary monitor.

    Mirrors the slice of ``main.py:get_main_win_from_screen_metrics`` /
    ``set_window_size`` that sizes the main app's window.
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


def _run_cli_reader(
    reader_settings: ReaderSettings,
    comics_database: ComicsDatabase,
    fanta_info: FantaComicBookInfo,
    comic: ComicBook,
) -> None:
    # Deferred kivy imports — must happen only after ``ConfigInfo()`` has set
    # KIVY_HOME.
    from kivy.config import Config

    # Pin the window onto the primary monitor before the Window is realised.
    # The shared barks-reader.ini may carry coordinates from a previous run on
    # a different monitor, which otherwise leaves a black window on the wrong
    # display.
    win_left, win_top, win_width, win_height = _primary_monitor_window_geometry()
    Config.set("graphics", "left", win_left)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "top", win_top)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "width", win_width)  # ty: ignore[unresolved-attribute]
    Config.set("graphics", "height", win_height)  # ty: ignore[unresolved-attribute]
    logger.info(
        f"CLI window pinned to primary monitor: ({win_left},{win_top}) {win_width}x{win_height}."
    )

    app_cls = _build_cli_app_class(reader_settings, comics_database, fanta_info, comic, win_height)

    try:
        app_cls().run()
    except MissingVolumeError as exc:
        logger.error(f"Cannot read '{exc.title}': missing volume '{exc.missing_vol}'.")
        raise typer.Exit(code=1) from exc


def _build_cli_app_class(
    reader_settings: ReaderSettings,
    comics_database: ComicsDatabase,
    fanta_info: FantaComicBookInfo,
    comic: ComicBook,
    window_height: int,
) -> type:
    """Build the single-screen Kivy ``App`` subclass that hosts the reader.

    Kivy imports are local: this factory may only be called after
    ``ConfigInfo()`` has set ``KIVY_HOME``. The returned class closes over the
    reader inputs so ``app_cls()`` takes no arguments. ``window_height`` is
    needed up-front to seed ``FontManager`` — without it, font sizes default
    to 0 and the action-bar title renders as dots.
    """
    from barks_reader.ui.comic_book_reader import get_barks_comic_reader_screen
    from barks_reader.ui.font_manager import FontManager
    from barks_reader.ui.reader_screens import COMIC_BOOK_READER_SCREEN
    from kivy.app import App
    from kivy.core.window import Window
    from kivy.lang import Builder
    from kivy.uix.screenmanager import ScreenManager

    app_icon_path = str(reader_settings.sys_file_paths.get_barks_reader_app_window_icon_path())

    class BarksComicReaderCliApp(App):
        def __init__(self, **kwargs: str) -> None:
            super().__init__(**kwargs)
            self.title = f"Barks Reader - {fanta_info.comic_book_info.get_title_str()}"
            self.icon = app_icon_path
            self.reader_settings = reader_settings
            self.font_manager = FontManager()
            # Without this the action-bar title's [size={app_title_font_size}]
            # markup expands to size=0 and the title renders invisibly.
            self.font_manager.update_font_sizes(window_height)
            self._screen = None

        def build(self) -> ScreenManager:
            # The comic_book_reader.kv references ``fm`` and ``sys_paths`` plus
            # ``BarButton`` (defined inline in main_screen.kv). Wire them up
            # without pulling in the full main-screen kv graph.
            Builder.load_string("#:set fm app.font_manager")
            Builder.load_string("#:set sys_paths app.reader_settings.sys_file_paths")
            Builder.load_string(
                "<BarButton@ActionButton>:\n    mipmap: True\n    draggable: False\n"
            )

            self._screen = get_barks_comic_reader_screen(
                COMIC_BOOK_READER_SCREEN,
                self.reader_settings,
                app_icon_path,
                self.font_manager,
                self._on_comic_ready,
                self._on_close,
            )

            manager = ScreenManager()
            manager.add_widget(self._screen)
            manager.current = COMIC_BOOK_READER_SCREEN
            return manager

        def on_start(self) -> None:
            panel_segments_adapter = FantagraphicsPanelSegmentsAdapter(
                comics_database,
                self.reader_settings.sys_file_paths.get_barks_reader_fantagraphics_panel_segments_root_dir(),
            )
            layout_builder = ComicLayoutBuilder(
                sorted_pages_port=panel_segments_adapter,
                required_dimensions_port=panel_segments_adapter,
            )
            layout, image_builder = prepare_comic_for_reading(
                comic, self.reader_settings, layout_builder
            )

            assert self._screen is not None
            self._screen.comic_book_reader.read_comic(
                fanta_info,
                True,  # noqa: FBT003 — use_fantagraphics_overrides
                image_builder,
                COMIC_BEGIN_PAGE,
                layout.page_map,
            )

        def _on_comic_ready(self) -> None:
            assert self._screen is not None
            self._screen.is_active(active=True)

        def _on_close(self) -> None:
            App.get_running_app().stop()
            Window.close()

    return BarksComicReaderCliApp


if __name__ == "__main__":
    app()
