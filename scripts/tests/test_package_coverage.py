"""Tests for the per-package coverage floors."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import package_coverage
import pytest
from package_coverage import FLOORS, TOTAL, judge, main, measure

if TYPE_CHECKING:
    from pathlib import Path

FLOOR = {"small": 99.0, "large": 97.8}


class TestJudge:
    def test_every_package_at_or_over_its_floor_passes(self) -> None:
        passed, lines = judge({"small": 99.0, "large": 98.8}, FLOOR)
        assert passed
        assert lines == ["small   99.0%  ok", "large   98.8%  ok"]

    def test_one_package_under_its_floor_fails_and_is_named(self) -> None:
        passed, lines = judge({"small": 98.9, "large": 98.8}, FLOOR)
        assert not passed
        assert lines == ["small   98.9%  FAIL - below its floor, 99.0%", "large   98.8%  ok"]

    def test_a_later_package_passing_does_not_hide_an_earlier_failure(self) -> None:
        passed, _lines = judge({"small": 50.0, "large": 100.0}, FLOOR)
        assert not passed

    def test_a_figure_is_judged_as_it_is_printed(self) -> None:
        """98.96 prints as 99.0, so it must not fail a floor of 99.0."""
        passed, lines = judge({"small": 98.96, "large": 100.0}, FLOOR)
        assert passed
        assert lines[0] == "small   99.0%  ok"


class TestMeasure:
    def test_each_package_is_reported_by_its_folder_and_the_total_by_none(
        self, tmp_path: Path
    ) -> None:
        with patch.object(package_coverage.coverage, "Coverage") as coverage_class:
            cov = coverage_class.return_value
            cov.report.side_effect = [99.5, 98.0]
            figures = measure(tmp_path / ".coverage", ["okf_reader", TOTAL])
        assert figures == {"okf_reader": 99.5, TOTAL: 98.0}
        assert coverage_class.call_args.kwargs["data_file"] == str(tmp_path / ".coverage")
        cov.load.assert_called_once_with()
        includes = [call.kwargs["include"] for call in cov.report.call_args_list]
        assert includes == ["*/okf_reader/*", None]


class TestMain:
    def test_no_data_file_fails_and_says_how_to_make_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--data-file", str(tmp_path / "missing")]) == 1
        assert "pytest --cov" in capsys.readouterr().out

    @pytest.mark.parametrize(("slip", "status"), [(0.0, 0), (0.1, 1)])
    def test_the_exit_status_follows_the_floors(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], slip: float, status: int
    ) -> None:
        data = tmp_path / ".coverage"
        data.write_bytes(b"")
        measured = dict(FLOORS) | {"okf_reader": FLOORS["okf_reader"] - slip}
        with patch.object(package_coverage, "measure", return_value=measured) as measure_mock:
            assert main(["--data-file", str(data)]) == status
        measure_mock.assert_called_once_with(data, list(FLOORS))
        out = capsys.readouterr().out.splitlines()
        assert len(out) == len(FLOORS)
        assert all(line.startswith("package coverage: ") for line in out)


def test_every_measured_package_has_a_floor() -> None:
    """A package added to the coverage source must get a floor with it."""
    import tomllib  # noqa: PLC0415

    config = tomllib.loads((package_coverage.REPO_ROOT / "pyproject.toml").read_text("utf-8"))
    sources = config["tool"]["coverage"]["run"]["source"]
    assert {source.rsplit("/", 1)[1] for source in sources} == set(FLOORS) - {TOTAL}
