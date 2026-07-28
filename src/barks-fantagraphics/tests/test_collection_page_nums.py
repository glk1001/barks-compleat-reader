"""Guard ``get_collection_page_nums`` - the shared source of truth for staged pages.

The synthetic collections ("All One-Pagers" in FANTA_01, "All Covers" in FANTA_02)
are staged as "extra" pages in their nominal volume's *fixes* dir, numbered from the
relevant collection page base. The build-side integrity checker validates fixes-dir
page numbers against this set, so a drift between it and the pages actually built
would either block a build run or let bogus page numbers through.

These tests pin the contract: the set is derived from the collection page lists (not
recomputed from the base), it is contiguous from the base, and volumes hosting no
collection get an empty set.
"""

from __future__ import annotations

import pytest
from barks_fantagraphics.barks_covers import (
    COVER_COLLECTION_PAGE_BASE,
    get_cover_collection_pages,
    get_located_covers,
)
from barks_fantagraphics.comic_book_info import (
    COVER_COLLECTION_VOLUME,
    ONE_PAGER_COLLECTION_PAGE_BASE,
    ONE_PAGER_COLLECTION_VOLUME,
    get_collection_page_nums,
    get_located_one_pagers,
    get_one_pager_collection_pages,
)
from barks_fantagraphics.fanta_comics_info import (
    FANTA_SOURCE_COMICS,
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
)

# Volumes that host no synthetic collection: every other volume must return empty.
_NON_COLLECTION_VOLUMES = [
    volume
    for volume in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1)
    if volume not in (ONE_PAGER_COLLECTION_VOLUME, COVER_COLLECTION_VOLUME)
]


class TestCollectionPageNums:
    def test_one_pager_volume_matches_its_collection_pages(self) -> None:
        # Derived from the page list itself, so authoring a new one-pager location
        # extends this set without touching the checker.
        expected = {int(page.page_filenames) for page in get_one_pager_collection_pages()}
        assert get_collection_page_nums(ONE_PAGER_COLLECTION_VOLUME) == expected

    def test_cover_volume_matches_its_collection_pages(self) -> None:
        expected = {int(page.page_filenames) for page in get_cover_collection_pages()}
        assert get_collection_page_nums(COVER_COLLECTION_VOLUME) == expected

    def test_one_pager_volume_is_contiguous_from_base(self) -> None:
        num_located = len(get_located_one_pagers())
        assert num_located, "No located one-pagers (ONE_PAGER_LOCATIONS all _TODO)."
        assert get_collection_page_nums(ONE_PAGER_COLLECTION_VOLUME) == set(
            range(
                ONE_PAGER_COLLECTION_PAGE_BASE,
                ONE_PAGER_COLLECTION_PAGE_BASE + num_located,
            )
        )

    def test_cover_volume_is_contiguous_from_base(self) -> None:
        num_located = len(get_located_covers())
        assert num_located, "No located covers (COVER_LOCATIONS all unset)."
        assert get_collection_page_nums(COVER_COLLECTION_VOLUME) == set(
            range(COVER_COLLECTION_PAGE_BASE, COVER_COLLECTION_PAGE_BASE + num_located)
        )

    @pytest.mark.parametrize("volume", _NON_COLLECTION_VOLUMES)
    def test_other_volumes_stage_no_collection_pages(self, volume: int) -> None:
        assert get_collection_page_nums(volume) == frozenset()

    def test_the_two_collections_use_different_volumes(self) -> None:
        # They share a page base (500), so they must not share a volume or their
        # staged pages would collide in one fixes dir.
        assert ONE_PAGER_COLLECTION_VOLUME != COVER_COLLECTION_VOLUME

    def test_staged_pages_clear_every_real_volume_page_count(self) -> None:
        # The bases are chosen "well above any real volume's page count" so staged
        # pages never collide with real ones. Pin that invariant.
        max_real_pages = max(book.num_pages for book in FANTA_SOURCE_COMICS.values())
        for volume in (ONE_PAGER_COLLECTION_VOLUME, COVER_COLLECTION_VOLUME):
            assert min(get_collection_page_nums(volume)) > max_real_pages
