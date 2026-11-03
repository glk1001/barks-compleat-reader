"""Tests for the shipped wiki copy's staleness comparison."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

import check_wiki_copy
import pytest
from check_wiki_copy import differences, report_staleness

if TYPE_CHECKING:
    from pathlib import Path


def _bundle(root: Path, pages: dict[str, str]) -> Path:
    for rel, text in pages.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    return root


class TestDifferences:
    def test_missing_extra_and_changed_pages_are_told_apart(self, tmp_path: Path) -> None:
        copy = _bundle(
            tmp_path / "copy",
            {"index.md": "x", "concept/stories/a.md": "old", "concept/stories/gone.md": "g"},
        )
        fresh = _bundle(
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
        copy, fresh = _bundle(tmp_path / "copy", pages), _bundle(tmp_path / "fresh", pages)
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
