"""Tests for the overnight dead-code report: vulture's unused names that nothing ran.

The coverage data is written by hand (``CoverageData.add_lines``), not traced: a
second tracer started inside a suite run with ``--cov`` would take over from it.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING
from unittest.mock import patch

import coverage
import dead_code_report
import pytest
from dead_code_report import Finding, body_lines, main, named_in, never_ran, parse_vulture, report

if TYPE_CHECKING:
    from pathlib import Path

VULTURE_OUTPUT = """\
src/pkg/a.py:12: unused function 'helper' (60% confidence, 4 lines)
src/pkg/a.py:30: unused method 'on_press' (60% confidence, 2 lines)
src/pkg/b.py:5: unused class 'Viewer' (60% confidence, 20 lines)
src/pkg/b.py:40: unused property 'width_px' (60% confidence, 3 lines)
src/pkg/b.py:2: unused import 'os' (90% confidence, 1 line)
src/pkg/b.py:50: unused variable 'scratch' (60% confidence, 1 line)
src/pkg/b.py:60: unused attribute 'colour' (60% confidence, 1 line)
"""

MODULE = textwrap.dedent('''\
    """A module with one function that runs and some that do not."""


    def used(x):
        return x + 1


    def dead(x):
        """Nothing calls this."""
        y = x * 2
        return y


    class Holder:
        size = 3

        def method(self):
            return self.size

        @property
        def area(self):
            return self.size**2


    def kv_handler():
        return None


    def empty():
        """Only a docstring: no statement to judge by."""
    ''')


class TestParseVulture:
    def test_functions_methods_classes_and_properties_are_kept(self) -> None:
        assert parse_vulture(VULTURE_OUTPUT) == [
            Finding("src/pkg/a.py", 12, "function", "helper"),
            Finding("src/pkg/a.py", 30, "method", "on_press"),
            Finding("src/pkg/b.py", 5, "class", "Viewer"),
            Finding("src/pkg/b.py", 40, "property", "width_px"),
        ]

    def test_a_finding_reads_as_where_and_what(self) -> None:
        assert str(Finding("src/pkg/a.py", 12, "function", "helper")) == (
            "src/pkg/a.py:12: function helper"
        )


class TestBodyLines:
    def test_a_function_is_its_body(self) -> None:
        assert body_lines(MODULE, 8) == {9, 10, 11}

    def test_a_class_is_its_methods_bodies_not_its_own(self) -> None:
        """A class body runs at import; only its methods say whether it was used."""
        assert body_lines(MODULE, 14) == {18, 22}

    def test_a_decorated_function_is_found_by_its_def_line(self) -> None:
        assert body_lines(MODULE, 21) == {22}

    def test_a_line_with_no_definition_is_none(self) -> None:
        assert body_lines(MODULE, 9) is None


class TestNeverRan:
    def test_statements_none_of_which_ran(self) -> None:
        assert never_ran({9, 10, 11}, [5, 10, 11], {5})

    def test_one_statement_that_ran_is_enough(self) -> None:
        assert not never_ran({9, 10, 11}, [5, 10, 11], {5, 11})

    def test_a_body_with_no_statements_cannot_be_judged(self) -> None:
        assert not never_ran({29}, [5, 10, 11], set())


class TestNamedIn:
    def test_a_name_counts_only_as_a_whole_word(self, tmp_path: Path) -> None:
        (tmp_path / "x.py").write_text("dead_code_helper()\nhelper_two = 1\n")
        (tmp_path / "y.kv").write_text("on_press: root.on_goto()\n")
        assert named_in([tmp_path / "x.py", tmp_path / "y.kv"], {"helper", "on_press"}) == {
            "on_press"
        }

    def test_copies_of_the_code_are_not_uses(self, tmp_path: Path) -> None:
        for folder in (".venv/lib", "mutants/src", "build", "pkg/__pycache__"):
            (tmp_path / folder).mkdir(parents=True)
            (tmp_path / folder / "copy.py").write_text("dead()\n")
        files = dead_code_report._python_and_kv_files([tmp_path])  # noqa: SLF001
        assert named_in(files, {"dead"}) == set()

    def test_a_package_called_build_below_the_top_is_searched(self, tmp_path: Path) -> None:
        """barks-comic-building has src/barks_comic_building/build/."""
        package = tmp_path / "src" / "pkg" / "build"
        package.mkdir(parents=True)
        (package / "build_comics.py").write_text("get_max_timestamp(pages)\n")
        files = dead_code_report._python_and_kv_files([tmp_path])  # noqa: SLF001
        assert named_in(files, {"get_max_timestamp"}) == {"get_max_timestamp"}

    def test_missing_places_are_passed_over(self, tmp_path: Path) -> None:
        files = dead_code_report._python_and_kv_files([tmp_path / "gone", tmp_path / "x.py"])  # noqa: SLF001
        assert files == []


@pytest.fixture
def measured(tmp_path: Path) -> tuple[Path, Path]:
    """Return a tree with MODULE in it, and coverage data in which only ``used`` ran."""
    module = tmp_path / "src" / "mod.py"
    module.parent.mkdir()
    module.write_text(MODULE)
    data_file = tmp_path / ".coverage"
    data = coverage.CoverageData(basename=str(data_file))
    # The module's top-level statements (import time) and used()'s body.
    data.add_lines({str(module): {1, 4, 5, 8, 14, 15, 17, 20, 21, 25, 29}})
    data.write()
    return tmp_path, data_file


def _findings() -> list[Finding]:
    return [
        Finding("src/mod.py", 4, "function", "used"),
        Finding("src/mod.py", 8, "function", "dead"),
        Finding("src/mod.py", 14, "class", "Holder"),
        Finding("src/mod.py", 21, "property", "area"),
        Finding("src/mod.py", 25, "function", "kv_handler"),
        Finding("src/mod.py", 29, "function", "empty"),
        Finding("src/elsewhere.py", 1, "function", "unmeasured"),
    ]


class TestReport:
    def test_what_never_ran_and_is_named_nowhere_is_listed(
        self, measured: tuple[Path, Path]
    ) -> None:
        root, data_file = measured
        kv = root / "screen.kv"
        kv.write_text("on_release: root.kv_handler()\n")

        result = report(_findings(), data_file, [kv], root=root)

        assert [f.name for f in result.dead] == ["dead", "Holder", "area"]
        assert (result.ran, result.named, result.unmeasured) == (2, 1, 1)


class TestMain:
    def test_it_lists_what_it_found_and_exits_1(
        self, measured: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, data_file = measured
        output = "src/mod.py:8: unused function 'dead' (60% confidence, 4 lines)\n"
        with (
            patch.object(dead_code_report, "run_vulture", return_value=output),
            patch.object(dead_code_report, "REPO_ROOT", root),
        ):
            assert main([str(data_file), "--siblings", str(root / "no-such-sibling")]) == 1

        out = capsys.readouterr().out
        assert "no-such-sibling: not checked out; its uses are not counted" in out
        assert "dead-code: 1 unused and never run" in out
        assert "  src/mod.py:8: function dead" in out

    def test_with_nothing_found_it_exits_0(
        self, measured: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, data_file = measured
        with (
            patch.object(dead_code_report, "run_vulture", return_value=""),
            patch.object(dead_code_report, "REPO_ROOT", root),
        ):
            assert main([str(data_file), "--siblings"]) == 0
        assert "dead-code: 0 unused and never run" in capsys.readouterr().out

    def test_when_vulture_fails_it_exits_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(dead_code_report, "run_vulture", return_value=None):
            assert main([str(tmp_path / ".coverage")]) == 2  # noqa: PLR2004
        assert "dead-code: vulture failed to run" in capsys.readouterr().out
