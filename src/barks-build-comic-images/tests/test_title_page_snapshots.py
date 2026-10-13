# ruff: noqa: SLF001
# cspell:ignore getbbox
"""Title pages drawn pixel for pixel as they were when their snapshots were taken.

The other title page tests check its parts; these check the whole page, so a change that
moves anything on it, by one pixel or on one platform, fails here. A Pillow upgrade can do
that unnoticed, and so did the Windows text layout, which once lettered titles wider.

Each page is drawn around a made-up inset, as CI has no comic library to take a real one
from: most in 3:2, but one wide and one tall, to hold the inset's sizing by shape too.
After an intended change, take new snapshots by running these tests with
``UPDATE_TITLE_PAGE_SNAPSHOTS=1``, and look at each new png before committing it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from barks_build_comic_images.build_comic_images import ComicBookImageBuilder
from barks_build_comic_images.image_io import open_image_for_reading
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.pages import EMPTY_IMAGE_FILEPATH
from PIL import Image, ImageChops, ImageDraw

_SNAPSHOT_DIR = Path(__file__).parent / "data" / "title-pages"
_UPDATE_SNAPSHOTS = os.environ.get("UPDATE_TITLE_PAGE_SNAPSHOTS") == "1"

_INSET_3_2 = (1200, 800)
_INSET_WIDE = (1500, 500)  # 3:1: widened past the width cap towards the minimum height
_INSET_TALL = (600, 800)  # 3:4: no taller than 4:3 art at the width cap

# Each story's snapshot and its inset's size, and what its page shows that the others don't.
_SNAPSHOTS = {
    # The default red, a small-words line ("in the"), three lines of credits; a wide inset.
    "Lost in the Andes!": ("lost-in-the-andes.png", _INSET_WIDE),
    # An issue name for a title: the "Comics and Stories" masthead and a number, in purple.
    "The Hypno-Gun": ("the-hypno-gun.png", _INSET_3_2),
    # A US-censored issue: the masthead's number with its raised footnote mark, in green.
    "Silent Night": ("silent-night.png", _INSET_3_2),
    # An issue title on two lines, "Uncle / Scrooge #14", in yellow, the faintest colour.
    "Faulty Fortune": ("faulty-fortune.png", _INSET_3_2),
    # A title too wide for the page, lettered smaller to fit.
    "The Great Steamboat Race": ("the-great-steamboat-race.png", _INSET_3_2),
    # Three lines, one an article line ("the Farm"), in green; a tall inset.
    "The Day the Farm Stood Still": ("the-day-the-farm-stood-still.png", _INSET_TALL),
}


@pytest.fixture(scope="module")
def db() -> ComicsDatabase:
    return ComicsDatabase(for_building_comics=False)


def _make_inset(directory: Path, size: tuple[int, int]) -> Path:
    """Return a made-up inset: a sun on a sky, outlined in black to show the scaling."""
    width, height = size
    path = directory / f"inset-{width}x{height}.png"
    image = Image.new("RGB", size, (90, 160, 220))
    sun = (width // 4, height * 3 // 16, width * 3 // 4, height * 13 // 16)
    ImageDraw.Draw(image).ellipse(sun, fill=(240, 200, 40), outline=(0, 0, 0), width=12)
    image.save(path)
    return path


def _get_title_page(db: ComicsDatabase, title: str, inset: Path) -> Image.Image:
    comic = db.get_comic_book(title, intro_inset_file=inset)
    builder = ComicBookImageBuilder(comic, EMPTY_IMAGE_FILEPATH)
    return builder._get_dest_title_page_image(open_image_for_reading(EMPTY_IMAGE_FILEPATH))


@pytest.mark.parametrize(
    ("title", "snapshot", "inset_size"),
    [(title, snapshot, inset_size) for title, (snapshot, inset_size) in _SNAPSHOTS.items()],
    ids=list(_SNAPSHOTS),
)
def test_the_title_page_matches_its_snapshot(
    db: ComicsDatabase, tmp_path: Path, title: str, snapshot: str, inset_size: tuple[int, int]
) -> None:
    inset = _make_inset(tmp_path, inset_size)
    page = _get_title_page(db, title, inset).convert("RGB")
    snapshot_file = _SNAPSHOT_DIR / snapshot

    if _UPDATE_SNAPSHOTS:
        snapshot_file.parent.mkdir(parents=True, exist_ok=True)
        page.save(snapshot_file, optimize=True)
        pytest.skip(f"took a new snapshot: {snapshot_file}")

    assert snapshot_file.is_file(), (
        f"No snapshot {snapshot_file}: take one with UPDATE_TITLE_PAGE_SNAPSHOTS=1."
    )
    with Image.open(snapshot_file) as expected_image:
        expected = expected_image.convert("RGB")
    assert page.size == expected.size, f"The page is {page.size}, its snapshot {expected.size}."

    difference = ImageChops.difference(page, expected)
    if (changed := difference.getbbox()) is not None:
        page_file = tmp_path / snapshot
        page.save(page_file)
        # The changed pixels in black on white, so a one-pixel shift shows.
        diff_file = tmp_path / f"diff-{snapshot}"
        difference.convert("L").point(lambda v: 0 if v else 255).save(diff_file)
        pytest.fail(
            f'The "{title}" title page differs from its snapshot within {changed}.'
            f" The new page is in {page_file}, the changed pixels in {diff_file}."
            " If the change was intended, take new snapshots with UPDATE_TITLE_PAGE_SNAPSHOTS=1."
        )
