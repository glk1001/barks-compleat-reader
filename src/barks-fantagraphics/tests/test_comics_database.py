from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics import comics_database as comics_database_module
from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_book_info import NON_COMIC_TITLES
from barks_fantagraphics.comics_consts import BARKS_ROOT_DIR, IMAGES_SUBDIR
from barks_fantagraphics.comics_database import (
    ComicsDatabase,
    TitleNotFoundError,
    _get_story_titles_dir,
    check_comic_ok_for_building,
    get_fanta_restored_ocr_prelim_root_dir,
    get_fanta_restored_ocr_prelim_volume_dir,
    get_fanta_title_for_volume,
    make_all_fantagraphics_directories,
)
from barks_fantagraphics.comics_helpers import validate_ini_files_against_barks_titles
from barks_fantagraphics.fanta_comics_info import (
    FANTAGRAPHICS_DIRNAME,
    FANTAGRAPHICS_FIXES_DIRNAME,
    FANTAGRAPHICS_FIXES_SCRAPS_DIRNAME,
    FANTAGRAPHICS_PANEL_SEGMENTS_DIRNAME,
    FANTAGRAPHICS_RESTORED_DIRNAME,
    FANTAGRAPHICS_RESTORED_OCR_DIRNAME,
    FANTAGRAPHICS_RESTORED_SVG_DIRNAME,
    FANTAGRAPHICS_RESTORED_UPSCAYLED_DIRNAME,
    FANTAGRAPHICS_UPSCAYLED_DIRNAME,
    FANTAGRAPHICS_UPSCAYLED_FIXES_DIRNAME,
    FIRST_VOLUME_NUMBER,
    LAST_VOLUME_NUMBER,
)
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

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


class TestComicBookIniFiles:
    def test_all_ini_files_are_valid(self) -> None:
        validate_ini_files_against_barks_titles()


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


# ---------------------------------------------------------------------------
# The derived trees' directory getters, which the build and OCR pipelines use
# ---------------------------------------------------------------------------

# (getter stem, the tree's dirname, whether it has a per-volume images dir)
_TREES = [
    ("fantagraphics_upscayled", FANTAGRAPHICS_UPSCAYLED_DIRNAME, True),
    ("fantagraphics_restored", FANTAGRAPHICS_RESTORED_DIRNAME, True),
    ("fantagraphics_restored_upscayled", FANTAGRAPHICS_RESTORED_UPSCAYLED_DIRNAME, True),
    ("fantagraphics_restored_svg", FANTAGRAPHICS_RESTORED_SVG_DIRNAME, True),
    ("fantagraphics_panel_segments", FANTAGRAPHICS_PANEL_SEGMENTS_DIRNAME, False),
    ("fantagraphics_fixes", FANTAGRAPHICS_FIXES_DIRNAME, True),
    ("fantagraphics_upscayled_fixes", FANTAGRAPHICS_UPSCAYLED_FIXES_DIRNAME, True),
    ("fantagraphics_fixes_scraps", FANTAGRAPHICS_FIXES_SCRAPS_DIRNAME, True),
]


class TestDerivedTreeDirs:
    """Each tree is <barks root>/<its dirname>/<volume title>[/images]."""

    @pytest.mark.parametrize(("stem", "dirname", "has_images"), _TREES, ids=[t[0] for t in _TREES])
    def test_root_volume_and_image_dirs(
        self, db: ComicsDatabase, stem: str, dirname: str, has_images: bool
    ) -> None:
        volume = FIRST_VOLUME_NUMBER + 4
        root = BARKS_ROOT_DIR / dirname
        volume_dir = root / db.get_fantagraphics_volume_title(volume)
        assert getattr(db, f"get_{stem}_dirname")() == dirname
        assert getattr(db, f"get_{stem}_root_dir")() == root
        assert getattr(db, f"get_{stem}_volume_dir")(volume) == volume_dir
        if has_images:
            assert getattr(db, f"get_{stem}_volume_image_dir")(volume) == volume_dir / IMAGES_SUBDIR

    def test_the_originals(self, db: ComicsDatabase) -> None:
        volume_dir = BARKS_ROOT_DIR / FANTAGRAPHICS_DIRNAME / db.get_fantagraphics_volume_title(5)
        assert db.get_fantagraphics_original_root_dir() == BARKS_ROOT_DIR / FANTAGRAPHICS_DIRNAME
        assert db.get_fantagraphics_volume_dir(5) == volume_dir
        assert db.get_fantagraphics_volume_image_dir(5) == volume_dir / IMAGES_SUBDIR

    def test_the_ocr_tree_has_raw_prelim_and_annotations_under_it(self, db: ComicsDatabase) -> None:
        root = BARKS_ROOT_DIR / FANTAGRAPHICS_RESTORED_OCR_DIRNAME
        title = db.get_fantagraphics_volume_title(5)
        assert db.get_fantagraphics_restored_ocr_dirname() == FANTAGRAPHICS_RESTORED_OCR_DIRNAME
        assert db.get_fantagraphics_restored_ocr_root_dir() == root
        assert db.get_fantagraphics_restored_ocr_raw_root_dir() == root / "Raw"
        assert db.get_fantagraphics_restored_ocr_raw_volume_dir(5) == root / "Raw" / title
        assert db.get_fantagraphics_restored_ocr_annotations_root_dir() == root / "Annotations"
        assert (
            db.get_fantagraphics_restored_ocr_annotations_volume_dir(5)
            == root / "Annotations" / title
        )
        assert db.get_fantagraphics_restored_ocr_prelim_root_dir() == (
            get_fanta_restored_ocr_prelim_root_dir(root)
        )
        assert db.get_fantagraphics_restored_ocr_prelim_volume_dir(5) == (
            get_fanta_restored_ocr_prelim_volume_dir(root, 5)
        )


# ---------------------------------------------------------------------------
# Looking a comic up by story or issue title, and what a miss says
# ---------------------------------------------------------------------------


# cspell:ignore Andez Zzzzqqq  (deliberate misses)


class TestTitleLookupErrors:
    def test_an_issue_with_several_stories_is_refused(self, db: ComicsDatabase) -> None:
        with pytest.raises(RuntimeError, match="an issue title that has multiple titles"):
            db.get_comic_book("CP 1")
        with pytest.raises(RuntimeError, match="an issue title that has multiple titles"):
            db.get_fanta_comic_book_info("CP 1")

    def test_a_near_miss_issue_suggests_the_closest(self, db: ComicsDatabase) -> None:
        with pytest.raises(RuntimeError, match='Did you mean "FC 199"'):
            db.get_comic_book("FC 99999")
        with pytest.raises(RuntimeError, match='Did you mean "FC 199"'):
            db.get_fanta_comic_book_info("FC 99999")

    def test_a_near_miss_story_title_suggests_the_closest(self, db: ComicsDatabase) -> None:
        with pytest.raises(TitleNotFoundError, match='Did you mean "Lost in the Andes!"') as err:
            db.get_comic_book("Lost in the Andez")
        assert err.value.title == "Lost in the Andez"

    def test_a_title_like_nothing_says_so_plainly(self, db: ComicsDatabase) -> None:
        with pytest.raises(TitleNotFoundError, match=r'^Could not find title "Zzzzqqq"\.$'):
            db.get_comic_book("Zzzzqqq")

    def test_a_single_story_issue_finds_its_story(self, db: ComicsDatabase) -> None:
        info = db.get_fanta_comic_book_info("ANDERS 47")
        assert info.comic_book_info.get_title_str() == "Pied Piper of Duckburg"

    def test_a_single_story_issue_opens_the_comic_book_of_its_story(
        self, db: ComicsDatabase
    ) -> None:
        comic = db.get_comic_book("ANDERS 47")
        assert comic.ini_file.name == "Pied Piper of Duckburg.ini"


class TestTitleEnumWrappers:
    """The lookups for callers that already hold a ``Titles`` member."""

    def test_a_titles_volume_is_its_story_titles(self, db: ComicsDatabase) -> None:
        assert db.get_fanta_volume_int_for(Titles.PIED_PIPER_OF_DUCKBURG) == (
            db.get_fanta_volume_int("Pied Piper of Duckburg")
        )

    def test_a_titles_comic_book_is_its_story_titles(self, db: ComicsDatabase) -> None:
        comic = db.get_comic_book_for(Titles.PIED_PIPER_OF_DUCKBURG)
        assert comic.ini_file.name == "Pied Piper of Duckburg.ini"


class TestNonComicTitles:
    """A volume's articles and introductions can be left out of its titles."""

    def test_they_are_left_out_only_when_asked(self, db: ComicsDatabase) -> None:
        every = {title for title, _ in db.get_configured_titles_in_fantagraphics_volume(7)}
        comics = {
            title
            for title, _ in db.get_configured_titles_in_fantagraphics_volume(
                7, exclude_non_comics=True
            )
        }
        assert every - comics == {
            "Don Ault - Fantagraphics Introduction",
            "Rich Tommaso - On Coloring Barks",
        }
        assert all(STR_TITLE_TO_ENUM[title] in NON_COMIC_TITLES for title in every - comics)
        assert not any(STR_TITLE_TO_ENUM[title] in NON_COMIC_TITLES for title in comics)


class TestBuildingChecks:
    def test_a_database_for_building_checks_each_comic_it_opens(self) -> None:
        builder = ComicsDatabase(for_building_comics=True)
        with patch.object(comics_database_module, "check_comic_ok_for_building") as checked:
            comic = builder.get_comic_book("Pied Piper of Duckburg")
        checked.assert_called_once_with(comic)

    def test_a_database_for_reading_does_not(self, db: ComicsDatabase) -> None:
        with patch.object(comics_database_module, "check_comic_ok_for_building") as checked:
            db.get_comic_book("Pied Piper of Duckburg")
        checked.assert_not_called()


# ---------------------------------------------------------------------------
# The build pipeline's checks (barks-comic-building calls these; no test reached them)
# ---------------------------------------------------------------------------


@pytest.fixture
def log_lines() -> Iterator[list[str]]:
    """Collect loguru's messages, at every level, while the test runs."""
    lines: list[str] = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level=0)
    yield lines
    logger.remove(sink)


class _FakeDb:
    """The volume directory lookups make_all_fantagraphics_directories asks for, under `root`.

    A volume's dir is root/<what>/<NN>; a root dir, root/<what>.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def __getattr__(self, name: str) -> Callable[..., Path]:
        what = name.removeprefix("get_fantagraphics_")
        if what.endswith("_root_dir"):
            return lambda: self.root / what
        return lambda volume: self.root / what / f"{volume:02d}"


DERIVED_VOLUME_DIRS = [
    "upscayled_volume_image_dir",
    "restored_volume_image_dir",
    "restored_upscayled_volume_image_dir",
    "restored_svg_volume_image_dir",
    "restored_ocr_raw_volume_dir",
    "fixes_volume_image_dir",
    "upscayled_fixes_volume_image_dir",
    "panel_segments_volume_dir",
]
SYMLINKED_ROOTS = ["upscayled_root_dir", "restored_upscayled_root_dir", "restored_svg_root_dir"]


class TestMakeAllFantagraphicsDirectories:
    @pytest.fixture
    def made(self, tmp_path: Path, log_lines: list[str]) -> tuple[Path, list[str]]:
        """Run it over volumes 1 to 3, with originals for 1 and 3 only and one root symlinked."""
        for volume in (1, 3):
            (tmp_path / "volume_dir" / f"{volume:02d}").mkdir(parents=True)
        (tmp_path / "upscayled-target").mkdir()
        (tmp_path / "upscayled_root_dir").symlink_to(tmp_path / "upscayled-target")
        with (
            patch.object(comics_database_module, "FIRST_VOLUME_NUMBER", 1),
            patch.object(comics_database_module, "LAST_VOLUME_NUMBER", 3),
            patch.object(comics_database_module, "FANTA_VOLUME_OVERRIDES_ROOT", tmp_path / "ovr"),
        ):
            make_all_fantagraphics_directories(cast("ComicsDatabase", _FakeDb(tmp_path)))
        return tmp_path, log_lines

    def test_each_volume_with_originals_gets_its_derived_dirs(
        self, made: tuple[Path, list[str]]
    ) -> None:
        root, _ = made
        for volume in ("01", "03"):
            for what in DERIVED_VOLUME_DIRS:
                assert (root / what / volume).is_dir(), f"{what} for volume {volume}"
            for scraps in ("standard", "upscayled", "restored"):
                assert (root / "fixes_scraps_volume_image_dir" / volume / scraps).is_dir()
        assert (root / "ovr").is_dir()

    def test_a_volume_without_originals_is_skipped_and_named(
        self, made: tuple[Path, list[str]]
    ) -> None:
        root, lines = made
        assert not any((root / what / "02").exists() for what in DERIVED_VOLUME_DIRS)
        assert any("No Fantagraphics original dir for volume 2" in line for line in lines)

    def test_a_missing_symlink_is_an_error_and_a_present_one_is_not(
        self, made: tuple[Path, list[str]]
    ) -> None:
        root, lines = made
        missing = [line for line in lines if line.startswith("Symlink not found")]
        assert missing == [f'Symlink not found: "{root / name}".' for name in SYMLINKED_ROOTS[1:]]

    def test_dirs_already_there_are_left_alone(
        self, made: tuple[Path, list[str]], log_lines: list[str]
    ) -> None:
        root, _ = made
        log_lines.clear()
        with (
            patch.object(comics_database_module, "FIRST_VOLUME_NUMBER", 1),
            patch.object(comics_database_module, "LAST_VOLUME_NUMBER", 1),
            patch.object(comics_database_module, "FANTA_VOLUME_OVERRIDES_ROOT", root / "ovr"),
        ):
            make_all_fantagraphics_directories(cast("ComicsDatabase", _FakeDb(root)))
        assert not any(line.startswith("Created dir") for line in log_lines)
        assert any(line.startswith("Dir already exists") for line in log_lines)

    def test_the_database_method_runs_it_for_itself(self) -> None:
        db = MagicMock(spec=ComicsDatabase)
        with patch.object(comics_database_module, "make_all_fantagraphics_directories") as made:
            ComicsDatabase.make_all_fantagraphics_directories(db)
        made.assert_called_once_with(db)


# The directories a comic must have to be built, in the order they are checked: the
# comic's attribute or method for each, and what the error calls it.
BUILD_DIRS = [
    ("dirs.srce_dir", "srce directory"),
    ("get_srce_image_dir", "srce image directory"),
    ("dirs.srce_upscayled_dir", "srce upscayled directory"),
    ("get_srce_upscayled_image_dir", "srce upscayled image directory"),
    ("dirs.srce_restored_dir", "srce restored directory"),
    ("get_srce_restored_image_dir", "srce restored image directory"),
    ("dirs.srce_fixes_dir", "srce fixes directory"),
    ("get_srce_original_fixes_image_dir", "srce fixes image directory"),
]


def _comic_with_dirs(root: Path, missing: str | None = None) -> MagicMock:
    """Return a stand-in comic whose build dirs are under `root`, all made but `missing`."""
    comic = MagicMock()
    for index, (where, _what) in enumerate(BUILD_DIRS):
        path = root / f"dir{index}"
        if where != missing:
            path.mkdir()
        if where.startswith("dirs."):
            setattr(comic.dirs, where.removeprefix("dirs."), path)
        else:
            getattr(comic, where).return_value = path
    return comic


class TestCheckComicOkForBuilding:
    def test_a_comic_with_every_dir_passes(self, tmp_path: Path) -> None:
        check_comic_ok_for_building(_comic_with_dirs(tmp_path))

    @pytest.mark.parametrize(("where", "what"), BUILD_DIRS)
    def test_each_missing_dir_is_named(self, tmp_path: Path, where: str, what: str) -> None:
        with pytest.raises(FileNotFoundError, match=f"Could not find {what} "):
            check_comic_ok_for_building(_comic_with_dirs(tmp_path, missing=where))

    def test_the_database_method_checks_the_same(self) -> None:
        comic = MagicMock()
        with patch.object(comics_database_module, "check_comic_ok_for_building") as checked:
            ComicsDatabase.check_comic_ok_for_building(comic)
        checked.assert_called_once_with(comic)
