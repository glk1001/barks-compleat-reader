"""Tests for the reader-files validator's layout (10) and wiki-join (11) phases.

Phase 10 runs the reader's own layout builder, so these tests stub only what
reads the data pack (the comics database, the panel-segments adapter and the
page enumeration) and keep the builder real. Phase 11 runs against small
bundles written under ``tmp_path``.
"""

from __future__ import annotations

import os
import time
import zipfile
from configparser import ConfigParser
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import validate_barks_reader_core as core
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.comic_book_info import ONE_PAGERS
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import ALL_FANTA_COMIC_BOOK_INFO
from barks_fantagraphics.page_classes import CleanPage, SrceAndDestPages
from barks_reader.core.reader_settings import (
    BARKS_READER_SECTION,
    UNSET_WIKI_BUNDLE_DIR_MARKER,
    USE_LIVE_WIKI_BUNDLE,
    WIKI_BUNDLE_DIR,
    WIKI_BUNDLE_SUBDIR,
)

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
