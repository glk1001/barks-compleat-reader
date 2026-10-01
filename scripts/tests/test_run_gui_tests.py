"""Tests for the Windows GUI test runner's coverage merge."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import run_gui_tests

if TYPE_CHECKING:
    from pathlib import Path


class TestMergeCoverage:
    """Each boot's data file is merged into .coverage.gui, as run_gui_tests.sh does."""

    def _merge(self, env: dict[str, str]) -> list[list[str]]:
        with patch.object(run_gui_tests.subprocess, "run") as run:
            run.return_value.returncode = 0
            run_gui_tests.merge_coverage(env)
        return [c.args[0] for c in run.call_args_list]

    def test_the_boots_are_merged(self, tmp_path: Path) -> None:
        (tmp_path / ".coverage.gui.host.123.456").write_bytes(b"")
        (cmd,) = self._merge({"BARKS_PROBE_COVERAGE": str(tmp_path)})
        assert cmd[1:5] == ["-m", "coverage", "combine", "--append"]
        assert f"--data-file={tmp_path / '.coverage.gui'}" in cmd
        assert cmd[-1] == str(tmp_path)

    def test_nothing_without_the_folder(self) -> None:
        assert self._merge({}) == []

    def test_nothing_when_no_boot_measured_any(self, tmp_path: Path) -> None:
        assert self._merge({"BARKS_PROBE_COVERAGE": str(tmp_path)}) == []

    def test_nothing_for_a_built_executable(self, tmp_path: Path) -> None:
        (tmp_path / ".coverage.gui.host.123.456").write_bytes(b"")
        env = {"BARKS_PROBE_COVERAGE": str(tmp_path), "BARKS_PROBE_APP": "reader.exe"}
        assert self._merge(env) == []
