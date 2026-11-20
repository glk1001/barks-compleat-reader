# ruff: noqa: SLF001
"""Tests for the validator's error collector and its file phases: 1, 3 to 9.

The nightly run takes these phases over a sound data pack, where nothing they
report ever happens. Here each is run against a small broken one under
``tmp_path``: a missing folder, a stray file, a volume with a page gone.
"""

from __future__ import annotations

import io
import zipfile
from configparser import ConfigParser
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import validate_barks_reader_core as core
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_fantagraphics.comic_book_info import COVERS_SET, ONE_PAGERS
from barks_fantagraphics.comics_consts import PageType
from barks_fantagraphics.fanta_comics_info import (
    ALL_FANTA_COMIC_BOOK_INFO,
    get_fanta_volume_from_str,
)
from barks_fantagraphics.page_classes import CleanPage, SrceAndDestPages
from barks_reader.core.reader_file_paths import (
    EDITED_SUBDIR,
    BarksPanelsExtType,
    PanelDirNames,
    ReaderFilePaths,
)
from barks_reader.core.reader_settings import (
    BARKS_READER_SECTION,
    FANTA_DIR,
    JPG_BARKS_PANELS_ZIP,
    PNG_BARKS_PANELS_DIR,
    PREBUILT_COMICS_DIR,
)
from barks_reader.core.reader_utils import EMPTY_PAGE_KEY
from comic_utils.decryption import DecryptionError
from loguru import logger
from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Iterator

ANDES = ENUM_TO_STR_TITLE[Titles.LOST_IN_THE_ANDES]
ANDES_VOLUME = get_fanta_volume_from_str(
    ALL_FANTA_COMIC_BOOK_INFO[Titles.LOST_IN_THE_ANDES].fantagraphics_volume
)
# The one volume the Fantagraphics tests make: its pages are numbered from 001.
VOLUME = 2


def _only_phase(collector: core.ErrorCollector) -> core.PhaseResult:
    assert len(collector.phases) == 1
    return collector.phases[0]


def _kinds(phase: core.PhaseResult) -> list[str]:
    return [word for msg in phase.errors for word in msg.split() if word.startswith("kind=")]


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (40, 80, 120)).save(buf, format="PNG")
    return buf.getvalue()


def _write(path: Path, data: bytes | str = b"") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)
    return path


def _cfg_info(tmp_path: Path, **settings: Path | str) -> MagicMock:
    """Stand in for ConfigInfo: an app config file holding `settings`."""
    config = ConfigParser()
    config[BARKS_READER_SECTION] = {key: str(value) for key, value in settings.items()}
    ini = tmp_path / "config" / "barks-reader.ini"
    ini.parent.mkdir(exist_ok=True)
    with ini.open("w", encoding="utf-8") as file:
        config.write(file)
    return MagicMock(app_config_path=ini)


def _panels_dir(root: Path) -> Path:
    """Make a complete PNG panels folder: every category, and the insets' edited folder."""
    for dir_name in PanelDirNames:
        (root / dir_name.value).mkdir(parents=True, exist_ok=True)
    (root / PanelDirNames.INSETS.value / EDITED_SUBDIR).mkdir(exist_ok=True)
    return root


def _png_variant(root: Path) -> ReaderFilePaths:
    file_paths = ReaderFilePaths()
    file_paths.set_barks_panels_source(_panels_dir(root), BarksPanelsExtType.MOSTLY_PNG)
    return file_paths


def _panels_zip(path: Path, members: dict[str, bytes]) -> Path:
    """Write a panels zip with every category folder and `members` beside them."""
    with zipfile.ZipFile(path, "w") as panels:
        for dir_name in PanelDirNames:
            panels.writestr(f"{dir_name.value}/", b"")
        for name, data in members.items():
            panels.writestr(name, data)
    return path


@pytest.fixture
def logged() -> Iterator[list[str]]:
    lines: list[str] = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="INFO")
    yield lines
    logger.remove(sink)


# ---------------------------------------------------------------------------
# The collector
# ---------------------------------------------------------------------------


class TestErrorCollector:
    def test_a_run_with_no_error_has_not_failed(self) -> None:
        collector = core.ErrorCollector()
        collector.start_phase("Config", "1")
        collector.start_phase("System File Paths", "2")

        assert not collector.any_failed

    def test_one_error_in_any_phase_fails_the_run(self) -> None:
        """The script's exit status: a clean first phase does not excuse a later one."""
        collector = core.ErrorCollector()
        collector.start_phase("Config", "1")
        collector.start_phase("System File Paths", "2").add("statistics_dir: missing")

        assert collector.any_failed
        assert [phase.failed for phase in collector.phases] == [False, True]

    def test_an_error_is_logged_under_its_phase_as_it_is_found(self, logged: list[str]) -> None:
        core.PhaseResult(name="Config").add("app_dir: missing directory /x")

        assert logged == ["[Config] app_dir: missing directory /x"]

    @pytest.mark.parametrize(
        ("errors", "skipped", "extra", "line"),
        [
            ([], False, "", "[Wiki] OK (0 errors, 3 checked)"),
            (["a", "b"], False, "", "[Wiki] FAIL (2 errors, 3 checked)"),
            ([], False, "(1 joined)", "[Wiki] OK (0 errors, 3 checked) (1 joined)"),
            ([], True, "(1 joined)", "[Wiki] SKIPPED"),
        ],
    )
    def test_each_phase_ends_on_one_summary_line(
        self, logged: list[str], errors: list[str], skipped: bool, extra: str, line: str
    ) -> None:
        phase = core.PhaseResult(
            name="Wiki", errors=errors, items_checked=3, skipped=skipped, summary_extra=extra
        )

        core.ErrorCollector.finalize_phase(phase)

        assert logged == [line]


# ---------------------------------------------------------------------------
# Phase 1
# ---------------------------------------------------------------------------


class TestPhase1Config:
    @staticmethod
    def _config(tmp_path: Path) -> SimpleNamespace:
        return SimpleNamespace(
            app_dir=tmp_path,
            app_config_dir=tmp_path / "config",
            app_config_path=tmp_path / "config" / "barks-reader.ini",
            app_data_dir=tmp_path / "data",
            kivy_config_dir=tmp_path / "config" / "kivy",
        )

    def test_a_config_that_cannot_be_built_is_one_error_and_no_config(self) -> None:
        collector = core.ErrorCollector()
        with patch.object(core, "ConfigInfo", side_effect=RuntimeError("no home")):
            assert core.phase1_config(collector, None, None) is None

        assert _only_phase(collector).errors == ["failed to construct ConfigInfo: no home"]

    def test_each_missing_folder_and_the_missing_file_is_an_error(self, tmp_path: Path) -> None:
        config = self._config(tmp_path)
        collector = core.ErrorCollector()
        with patch.object(core, "ConfigInfo", return_value=config):
            assert core.phase1_config(collector, None, None) is config

        phase = _only_phase(collector)
        assert phase.errors == [
            f"app_config_dir: missing directory {config.app_config_dir}",
            f"app_config_path: missing file {config.app_config_path}",
            f"app_data_dir: missing directory {config.app_data_dir}",
            f"kivy_config_dir: missing directory {config.kivy_config_dir}",
        ]
        assert phase.items_checked == 5  # noqa: PLR2004

    def test_a_whole_config_passes(self, tmp_path: Path) -> None:
        config = self._config(tmp_path)
        config.kivy_config_dir.mkdir(parents=True)
        config.app_data_dir.mkdir()
        config.app_config_path.touch()
        collector = core.ErrorCollector()
        with patch.object(core, "ConfigInfo", return_value=config):
            core.phase1_config(collector, None, None)

        assert _only_phase(collector).errors == []

    def test_the_command_line_s_folders_are_what_the_config_is_built_from(
        self, tmp_path: Path
    ) -> None:
        seen: dict[str, str | None] = {}

        def build() -> SimpleNamespace:
            seen["config"] = core.os.environ.get("BARKS_READER_CONFIG_DIR")
            seen["data"] = core.os.environ.get("BARKS_READER_DATA_DIR")
            return self._config(tmp_path)

        with patch.object(core, "ConfigInfo", side_effect=build):
            core.phase1_config(core.ErrorCollector(), tmp_path / "c", tmp_path / "d")

        assert seen == {"config": str(tmp_path / "c"), "data": str(tmp_path / "d")}


# ---------------------------------------------------------------------------
# Phase 3
# ---------------------------------------------------------------------------


class TestPhase3ReaderFilePaths:
    @staticmethod
    def _run(cfg_info: MagicMock, reader_files: Path) -> core.PhaseResult:
        collector = core.ErrorCollector()
        core.phase3_reader_file_paths(collector, cfg_info, reader_files)
        return _only_phase(collector)

    def test_the_panels_zip_must_be_there(self, tmp_path: Path) -> None:
        phase = self._run(_cfg_info(tmp_path), tmp_path)

        assert phase.errors == [f"panels_source: missing {tmp_path / JPG_BARKS_PANELS_ZIP}"]

    def test_an_app_config_that_is_not_there_is_said(self, tmp_path: Path) -> None:
        cfg_info = MagicMock(app_config_path=tmp_path / "absent.ini")

        phase = self._run(cfg_info, tmp_path)

        assert phase.errors[0] == f"app config INI not readable: {tmp_path / 'absent.ini'}"

    def test_a_zip_missing_category_folders_names_each_one(self, tmp_path: Path) -> None:
        """The app stops at the first missing folder; the validator lists them all."""
        with zipfile.ZipFile(tmp_path / JPG_BARKS_PANELS_ZIP, "w") as panels:
            panels.writestr("Insets/", b"")
            panels.writestr("Covers/x.jpg", b"")

        phase = self._run(_cfg_info(tmp_path), tmp_path)

        assert phase.errors[0].startswith("panels_source check raised: ")
        missing = [e for e in phase.errors if e.startswith("panels_zip: missing entry")]
        assert len(missing) == len(PanelDirNames) - 2
        assert "panels_zip: missing entry 'Splash'" in missing
        assert "panels_zip: missing entry 'Covers'" not in missing  # a member under it will do

    def test_a_whole_zip_passes(self, tmp_path: Path) -> None:
        _panels_zip(tmp_path / JPG_BARKS_PANELS_ZIP, {})

        phase = self._run(_cfg_info(tmp_path), tmp_path)

        assert phase.errors == []
        assert phase.items_checked == 1 + len(PanelDirNames)

    def test_a_zip_that_is_no_zip_is_one_error(self, tmp_path: Path) -> None:
        (tmp_path / JPG_BARKS_PANELS_ZIP).write_bytes(b"not a zip")

        phase = self._run(_cfg_info(tmp_path), tmp_path)

        assert len(phase.errors) == 1
        assert phase.errors[0].startswith("set_barks_panels_source failed: ")

    def test_a_configured_png_folder_is_checked_as_well(self, tmp_path: Path) -> None:
        _panels_zip(tmp_path / JPG_BARKS_PANELS_ZIP, {})
        png = tmp_path / "png"
        (png / "Insets").mkdir(parents=True)

        phase = self._run(_cfg_info(tmp_path, **{PNG_BARKS_PANELS_DIR: png}), tmp_path)

        assert phase.errors[0].startswith("panels_source check raised: ")
        assert f"panels_dir: missing 'Splash' under {png}" in phase.errors
        assert f"panels_dir: missing 'Insets/{EDITED_SUBDIR}' under {png}" in phase.errors
        assert f"panels_dir: missing 'Insets' under {png}" not in phase.errors
        assert len(phase.errors) == 1 + (len(PanelDirNames) - 1) + 1

    def test_a_whole_png_folder_passes(self, tmp_path: Path) -> None:
        _panels_zip(tmp_path / JPG_BARKS_PANELS_ZIP, {})
        png = _panels_dir(tmp_path / "png")

        phase = self._run(_cfg_info(tmp_path, **{PNG_BARKS_PANELS_DIR: png}), tmp_path)

        assert phase.errors == []

    def test_a_png_folder_that_is_not_there_is_not_asked_for(self, tmp_path: Path) -> None:
        """The PNG folder is extra: only the zip is required."""
        _panels_zip(tmp_path / JPG_BARKS_PANELS_ZIP, {})
        cfg_info = _cfg_info(tmp_path, **{PNG_BARKS_PANELS_DIR: tmp_path / "gone"})

        assert self._run(cfg_info, tmp_path).errors == []


class TestBuildReaderFilePaths:
    def test_the_zip_comes_first_and_the_png_folder_second(self, tmp_path: Path) -> None:
        _panels_zip(tmp_path / JPG_BARKS_PANELS_ZIP, {})
        png = _panels_dir(tmp_path / "png")

        variants = core.build_reader_file_paths(
            _cfg_info(tmp_path, **{PNG_BARKS_PANELS_DIR: png}), tmp_path
        )

        assert [v.barks_panels_are_encrypted for v in variants] == [True, False]

    def test_with_neither_there_is_nothing_to_check(self, tmp_path: Path) -> None:
        assert core.build_reader_file_paths(_cfg_info(tmp_path), tmp_path) == []

    def test_a_folder_missing_categories_is_kept_and_a_broken_zip_is_not(
        self, tmp_path: Path
    ) -> None:
        """Phase 3 has said what is wrong with both; the folder's insets still resolve."""
        (tmp_path / JPG_BARKS_PANELS_ZIP).write_bytes(b"not a zip")
        png = tmp_path / "png"
        png.mkdir()

        variants = core.build_reader_file_paths(
            _cfg_info(tmp_path, **{PNG_BARKS_PANELS_DIR: png}), tmp_path
        )

        assert [v._barks_panels_source for v in variants] == [png]


# ---------------------------------------------------------------------------
# Phases 4 and 5
# ---------------------------------------------------------------------------


class TestDocumentPhases:
    """The introduction (4) and the appendices (5): a folder of pages, and the articles."""

    @staticmethod
    def _sys_paths(doc_dir: Path) -> MagicMock:
        sys_paths = MagicMock()
        sys_paths.get_intro_doc_dir.return_value = doc_dir
        sys_paths.get_censorship_fixes_doc_dir.return_value = doc_dir
        return sys_paths

    @pytest.mark.parametrize(
        ("run", "label"),
        [
            (core.phase4_introduction, "intro_doc_dir"),
            (core.phase5_appendices, "censorship_fixes_doc_dir"),
        ],
    )
    def test_the_pages_folder_must_be_there_and_hold_a_page(
        self, tmp_path: Path, run: object, label: str
    ) -> None:
        assert callable(run)
        doc_dir = tmp_path / "doc"

        collector = core.ErrorCollector()
        run(collector, self._sys_paths(doc_dir), [])
        assert collector.phases[0].errors == [f"{label}: missing directory {doc_dir}"]

        _write(doc_dir / "notes.txt")
        _write(doc_dir / "cover.png")  # an image, but not named as a page
        collector = core.ErrorCollector()
        run(collector, self._sys_paths(doc_dir), [])
        assert collector.phases[0].errors == [f"{label}: no page-NNN.(jpg|png) files in {doc_dir}"]

        _write(doc_dir / "page-001.jpg")
        collector = core.ErrorCollector()
        run(collector, self._sys_paths(doc_dir), [])
        assert collector.phases[0].errors == []

    def test_an_article_needs_no_inset_but_one_it_has_must_load(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "doc"
        _write(doc_dir / "page-001.jpg")
        variant = _png_variant(tmp_path / "png")
        collector = core.ErrorCollector()
        core.phase4_introduction(collector, self._sys_paths(doc_dir), [variant])
        assert collector.phases[0].errors == []

        intro = ENUM_TO_STR_TITLE[core._INTRO_ARTICLE]
        inset = core.get_filename_from_title(core._INTRO_ARTICLE, ".png")
        _write(tmp_path / "png" / "Insets" / inset, b"not a png")
        collector = core.ErrorCollector()
        core.phase4_introduction(collector, self._sys_paths(doc_dir), [variant])

        assert _kinds(collector.phases[0]) == ["kind=inset_load_failed"]
        assert collector.phases[0].errors[0].startswith(f"Title:{intro} ")

    def test_each_appendix_article_is_checked_in_each_variant(self, tmp_path: Path) -> None:
        doc_dir = tmp_path / "doc"
        _write(doc_dir / "page-001.png")
        variants = [_png_variant(tmp_path / "a"), _png_variant(tmp_path / "b")]
        collector = core.ErrorCollector()

        core.phase5_appendices(collector, self._sys_paths(doc_dir), variants)

        phase = _only_phase(collector)
        assert phase.errors == []
        # The folder and its pages, then every article in both variants.
        assert phase.items_checked == 2 + len(core._APPENDIX_ARTICLES) * len(variants)


# ---------------------------------------------------------------------------
# Phase 6
# ---------------------------------------------------------------------------


def _volume_zip(path: Path, pages: list[str]) -> Path:
    with zipfile.ZipFile(path, "w") as volume:
        for page in pages:
            volume.writestr(f"images/{page}", _png_bytes())
    return path


class TestPhase6Fantagraphics:
    """One volume in the list, so a library of one file is a whole library."""

    @pytest.fixture
    def library(self, tmp_path: Path) -> Iterator[SimpleNamespace]:
        archive_root = tmp_path / "library"
        override_root = tmp_path / "overrides"
        archive_root.mkdir()
        override_root.mkdir()
        sys_paths = MagicMock()
        sys_paths.get_barks_reader_fantagraphics_overrides_root_dir.return_value = override_root
        with (
            patch.object(core, "FIRST_VOLUME_NUMBER", VOLUME),
            patch.object(core, "LAST_VOLUME_NUMBER", VOLUME),
        ):
            yield SimpleNamespace(
                archive_root=archive_root,
                override_root=override_root,
                sys_paths=sys_paths,
                cfg_info=_cfg_info(tmp_path, **{FANTA_DIR: archive_root}),
            )

    @staticmethod
    def _run(library: SimpleNamespace) -> tuple[core.PhaseResult, core.FantaState]:
        collector = core.ErrorCollector()
        state = core.phase6_fantagraphics(collector, library.cfg_info, library.sys_paths)
        return _only_phase(collector), state

    def test_a_sound_volume_is_loaded(self, library: SimpleNamespace) -> None:
        volume = _volume_zip(library.archive_root / "02-vol.cbz", ["001.png", "002.png"])

        phase, state = self._run(library)

        assert phase.errors == []
        assert phase.summary_extra == "(1 archives loaded, 0 volumes flagged)"
        archive = state.archives[VOLUME]
        assert (archive.archive_filename, archive.first_page, archive.last_page) == (volume, 1, 2)
        assert not archive.is_missing

    def test_a_library_that_is_not_there_stops_the_phase(self, library: SimpleNamespace) -> None:
        library.archive_root.rmdir()
        with patch.object(core, "find_fanta_volumes_dirpath", return_value=None):
            phase, state = self._run(library)

        assert phase.errors == ["archive_root: missing None"]
        assert state.archives == {}

    def test_an_overrides_folder_that_is_not_there_stops_the_phase(
        self, library: SimpleNamespace
    ) -> None:
        library.override_root.rmdir()

        phase, state = self._run(library)

        assert phase.errors == [f"override_root: missing {library.override_root}"]
        assert state.archives == {}

    def test_a_library_that_cannot_be_listed_stops_the_phase(
        self, library: SimpleNamespace
    ) -> None:
        with patch.object(
            core.FantagraphicsVolumeArchives,
            "get_all_volume_filenames",
            side_effect=PermissionError("denied"),
        ):
            phase, _state = self._run(library)

        assert phase.errors == ["could not enumerate volume archives: denied"]

    def test_a_volume_with_no_file_is_flagged(self, library: SimpleNamespace) -> None:
        phase, state = self._run(library)

        assert phase.errors == [f"Volume {VOLUME}: missing archive file"]
        assert state.error_volumes == {VOLUME}
        assert phase.summary_extra == "(0 archives loaded, 1 volumes flagged)"

    def test_a_volume_with_two_files_is_flagged(self, library: SimpleNamespace) -> None:
        _volume_zip(library.archive_root / "02-vol.cbz", ["001.png", "002.png"])
        _volume_zip(library.archive_root / "02-copy.cbz", ["001.png", "002.png"])

        phase, state = self._run(library)

        assert phase.errors == [f"Volume {VOLUME}: duplicate archive files"]
        assert state.error_volumes == {VOLUME}

    @pytest.mark.parametrize(
        ("pages", "error"),
        [
            ([], "EmptyArchiveError"),
            (["001.png", "003.png"], "PageNumError"),
            (["001.png", "002.jpg"], "RuntimeError"),
        ],
    )
    def test_a_volume_the_app_could_not_load_is_flagged_and_left_out(
        self, library: SimpleNamespace, pages: list[str], error: str
    ) -> None:
        _volume_zip(library.archive_root / "02-vol.cbz", pages)

        phase, state = self._run(library)

        assert len(phase.errors) == 1
        assert phase.errors[0].startswith(f"Volume {VOLUME}: {error}: ")
        assert state.error_volumes == {VOLUME}
        assert state.archives == {}

    def test_a_volume_that_is_no_zip_is_flagged(self, library: SimpleNamespace) -> None:
        """A truncated copy: it stopped the whole run with a traceback until it was caught."""
        (library.archive_root / "02-vol.cbz").write_bytes(b"not a zip")

        phase, state = self._run(library)

        assert phase.errors == [f"Volume {VOLUME}: BadZipFile: File is not a zip file"]
        assert state.error_volumes == {VOLUME}
        assert state.archives == {}

    def test_a_stray_in_the_overrides_folder_is_an_error_beside_a_sound_volume(
        self, library: SimpleNamespace
    ) -> None:
        _volume_zip(library.archive_root / "02-vol.cbz", ["001.png", "002.png"])
        (library.override_root / "notes.txt").touch()

        phase, state = self._run(library)

        assert phase.errors == [
            f'override directory holds an unexpected entry: "{library.override_root / "notes.txt"}"'
        ]
        assert VOLUME in state.archives

    def test_overrides_that_cannot_be_listed_are_one_error(self, tmp_path: Path) -> None:
        archives = MagicMock()
        archives.scan_override_root.side_effect = PermissionError("denied")
        phase = core.PhaseResult(name="test")

        assert core._scan_override_archives(phase, archives) == {}

        assert phase.errors == ["could not enumerate override archives: denied"]
        assert not list(tmp_path.iterdir())


class TestResolveArchiveRoot:
    @staticmethod
    def _config(**settings: str) -> ConfigParser:
        config = ConfigParser()
        config[BARKS_READER_SECTION] = settings
        return config

    def test_the_configured_library_is_used_when_it_is_there(self, tmp_path: Path) -> None:
        config = self._config(**{FANTA_DIR: str(tmp_path)})
        with patch.object(core, "find_fanta_volumes_dirpath") as search:
            assert core._resolve_archive_root(MagicMock(), config) == tmp_path

        search.assert_not_called()

    @pytest.mark.parametrize("setting", [{}, {FANTA_DIR: "/no/such/library"}])
    def test_else_the_app_s_own_search_is_used(
        self, tmp_path: Path, setting: dict[str, str]
    ) -> None:
        cfg_info = MagicMock()
        with patch.object(core, "find_fanta_volumes_dirpath", return_value=tmp_path) as search:
            assert core._resolve_archive_root(cfg_info, self._config(**setting)) == tmp_path

        search.assert_called_once_with(cfg_info, "Fantagraphics-original")

    def test_a_search_that_finds_no_folder_is_no_library(self, tmp_path: Path) -> None:
        with patch.object(core, "find_fanta_volumes_dirpath", return_value=tmp_path / "gone"):
            assert core._resolve_archive_root(MagicMock(), self._config()) is None


# ---------------------------------------------------------------------------
# Phase 7
# ---------------------------------------------------------------------------


# Every title with a comic of its own: one-pagers and covers are pages of a collection.
_COMICS = tuple(t for t in ALL_FANTA_COMIC_BOOK_INFO if t not in ONE_PAGERS and t not in COVERS_SET)


class TestPhase7PrebuiltCbzs:
    @staticmethod
    def _run(cfg_info: MagicMock) -> core.PhaseResult:
        collector = core.ErrorCollector()
        core.phase7_prebuilt_cbzs(collector, cfg_info)
        return _only_phase(collector)

    def test_a_folder_that_is_not_there_is_one_error(self, tmp_path: Path) -> None:
        gone = tmp_path / "gone"

        phase = self._run(_cfg_info(tmp_path, **{PREBUILT_COMICS_DIR: gone}))

        assert phase.errors == [f"Prebuilt: missing_dir {gone}"]

    def test_with_no_setting_the_app_s_default_folder_is_checked(self, tmp_path: Path) -> None:
        with patch.object(
            core.ReaderFilePaths,
            "get_default_prebuilt_comic_zips_dir",
            return_value=tmp_path / "default",
        ):
            phase = self._run(_cfg_info(tmp_path))

        assert phase.errors == [f"Prebuilt: missing_dir {tmp_path / 'default'}"]

    def test_every_comic_s_file_is_asked_for_and_no_one_pager_s_or_cover_s(
        self, tmp_path: Path
    ) -> None:
        prebuilt = tmp_path / "prebuilt"
        prebuilt.mkdir()

        phase = self._run(_cfg_info(tmp_path, **{PREBUILT_COMICS_DIR: prebuilt}))

        assert phase.items_checked == len(_COMICS) == len(phase.errors)
        assert all(e.startswith(f"Prebuilt: missing {prebuilt}") for e in phase.errors)
        assert all(e.endswith(".cbz") for e in phase.errors)
        assert sum(ANDES in e for e in phase.errors) == 1

    def test_a_file_that_is_there_is_not_reported(self, tmp_path: Path) -> None:
        prebuilt = tmp_path / "prebuilt"
        prebuilt.mkdir()
        cfg_info = _cfg_info(tmp_path, **{PREBUILT_COMICS_DIR: prebuilt})
        (andes_file,) = [
            Path(e.removeprefix("Prebuilt: missing "))
            for e in self._run(cfg_info).errors
            if ANDES in e
        ]
        andes_file.touch()

        phase = self._run(cfg_info)

        assert len(phase.errors) == len(_COMICS) - 1
        assert not any(ANDES in e for e in phase.errors)


# ---------------------------------------------------------------------------
# Phase 8a
# ---------------------------------------------------------------------------


def _sound_archive() -> MagicMock:
    return MagicMock(is_missing=False)


class TestPhase8aPerTitlePanelFiles:
    @staticmethod
    def _run(
        variants: list[ReaderFilePaths],
        state: core.FantaState,
        known_missing: frozenset[str] = frozenset(),
    ) -> core.PhaseResult:
        collector = core.ErrorCollector()
        core.phase8a_per_title_panel_files(collector, variants, state, [ANDES], known_missing)
        return _only_phase(collector)

    @staticmethod
    def _state() -> core.FantaState:
        return core.FantaState(archives={ANDES_VOLUME: _sound_archive()})

    @staticmethod
    def _with_andes_files(root: Path) -> ReaderFilePaths:
        """Make a panels folder holding what Lost in the Andes must have: inset and a panel."""
        variant = _png_variant(root)
        inset = core.get_filename_from_title(Titles.LOST_IN_THE_ANDES, ".png")
        _write(root / "Insets" / inset, _png_bytes())
        _write(root / "Favourites" / ANDES / "1.png", _png_bytes())
        return variant

    def test_a_title_with_its_files_and_its_volume_passes(self, tmp_path: Path) -> None:
        phase = self._run([self._with_andes_files(tmp_path)], self._state())

        assert phase.errors == []
        assert phase.summary_extra == (
            "(0 titles with file errors, 0 broken volume bindings, 0 JPG/PNG count mismatches,"
            " 2 files test-loaded, 0 insets known missing)"
        )

    def test_a_title_whose_volume_was_not_loaded_is_an_error(self, tmp_path: Path) -> None:
        phase = self._run([self._with_andes_files(tmp_path)], core.FantaState())

        assert phase.errors == [f"Title:{ANDES} kind=missing_volume volume={ANDES_VOLUME}"]
        assert "1 broken volume bindings" in phase.summary_extra

    def test_a_title_whose_volume_is_marked_missing_is_an_error(self, tmp_path: Path) -> None:
        state = core.FantaState(archives={ANDES_VOLUME: MagicMock(is_missing=True)})

        phase = self._run([self._with_andes_files(tmp_path)], state)

        assert _kinds(phase) == ["kind=missing_volume"]

    def test_a_title_whose_volume_phase_6_flagged_is_an_error(self, tmp_path: Path) -> None:
        state = self._state()
        state.error_volumes.add(ANDES_VOLUME)

        phase = self._run([self._with_andes_files(tmp_path)], state)

        assert phase.errors == [f"Title:{ANDES} kind=volume_invalid volume={ANDES_VOLUME}"]

    def test_a_title_s_file_errors_are_counted_once_per_title(self, tmp_path: Path) -> None:
        phase = self._run([_png_variant(tmp_path)], self._state())

        assert _kinds(phase) == ["kind=missing_inset", "kind=no_panel_files"]
        assert "(1 titles with file errors, 0 broken volume bindings" in phase.summary_extra

    def test_a_file_that_is_no_image_and_one_that_will_not_load_are_errors(
        self, tmp_path: Path
    ) -> None:
        variant = self._with_andes_files(tmp_path)
        _write(tmp_path / "Favourites" / ANDES / "notes.txt")
        _write(tmp_path / "Splash" / ANDES / EDITED_SUBDIR / "2.png", b"not a png")

        phase = self._run([variant], self._state())

        assert sorted(_kinds(phase)) == [
            "kind=edited_splash_load_failed",
            "kind=favourite_non_image_file",
        ]

    def test_the_two_panel_sources_must_hold_the_same_number_of_files(self, tmp_path: Path) -> None:
        first = self._with_andes_files(tmp_path / "a")
        second = self._with_andes_files(tmp_path / "b")
        _write(tmp_path / "b" / "Closeups" / ANDES / "9.png", _png_bytes())

        phase = self._run([first, second], self._state())

        assert phase.errors == [f"Title:{ANDES} kind=file_count_mismatch jpg_total=2 png_total=3"]
        assert "1 JPG/PNG count mismatches, 2+3 files test-loaded" in phase.summary_extra

    def test_a_known_missing_entry_that_is_no_title_is_an_error(self, tmp_path: Path) -> None:
        phase = self._run(
            [self._with_andes_files(tmp_path)], self._state(), frozenset({"No Such Story"})
        )

        assert phase.errors == ["KnownMissingInsets: kind=unknown_title title='No Such Story'"]

    def test_the_audit_is_handed_what_the_sweep_visited(self, tmp_path: Path) -> None:
        collector = core.ErrorCollector()

        (ctx,) = core.phase8a_per_title_panel_files(
            collector, [self._with_andes_files(tmp_path)], self._state(), [ANDES]
        )

        inset = core.get_filename_from_title(Titles.LOST_IN_THE_ANDES, ".png")
        assert ctx.visited == {f"Insets/{inset}", f"Favourites/{ANDES}/1.png"}
        assert not ctx.is_zip


# ---------------------------------------------------------------------------
# Phase 8b
# ---------------------------------------------------------------------------


class TestPhase8bAuditPanelFiles:
    @staticmethod
    def _run(
        variant: ReaderFilePaths, visited: set[str], *, title_filter_active: bool = False
    ) -> core.PhaseResult:
        ctx = core._build_audit_ctx(variant)
        ctx.visited.update(visited)
        collector = core.ErrorCollector()
        core.phase8b_audit_panel_files(
            collector, [variant], [ctx], title_filter_active=title_filter_active
        )
        return _only_phase(collector)

    def test_a_folder_of_visited_files_passes(self, tmp_path: Path) -> None:
        variant = _png_variant(tmp_path)
        _write(tmp_path / "Favourites" / ANDES / "1.png")

        phase = self._run(variant, {f"Favourites/{ANDES}/1.png"})

        assert phase.errors == []
        assert phase.items_checked == 1
        assert phase.summary_extra == "(0 non-image files, 0 unvisited image files)"

    def test_an_image_the_sweep_never_saw_is_an_error(self, tmp_path: Path) -> None:
        """A title folder with a typo in its name, or a file in the wrong category."""
        variant = _png_variant(tmp_path)
        stray = _write(tmp_path / "Favourites" / "Lost in the Andes" / "1.png")

        phase = self._run(variant, set())

        assert phase.errors == [f"Source:{tmp_path.name} kind=unvisited_image_file path={stray}"]
        assert phase.summary_extra == "(0 non-image files, 1 unvisited image files)"

    def test_a_file_that_is_no_image_is_an_error_unless_the_sweep_reported_it(
        self, tmp_path: Path
    ) -> None:
        variant = _png_variant(tmp_path)
        stray = _write(tmp_path / "Nontitles" / ".DS_Store")
        _write(tmp_path / "Favourites" / ANDES / "notes.txt")

        phase = self._run(variant, {f"Favourites/{ANDES}/notes.txt"})

        assert phase.errors == [f"Source:{tmp_path.name} kind=non_image_file path={stray}"]

    @pytest.mark.parametrize(
        "path",
        [
            "Nontitles/anything.png",
            "Insets/Some Title-no-overrides.png",
            "Favourites/Oil Paintings/sub/1.png",
        ],
    )
    def test_images_the_sweep_does_not_key_by_title_are_left(
        self, tmp_path: Path, path: str
    ) -> None:
        variant = _png_variant(tmp_path)
        _write(tmp_path / path)

        assert self._run(variant, set()).errors == []

    def test_with_a_title_filter_only_non_images_are_judged(self, tmp_path: Path) -> None:
        variant = _png_variant(tmp_path)
        _write(tmp_path / "Favourites" / "Another Story" / "1.png")
        stray = _write(tmp_path / "Covers" / "index.json")

        phase = self._run(variant, set(), title_filter_active=True)

        assert phase.errors == [f"Source:{tmp_path.name} kind=non_image_file path={stray}"]
        assert "unvisited-image check skipped: title filter active" in phase.summary_extra

    def test_a_zip_s_members_are_walked_and_its_folders_are_not(self, tmp_path: Path) -> None:
        panels = _panels_zip(
            tmp_path / JPG_BARKS_PANELS_ZIP,
            {"Favourites/Typo/1.jpg": b"", f"Favourites/{ANDES}/1.jpg": b"", "Covers/x.txt": b""},
        )
        variant = ReaderFilePaths()
        variant.set_barks_panels_source(panels, BarksPanelsExtType.JPG)

        phase = self._run(variant, {f"Favourites/{ANDES}/1.jpg"})

        assert sorted(_kinds(phase)) == ["kind=non_image_file", "kind=unvisited_image_file"]
        assert phase.items_checked == 3  # noqa: PLR2004 - the members; no category folder
        assert all(e.startswith(f"Source:{JPG_BARKS_PANELS_ZIP} ") for e in phase.errors)


# ---------------------------------------------------------------------------
# Phase 9
# ---------------------------------------------------------------------------


def _pages(*names: str, page_type: PageType = PageType.BODY) -> SrceAndDestPages:
    pages = [CleanPage(name, page_type) for name in names]
    return SrceAndDestPages(srce_pages=pages, dest_pages=pages)


class TestCheckOneTitleLoad:
    """One title's pages, decoded from a real volume of three pages."""

    @pytest.fixture
    def archive(self, tmp_path: Path) -> core.FantagraphicsArchive:
        volume = _volume_zip(tmp_path / "02-vol.cbz", ["001.png", "002.png", "003.png"])
        archives = core.FantagraphicsVolumeArchives(tmp_path, tmp_path / "overrides", [VOLUME])
        return core._process_one_archive(archives, VOLUME, volume, None)

    @staticmethod
    def _check(
        archive: core.FantagraphicsArchive, pages: SrceAndDestPages | Exception
    ) -> tuple[core.PhaseResult, core._Phase9Counts]:
        phase = core.PhaseResult(name="test")
        counts = core._Phase9Counts()
        with patch.object(core, "get_srce_and_dest_pages_in_order") as in_order:
            if isinstance(pages, Exception):
                in_order.side_effect = pages
            else:
                in_order.return_value = pages
            core.check_one_title_load(phase, counts, ANDES, MagicMock(), archive)
        return phase, counts

    def test_pages_that_decode_pass(self, archive: core.FantagraphicsArchive) -> None:
        phase, counts = self._check(archive, _pages("001.png", "003.png"))

        assert phase.errors == []
        assert phase.items_checked == 2  # noqa: PLR2004
        assert counts == core._Phase9Counts()

    def test_a_page_the_volume_does_not_hold_is_an_error(
        self, archive: core.FantagraphicsArchive
    ) -> None:
        phase, counts = self._check(archive, _pages("001.png", "004.png"))

        assert phase.errors == [
            f"Title:{ANDES} kind=page_load_failed page=004 reason=page_not_in_volume"
        ]
        assert counts.page_load_failed == 1

    def test_a_page_that_will_not_decode_is_an_error(
        self, archive: core.FantagraphicsArchive
    ) -> None:
        with zipfile.ZipFile(archive.archive_filename, "w") as volume:
            volume.writestr("images/001.png", b"not a png")

        phase, counts = self._check(archive, _pages("001.png"))

        assert len(phase.errors) == 1
        assert phase.errors[0].startswith(
            f"Title:{ANDES} kind=page_load_failed page=001 source=archive reason="
        )
        assert counts.page_load_failed == 1

    def test_a_page_that_will_not_decrypt_is_counted_apart(
        self, archive: core.FantagraphicsArchive
    ) -> None:
        with patch.object(core, "reader_load_pil", side_effect=DecryptionError("bad key")):
            phase, counts = self._check(archive, _pages("001.png"))

        assert phase.errors == [
            f"Title:{ANDES} kind=decryption_failed page=001 source=archive reason=bad key"
        ]
        assert (counts.decryption_failed, counts.page_load_failed) == (1, 0)

    def test_title_and_blank_pages_have_no_scan_to_decode(
        self, archive: core.FantagraphicsArchive
    ) -> None:
        placeholders = SrceAndDestPages(
            srce_pages=[
                CleanPage(f"{EMPTY_PAGE_KEY}.png", PageType.TITLE),
                CleanPage(f"{EMPTY_PAGE_KEY}.png", PageType.BLANK_PAGE),
            ],
            dest_pages=[],
        )

        phase, _counts = self._check(archive, placeholders)

        assert phase.errors == []
        assert phase.items_checked == 0

    def test_a_volume_that_cannot_be_opened_fails_every_page_at_once(
        self, archive: core.FantagraphicsArchive
    ) -> None:
        archive.archive_filename.write_bytes(b"not a zip")

        phase, counts = self._check(archive, _pages("001.png", "002.png"))

        assert len(phase.errors) == 1
        assert phase.errors[0].startswith(
            f"Title:{ANDES} kind=page_load_failed page=* reason=cannot_open_volume_cbz: "
        )
        assert counts.page_load_failed == 2  # noqa: PLR2004

    def test_pages_that_cannot_be_listed_are_a_failed_load(
        self, archive: core.FantagraphicsArchive
    ) -> None:
        phase, counts = self._check(archive, KeyError("no ini"))

        assert phase.errors == [
            f"Title:{ANDES} kind=comic_book_load_failed reason=page_enum_failed: KeyError: 'no ini'"
        ]
        assert counts.load_failed == 1


class TestOverridePages:
    """A volume with an override archive: its pages come from there, encrypted."""

    @pytest.fixture
    def archive(self, tmp_path: Path) -> core.FantagraphicsArchive:
        volume = _volume_zip(tmp_path / "02-vol.cbz", ["001.png", "002.png"])
        overrides = tmp_path / "overrides"
        overrides.mkdir()
        with zipfile.ZipFile(overrides / "02-vol.cbz", "w") as override:
            override.writestr("002.png", _png_bytes())
        archives = core.FantagraphicsVolumeArchives(tmp_path, overrides, [VOLUME])
        return core._process_one_archive(archives, VOLUME, volume, overrides / "02-vol.cbz")

    def test_an_overridden_page_is_read_from_the_override_archive_as_encrypted(
        self, archive: core.FantagraphicsArchive
    ) -> None:
        assert archive.has_overrides()
        phase = core.PhaseResult(name="test")
        with (
            patch.object(core, "get_srce_and_dest_pages_in_order", return_value=_pages("002.png")),
            patch.object(core, "reader_load_pil") as load,
        ):
            core.check_one_title_load(phase, core._Phase9Counts(), ANDES, MagicMock(), archive)

        assert phase.errors == []
        member = load.call_args.args[0]
        assert Path(member.root.filename) == archive.override_archive_filename
        assert load.call_args.kwargs == {"encrypted_zip": True, "use_ext_hint": True}

    def test_an_override_archive_that_cannot_be_opened_fails_the_pages_that_need_it(
        self, archive: core.FantagraphicsArchive
    ) -> None:
        assert archive.override_archive_filename is not None
        archive.override_archive_filename.write_bytes(b"not a zip")
        phase = core.PhaseResult(name="test")
        counts = core._Phase9Counts()
        with patch.object(
            core, "get_srce_and_dest_pages_in_order", return_value=_pages("001.png", "002.png")
        ):
            core.check_one_title_load(phase, counts, ANDES, MagicMock(), archive)

        assert len(phase.errors) == 2  # noqa: PLR2004
        assert phase.errors[0].startswith(
            f"Title:{ANDES} kind=page_load_failed page=* reason=cannot_open_override_cbz: "
        )
        assert phase.errors[1] == (
            f"Title:{ANDES} kind=page_load_failed page=002"
            " source=override reason=override_archive_not_open"
        )
        assert counts.page_load_failed == 1  # page 001 still came from the volume


class TestPhase9PerTitleLoad:
    @staticmethod
    def _run(state: core.FantaState, db: MagicMock | Exception) -> core.PhaseResult:
        collector = core.ErrorCollector()
        with patch.object(core, "ComicsDatabase") as database:
            if isinstance(db, Exception):
                database.side_effect = db
            else:
                database.return_value = db
            core.phase9_per_title_load(collector, state, [ANDES])
        return _only_phase(collector)

    @staticmethod
    def _state() -> core.FantaState:
        return core.FantaState(archives={ANDES_VOLUME: _sound_archive()})

    def test_with_no_volumes_from_phase_6_nothing_is_loaded(self) -> None:
        phase = self._run(core.FantaState(), MagicMock())

        assert len(phase.errors) == 1
        assert phase.errors[0].startswith("Phase 6 produced no archives")

    def test_a_database_that_cannot_be_built_is_one_error(self) -> None:
        phase = self._run(self._state(), RuntimeError("no ini files"))

        assert phase.errors == ["could not construct ComicsDatabase: no ini files"]

    def test_a_title_the_database_cannot_load_is_an_error(self) -> None:
        db = MagicMock()
        db.get_comic_book.side_effect = FileNotFoundError("no ini")

        phase = self._run(self._state(), db)

        assert phase.errors == [
            f"Title:{ANDES} kind=comic_book_load_failed reason=FileNotFoundError: no ini"
        ]
        assert phase.summary_extra == "(1 load-failed, 0 page-load-failed, 0 decryption-failed)"

    def test_a_title_whose_volume_is_missing_is_left_to_phase_8(self) -> None:
        state = core.FantaState(archives={ANDES_VOLUME + 1: _sound_archive()})
        db = MagicMock()

        phase = self._run(state, db)

        assert phase.errors == []
        db.get_comic_book.assert_not_called()

    def test_a_title_that_loads_has_its_pages_checked_in_its_own_volume(self) -> None:
        state = self._state()
        db = MagicMock()
        with patch.object(core, "check_one_title_load") as check:
            phase = self._run(state, db)

        assert phase.errors == []
        (checked,) = check.call_args_list
        assert checked.args[2:] == (
            ANDES,
            db.get_comic_book.return_value,
            state.archives[ANDES_VOLUME],
        )
