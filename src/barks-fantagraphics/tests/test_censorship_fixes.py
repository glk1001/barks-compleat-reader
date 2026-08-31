"""Tests for resolving a censorship-fixes row's `Story` cell to a real story.

Every other consumer of the CSV starts here. `barks-check-build` grades each row against
the story it names, `barks-ocr-censorship-csv` derives the Volume, Image and Fanta_page
columns from it, and the wiki's censorship table prints it - and all three go through
`resolve_censorship_story` and `censorship_story_pages`. A cell that does not resolve
therefore does not fail in one place: it fails in three, and two of them by raising.

The database is built from the `.ini` files, so what it knows is the 465 stories that
have one - not the 954 titles. A one-pager has no `.ini`; it is a member of the
`All One-Pagers` collection. So the first one-pager fix ever recorded resolved nowhere,
and reported itself as `UNKNOWN_STORY` - "names no story this database knows" - which
reads like a typo in the cell rather than a whole class of title the lookup could not
reach. `ONE_PAGER_LOCATIONS` is where those titles' volume and page are authored, and
this is what makes the CSV able to name one.

The last test is the one that would have caught it: every row of the shipped CSV
resolves. Nothing asserted that before, which is why a hand-added row could break the
wiki build and the derive tool at once and only show up as a puzzling integrity finding.
"""

from __future__ import annotations

import pytest
from barks_fantagraphics import comic_book_info as cbi
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.censorship_fixes import (
    ONE_PAGER_COMIC_PAGE,
    CensorshipFixesError,
    censorship_story_pages,
    one_pager_location,
    read_censorship_fixes,
    resolve_censorship_story,
)
from barks_fantagraphics.comic_book_info import ONE_PAGER_LOCATIONS, get_located_one_pagers
from barks_fantagraphics.comics_database import ComicsDatabase, TitleNotFoundError

# The one-pager the CSV actually records a fix against: page 072 of volume 14.
ONE_PAGER = Titles.DINER_DILEMMA
ONE_PAGER_STR = ENUM_TO_STR_TITLE[ONE_PAGER]


@pytest.fixture(scope="module")
def db() -> ComicsDatabase:
    """Real ComicsDatabase (reads story-titles INI files, no comic dirs needed)."""
    return ComicsDatabase(for_building_comics=False)


class TestAOnePagerIsNotADatabaseStory:
    """The premise the rest of this file rests on - stated, so it cannot drift silently."""

    def test_the_database_does_not_know_it(self, db: ComicsDatabase) -> None:
        is_title, _closest = db.is_story_title(ONE_PAGER_STR)

        assert not is_title

    def test_and_cannot_open_a_comic_book_for_it(self, db: ComicsDatabase) -> None:
        with pytest.raises(TitleNotFoundError):
            db.get_comic_book(ONE_PAGER_STR)

    def test_but_it_is_a_real_located_title(self) -> None:
        assert ONE_PAGER in get_located_one_pagers()


class TestOnePagerLocationLookup:
    def test_a_located_one_pager_gives_its_volume_and_page(self) -> None:
        volume, page, _issue_page = ONE_PAGER_LOCATIONS[ONE_PAGER]

        assert one_pager_location(ONE_PAGER_STR) == (volume, page)

    def test_an_ordinary_story_title_is_not_one(self) -> None:
        assert one_pager_location("Frozen Gold") is None

    def test_a_cell_that_names_no_title_at_all_is_not_one(self) -> None:
        assert one_pager_location("WDCS 132") is None
        assert one_pager_location("Not A Title") is None

    def test_an_unauthored_one_pager_is_not_located(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A `_TODO` (0, 0, 0) placeholder has no volume to point a fix at, so it must not
        # resolve - the row would otherwise be graded against volume 0.
        monkeypatch.setattr(cbi, "ONE_PAGER_LOCATIONS", {ONE_PAGER: (0, 0, 0)})

        assert one_pager_location(ONE_PAGER_STR) is None


class TestResolvingTheStoryCell:
    def test_a_one_pager_resolves_to_itself(self, db: ComicsDatabase) -> None:
        assert resolve_censorship_story(db, ONE_PAGER_STR) == ONE_PAGER_STR

    def test_an_ordinary_title_still_resolves(self, db: ComicsDatabase) -> None:
        assert resolve_censorship_story(db, "Frozen Gold") == "Frozen Gold"

    def test_an_issue_string_still_resolves(self, db: ComicsDatabase) -> None:
        assert resolve_censorship_story(db, "WDCS 132") == "Ten-Star Generals"

    def test_an_unknown_cell_is_still_refused(self, db: ComicsDatabase) -> None:
        # The one-pager fallback must not turn a typo into a silent pass.
        with pytest.raises(CensorshipFixesError, match="not a known title or issue"):
            resolve_censorship_story(db, "Dinner Dilemma")


class TestTheStoryPages:
    def test_a_one_pager_has_one_numbered_page(self, db: ComicsDatabase) -> None:
        # Numbered rather than unnumbered, so a row against it reads like every other
        # row - and so `barks-ocr-censorship-csv`, which refuses a story with no BODY
        # pages, can derive its columns.
        volume, page, _issue_page = ONE_PAGER_LOCATIONS[ONE_PAGER]

        pages = censorship_story_pages(db, ONE_PAGER_STR)

        assert pages.volume == volume
        assert pages.body_images == {ONE_PAGER_COMIC_PAGE: f"{page:03d}"}
        assert pages.unnumbered_images == frozenset()

    def test_the_volume_is_the_one_the_scan_is_in(self, db: ComicsDatabase) -> None:
        # Not `FANTA_01`, where the collection stages it: a fix is made to the scan where
        # it actually lives, and that is the page the CSV names.
        pages = censorship_story_pages(db, ONE_PAGER_STR)

        assert pages.volume != 1

    def test_an_ordinary_story_still_reads_from_its_ini(self, db: ComicsDatabase) -> None:
        pages = censorship_story_pages(db, "Frozen Gold")

        assert pages.volume > 0
        assert len(pages.body_images) > 1


class TestTheShippedCsvResolves:
    """Every row of the real CSV, which is what a hand-added row breaks."""

    def test_every_story_cell_resolves_to_a_story_with_pages(self, db: ComicsDatabase) -> None:
        unresolved = []
        for story in {row.story for row in read_censorship_fixes()}:
            try:
                censorship_story_pages(db, resolve_censorship_story(db, story))
            except (CensorshipFixesError, TitleNotFoundError) as e:
                unresolved.append(f"{story}: {e}")

        assert not unresolved

    def test_every_row_names_the_volume_its_story_is_in(self, db: ComicsDatabase) -> None:
        # The other half of what `barks-check-build` grades, and the half a one-pager
        # row got wrong for free: with the story unresolved there was no volume to
        # compare against, so the mismatch could not even be seen.
        pages_by_story = {
            story: censorship_story_pages(db, resolve_censorship_story(db, story))
            for story in {row.story for row in read_censorship_fixes()}
        }

        wrong = [
            f"{row.story} row says volume {row.volume},"
            f" story is in {pages_by_story[row.story].volume}"
            for row in read_censorship_fixes()
            if row.volume != pages_by_story[row.story].volume
        ]

        assert not wrong
