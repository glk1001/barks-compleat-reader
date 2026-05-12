"""Shared orchestration helpers for booting the reader.

These are Kivy-free so both the main app (``BarksReaderApp``) and lightweight
CLI entry points (e.g. ``scripts/read_comic.py``) can share the wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_build_comic_images.build_comic_images import ComicBookImageBuilder
from comic_utils.get_panel_bytes import get_decrypted_bytes

if TYPE_CHECKING:
    from configparser import ConfigParser

    from barks_fantagraphics.comic_book import ComicBook
    from barks_fantagraphics.comics_database import ComicsDatabase

    from .comic_book_page_info import ComicLayout, ComicLayoutBuilder
    from .config_info import ConfigInfo
    from .reader_settings import ReaderSettings


def bootstrap_reader_environment(
    reader_settings: ReaderSettings,
    comics_database: ComicsDatabase,
    parser: ConfigParser,
    config_info: ConfigInfo,
) -> None:
    """Wire ``ReaderSettings`` and ``ComicsDatabase`` to the on-disk config.

    Shared by the main app's settings-init path and CLI entry points. Does
    *not* perform main-app-specific steps (alt-escape key, virtual keyboard,
    ``validate_settings``) — those stay in ``BarksReaderApp``.
    """
    reader_settings.set_config(parser, config_info.app_config_path, config_info.app_data_dir)  # ty: ignore[invalid-argument-type]
    reader_settings.set_barks_panels_dir()

    comics_database.set_inset_info(
        reader_settings.file_paths.get_comic_inset_files_dir(),  # ty: ignore[invalid-argument-type]
        reader_settings.file_paths.get_inset_file_ext(),
    )
    reader_settings.sys_file_paths.set_barks_reader_files_dir(reader_settings.reader_files_dir)


def prepare_comic_for_reading(
    comic: ComicBook,
    reader_settings: ReaderSettings,
    layout_builder: ComicLayoutBuilder,
) -> tuple[ComicLayout, ComicBookImageBuilder]:
    """Build the ``(layout, image_builder)`` pair the reader screen needs.

    Single source of truth for the comic-reading prep pipeline:
    page-map layout, decryption-func selection, image-builder
    construction, required-dimensions wiring.
    """
    layout = layout_builder.build(comic)

    get_decrypted_func = (
        get_decrypted_bytes if reader_settings.file_paths.barks_panels_are_encrypted else None
    )
    image_builder = ComicBookImageBuilder(
        comic,
        reader_settings.sys_file_paths.get_empty_page_file(),
        get_inset_decrypted_bytes=get_decrypted_func,
    )
    image_builder.set_required_dim(layout_builder.get_required_dimensions(comic))

    return layout, image_builder
