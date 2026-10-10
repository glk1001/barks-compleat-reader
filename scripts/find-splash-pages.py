# ruff: noqa: T201
"""Find every story's splash pages from its panel boxes, and print them as tag data.

A splash panel takes the space of four of the story's normal panels
(barks_fantagraphics.splash_pages); page 1 is left out. The pages are read from the
Fantagraphics panel-segments JSONs (ComicsDatabase's panel-segments root) and
numbered as the reader numbers them.

Prints the Tags.SPLASH list for BARKS_TAGGED_TITLES and its BARKS_TAGGED_PAGES
entries, ready to paste into barks_tags_data.py, then a cross-check against the
two other sources: the ini files' "= SPLASH" pages and the Barks panels Splash
folder (from the reader's settings, PNG panels). Those mostly hold Fantagraphics
back-matter reproductions, so they confirm a title, not a page; a Splash-folder
image from a body page should be on a splash page.

Phase 12 of validate-barks-reader-files.py checks the pasted data nightly.

Run via ``uv run scripts/find-splash-pages.py``.
"""

from configparser import ConfigParser
from pathlib import Path

import typer
from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_book import get_num_splashes
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_reader.core.config_info import ConfigInfo  # make sure this is before any kivy imports
from barks_reader.core.reader_settings import ReaderSettings
from loguru import logger
from validate_barks_reader_core import (
    find_title_splash_pages,
    get_splash_story_titles,
    make_splash_layout_builder,
)

app = typer.Typer()


def _get_splash_dir() -> Path:
    """Return the Splash folder of the reader's PNG Barks panels."""
    config_info = ConfigInfo()
    config = ConfigParser()
    config.read(config_info.app_config_path)
    reader_settings = ReaderSettings()
    reader_settings.set_config(config, config_info.app_config_path, config_info.app_data_dir)  # ty: ignore[invalid-argument-type]
    reader_settings.force_barks_panels_dir(use_png_images=True)
    splash_dir = reader_settings.file_paths.get_comic_splash_files_dir()
    assert isinstance(splash_dir, Path), "PNG panels are a directory, not a zip."
    return splash_dir


def _print_tag_data(splash_pages: dict[Titles, list[str]]) -> None:
    print("    Tags.SPLASH: [")
    for title in sorted(splash_pages):
        print(f"        Titles.{title.name},")
    print("    ],")
    print()
    # BARKS_TAGGED_PAGES lists each tag's titles alphabetically.
    for title in sorted(splash_pages, key=lambda t: t.name):
        pages = ", ".join(f'"{page}"' for page in splash_pages[title])
        print(f"    (Tags.SPLASH, Titles.{title.name}): [{pages}],")


def _cross_check(
    db: ComicsDatabase, splash_pages: dict[Titles, list[str]], splash_dir: Path
) -> list[str]:
    """Return each way the ini files and the Splash folder disagree with the panel boxes."""
    disagreements = [
        f'ini: "{title_str}" has a SPLASH page but no splash found.'
        for title_str in get_splash_story_titles()
        if get_num_splashes(db.get_comic_book(title_str))
        and STR_TITLE_TO_ENUM[title_str] not in splash_pages
    ]

    builder = make_splash_layout_builder(db, db.get_fantagraphics_panel_segments_root_dir())
    for title_dir in sorted(d for d in splash_dir.iterdir() if d.is_dir()):
        title = STR_TITLE_TO_ENUM.get(title_dir.name)
        if title is None:
            disagreements.append(f'Splash folder: "{title_dir.name}" is no title.')
            continue
        if title not in splash_pages:
            disagreements.append(f'Splash folder: "{title_dir.name}" but no splash found.')
            continue
        body_pages = {
            Path(page.srce_page.page_filename).stem: page.display_page_num
            for page in builder.build(db.get_comic_book(title_dir.name)).page_map.values()
            if page.page_type == PageType.BODY
        }
        for image in sorted(f for f in title_dir.iterdir() if f.is_file()):
            page = body_pages.get(image.stem.split("-")[0])
            if page is not None and page not in splash_pages[title]:
                disagreements.append(
                    f'Splash folder: "{title_dir.name}/{image.name}" is page {page},'
                    f" not a splash page ({', '.join(splash_pages[title])})."
                )
    return disagreements


@app.command(help="Find every story's splash pages and print them as tag data.")
def main() -> None:
    logger.remove()
    db = ComicsDatabase(for_building_comics=False)
    panel_segments_root = db.get_fantagraphics_panel_segments_root_dir()
    builder = make_splash_layout_builder(db, panel_segments_root)

    splash_pages: dict[Titles, list[str]] = {}
    for title_str in get_splash_story_titles():
        pages = find_title_splash_pages(db, builder, panel_segments_root, title_str)
        if pages:
            splash_pages[STR_TITLE_TO_ENUM[title_str]] = pages

    _print_tag_data(splash_pages)

    print()
    print(f"# {len(splash_pages)} stories, {sum(map(len, splash_pages.values()))} splash pages.")
    disagreements = _cross_check(db, splash_pages, _get_splash_dir())
    print(f"# Cross-check: {len(disagreements)} disagreement(s).")
    for disagreement in disagreements:
        print(f"#   {disagreement}")


if __name__ == "__main__":
    app()
