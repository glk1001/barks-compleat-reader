"""Tests for the validator's layout (10), wiki-join (11), splash (12) and index (13) phases.

Phase 10 runs the reader's own layout builder, so these tests stub only what
reads the data pack (the comics database, the panel-segments adapter and the
page enumeration) and keep the builder real. Phase 11 runs against small
bundles written under ``tmp_path``.
"""

from __future__ import annotations

import json
import os
import time
import zipfile
from configparser import ConfigParser
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import validate_barks_reader_core as core
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, STR_TITLE_TO_ENUM, Titles
from barks_fantagraphics.comic_book_info import (
    NON_COMIC_TITLES,
    ONE_PAGERS,
    get_filename_from_title,
    get_located_one_pagers,
    is_covers_collection,
    is_one_pager_collection,
)
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_fantagraphics.page_classes import CleanPage, SrceAndDestPages
from barks_fantagraphics.speech_markup import strip_markup
from barks_fantagraphics.testing.whoosh_index import build_test_index
from barks_reader.core.comic_book_page_info import PageInfo
from barks_reader.core.reader_settings import (
    BARKS_READER_SECTION,
    UNSET_WIKI_BUNDLE_DIR_MARKER,
    USE_LIVE_WIKI_BUNDLE,
    WIKI_BUNDLE_DIR,
    WIKI_BUNDLE_SUBDIR,
)
from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Iterator

ANDES = "Lost in the Andes!"
VOLUME_DIR = "vol"


def _only_phase(collector: core.ErrorCollector) -> core.PhaseResult:
    assert len(collector.phases) == 1
    return collector.phases[0]


def _kinds(phase: core.PhaseResult) -> list[str]:
    return [word for msg in phase.errors for word in msg.split() if word.startswith("kind=")]


# ---------------------------------------------------------------------------
# Phase 10
# ---------------------------------------------------------------------------


def _body_pages(count: int) -> SrceAndDestPages:
    pages = [CleanPage(f"{num:03d}.jpg", PageType.BODY) for num in range(1, count + 1)]
    return SrceAndDestPages(srce_pages=pages, dest_pages=pages)


class TestPhase10Layout:
    @pytest.fixture
    def segments_root(self, tmp_path: Path) -> Path:
        (tmp_path / VOLUME_DIR).mkdir()
        return tmp_path

    @pytest.fixture
    def sys_paths(self, segments_root: Path) -> MagicMock:
        paths = MagicMock()
        paths.get_barks_reader_fantagraphics_panel_segments_root_dir.return_value = segments_root
        return paths

    @pytest.fixture
    def db(self) -> Iterator[MagicMock]:
        comic = MagicMock()
        comic.fanta_info.comic_book_info.title = Titles.LOST_IN_THE_ANDES
        comic.solo_page_keys = set()
        with patch.object(core, "ComicsDatabase") as db_class:
            database = db_class.return_value
            database.get_comic_book.return_value = comic
            database.get_fantagraphics_volume_title.return_value = VOLUME_DIR
            yield database

    @pytest.fixture
    def pages(self) -> Iterator[MagicMock]:
        """Stand in for both page sources: the enumeration and the reader's adapter."""
        pages = _body_pages(2)
        with (
            patch.object(core, "get_srce_and_dest_pages_in_order", return_value=pages),
            patch.object(core, "FantagraphicsPanelSegmentsAdapter") as adapter_class,
        ):
            adapter_class.return_value.get_sorted_pages.return_value = pages
            yield adapter_class.return_value

    @staticmethod
    def _write_segment_files(segments_root: Path, *stems: str) -> None:
        for stem in stems:
            (segments_root / VOLUME_DIR / f"{stem}.json").write_text("{}")

    @staticmethod
    def _run(sys_paths: MagicMock, title: str = ANDES) -> core.PhaseResult:
        collector = core.ErrorCollector()
        core.phase10_layout(collector, sys_paths, core.FantaState(), [title])
        return _only_phase(collector)

    @pytest.mark.usefixtures("db", "pages")
    def test_a_title_with_its_segments_builds_cleanly(
        self, sys_paths: MagicMock, segments_root: Path
    ) -> None:
        self._write_segment_files(segments_root, "001", "002")
        phase = self._run(sys_paths)
        assert phase.errors == []
        assert phase.items_checked == 1

    @pytest.mark.usefixtures("pages")
    def test_the_layouts_built_are_kept_for_phase_12(
        self, sys_paths: MagicMock, segments_root: Path, db: MagicMock
    ) -> None:
        self._write_segment_files(segments_root, "001", "002")
        built = core.phase10_layout(core.ErrorCollector(), sys_paths, core.FantaState(), [ANDES])
        assert built is not None
        assert built.db is db
        assert built.panel_segments_root == segments_root
        comic, layout = built.layouts[ANDES]
        assert comic is db.get_comic_book.return_value
        assert list(layout.page_map) == ["1", "2"]

    @pytest.mark.usefixtures("db")
    def test_a_layout_that_failed_is_not_kept(
        self, sys_paths: MagicMock, segments_root: Path, pages: MagicMock
    ) -> None:
        self._write_segment_files(segments_root, "001", "002")
        pages.get_sorted_pages.side_effect = FileNotFoundError("no such json")
        built = core.phase10_layout(core.ErrorCollector(), sys_paths, core.FantaState(), [ANDES])
        assert built is not None
        assert built.layouts == {}

    def test_without_a_database_there_are_no_layouts(self, sys_paths: MagicMock) -> None:
        with patch.object(core, "ComicsDatabase", side_effect=RuntimeError("no ini")):
            assert core.phase10_layout(core.ErrorCollector(), sys_paths, core.FantaState()) is None

    @pytest.mark.usefixtures("db")
    def test_a_raising_build_is_a_layout_failure(
        self, sys_paths: MagicMock, segments_root: Path, pages: MagicMock
    ) -> None:
        self._write_segment_files(segments_root, "001", "002")
        pages.get_sorted_pages.side_effect = FileNotFoundError("no such json")
        phase = self._run(sys_paths)
        assert _kinds(phase) == ["kind=layout_build_failed"]
        assert "FileNotFoundError: no such json" in phase.errors[0]

    @pytest.mark.usefixtures("db")
    def test_an_empty_page_list_cannot_be_laid_out(
        self, sys_paths: MagicMock, pages: MagicMock
    ) -> None:
        pages.get_sorted_pages.return_value = _body_pages(0)
        with patch.object(core, "get_srce_and_dest_pages_in_order", return_value=_body_pages(0)):
            phase = self._run(sys_paths)
        assert _kinds(phase) == ["kind=layout_build_failed"]

    @pytest.mark.usefixtures("pages")
    def test_a_comic_that_will_not_load_is_reported_once(
        self, sys_paths: MagicMock, db: MagicMock
    ) -> None:
        db.get_comic_book.side_effect = KeyError("bad ini")
        phase = self._run(sys_paths)
        assert _kinds(phase) == ["kind=comic_book_load_failed"]

    @pytest.mark.usefixtures("pages")
    def test_a_one_pager_is_not_a_title_of_its_own(
        self, sys_paths: MagicMock, db: MagicMock
    ) -> None:
        one_pager = ENUM_TO_STR_TITLE[next(iter(ONE_PAGERS))]
        phase = self._run(sys_paths, one_pager)
        assert phase.items_checked == 0
        db.get_comic_book.assert_not_called()

    @pytest.mark.usefixtures("db")
    def test_a_missing_json_skips_the_build_that_would_fail_on_it(
        self, sys_paths: MagicMock, segments_root: Path, pages: MagicMock
    ) -> None:
        self._write_segment_files(segments_root, "001")
        phase = self._run(sys_paths)
        assert _kinds(phase) == ["kind=missing_segments_json"]
        assert "page=002" in phase.errors[0]
        pages.get_sorted_pages.assert_not_called()

    @pytest.mark.usefixtures("db", "pages")
    def test_a_missing_volume_dir_is_one_error(
        self, sys_paths: MagicMock, segments_root: Path
    ) -> None:
        (segments_root / VOLUME_DIR).rmdir()
        phase = self._run(sys_paths)
        assert _kinds(phase) == ["kind=missing_segments_dir"]


_DIR_GETTERS = (
    "get_comic_inset_files_dir",
    "get_comic_cover_files_dir",
    "get_comic_bw_files_dir",
    "get_comic_ai_files_dir",
    "get_comic_censorship_files_dir",
    "get_comic_closeup_files_dir",
    "get_comic_favourite_files_dir",
    "get_comic_original_art_files_dir",
    "get_comic_search_files_dir",
    "get_comic_silhouette_files_dir",
    "get_comic_splash_files_dir",
)


def _check_title_files(
    tmp_path: Path, title: Titles, known_missing: frozenset[str] = frozenset()
) -> tuple[core.PhaseResult, core._TitleCounts | None]:
    """Run one title's panel-file check against a panel source rooted at ``tmp_path``."""
    file_paths = MagicMock(barks_panels_are_encrypted=False)
    file_paths.get_inset_file_ext.return_value = ".png"
    for getter in _DIR_GETTERS:
        getattr(file_paths, getter).return_value = tmp_path
    phase = core.PhaseResult(name="Per-title Panel Files")
    ctx = core._AuditCtx(panel_source=tmp_path, is_zip=False)  # noqa: SLF001
    counts = core._validate_title_files(  # noqa: SLF001
        phase, file_paths, ctx, ENUM_TO_STR_TITLE[title], known_missing
    )
    return phase, counts


class TestValidateTitleFiles:
    """A title's panel files, against a panel source with none at all."""

    def test_a_story_needs_an_inset_and_a_panel_file(self, tmp_path: Path) -> None:
        phase, _ = _check_title_files(tmp_path, Titles.LOST_IN_THE_ANDES)
        assert _kinds(phase) == ["kind=missing_inset", "kind=no_panel_files"]

    def test_the_all_covers_collection_needs_neither(self, tmp_path: Path) -> None:
        assert _check_title_files(tmp_path, Titles.ALL_COVERS)[0].errors == []


class TestKnownMissingInsets:
    ONE_PAGER = get_located_one_pagers()[0]

    def _listed(self) -> frozenset[str]:
        return frozenset({ENUM_TO_STR_TITLE[self.ONE_PAGER]})

    def test_a_located_one_pager_needs_its_inset(self, tmp_path: Path) -> None:
        phase, _ = _check_title_files(tmp_path, self.ONE_PAGER)
        assert _kinds(phase) == ["kind=missing_inset"]

    def test_listed_it_is_counted_not_failed(self, tmp_path: Path) -> None:
        phase, counts = _check_title_files(tmp_path, self.ONE_PAGER, self._listed())
        assert phase.errors == []
        assert counts is not None
        assert counts.inset_known_missing is True

    def test_listed_with_its_inset_is_stale(self, tmp_path: Path) -> None:
        Image.new("RGB", (4, 4)).save(tmp_path / get_filename_from_title(self.ONE_PAGER, ".png"))
        phase, _ = _check_title_files(tmp_path, self.ONE_PAGER, self._listed())
        assert _kinds(phase) == ["kind=known_missing_inset_present"]

    def test_listed_but_needing_no_inset_is_stale(self, tmp_path: Path) -> None:
        listed = frozenset({ENUM_TO_STR_TITLE[Titles.ALL_COVERS]})
        phase, _ = _check_title_files(tmp_path, Titles.ALL_COVERS, listed)
        assert _kinds(phase) == ["kind=known_missing_inset_not_required"]

    def test_a_line_that_names_no_title_fails(self) -> None:
        collector = core.ErrorCollector()
        core.phase8a_per_title_panel_files(
            collector, [], MagicMock(), titles_filter=[], known_missing_insets=frozenset({"Nope"})
        )
        assert _kinds(_only_phase(collector)) == ["kind=unknown_title"]

    def test_the_file_skips_comments_and_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "known.txt"
        path.write_text("# a comment\n\n  Lost in the Andes!  \nCoffee for Two\n")
        assert core.load_known_missing_insets(path) == {"Lost in the Andes!", "Coffee for Two"}

    def test_no_file_is_an_empty_list(self, tmp_path: Path) -> None:
        assert core.load_known_missing_insets(tmp_path / "absent.txt") == frozenset()

    def test_the_committed_list_names_only_titles(self) -> None:
        listed = core.load_known_missing_insets()
        assert listed
        assert listed <= STR_TITLE_TO_ENUM.keys()


class TestCheckSegmentsJson:
    MEMBER = "images/001.jpg"
    SRCE_TIME = (2024, 6, 1, 12, 0, 0)

    @pytest.fixture
    def volume_zip(self, tmp_path: Path) -> Iterator[zipfile.ZipFile]:
        path = tmp_path / "volume.cbz"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(zipfile.ZipInfo(self.MEMBER, date_time=self.SRCE_TIME), b"jpg")
        with zipfile.ZipFile(path) as zf:
            yield zf

    def _check(self, tmp_path: Path, volume_zip: zipfile.ZipFile) -> tuple[bool, core.PhaseResult]:
        phase = core.PhaseResult(name="test")
        present = core._check_segments_json(  # noqa: SLF001
            phase,
            core._Phase10Counts(),  # noqa: SLF001
            ANDES,
            "001",
            tmp_path,
            volume_zip,
            # A Windows path, so that every platform checks the member is named with '/'.
            PureWindowsPath(self.MEMBER),
        )
        return present, phase

    def _write_json(self, tmp_path: Path, offset: float) -> None:
        json_path = tmp_path / "001.json"
        json_path.write_text("{}")
        mtime = time.mktime((*self.SRCE_TIME, 0, 0, -1)) + offset
        os.utime(json_path, (mtime, mtime))

    def test_missing(self, tmp_path: Path, volume_zip: zipfile.ZipFile) -> None:
        present, phase = self._check(tmp_path, volume_zip)
        assert not present
        assert _kinds(phase) == ["kind=missing_segments_json"]

    def test_newer_than_its_page_is_fine(self, tmp_path: Path, volume_zip: zipfile.ZipFile) -> None:
        self._write_json(tmp_path, offset=60)
        present, phase = self._check(tmp_path, volume_zip)
        assert present
        assert phase.errors == []

    def test_older_than_its_page_is_stale(
        self, tmp_path: Path, volume_zip: zipfile.ZipFile
    ) -> None:
        self._write_json(tmp_path, offset=-60)
        present, phase = self._check(tmp_path, volume_zip)
        assert present  # stale, but the reader can still build from it
        assert _kinds(phase) == ["kind=stale_segments_json"]


# ---------------------------------------------------------------------------
# Phase 11
# ---------------------------------------------------------------------------


def _write_bundle(bundle: Path, pages: dict[str, str | None]) -> Path:
    """Write a bundle root and story pages: relative path under stories -> title (None: none)."""
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "index.md").write_text("---\ntitle: Index\n---\n")
    for rel, title in pages.items():
        page = bundle / "concept" / "stories" / rel
        page.parent.mkdir(parents=True, exist_ok=True)
        frontmatter = f'title: "{title}"' if title is not None else "type: concept"
        page.write_text(f"---\n{frontmatter}\n---\n\nBody.\n")
    return bundle


def _run_wiki(
    bundle: Path | None, titles: list[str] | None = None, *, strict: bool = False
) -> core.PhaseResult:
    collector = core.ErrorCollector()
    core.phase11_wiki(collector, bundle, titles, strict=strict)
    return _only_phase(collector)


def _gyro_title() -> Titles:
    return next(
        title
        for title, info in ALL_FANTA_COMIC_BOOK_INFO.items()
        if info.series_name == "Gyro Gearloose"
    )


class TestPhase11Wiki:
    def test_a_joined_page(self, tmp_path: Path) -> None:
        bundle = _write_bundle(tmp_path, {"donald-duck-adventures/lost-in-the-andes.md": ANDES})
        phase = _run_wiki(bundle, [ANDES])
        assert phase.errors == []
        assert "1 joined" in phase.summary_extra

    def test_a_page_in_a_directory_the_reader_does_not_look_in(self, tmp_path: Path) -> None:
        bundle = _write_bundle(tmp_path, {"misc/lost-in-the-andes.md": ANDES})
        phase = _run_wiki(bundle, [ANDES])
        assert _kinds(phase) == ["kind=wiki_page_unreachable"]
        assert "looked_in=donald-duck-adventures" in phase.errors[0]

    def test_a_non_canonical_title_on_a_story_slug(self, tmp_path: Path) -> None:
        bundle = _write_bundle(
            tmp_path, {"donald-duck-adventures/lost-in-the-andes.md": "Lost In The Andes!"}
        )
        phase = _run_wiki(bundle, [ANDES])
        assert _kinds(phase) == ["kind=story_page_title_mismatch"]
        assert f"expected={ANDES!r}" in phase.errors[0]

    def test_a_non_corpus_story_is_only_counted(self, tmp_path: Path) -> None:
        bundle = _write_bundle(tmp_path, {"non-disney/a-western-tale.md": "A Western Tale"})
        phase = _run_wiki(bundle, [ANDES])
        assert phase.errors == []
        assert "1 outside-corpus" in phase.summary_extra

    def test_a_page_that_is_not_utf8_is_its_own_error(self, tmp_path: Path) -> None:
        """A page the reader cannot decode is reported, and the other pages still join."""
        bundle = _write_bundle(tmp_path, {"donald-duck-adventures/lost-in-the-andes.md": ANDES})
        bad = bundle / "concept" / "stories" / "misc" / "latin-1.md"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_bytes(b"---\ntitle: Caf\xe9\n---\n")
        phase = _run_wiki(bundle, [ANDES])
        assert _kinds(phase) == ["kind=story_page_unreadable"]
        assert "Page:concept/stories/misc/latin-1.md" in phase.errors[0]
        assert "1 joined" in phase.summary_extra

    def test_a_page_with_no_title(self, tmp_path: Path) -> None:
        bundle = _write_bundle(tmp_path, {"misc/untitled.md": None})
        phase = _run_wiki(bundle)
        assert _kinds(phase) == ["kind=story_page_no_title"]

    def test_a_title_the_reader_does_not_carry_is_skipped(self, tmp_path: Path) -> None:
        title = next(t for t in Titles if t not in ALL_FANTA_COMIC_BOOK_INFO)
        bundle = _write_bundle(tmp_path, {"misc/elsewhere.md": ENUM_TO_STR_TITLE[title]})
        phase = _run_wiki(bundle, [ANDES])
        assert phase.errors == []
        assert "1 not-in-reader" in phase.summary_extra

    def test_a_story_filed_in_both_candidate_directories(self, tmp_path: Path) -> None:
        title = _gyro_title()
        title_str = ENUM_TO_STR_TITLE[title]
        slug = core.story_slug(title_str)
        bundle = _write_bundle(
            tmp_path,
            {f"gyro-gearloose-stories/{slug}.md": title_str, f"misc/{slug}.md": title_str},
        )
        phase = _run_wiki(bundle, [title_str])
        assert _kinds(phase) == ["kind=duplicate_wiki_page"]

    def test_an_unwritten_page_is_counted_by_default(self, tmp_path: Path) -> None:
        phase = _run_wiki(_write_bundle(tmp_path, {}), [ANDES])
        assert phase.errors == []
        assert "1 unwritten" in phase.summary_extra

    def test_an_unwritten_page_fails_when_strict(self, tmp_path: Path) -> None:
        phase = _run_wiki(_write_bundle(tmp_path, {}), [ANDES], strict=True)
        assert _kinds(phase) == ["kind=missing_wiki_page"]
        assert "slug=lost-in-the-andes" in phase.errors[0]

    def test_no_bundle(self) -> None:
        assert _run_wiki(None).errors == ["Wiki: missing_bundle"]


class TestResolveWikiBundleDir:
    @staticmethod
    def _cfg_info(tmp_path: Path, **settings: str) -> MagicMock:
        config = ConfigParser()
        config[BARKS_READER_SECTION] = settings
        ini = tmp_path / "barks-reader.ini"
        with ini.open("w") as f:
            config.write(f)
        cfg_info = MagicMock()
        cfg_info.app_config_path = ini
        return cfg_info

    def test_an_explicit_bundle_wins(self, tmp_path: Path) -> None:
        bundle = _write_bundle(tmp_path / "explicit", {})
        cfg_info = self._cfg_info(tmp_path, **{USE_LIVE_WIKI_BUNDLE: "1"})
        assert core.resolve_wiki_bundle_dir(cfg_info, tmp_path, bundle) == bundle

    def test_the_live_bundle_when_switched_on(self, tmp_path: Path) -> None:
        bundle = _write_bundle(tmp_path / "live", {})
        cfg_info = self._cfg_info(
            tmp_path, **{USE_LIVE_WIKI_BUNDLE: "1", WIKI_BUNDLE_DIR: str(bundle)}
        )
        assert core.resolve_wiki_bundle_dir(cfg_info, tmp_path, None) == bundle

    def test_the_live_bundle_unset(self, tmp_path: Path) -> None:
        cfg_info = self._cfg_info(
            tmp_path,
            **{USE_LIVE_WIKI_BUNDLE: "1", WIKI_BUNDLE_DIR: UNSET_WIKI_BUNDLE_DIR_MARKER},
        )
        assert core.resolve_wiki_bundle_dir(cfg_info, tmp_path, None) is None

    def test_the_reader_files_copy_by_default(self, tmp_path: Path) -> None:
        bundle = _write_bundle(tmp_path / WIKI_BUNDLE_SUBDIR, {})
        cfg_info = self._cfg_info(tmp_path)
        assert core.resolve_wiki_bundle_dir(cfg_info, tmp_path, None) == bundle

    def test_a_directory_without_an_index_is_not_a_bundle(self, tmp_path: Path) -> None:
        (tmp_path / WIKI_BUNDLE_SUBDIR).mkdir()
        cfg_info = self._cfg_info(tmp_path, **{USE_LIVE_WIKI_BUNDLE: "0"})
        assert core.resolve_wiki_bundle_dir(cfg_info, tmp_path, None) is None


# ---------------------------------------------------------------------------
# Phase 12
# ---------------------------------------------------------------------------

_NORMAL_PAGE = [[0, 0, 100, 100]] * 8
_SPLASH_PAGE = [[0, 0, 400, 100], *[[0, 0, 100, 100]] * 4]


def _write_segments(segments_dir: Path, stem: str, panels: list[list[int]]) -> None:
    segments = {"overall_bounds": [0, 0, 800, 100], "panels": panels}
    (segments_dir / f"{stem}.json").write_text(json.dumps(segments))


class TestFindTitleSplashPages:
    @staticmethod
    def _find(tmp_path: Path, page_types: list[PageType]) -> list[str]:
        page_map = {
            str(num): PageInfo(
                num - 1,
                str(num),
                page_type,
                CleanPage(f"{num:03d}.jpg", page_type),
                CleanPage(f"{num:03d}.jpg", page_type),
            )
            for num, page_type in enumerate(page_types, 1)
        }
        db = MagicMock()
        db.get_fantagraphics_volume_title.return_value = VOLUME_DIR
        layout = MagicMock()
        layout.page_map = page_map
        return core.find_title_splash_pages(db, MagicMock(), layout, tmp_path)

    def test_a_splash_is_found_by_its_page_number(self, tmp_path: Path) -> None:
        (tmp_path / VOLUME_DIR).mkdir()
        for stem, panels in (("001", _NORMAL_PAGE), ("002", _NORMAL_PAGE), ("003", _SPLASH_PAGE)):
            _write_segments(tmp_path / VOLUME_DIR, stem, panels)
        assert self._find(tmp_path, [PageType.BODY] * 3) == ["3"]

    def test_page_1_can_be_a_splash(self, tmp_path: Path) -> None:
        (tmp_path / VOLUME_DIR).mkdir()
        for stem, panels in (("001", _SPLASH_PAGE), ("002", _NORMAL_PAGE), ("003", _NORMAL_PAGE)):
            _write_segments(tmp_path / VOLUME_DIR, stem, panels)
        assert self._find(tmp_path, [PageType.BODY] * 3) == ["1"]

    def test_only_body_pages_are_read(self, tmp_path: Path) -> None:
        # The back-matter page has no JSON: reading it would raise.
        (tmp_path / VOLUME_DIR).mkdir()
        for stem, panels in (("001", _NORMAL_PAGE), ("002", _SPLASH_PAGE)):
            _write_segments(tmp_path / VOLUME_DIR, stem, panels)
        assert self._find(tmp_path, [PageType.BODY, PageType.BODY, PageType.BACK_MATTER]) == ["2"]


_SPLASH_STORY = Titles.LOST_IN_THE_ANDES
_OTHER_STORY = Titles.VOODOO_HOODOO


def _built_layouts(*title_strs: str) -> core.BuiltLayouts:
    """Stand in for Phase 10's layouts: each story's comic carries its title."""
    built = core.BuiltLayouts(MagicMock(), Path("segments"))
    for title_str in title_strs:
        comic = MagicMock()
        comic.title_str = title_str
        built.layouts[title_str] = (comic, MagicMock())
    return built


class TestPhase12SplashTags:
    @staticmethod
    def _run(
        found: dict[Titles, list[str] | Exception],
        tagged: dict[Titles, list[str]],
        titles_filter: list[str] | None = None,
        story_titles: list[Titles] | None = None,
        exceptions: dict[Titles, list[str]] | None = None,
    ) -> core.PhaseResult:
        def find(_db: object, comic: MagicMock, _layout: object, _root: Path) -> list[str]:
            result = found.get(STR_TITLE_TO_ENUM[comic.title_str], [])
            if isinstance(result, Exception):
                raise result
            return result

        stories = [ENUM_TO_STR_TITLE[t] for t in (story_titles or list(found))]
        built = _built_layouts(*stories)
        collector = core.ErrorCollector()
        with (
            patch.object(core, "get_splash_story_titles", return_value=stories),
            patch.object(core, "find_title_splash_pages", side_effect=find),
            patch.object(core, "BARKS_TAGGED_TITLES", {core.Tags.SPLASH: list(tagged)}),
            patch.object(
                core,
                "BARKS_TAGGED_PAGES",
                {(core.Tags.SPLASH, title): pages for title, pages in tagged.items()},
            ),
            patch.object(core, "SPLASH_EXCEPTIONS", exceptions or {}),
        ):
            core.phase12_splash_tags(collector, built, titles_filter)
        return _only_phase(collector)

    def test_tags_that_agree_with_the_panels_pass(self) -> None:
        found: dict[Titles, list[str] | Exception] = {_SPLASH_STORY: ["7", "20"], _OTHER_STORY: []}
        phase = self._run(found, {_SPLASH_STORY: ["7", "20"]})
        assert phase.errors == []
        assert phase.items_checked == len(found)

    def test_an_untagged_splash(self) -> None:
        phase = self._run({_SPLASH_STORY: ["7"]}, {})
        assert _kinds(phase) == ["kind=splash_untagged"]
        assert "pages=7" in phase.errors[0]

    def test_a_tag_on_a_story_with_no_splash(self) -> None:
        phase = self._run({_SPLASH_STORY: []}, {_SPLASH_STORY: ["7"]})
        assert _kinds(phase) == ["kind=splash_tagged_without_splash"]

    def test_tagged_pages_that_differ(self) -> None:
        phase = self._run({_SPLASH_STORY: ["7", "20"]}, {_SPLASH_STORY: ["7"]})
        assert _kinds(phase) == ["kind=splash_pages_differ"]
        assert "found=7,20 tagged=7" in phase.errors[0]

    def test_a_story_whose_pages_cannot_be_read_is_unchecked(self) -> None:
        phase = self._run({_SPLASH_STORY: FileNotFoundError("no json")}, {_SPLASH_STORY: ["7"]})
        assert _kinds(phase) == ["kind=splash_unchecked"]

    def test_a_story_phase_10_could_not_lay_out_is_unchecked(self) -> None:
        collector = core.ErrorCollector()
        with patch.object(core, "get_splash_story_titles", return_value=[ANDES]):
            core.phase12_splash_tags(collector, _built_layouts(), [ANDES])
        phase = _only_phase(collector)
        assert _kinds(phase) == ["kind=splash_unchecked"]
        assert "no layout from Phase 10" in phase.errors[0]

    def test_without_phase_10s_layouts_nothing_is_checked(self) -> None:
        collector = core.ErrorCollector()
        core.phase12_splash_tags(collector, None)
        phase = _only_phase(collector)
        assert phase.errors == ["unchecked: Phase 10 built no layouts (no comics database)"]
        assert phase.items_checked == 0

    def test_a_tagged_title_that_is_no_story_checked(self) -> None:
        one_pager = next(iter(ONE_PAGERS))
        phase = self._run(
            {_SPLASH_STORY: ["7"]},
            {_SPLASH_STORY: ["7"], one_pager: []},
            story_titles=[_SPLASH_STORY],
        )
        assert _kinds(phase) == ["kind=splash_tagged_not_a_story"]

    def test_a_title_filter_judges_only_its_titles(self) -> None:
        phase = self._run(
            {_SPLASH_STORY: ["7"]},
            {_SPLASH_STORY: ["7"], _OTHER_STORY: ["3"]},
            titles_filter=[ENUM_TO_STR_TITLE[_SPLASH_STORY]],
        )
        assert phase.errors == []

    def test_an_excepted_title_may_go_untagged(self) -> None:
        phase = self._run({_SPLASH_STORY: ["1", "7"]}, {}, exceptions={_SPLASH_STORY: []})
        assert phase.errors == []
        assert "1 excepted" in phase.summary_extra

    def test_an_excepted_title_may_not_be_tagged(self) -> None:
        phase = self._run(
            {_SPLASH_STORY: ["1", "7"]},
            {_SPLASH_STORY: ["1", "7"]},
            exceptions={_SPLASH_STORY: []},
        )
        assert _kinds(phase) == ["kind=splash_tagged_without_splash"]

    def test_an_excepted_page_is_left_out_of_the_tag(self) -> None:
        found: dict[Titles, list[str] | Exception] = {_SPLASH_STORY: ["1", "7"]}
        exceptions = {_SPLASH_STORY: ["1"]}
        assert self._run(found, {_SPLASH_STORY: ["7"]}, exceptions=exceptions).errors == []
        phase = self._run(found, {_SPLASH_STORY: ["1", "7"]}, exceptions=exceptions)
        assert _kinds(phase) == ["kind=splash_pages_differ"]
        assert "found=7 tagged=1,7" in phase.errors[0]

    def test_an_exception_for_a_page_that_is_no_splash_is_stale(self) -> None:
        phase = self._run(
            {_SPLASH_STORY: ["7"]}, {_SPLASH_STORY: ["7"]}, exceptions={_SPLASH_STORY: ["1"]}
        )
        assert _kinds(phase) == ["kind=splash_exception_stale"]
        assert "pages=1" in phase.errors[0]

    def test_an_exception_for_a_story_with_no_splash_is_stale(self) -> None:
        phase = self._run({_SPLASH_STORY: []}, {}, exceptions={_SPLASH_STORY: []})
        assert _kinds(phase) == ["kind=splash_exception_stale"]

    def test_an_exception_that_is_no_story_checked(self) -> None:
        one_pager = next(iter(ONE_PAGERS))
        phase = self._run(
            {_SPLASH_STORY: ["7"]},
            {_SPLASH_STORY: ["7"]},
            story_titles=[_SPLASH_STORY],
            exceptions={one_pager: []},
        )
        assert _kinds(phase) == ["kind=splash_exception_not_a_story"]


class TestGetExpectedSplashPages:
    def test_a_title_without_exceptions_keeps_its_pages(self) -> None:
        with patch.object(core, "SPLASH_EXCEPTIONS", {}):
            assert core.get_expected_splash_pages(_SPLASH_STORY, ["1", "7"]) == ["1", "7"]

    def test_an_excepted_title_keeps_none(self) -> None:
        with patch.object(core, "SPLASH_EXCEPTIONS", {_SPLASH_STORY: []}):
            assert core.get_expected_splash_pages(_SPLASH_STORY, ["1", "7"]) == []

    def test_excepted_pages_are_left_out(self) -> None:
        with patch.object(core, "SPLASH_EXCEPTIONS", {_SPLASH_STORY: ["1"]}):
            assert core.get_expected_splash_pages(_SPLASH_STORY, ["1", "7"]) == ["7"]


class TestGetStaleSplashExceptionPages:
    @staticmethod
    def _stale(found: list[str], exceptions: dict[Titles, list[str]]) -> list[str] | None:
        with patch.object(core, "SPLASH_EXCEPTIONS", exceptions):
            return core.get_stale_splash_exception_pages(_SPLASH_STORY, found)

    def test_a_title_without_an_exception_has_nothing_stale(self) -> None:
        assert self._stale([], {}) is None

    def test_an_exception_whose_pages_are_still_splashes_holds(self) -> None:
        assert self._stale(["1", "7"], {_SPLASH_STORY: ["1"]}) is None

    def test_a_whole_title_exception_holds_while_there_is_a_splash(self) -> None:
        assert self._stale(["7"], {_SPLASH_STORY: []}) is None

    def test_exempt_pages_no_longer_splashes_are_stale(self) -> None:
        assert self._stale(["7"], {_SPLASH_STORY: ["1", "7", "9"]}) == ["1", "9"]

    def test_with_no_splash_at_all_the_whole_exception_is_stale(self) -> None:
        assert self._stale([], {_SPLASH_STORY: ["1"]}) == []
        assert self._stale([], {_SPLASH_STORY: []}) == []


class TestGetSplashStoryTitles:
    def test_articles_and_collections_are_left_out(self) -> None:
        titles = {STR_TITLE_TO_ENUM[t] for t in core.get_splash_story_titles()}
        assert _SPLASH_STORY in titles
        assert not titles & set(NON_COMIC_TITLES)
        assert not titles & set(ONE_PAGERS)
        assert not any(is_one_pager_collection(t) or is_covers_collection(t) for t in titles)


# ---------------------------------------------------------------------------
# Phase 13
# ---------------------------------------------------------------------------

_OTHER = ENUM_TO_STR_TITLE[_OTHER_STORY]
_ANDES_VOLUME = 7
_STORIES = [(ANDES, _ANDES_VOLUME), (_OTHER, 8)]
_DUK_DUK = "QWAK QWAKS ARE A VOODOO CULT OF THE [b]DUK DUK[/b] TRIBE"


def _bubble(
    title: str, page: str, group: str, text: str, speaker: str = "", **entities: str
) -> dict[str, str]:
    """Return a stored bubble, its entities given by type: ``person="Duk Duk,Qwak Qwaks"``."""
    doc = {
        "title": title,
        "fanta_vol": "7",
        "fanta_page": page,
        "comic_page": "1",
        "content_id": group,
        "panel_num": "1",
        "speaker": speaker,
        "unstemmed": strip_markup(text).lower(),
        "content_raw": text,
    }
    doc.update({f"entities_{entity_type}": names for entity_type, names in entities.items()})
    return doc


def _index(
    tmp_path: Path,
    docs: list[dict[str, str]],
    volumes: str = "[7]",
    terms: dict[str, list[str]] | None = None,
    speakers: dict[str, int] | None = None,
) -> MagicMock:
    """Write an index and its sidecars under ``tmp_path`` and return the sys paths to it.

    Unless given, the term and speaker sidecars say what the bubbles store, as a
    build's do; ``volumes`` is the raw text of the volumes file, "" for none.
    """
    folder = tmp_path / "Indexes"
    folder.mkdir(parents=True)
    build_test_index(folder, docs)
    if volumes:
        (folder / core.INDEX_VOLUMES_FILE).write_text(volumes)
    if terms is None:
        terms = {}
        for doc in docs:
            for key, names in doc.items():
                if key.startswith("entities_") and names:
                    terms.setdefault(key.removeprefix("entities_"), []).extend(names.split(","))
    for entity_type, names in terms.items():
        (folder / f"entities-{entity_type}-terms.json").write_text(json.dumps(sorted(set(names))))
    if speakers is None:
        speakers = {}
        for doc in docs:
            if doc["speaker"]:
                speakers[doc["speaker"]] = speakers.get(doc["speaker"], 0) + 1
    (folder / "speakers.json").write_text(json.dumps(speakers))
    sys_paths = MagicMock()
    sys_paths.get_barks_reader_indexes_dir.return_value = folder
    return sys_paths


def _run_index_phase(
    sys_paths: MagicMock,
    stories: list[tuple[str, int]] | None = None,
    titles_filter: list[str] | None = None,
) -> core.PhaseResult:
    def story_titles(titles_filter: list[str] | None = None) -> list[tuple[str, int]]:
        return [
            (title, volume)
            for title, volume in (stories or _STORIES)
            if titles_filter is None or title in titles_filter
        ]

    collector = core.ErrorCollector()
    with patch.object(core, "get_index_story_titles", side_effect=story_titles):
        core.phase13_search_index(collector, sys_paths, titles_filter)
    return _only_phase(collector)


class TestPhase13SearchIndex:
    def test_a_sound_index_passes(self, tmp_path: Path) -> None:
        docs = [
            _bubble(ANDES, "041", "0", _DUK_DUK, "Donald", person="Duk Duk,Qwak Qwaks"),
            _bubble(ANDES, "041", "1", "SQUARE EGGS!", "Donald"),
        ]
        phase = _run_index_phase(_index(tmp_path, docs))
        assert phase.errors == []
        assert phase.items_checked == len(docs)
        assert phase.summary_extra == "(1 volumes, 1 titles, 0 titles with a name no bubble says)"

    def test_a_name_its_bubble_does_not_say(self, tmp_path: Path) -> None:
        """One error per title, counting its bubbles and naming the first."""
        docs = [
            _bubble(ANDES, "041", "0", _DUK_DUK, person="Duk Duk"),
            _bubble(ANDES, "041", "1", "AT LAST, SOMETHING EASY!", person="Pulpbugle"),
            _bubble(ANDES, "042", "3", "SQUARE EGGS!", location="Duckburg"),
        ]
        phase = _run_index_phase(_index(tmp_path, docs))
        assert _kinds(phase) == ["kind=index_entity_not_in_bubble"]
        assert phase.errors[0].startswith(f"Title:{ANDES} ")
        assert 'bubbles=2 first=page 041 group 1 person "Pulpbugle"' in phase.errors[0]
        assert "1 titles with a name no bubble says" in phase.summary_extra

    def test_a_name_read_through_markup_and_a_lettering_break(self, tmp_path: Path) -> None:
        """The tagger saw ai_text: breaks joined, markup gone, so the check reads the same."""
        docs = [
            _bubble(
                ANDES,
                "041",
                "0",
                "GO TO [b]DUCK[/b]\u00ad\nBURG, DUK\nDUK!",
                location="Duckburg",
                person="Duk Duk",
            )
        ]
        assert _run_index_phase(_index(tmp_path, docs)).errors == []

    def test_a_story_of_an_indexed_volume_with_no_bubble_is_missing(self, tmp_path: Path) -> None:
        docs = [_bubble(ANDES, "041", "0", "SQUARE EGGS!")]
        phase = _run_index_phase(_index(tmp_path, docs), stories=[(ANDES, 7), (_OTHER, 7)])
        assert _kinds(phase) == ["kind=index_title_missing"]
        assert phase.errors[0] == f"Title:{_OTHER} kind=index_title_missing volume=7"

    def test_a_story_of_a_volume_not_yet_indexed_is_not_required(self, tmp_path: Path) -> None:
        docs = [_bubble(ANDES, "041", "0", "SQUARE EGGS!")]
        assert _run_index_phase(_index(tmp_path, docs), stories=_STORIES).errors == []

    def test_an_indexed_title_that_is_no_story(self, tmp_path: Path) -> None:
        docs = [_bubble(ANDES, "041", "0", "EGGS!"), _bubble("Not a Story", "001", "0", "HI!")]
        phase = _run_index_phase(_index(tmp_path, docs))
        assert phase.errors == ["Title:Not a Story kind=index_title_not_a_story"]
        # A subset of titles cannot say what else the index should hold.
        assert _run_index_phase(_index(tmp_path / "f", docs), titles_filter=[ANDES]).errors == []

    def test_the_volumes_file(self, tmp_path: Path) -> None:
        docs = [_bubble(ANDES, "041", "0", "EGGS!")]
        missing = _run_index_phase(_index(tmp_path / "a", docs, volumes=""))
        assert _kinds(missing) == ["kind=index_volumes_missing"]
        unreadable = _run_index_phase(_index(tmp_path / "b", docs, volumes="nonsense"))
        assert _kinds(unreadable) == ["kind=index_volumes_unreadable"]
        for i, bad in enumerate(("[]", "[0]", '["7"]', "7")):
            phase = _run_index_phase(_index(tmp_path / f"bad{i}", docs, volumes=bad))
            assert _kinds(phase) == ["kind=index_volumes_bad"], bad
        # Without a volume list no story is required, so only the list is reported.
        assert len(missing.errors) == 1

    def test_sidecars_that_disagree_with_the_bubbles(self, tmp_path: Path) -> None:
        docs = [_bubble(ANDES, "041", "0", _DUK_DUK, "Donald", person="Duk Duk,Qwak Qwaks")]
        sys_paths = _index(
            tmp_path, docs, terms={"person": ["Duk Duk", "Gyro"]}, speakers={"Donald": 2}
        )
        phase = _run_index_phase(sys_paths)
        assert _kinds(phase) == ["kind=index_entity_terms_differ", "kind=index_speakers_differ"]
        assert "type=person unlisted=['Qwak Qwaks'] extra=['Gyro']" in phase.errors[0]
        assert "speakers=['Donald'] count=1" in phase.errors[1]
        # Whole-index data: a subset of titles cannot judge it.
        assert _run_index_phase(sys_paths, titles_filter=[ANDES]).errors == []

    def test_a_title_filter_judges_only_its_titles_bubbles(self, tmp_path: Path) -> None:
        docs = [
            _bubble(ANDES, "041", "0", "EGGS!"),
            _bubble(_OTHER, "090", "0", "VOODOO!", person="Pulpbugle"),
        ]
        phase = _run_index_phase(_index(tmp_path, docs), titles_filter=[ANDES])
        assert phase.errors == []
        assert phase.items_checked == 1

    def test_without_a_usable_index_nothing_is_checked(self, tmp_path: Path) -> None:
        sys_paths = MagicMock()
        sys_paths.get_barks_reader_indexes_dir.return_value = tmp_path
        phase = _run_index_phase(sys_paths)
        assert len(phase.errors) == 1
        assert phase.errors[0].startswith(f'unchecked: no usable search index in "{tmp_path}"')
        assert phase.items_checked == 0


class TestGetIndexStoryTitles:
    def test_the_splash_stories_with_their_volumes(self) -> None:
        stories = core.get_index_story_titles()
        assert [title for title, _volume in stories] == core.get_splash_story_titles()
        assert all(isinstance(volume, int) for _title, volume in stories)
        assert dict(stories)[ANDES] == _ANDES_VOLUME
