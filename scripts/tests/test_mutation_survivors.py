"""Tests for sorting the overnight mutation stage's survivors by what they are."""

# cspell:ignoreRegExp /xǁ\w+ǁ\w+/  (mutmut's method mutants: xǁ<Class>ǁ<method>)

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import mutation_survivors as ms
from mutation_survivors import (
    Listed,
    Survivor,
    change_of,
    is_log_wording,
    read_listed,
    report,
    sort_survivors,
    split_name,
    write_listed,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

CORE = "barks_reader.core.reader_formatter"


class TestNames:
    def test_a_function_mutant_names_its_module_and_function(self) -> None:
        assert split_name(f"{CORE}.x_mark_terms_in_text__mutmut_13") == (
            CORE,
            "mark_terms_in_text",
        )

    def test_a_method_mutant_names_its_class_and_method(self) -> None:
        assert split_name("barks_reader.core.screen_metrics.xǁScreenMetricsǁrefresh__mutmut_3") == (
            "barks_reader.core.screen_metrics",
            "ScreenMetrics.refresh",
        )


class TestChange:
    def test_the_change_is_the_lines_taken_out_and_put_in_stripped(self) -> None:
        original = "def f(x):\n    y = x + 1\n    return y\n"
        mutant = "def f(x):\n    y = x - 1\n    return y\n"
        assert change_of(original, mutant) == "- y = x + 1\n+ y = x - 1"

    def test_the_same_change_elsewhere_in_the_function_is_the_same(self) -> None:
        """Lines added above it move it down, and its identity must not move with it."""
        a = change_of("def f():\n    return 1\n", "def f():\n    return 2\n")
        b = change_of(
            "def f():\n    pass\n    pass\n    return 1\n",
            "def f():\n    pass\n    pass\n    return 2\n",
        )
        assert a == b


class TestLogWording:
    def test_a_blanked_logger_message_is_log_wording(self) -> None:
        assert is_log_wording(
            'def f(x):\n    logger.debug(f"Got {x}.")\n    return x\n',
            "def f(x):\n    logger.debug(None)\n    return x\n",
        )

    def test_a_message_split_over_lines_is_log_wording_too(self) -> None:
        assert is_log_wording(
            'def f(x):\n    logger.warning(\n        f"a {x}"\n        f" b"\n    )\n',
            'def f(x):\n    logger.warning(\n        "XXa bXX"\n    )\n',
        )

    def test_a_marker_logged_through_log_markers_is_never_log_wording(self) -> None:
        """Its text is what the GUI tests wait on."""
        assert not is_log_wording(
            "def f(i):\n    logger.info(log_markers.SHOWED_PAGE.format(index=i))\n",
            "def f(i):\n    logger.info(None)\n",
        )

    def test_a_changed_log_level_is_not_log_wording(self) -> None:
        assert not is_log_wording(
            'def f():\n    logger.debug("x")\n', 'def f():\n    logger.info("x")\n'
        )

    def test_a_change_outside_the_logger_call_is_not_log_wording(self) -> None:
        assert not is_log_wording(
            'def f(x):\n    logger.debug("x")\n    return x\n',
            'def f(x):\n    logger.debug("y")\n    return None\n',
        )

    def test_any_other_call_is_not_log_wording(self) -> None:
        assert not is_log_wording('def f():\n    print("a")\n', "def f():\n    print(None)\n")


class TestFile:
    def test_entries_come_back_as_written_quotes_backslashes_and_all(self, tmp_path: Path) -> None:
        path = tmp_path / "equivalents.toml"
        listed = Listed(
            equivalent={(CORE, "f", '- x = "a"\n+ x = ""'): 'Both are "falsy".'},
            untriaged=[(CORE, "g", '- p = r"\\d"\n+ p = None'), (CORE, "h", '- s = """"""')],
        )
        write_listed(path, listed)
        assert read_listed(path) == listed

    def test_no_file_lists_nothing(self, tmp_path: Path) -> None:
        assert read_listed(tmp_path / "missing.toml") == Listed({}, [])


def _survivor(function: str, change: str = "- a\n+ b", module: str = CORE) -> Survivor:
    return Survivor(module, function, change)


class TestSort:
    def test_each_survivor_is_sorted_into_its_class(self) -> None:
        listed = Listed(
            equivalent={_survivor("eq").key: "why"}, untriaged=[_survivor("backlog").key]
        )
        result = sort_survivors(
            [
                (_survivor("eq"), False),
                (_survivor("logged"), True),
                (_survivor("backlog"), False),
                (_survivor("fresh"), False),
            ],
            listed,
            {CORE},
        )
        names = [
            [s.function for s in group]
            for group in (result.equivalent, result.log_wording, result.untriaged, result.new)
        ]
        assert names == [["eq"], ["logged"], ["backlog"], ["fresh"]]

    def test_a_listed_entry_that_no_longer_survives_is_gone(self) -> None:
        listed = Listed(equivalent={}, untriaged=[_survivor("killed").key])
        assert sort_survivors([], listed, {CORE}).gone == [_survivor("killed").key]

    def test_an_entry_of_a_module_not_mutated_tonight_is_not_gone(self) -> None:
        """The other Linux machine mutates the other package."""
        listed = Listed(equivalent={}, untriaged=[_survivor("other", module="pkg.other").key])
        assert sort_survivors([], listed, {CORE}).gone == []


class TestReport:
    def test_the_counts_add_up_and_a_new_one_is_shown_with_its_change(self) -> None:
        result = ms.Sorted(
            equivalent=[_survivor("a")],
            log_wording=[_survivor("b"), _survivor("c")],
            untriaged=[_survivor("d")],
            new=[_survivor("fresh", "- x = 1\n+ x = 2")],
            gone=[],
        )
        lines = report(result, "barks-reader")
        assert lines[0] == (
            "mutation survivors (barks-reader): 5 = 3 equivalent (1 listed, 2 log wording)"
            " + 1 untriaged + 1 new"
        )
        assert f"  {CORE} fresh" in lines
        assert "      - x = 1" in lines
        assert "      + x = 2" in lines

    def test_gone_entries_are_named_for_taking_out(self) -> None:
        result = ms.Sorted([], [], [], [], gone=[(CORE, "killed", "- a\n+ b")])
        assert f"  {CORE} killed: - a" in report(result, "barks-reader")


class TestMain:
    @staticmethod
    def _run(
        tmp_path: Path, survivors: list[tuple[Survivor, bool]], *args: str
    ) -> tuple[int, Path]:
        path = tmp_path / "equivalents.toml"
        with patch.object(ms, "collect", return_value=(survivors, {CORE})):
            status = ms.main(["--package-dir", str(tmp_path), *args], equivalents_file=path)
        return status, path

    def test_a_new_survivor_warns(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        status, _ = self._run(tmp_path, [(_survivor("fresh"), False)])
        assert status == 1
        assert "NEW survivors" in capsys.readouterr().out

    def test_log_wording_alone_does_not_warn(self, tmp_path: Path) -> None:
        status, _ = self._run(tmp_path, [(_survivor("logged"), True)])
        assert status == 0

    def test_a_baseline_puts_the_new_in_the_backlog_and_then_none_is_new(
        self, tmp_path: Path
    ) -> None:
        survivors = [(_survivor("fresh"), False), (_survivor("logged"), True)]
        status, path = self._run(tmp_path, survivors, "--baseline")
        assert status == 0
        assert read_listed(path).untriaged == [_survivor("fresh").key]
        assert self._run(tmp_path, survivors)[0] == 0
