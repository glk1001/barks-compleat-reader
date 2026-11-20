"""Tests for check-barks-panel-sources.py: every file in the PNG panel source is a title's.

The overnight ``panel-sources`` stage runs it on the main PC's own source; here it is
run on small trees.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_fantagraphics.barks_titles import STR_TITLE_TO_ENUM
from barks_fantagraphics.comic_book_info import FILENAME_TO_TITLE_SPECIAL_CASE_MAP
from barks_reader.core.reader_consts_and_types import NO_OVERRIDES_SUFFIX
from barks_reader.core.reader_file_paths import EDITED_SUBDIR, PanelDirNames
from loguru import logger
from script_test_helpers import write_tree

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

ANDES = "Lost in the Andes!"
COVERS = PanelDirNames.COVERS.value
INSETS = PanelDirNames.INSETS.value
NONTITLES = PanelDirNames.NONTITLES.value
SPLASH = PanelDirNames.SPLASH.value


def _load() -> ModuleType:
    """Import the script: its name has hyphens, so no import statement reaches it."""
    path = Path(__file__).resolve().parent.parent / "check-barks-panel-sources.py"
    spec = importlib.util.spec_from_file_location("check_barks_panel_sources", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load()


def test_the_title_used_here_is_one() -> None:
    assert ANDES in STR_TITLE_TO_ENUM


class TestFilePathsAreTitles:
    def test_a_title_s_folder_cover_and_inset_are_all_its_own(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        paths = {f"{SPLASH}/{ANDES}/001", f"{COVERS}/{ANDES}", f"{INSETS}/{ANDES}"}

        assert check.check_file_paths_are_titles(paths) == 0
        assert "No errors found." in capsys.readouterr().out

    def test_a_cover_marked_as_having_no_overrides_is_still_its_title_s(self) -> None:
        assert check.check_file_paths_are_titles({f"{COVERS}/{ANDES}{NO_OVERRIDES_SUFFIX}"}) == 0

    def test_a_title_filed_under_its_special_file_name_is_known(self) -> None:
        filename = next(iter(FILENAME_TO_TITLE_SPECIAL_CASE_MAP))
        assert filename not in STR_TITLE_TO_ENUM  # so only the map makes it a title

        assert check.check_file_paths_are_titles({f"{SPLASH}/{filename}/001"}) == 0

    def test_edited_copies_and_the_nontitles_folder_are_not_judged(self) -> None:
        paths = {f"{SPLASH}/Not A Title/{EDITED_SUBDIR}/001", f"{NONTITLES}/Carl Barks/portrait"}

        assert check.check_file_paths_are_titles(paths) == 0

    def test_each_file_that_is_no_title_s_is_named_and_counted(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        paths = {f"{SPLASH}/Lost in the Alps/001", f"{COVERS}/Not A Title", f"{COVERS}/{ANDES}"}

        assert check.check_file_paths_are_titles(paths) == 2  # noqa: PLR2004

        out = capsys.readouterr().out
        assert f'"{Path(SPLASH) / "Lost in the Alps" / "001"}" is not a title.' in out
        assert f'"{Path(COVERS) / "Not A Title"}" is not a title.' in out
        assert "There were 2 title errors." in out


class TestMain:
    @pytest.fixture
    def logged(self) -> Iterator[list[str]]:
        """Collect what the script logs; its change of the log's sinks is kept from the suite."""
        messages: list[str] = []
        sink = logger.add(messages.append, format="{message}")
        with patch.object(check.logger, "remove"), patch.object(check.logger, "add"):
            yield messages
        logger.remove(sink)

    @staticmethod
    def _main(source: Path) -> int:
        paths = MagicMock()
        paths.get_default_png_barks_panels_source.return_value = source
        with patch.object(check, "ReaderFilePaths", return_value=paths):
            return check.main()

    def test_a_source_of_titles_alone_passes(self, tmp_path: Path, logged: list[str]) -> None:
        write_tree(tmp_path, {f"{SPLASH}/{ANDES}/001.png": b"", f"{COVERS}/{ANDES}.png": b""})

        assert self._main(tmp_path) == 0
        assert any("Found 2 file paths in PNG directory." in line for line in logged)

    @pytest.mark.usefixtures("logged")
    def test_a_file_that_is_no_title_s_fails_it(self, tmp_path: Path) -> None:
        write_tree(tmp_path, {f"{COVERS}/Not A Title.png": b""})

        assert self._main(tmp_path) == 1

    def test_a_missing_source_fails_it_and_is_named(
        self, tmp_path: Path, logged: list[str]
    ) -> None:
        missing = tmp_path / "no-such-source"

        assert self._main(missing) == 1
        assert any(f"PNG source directory not found: {missing}." in line for line in logged)
