from __future__ import annotations

from pathlib import Path

import pytest
from barks_fantagraphics.comics_consts import BARKS_ROOT_DIR
from barks_fantagraphics.comics_database import (
    ComicsDatabase,
    TitleNotFoundError,
    _get_story_titles_dir,
    get_fanta_restored_ocr_prelim_root_dir,
    get_fanta_restored_ocr_prelim_volume_dir,
    get_fanta_title_for_volume,
)
from barks_fantagraphics.fanta_comics_info import (
    FANTAGRAPHICS_DIRNAME,
    FANTAGRAPHICS_FIXES_DIRNAME,
    FANTAGRAPHICS_PANEL_SEGMENTS_DIRNAME,
    FANTAGRAPHICS_RESTORED_DIRNAME,
    FANTAGRAPHICS_RESTORED_UPSCAYLED_DIRNAME,
    FANTAGRAPHICS_UPSCAYLED_DIRNAME,
    FANTAGRAPHICS_UPSCAYLED_FIXES_DIRNAME,
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
)

# ---------------------------------------------------------------------------
# TitleNotFoundError
# ---------------------------------------------------------------------------


class TestTitleNotFoundError:
    def test_stores_title(self) -> None:
        err = TitleNotFoundError("msg", "Some Title")
        assert err.title == "Some Title"

    def test_is_exception(self) -> None:
        err = TitleNotFoundError("Could not find", "Bad Title")
        assert str(err) == "Could not find"


# ---------------------------------------------------------------------------
# Module-level functions (no ComicsDatabase instance required)
# ---------------------------------------------------------------------------


class TestGetFantaTitleForVolume:
    def test_returns_string(self) -> None:
        title = get_fanta_title_for_volume(1)
        assert isinstance(title, str)
        assert title

    def test_different_volumes_different_titles(self) -> None:
        assert get_fanta_title_for_volume(1) != get_fanta_title_for_volume(2)

    def test_all_volumes_have_titles(self) -> None:
        for vol in range(FIRST_VOLUME_NUMBER, LAST_VOLUME_NUMBER + 1):
            assert get_fanta_title_for_volume(vol)


class TestGetFantaRestoredOcrPrelimRootDir:
    def test_appends_prelim(self) -> None:
        root = Path("/some/ocr/root")
        result = get_fanta_restored_ocr_prelim_root_dir(root)
        assert result == root / "Prelim"


class TestGetFantaRestoredOcrPrelimVolumeDir:
    def test_structure_is_root_prelim_title(self) -> None:
        root = Path("/some/ocr/root")
        result = get_fanta_restored_ocr_prelim_volume_dir(root, 1)
        title = get_fanta_title_for_volume(1)
        assert result == root / "Prelim" / title


class TestGetStoryTitlesDir:
    def test_raises_when_dir_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="story titles directory"):
            _get_story_titles_dir(tmp_path)  # type: ignore[arg-type]

    def test_returns_dir_when_exists(self, tmp_path: Path) -> None:
        story_titles = tmp_path / "story-titles"  # type: ignore[operator]
        story_titles.mkdir()
        result = _get_story_titles_dir(tmp_path)  # type: ignore[arg-type]
        assert result == story_titles


# ---------------------------------------------------------------------------
# ComicsDatabase static methods
# ---------------------------------------------------------------------------


class TestComicsDatabaseStaticMethods:
    def test_get_fantagraphics_volume_title_returns_string(self) -> None:
        title = ComicsDatabase.get_fantagraphics_volume_title(1)
        assert isinstance(title, str)
        assert title

    def test_get_num_pages_in_fantagraphics_volume_returns_int(self) -> None:
        num_pages = ComicsDatabase.get_num_pages_in_fantagraphics_volume(1)
        assert isinstance(num_pages, int)
        assert num_pages > 0

    def test_get_root_dir_combines_with_barks_root(self) -> None:
        result = ComicsDatabase.get_root_dir("SomeSubdir")
        assert result == BARKS_ROOT_DIR / "SomeSubdir"

    def test_get_fantagraphics_dirname_returns_constant(self) -> None:
        assert ComicsDatabase.get_fantagraphics_dirname() == FANTAGRAPHICS_DIRNAME

    def test_get_fantagraphics_restored_dirname(self) -> None:
        assert ComicsDatabase.get_fantagraphics_restored_dirname() == FANTAGRAPHICS_RESTORED_DIRNAME

    def test_get_fantagraphics_upscayled_dirname(self) -> None:
        assert (
            ComicsDatabase.get_fantagraphics_upscayled_dirname() == FANTAGRAPHICS_UPSCAYLED_DIRNAME
        )

    def test_get_fantagraphics_restored_upscayled_dirname(self) -> None:
        assert (
            ComicsDatabase.get_fantagraphics_restored_upscayled_dirname()
            == FANTAGRAPHICS_RESTORED_UPSCAYLED_DIRNAME
        )

    def test_get_fantagraphics_fixes_dirname(self) -> None:
        assert ComicsDatabase.get_fantagraphics_fixes_dirname() == FANTAGRAPHICS_FIXES_DIRNAME

    def test_get_fantagraphics_upscayled_fixes_dirname(self) -> None:
        assert (
            ComicsDatabase.get_fantagraphics_upscayled_fixes_dirname()
            == FANTAGRAPHICS_UPSCAYLED_FIXES_DIRNAME
        )

    def test_get_fantagraphics_panel_segments_dirname(self) -> None:
        assert (
            ComicsDatabase.get_fantagraphics_panel_segments_dirname()
            == FANTAGRAPHICS_PANEL_SEGMENTS_DIRNAME
        )


# ---------------------------------------------------------------------------
# ComicsDatabase instance — methods that work on in-memory data
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db() -> ComicsDatabase:
    """Real ComicsDatabase (reads story-titles INI files, no filesystem comic dirs needed)."""
    return ComicsDatabase(for_building_comics=False)


@pytest.fixture(scope="module")
def known_title(db: ComicsDatabase) -> str:
    """Return any title that is confirmed to be in the story-titles database."""
    titles = db.get_all_story_titles()
    assert titles, "No story titles found — data directory may be empty"
    return titles[0]


class TestComicsDatabaseInstance:
    def test_get_all_story_titles_nonempty(self, db: ComicsDatabase) -> None:
        titles = db.get_all_story_titles()
        assert len(titles) > 0

    def test_get_all_story_titles_sorted(self, db: ComicsDatabase) -> None:
        titles = db.get_all_story_titles()
        assert titles == sorted(titles)

    def test_is_story_title_known_title(self, db: ComicsDatabase, known_title: str) -> None:
        found, close = db.is_story_title(known_title)
        assert found is True
        assert close == ""

    def test_is_story_title_unknown_returns_false(self, db: ComicsDatabase) -> None:
        found, _close = db.is_story_title("ZZZZZ_DEFINITELY_NOT_A_REAL_TITLE_XYZZY")
        assert found is False

    def test_get_fanta_volume_int_returns_int(self, db: ComicsDatabase, known_title: str) -> None:
        vol = db.get_fanta_volume_int(known_title)
        assert isinstance(vol, int)
        assert FIRST_VOLUME_NUMBER <= vol <= LAST_VOLUME_NUMBER

    def test_get_fanta_volume_returns_string(self, db: ComicsDatabase, known_title: str) -> None:
        vol_str = db.get_fanta_volume(known_title)
        assert isinstance(vol_str, str)
        assert vol_str.startswith("FANTA_")

    def test_get_fanta_comic_book_info_not_none(self, db: ComicsDatabase, known_title: str) -> None:
        info = db.get_fanta_comic_book_info(known_title)
        assert info is not None

    def test_get_all_titles_in_fantagraphics_volumes_nonempty(self, db: ComicsDatabase) -> None:
        titles = db.get_all_titles_in_fantagraphics_volumes([1])
        assert len(titles) > 0
        for title, _info in titles:
            assert isinstance(title, str)

    def test_get_all_titles_sorted(self, db: ComicsDatabase) -> None:
        titles = db.get_all_titles_in_fantagraphics_volumes([1])
        title_strs = [t[0] for t in titles]
        assert title_strs == sorted(title_strs)

    def test_get_configured_titles_is_subset_of_all(self, db: ComicsDatabase) -> None:
        all_titles = {t[0] for t in db.get_all_titles_in_fantagraphics_volumes([1])}
        configured = {t[0] for t in db.get_configured_titles_in_fantagraphics_volumes([1])}
        assert configured.issubset(all_titles)

    def test_get_configured_titles_multiple_volumes(self, db: ComicsDatabase) -> None:
        vol1 = db.get_configured_titles_in_fantagraphics_volumes([1])
        vol2 = db.get_configured_titles_in_fantagraphics_volumes([2])
        both = db.get_configured_titles_in_fantagraphics_volumes([1, 2])
        assert len(both) == len(vol1) + len(vol2)

    def test_get_fantagraphics_volume_dir_contains_title(self, db: ComicsDatabase) -> None:
        vol_title = ComicsDatabase.get_fantagraphics_volume_title(1)
        vol_dir = db.get_fantagraphics_volume_dir(1)
        assert vol_title in str(vol_dir)

    def test_get_story_title_from_issue_unknown(self, db: ComicsDatabase) -> None:
        found, titles, _close = db.get_story_title_from_issue("ZZZZZ_XYZZY_NOPE_99999")
        assert found is False
        assert titles == []

    def test_get_comics_database_dir_is_dir(self, db: ComicsDatabase) -> None:
        assert db.get_comics_database_dir().is_dir()

    def test_get_story_titles_dir_is_dir(self, db: ComicsDatabase) -> None:
        assert db.get_story_titles_dir().is_dir()
