"""Tests for the overnight run's coverage floor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from coverage_floor import judge, main, read_best

if TYPE_CHECKING:
    from pathlib import Path


class TestJudge:
    def test_the_first_night_records_its_total(self, tmp_path: Path) -> None:
        record = tmp_path / "coverage.json"
        assert judge(87.2, record) == (True, "new best, recorded: 87.2%")
        assert read_best(record) == 87.2  # noqa: PLR2004

    def test_a_higher_total_raises_the_best(self, tmp_path: Path) -> None:
        record = tmp_path / "coverage.json"
        judge(87.2, record)
        assert judge(88.0, record) == (True, "new best, recorded: 88.0% (was 87.2%)")
        assert read_best(record) == 88.0  # noqa: PLR2004

    def test_a_dip_inside_the_tolerance_passes_and_keeps_the_best(self, tmp_path: Path) -> None:
        record = tmp_path / "coverage.json"
        judge(87.2, record)
        assert judge(86.2, record) == (True, "within 1.0 of its best, 87.2%")
        assert read_best(record) == 87.2  # noqa: PLR2004

    def test_a_drop_past_the_tolerance_fails(self, tmp_path: Path) -> None:
        record = tmp_path / "coverage.json"
        judge(87.2, record)
        passed, line = judge(86.1, record)
        assert not passed
        assert line == "FAIL - combined 86.1% is more than 1.0 below its best, 87.2%"
        assert read_best(record) == 87.2  # noqa: PLR2004


def test_main_exits_one_below_the_floor(tmp_path: Path) -> None:
    record = tmp_path / "coverage.json"
    assert main(["87.2", "--record", str(record)]) == 0
    assert main(["80", "--record", str(record)]) == 1
    assert main(["80", "--record", str(record), "--tolerance", "10"]) == 0
