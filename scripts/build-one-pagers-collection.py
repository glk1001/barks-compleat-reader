"""Pre-bake the "All One-Pagers" collection into the FANTA_01 reader files.

The collection is read by the app as an ordinary single-volume (FANTA_01) comic
whose body pages are "extra" images numbered from
``ONE_PAGER_COLLECTION_PAGE_BASE`` (see
``comic_book_info.get_one_pager_collection_pages``). This script materialises
those pages so the reader can load them, driven entirely by
``ONE_PAGER_LOCATIONS``:

For each *located* one-pager ``i`` (chronological order), with source
``(volume, page)``:
  * read the restored page image ``Fantagraphics-restored/<vol>/images/<page>.png``,
    encrypt it with the panel key, and store it in the FANTA_01 override archive
    as ``<BASE+i>.png`` (an "extra" image);
  * copy that one-pager's panel-segment JSON into the FANTA_01 reader
    panel-segments dir as ``<BASE+i>.json`` (so the layout builder finds it).

The override archive is rewritten idempotently: existing non-collection entries
(volume fixes) are preserved by copying their raw bytes, and any previous
collection entries (``>= BASE``) are dropped and regenerated. Run this AFTER
regenerating the FANTA_01 fixes override, and re-run whenever
``ONE_PAGER_LOCATIONS`` changes.

Verify afterwards with::

    uv run scripts/validate-barks-reader-files.py --full-load-check --title "All One-Pagers"
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import typer
from barks_fantagraphics.comic_book_info import (
    ONE_PAGER_COLLECTION_PAGE_BASE,
    ONE_PAGER_LOCATIONS,
    get_located_one_pagers,
)
from barks_fantagraphics.comics_consts import (
    FANTA_VOLUME_OVERRIDES_ROOT,
    FANTA_VOLUME_READER_PANEL_SEGMENTS_ROOT,
)
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.fanta_comics_info import FANTA_OVERRIDE_ZIPS
from cli_setup import init_logging
from comic_utils.comic_consts import JSON_FILE_EXT, PNG_FILE_EXT
from comic_utils.common_typer_options import LogLevelArg  # noqa: TC002
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from loguru import logger

load_dotenv(Path(__file__).parent.parent / ".env.runtime")

APP_LOGGING_NAME = "1pgr"

# The collection's nominal volume - its pages live as "extra" images here.
COLLECTION_VOLUME = 1

FERNET = Fernet(os.environ["BARKS_ZIPS_KEY"])

app = typer.Typer()


def _page_str(num: int) -> str:
    return f"{num:03d}"


def _collection_segments_dir(db: ComicsDatabase) -> Path:
    vol_title = db.get_fantagraphics_volume_title(COLLECTION_VOLUME)
    return FANTA_VOLUME_READER_PANEL_SEGMENTS_ROOT / vol_title


def _source_segment_file(db: ComicsDatabase, volume: int, page: int) -> Path:
    vol_title = db.get_fantagraphics_volume_title(volume)
    return FANTA_VOLUME_READER_PANEL_SEGMENTS_ROOT / vol_title / (_page_str(page) + JSON_FILE_EXT)


def _source_image_file(db: ComicsDatabase, volume: int, page: int) -> Path:
    return db.get_fantagraphics_restored_volume_image_dir(volume) / (_page_str(page) + PNG_FILE_EXT)


def _build_collection_entries(
    db: ComicsDatabase,
) -> list[tuple[str, bytes, Path]]:
    """Return (override_arcname, encrypted_image_bytes, dest_segment_file) per page.

    Raises:
        FileNotFoundError: If a located one-pager's restored image or segment
            JSON is missing.

    """
    entries: list[tuple[str, bytes, Path]] = []
    seg_dir = _collection_segments_dir(db)

    for i, title in enumerate(get_located_one_pagers()):
        volume, page, _issue_page = ONE_PAGER_LOCATIONS[title]
        coll_page = ONE_PAGER_COLLECTION_PAGE_BASE + i

        image_file = _source_image_file(db, volume, page)
        if not image_file.is_file():
            msg = (
                f'Missing restored image for one-pager (vol {volume}, page {page}): "{image_file}".'
            )
            raise FileNotFoundError(msg)

        segment_file = _source_segment_file(db, volume, page)
        if not segment_file.is_file():
            msg = (
                f"Missing panel-segment JSON for one-pager"
                f' (vol {volume}, page {page}): "{segment_file}".'
            )
            raise FileNotFoundError(msg)

        encrypted = FERNET.encrypt(image_file.read_bytes())
        arcname = _page_str(coll_page) + PNG_FILE_EXT
        dest_segment = seg_dir / (_page_str(coll_page) + JSON_FILE_EXT)

        entries.append((arcname, encrypted, dest_segment))
        logger.debug(f'"{title.name}" (vol {volume}, page {page}) -> collection page {coll_page}.')

    return entries


def _entry_page_num(arcname: str) -> int | None:
    stem = Path(arcname).stem
    return int(stem) if stem.isdigit() else None


def _rewrite_override_archive(override_zip: Path, entries: list[tuple[str, bytes, Path]]) -> None:
    """Rewrite *override_zip*, keeping non-collection entries and adding *entries*.

    Existing entries are copied verbatim (still encrypted - no decryption needed)
    except any previous collection pages (page number >= BASE), which are dropped
    so the rebuild is idempotent.
    """
    kept: list[tuple[zipfile.ZipInfo, bytes]] = []
    if override_zip.is_file():
        with zipfile.ZipFile(override_zip, "r") as existing:
            for info in existing.infolist():
                page_num = _entry_page_num(info.filename)
                if page_num is not None and page_num >= ONE_PAGER_COLLECTION_PAGE_BASE:
                    continue  # stale collection page - regenerate
                kept.append((info, existing.read(info.filename)))

    tmp_zip = override_zip.with_suffix(override_zip.suffix + ".tmp")
    with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_STORED) as out:
        for info, data in kept:
            out.writestr(info, data)
        for arcname, encrypted, _dest_segment in entries:
            out.writestr(arcname, encrypted)

    tmp_zip.replace(override_zip)
    logger.info(f"Kept {len(kept)} existing entries, added {len(entries)} collection pages.")


def _write_segments(entries: list[tuple[str, bytes, Path]], db: ComicsDatabase) -> None:
    seg_dir = _collection_segments_dir(db)
    seg_dir.mkdir(parents=True, exist_ok=True)

    # Drop stale collection segment files first (idempotent).
    for existing in seg_dir.glob("*" + JSON_FILE_EXT):
        page_num = _entry_page_num(existing.name)
        if page_num is not None and page_num >= ONE_PAGER_COLLECTION_PAGE_BASE:
            existing.unlink()

    for i, (_arcname, _encrypted, dest_segment) in enumerate(entries):
        volume, page, _issue_page = ONE_PAGER_LOCATIONS[get_located_one_pagers()[i]]
        source = _source_segment_file(db, volume, page)
        dest_segment.write_bytes(source.read_bytes())


@app.command(help="Pre-bake the All One-Pagers collection into the FANTA_01 reader files.")
def main(log_level_str: LogLevelArg = "INFO") -> None:
    init_logging(APP_LOGGING_NAME, "build-one-pagers.log", log_level_str)

    db = ComicsDatabase(for_building_comics=False)

    located = get_located_one_pagers()
    if not located:
        logger.warning("No located one-pagers (ONE_PAGER_LOCATIONS is all _TODO). Nothing to do.")
        raise typer.Exit(code=0)

    logger.info(f"Pre-baking {len(located)} located one-pagers into the collection.")

    entries = _build_collection_entries(db)

    override_zip = FANTA_VOLUME_OVERRIDES_ROOT / FANTA_OVERRIDE_ZIPS[COLLECTION_VOLUME]
    logger.info(f'Updating override archive "{override_zip}".')
    _rewrite_override_archive(override_zip, entries)

    logger.info(f'Writing panel segments to "{_collection_segments_dir(db)}".')
    _write_segments(entries, db)

    logger.info(
        "Done. Verify with: validate-barks-reader-files.py --full-load-check"
        ' --title "All One-Pagers"'
    )


if __name__ == "__main__":
    app()
