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
        tmp_path: Path,
        *args: str,
        stale: bool = False,
        exported: bool = True,
        broken: bool = False,
        history_stale: bool = False,
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
            patch.object(check_wiki_copy, "history_is_stale", return_value=history_stale),
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

    @pytest.mark.parametrize("args", [(), ("--strict",)])
    def test_a_stale_illustrated_history_fails_either_way(
        self, tmp_path: Path, args: tuple[str, ...]
    ) -> None:
        assert self._main(tmp_path, *args, history_stale=True) == 1

    def test_the_history_is_looked_for_in_the_reader_s_documents(self, tmp_path: Path) -> None:
        with (
            patch.object(
                check_wiki_copy, "ErrorCollector", return_value=SimpleNamespace(any_failed=False)
            ),
            patch.object(
                check_wiki_copy,
                "phase1_config",
                return_value=SimpleNamespace(app_data_dir=tmp_path),
            ),
            patch.object(check_wiki_copy, "phase11_wiki"),
            patch.object(check_wiki_copy, "fresh_export", return_value=False),
            patch.object(check_wiki_copy, "history_is_stale", return_value=False) as history,
        ):
            check_wiki_copy.main([])

        (copy,) = history.call_args.args
        assert (
            copy.relative_to(tmp_path).as_posix().endswith("Various/documents/illustrated-history")
        )

    def test_without_a_usable_configuration_it_fails_before_looking(self) -> None:
        with (
            patch.object(check_wiki_copy, "phase1_config", return_value=None),
            patch.object(check_wiki_copy, "fresh_export") as export,
        ):
            assert check_wiki_copy.main([]) == 1

        export.assert_not_called()

    def test_strict_fails_a_stale_copy_with_its_own_status(self, tmp_path: Path) -> None:
        assert self._main(tmp_path, "--strict", stale=True) == check_wiki_copy.STALE_EXIT


class TestHistoryIsStale:
    CHAPTERS = {  # noqa: RUF012
        "01-raw-talent/page-1.jpg": b"one",
        "01-raw-talent/chapter.json": "{}",
        "00-cover/page-1.jpg": b"cover",
    }

    def test_a_copy_of_all_but_the_pdfs_is_current(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = write_tree(tmp_path / "source", {**self.CHAPTERS, "01-raw-talent.pdf": b"pdf"})
        copy = write_tree(tmp_path / "copy", self.CHAPTERS)

        assert check_wiki_copy.history_is_stale(copy, source) is False
        assert "illustrated history: current" in capsys.readouterr().out

    def test_a_chapter_made_again_and_not_copied_is_stale(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = write_tree(
            tmp_path / "source",
            {**self.CHAPTERS, "01-raw-talent/page-1.jpg": b"again", "06-new/page-1.jpg": b"new"},
        )
        copy = write_tree(tmp_path / "copy", {**self.CHAPTERS, "old/page-1.jpg": b"old"})

        assert check_wiki_copy.history_is_stale(copy, source) is True
        out = capsys.readouterr().out
        assert "STALE - 1 files changed, 1 missing, 1 no longer there" in out
        assert "changed  01-raw-talent/page-1.jpg" in out
        assert "missing  06-new/page-1.jpg" in out
        assert "extra    old/page-1.jpg" in out

    def test_no_copy_at_all_is_stale(self, tmp_path: Path) -> None:
        source = write_tree(tmp_path / "source", self.CHAPTERS)

        assert check_wiki_copy.history_is_stale(tmp_path / "gone", source) is True

    def test_a_machine_without_the_source_folder_does_not_check(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        copy = write_tree(tmp_path / "copy", self.CHAPTERS)

        assert check_wiki_copy.history_is_stale(copy, tmp_path / "gone") is False
        assert "not checked" in capsys.readouterr().out

    def test_a_long_list_is_cut_to_a_few_and_a_count(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        pages = {f"01/page-{number}.jpg": b"x" for number in range(14)}
        source = write_tree(tmp_path / "source", pages)

        assert check_wiki_copy.history_is_stale(tmp_path / "copy", source) is True
        assert "missing  ... and 4 more" in capsys.readouterr().out


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
