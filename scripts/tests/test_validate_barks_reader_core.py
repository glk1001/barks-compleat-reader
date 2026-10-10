"""Tests for the reader-files validator's layout (10), wiki-join (11) and splash (12) phases.

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
        builder = MagicMock()
        builder.build.return_value.page_map = page_map
        return core.find_title_splash_pages(db, builder, tmp_path, ANDES)

    def test_a_splash_after_page_1_is_found_by_its_page_number(self, tmp_path: Path) -> None:
        (tmp_path / VOLUME_DIR).mkdir()
        for stem, panels in (("001", _NORMAL_PAGE), ("002", _NORMAL_PAGE), ("003", _SPLASH_PAGE)):
            _write_segments(tmp_path / VOLUME_DIR, stem, panels)
        assert self._find(tmp_path, [PageType.BODY] * 3) == ["3"]

    def test_page_1_is_never_a_splash(self, tmp_path: Path) -> None:
        (tmp_path / VOLUME_DIR).mkdir()
        for stem, panels in (("001", _SPLASH_PAGE), ("002", _NORMAL_PAGE), ("003", _NORMAL_PAGE)):
            _write_segments(tmp_path / VOLUME_DIR, stem, panels)
        assert self._find(tmp_path, [PageType.BODY] * 3) == []

    def test_only_body_pages_are_read(self, tmp_path: Path) -> None:
        # The back-matter page has no JSON: reading it would raise.
        (tmp_path / VOLUME_DIR).mkdir()
        for stem, panels in (("001", _NORMAL_PAGE), ("002", _SPLASH_PAGE)):
            _write_segments(tmp_path / VOLUME_DIR, stem, panels)
        assert self._find(tmp_path, [PageType.BODY, PageType.BODY, PageType.BACK_MATTER]) == ["2"]


_SPLASH_STORY = Titles.LOST_IN_THE_ANDES
_OTHER_STORY = Titles.VOODOO_HOODOO


class TestPhase12SplashTags:
    @staticmethod
    def _run(
        found: dict[Titles, list[str] | Exception],
        tagged: dict[Titles, list[str]],
        titles_filter: list[str] | None = None,
        story_titles: list[Titles] | None = None,
    ) -> core.PhaseResult:
        def find(_db: object, _builder: object, _root: Path, title_str: str) -> list[str]:
            result = found.get(STR_TITLE_TO_ENUM[title_str], [])
            if isinstance(result, Exception):
                raise result
            return result

        stories = [ENUM_TO_STR_TITLE[t] for t in (story_titles or list(found))]
        collector = core.ErrorCollector()
        with (
            patch.object(core, "ComicsDatabase"),
            patch.object(core, "get_splash_story_titles", return_value=stories),
            patch.object(core, "find_title_splash_pages", side_effect=find),
            patch.object(core, "BARKS_TAGGED_TITLES", {core.Tags.SPLASH: list(tagged)}),
            patch.object(
                core,
                "BARKS_TAGGED_PAGES",
                {(core.Tags.SPLASH, title): pages for title, pages in tagged.items()},
            ),
        ):
            core.phase12_splash_tags(collector, MagicMock(), titles_filter)
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


class TestGetSplashStoryTitles:
    def test_articles_and_collections_are_left_out(self) -> None:
        titles = {STR_TITLE_TO_ENUM[t] for t in core.get_splash_story_titles()}
        assert _SPLASH_STORY in titles
        assert not titles & set(NON_COMIC_TITLES)
        assert not titles & set(ONE_PAGERS)
        assert not any(is_one_pager_collection(t) or is_covers_collection(t) for t in titles)
