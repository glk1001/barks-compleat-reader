"""Guard the pre-baked "All Covers" collection pages in the FANTA_02 override.

The collection is served to the reader as ordinary "extra" pages of the FANTA_02
volume, numbered from ``COVER_COLLECTION_PAGE_BASE`` (500) upward - one page per
*located* cover (``get_located_covers``), in bibliography order. These pages are
pre-baked (encrypted) into the FANTA_02 override archive by the offline staging +
build flow (barks-comic-building's ``barks-stage-covers``), so this test pins them
down: once any collection page is present, the override zip must contain *exactly*
the contiguous pages ``500 .. 500+N-1`` as ``.jpg`` entries.

Unlike the one-pager guard, a FANTA_02 override zip with *no* collection pages is
expected while the covers have not yet been staged and baked - that case skips
rather than fails. Locally a missing archive is still a hard failure; on CI -
where this machine-local data legitimately does not exist - the test is skipped.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest
from barks_fantagraphics.barks_covers import COVER_COLLECTION_PAGE_BASE, get_located_covers
from barks_fantagraphics.comics_consts import FANTA_VOLUME_OVERRIDES_ROOT
from barks_fantagraphics.fanta_comics_info import FANTA_OVERRIDE_ZIPS

# The collection's nominal volume - its pages live as "extra" images here.
COLLECTION_VOLUME = 2

JPG_EXT = ".jpg"
# The stored image bytes are Fernet ciphertext, which always begins with this.
FERNET_TOKEN_PREFIX = b"gAAAA"


def _override_zip_path() -> Path:
    return FANTA_VOLUME_OVERRIDES_ROOT / FANTA_OVERRIDE_ZIPS[COLLECTION_VOLUME]


def _page_num(arcname: str) -> int | None:
    stem = Path(arcname).stem
    return int(stem) if stem.isdigit() else None


def _expected_collection_arcnames() -> list[str]:
    """Return the contiguous ``<page>.jpg`` names, one per located cover."""
    located = get_located_covers()
    return [f"{COVER_COLLECTION_PAGE_BASE + i:03d}{JPG_EXT}" for i in range(len(located))]


@pytest.fixture(scope="module")
def override_zip_path() -> Path:
    """Path to the real FANTA_02 override archive.

    Hard-fails if absent locally; skips on CI, where the archive does not exist.
    """
    zip_path = _override_zip_path()
    if not zip_path.is_file():
        msg = f'FANTA_02 override archive is missing: "{zip_path}".'
        if os.environ.get("CI"):
            pytest.skip(msg)
        pytest.fail(msg)
    return zip_path


@pytest.fixture(scope="module")
def collection_names(override_zip_path: Path) -> list[str]:
    """Override entries belonging to the covers collection (page >= base).

    Skips while the collection has not yet been baked into the override.
    """
    with zipfile.ZipFile(override_zip_path, "r") as zf:
        names = [
            name
            for name in zf.namelist()
            if (page := _page_num(name)) is not None and page >= COVER_COLLECTION_PAGE_BASE
        ]
    if not names:
        pytest.skip("Covers collection not yet baked into the FANTA_02 override.")
    return names


class TestCoversCollectionPages:
    def test_located_covers_present(self) -> None:
        # The collection (and so this test) is meaningless with nothing to bake.
        assert get_located_covers(), "No located covers (COVER_LOCATIONS is empty)."

    def test_collection_pages_match_located_covers_exactly(
        self, collection_names: list[str]
    ) -> None:
        # Exactly the contiguous pages 500..500+N-1 as .jpg: no missing pages, no stale
        # extras, and no wrong extension (a stray 5xx.png would not match the .jpg name).
        assert sorted(collection_names) == sorted(_expected_collection_arcnames())

    def test_collection_pages_are_nonempty_encrypted_images(
        self, override_zip_path: Path, collection_names: list[str]
    ) -> None:
        with zipfile.ZipFile(override_zip_path, "r") as zf:
            for arcname in collection_names:
                data = zf.read(arcname)
                assert data.startswith(FERNET_TOKEN_PREFIX), (
                    f'Collection page "{arcname}" is not an encrypted image payload.'
                )
