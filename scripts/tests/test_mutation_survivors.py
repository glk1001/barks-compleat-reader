"""Tests for the overnight mutation stage's survivor comparison."""

# cspell:ignoreRegExp /xǁ\w+ǁ\w+/  (mutmut's method mutants: xǁ<Class>ǁ<method>)

from __future__ import annotations

from typing import TYPE_CHECKING

from mutation_survivors import main, read_record, survivors_by_module

if TYPE_CHECKING:
    from pathlib import Path

RESULTS = """\
    barks_reader.core.reader_formatter.x_mark_phrase_in_text__mutmut_4: survived
    barks_reader.core.reader_formatter.x_mark_phrase_in_text__mutmut_5: killed
    barks_reader.core.comic_reader_manager.xǁComicReaderManagerǁ__init____mutmut_9: survived
    barks_reader.core.navigation.tree_spec.x_build__mutmut_1: survived
    barks_reader.core.other_module.x_f__mutmut_1: survived
"""


class TestSurvivorsByModule:
    def test_functions_methods_and_packages_are_counted_under_their_module(self) -> None:
        found = survivors_by_module(
            RESULTS, ["reader_formatter", "comic_reader_manager", "navigation.tree_spec"]
        )
        assert {module: len(names) for module, names in found.items()} == {
            "reader_formatter": 1,
            "comic_reader_manager": 1,
            "navigation.tree_spec": 1,
        }
        assert found["reader_formatter"] == [
            "barks_reader.core.reader_formatter.x_mark_phrase_in_text__mutmut_4"
        ]

    def test_a_mutated_module_with_no_survivors_counts_zero(self) -> None:
        assert survivors_by_module(RESULTS, ["user_error_messages"]) == {"user_error_messages": []}


class TestMain:
    def test_the_first_run_only_records(self, tmp_path: Path) -> None:
        record = tmp_path / "mutation-survivors.json"
        assert main(["reader_formatter"], RESULTS, record) == 0
        assert read_record(record) == {"reader_formatter": 1}

    def test_a_rise_is_reported_once_and_recorded(self, tmp_path: Path) -> None:
        record = tmp_path / "mutation-survivors.json"
        main(["reader_formatter"], "", record)  # recorded at 0
        assert main(["reader_formatter"], RESULTS, record) == 1
        assert main(["reader_formatter"], RESULTS, record) == 0  # the new count is the record

    def test_a_fall_or_no_change_is_quiet(self, tmp_path: Path) -> None:
        record = tmp_path / "mutation-survivors.json"
        main(["reader_formatter", "comic_reader_manager"], RESULTS, record)
        assert main(["reader_formatter"], "", record) == 0
        assert read_record(record) == {"reader_formatter": 0, "comic_reader_manager": 1}

    def test_modules_outside_tonights_slice_keep_their_record(self, tmp_path: Path) -> None:
        record = tmp_path / "mutation-survivors.json"
        main(["comic_reader_manager"], RESULTS, record)
        main(["reader_formatter"], RESULTS, record)
        assert read_record(record) == {"comic_reader_manager": 1, "reader_formatter": 1}
