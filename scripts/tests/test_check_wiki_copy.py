"""Tests for the shipped wiki copy's staleness comparison."""

from __future__ import annotations

from typing import TYPE_CHECKING

from check_wiki_copy import differences, report_staleness

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


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
