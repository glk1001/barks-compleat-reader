"""Tests for the shipped wiki copy's staleness comparison."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import check_wiki_copy
import pytest
from check_wiki_copy import differences, report_staleness
from script_test_helpers import write_tree

if TYPE_CHECKING:
    from pathlib import Path


class TestDifferences:
    def test_missing_extra_and_changed_pages_are_told_apart(self, tmp_path: Path) -> None:
        copy = write_tree(
            tmp_path / "copy",
            {"index.md": "x", "concept/stories/a.md": "old", "concept/stories/gone.md": "g"},
        )
        fresh = write_tree(
            tmp_path / "fresh",
            {"index.md": "x", "concept/stories/a.md": "new", "concept/stories/b.md": "b"},
        )
        assert differences(copy, fresh) == {
            "missing": ["concept/stories/b.md"],
            "extra": ["concept/stories/gone.md"],
            "changed": ["concept/stories/a.md"],
        }

    def test_an_identical_copy_has_none(self, tmp_path: Path) -> None:
        pages = {"index.md": "x", "concept/stories/a.md": "same"}
        copy, fresh = write_tree(tmp_path / "copy", pages), write_tree(tmp_path / "fresh", pages)
        assert differences(copy, fresh) == {"missing": [], "extra": [], "changed": []}


class TestReportStaleness:
    def test_a_current_copy_says_so(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert report_staleness({"missing": [], "extra": [], "changed": []}) is False
        assert "current" in capsys.readouterr().out

    def test_a_long_list_is_cut_to_a_few_and_a_count(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        changed = [f"concept/stories/{n}.md" for n in range(25)]
        assert report_staleness({"missing": [], "extra": [], "changed": changed}) is True
        out = capsys.readouterr().out
        assert "STALE - 25 pages changed, 0 missing, 0 no longer exported" in out
        assert "concept/stories/9.md" in out
        assert "concept/stories/10.md" not in out
        assert "... and 15 more" in out


class TestExitStatus:
    """What the overnight stage (no flags) and the data pack build (--strict) are told."""

    @staticmethod
    def _main(
        tmp_path: Path, *args: str, stale: bool = False, exported: bool = True, broken: bool = False
    ) -> int:
        collector = SimpleNamespace(any_failed=broken)
        found = {"missing": [], "extra": [], "changed": ["a.md"] if stale else []}
        cfg = SimpleNamespace(app_data_dir=tmp_path)
        with (
            patch.object(check_wiki_copy, "ErrorCollector", return_value=collector),
            patch.object(check_wiki_copy, "phase1_config", return_value=cfg),
            patch.object(check_wiki_copy, "phase11_wiki"),
            patch.object(check_wiki_copy, "fresh_export", return_value=exported),
            patch.object(check_wiki_copy, "differences", return_value=found),
        ):
            return check_wiki_copy.main(list(args))

    def test_a_stale_copy_is_only_a_note_overnight(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert self._main(tmp_path, stale=True) == 0
        assert "a note only" in capsys.readouterr().out

    def test_a_broken_join_fails_overnight(self, tmp_path: Path) -> None:
        assert self._main(tmp_path, broken=True) == 1

    def test_no_export_is_no_failure_overnight(self, tmp_path: Path) -> None:
        assert self._main(tmp_path, exported=False) == 0

    @pytest.mark.parametrize(
        ("stale", "exported", "broken", "status"),
        [
            (False, True, False, 0),
            (True, True, False, check_wiki_copy.STALE_EXIT),
            (False, False, False, 1),
            (False, True, True, 1),
        ],
    )
    def test_strict_passes_only_a_copy_known_to_be_current(
        self, tmp_path: Path, *, stale: bool, exported: bool, broken: bool, status: int
    ) -> None:
        kwargs = {"stale": stale, "exported": exported, "broken": broken}
        assert self._main(tmp_path, "--strict", **kwargs) == status

    def test_without_a_usable_configuration_it_fails_before_looking(self) -> None:
        with (
            patch.object(check_wiki_copy, "phase1_config", return_value=None),
            patch.object(check_wiki_copy, "fresh_export") as export,
        ):
            assert check_wiki_copy.main([]) == 1

        export.assert_not_called()

    def test_strict_fails_a_stale_copy_with_its_own_status(self, tmp_path: Path) -> None:
        assert self._main(tmp_path, "--strict", stale=True) == check_wiki_copy.STALE_EXIT


class TestFreshExport:
    """The live bundle is exported by barks-wiki's own script, which this repo only runs."""

    @staticmethod
    def _export(
        tmp_path: Path, *, has_script: bool = True, status: int = 0
    ) -> tuple[bool, MagicMock]:
        wiki = tmp_path / "barks-wiki"
        script = wiki / "scripts" / "export_reader_wiki.py"
        if has_script:
            write_tree(wiki, {"scripts/export_reader_wiki.py": ""})
        done = MagicMock(returncode=status, stderr="no such bundle\n")
        with (
            patch.object(check_wiki_copy, "WIKI_REPO", wiki),
            patch.object(check_wiki_copy, "EXPORT_SCRIPT", script),
            patch.object(check_wiki_copy.subprocess, "run", return_value=done) as run,
        ):
            return check_wiki_copy.fresh_export(tmp_path / "out"), run

    def test_it_runs_the_wiki_s_export_into_the_folder_it_is_given(self, tmp_path: Path) -> None:
        exported, run = self._export(tmp_path)

        assert exported
        script = tmp_path / "barks-wiki" / "scripts" / "export_reader_wiki.py"
        assert run.call_args.args[0][1:] == ["-B", str(script), str(tmp_path / "out"), "--apply"]
        assert run.call_args.kwargs["cwd"] == tmp_path / "barks-wiki"

    def test_with_no_sibling_wiki_staleness_is_not_checked(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exported, run = self._export(tmp_path, has_script=False)

        assert not exported
        run.assert_not_called()
        assert "staleness not checked" in capsys.readouterr().out

    def test_an_export_that_fails_says_why(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exported, _ = self._export(tmp_path, status=1)

        assert not exported
        out = capsys.readouterr().out
        assert out == "wiki copy: the export failed - staleness not checked:\nno such bundle\n\n"
