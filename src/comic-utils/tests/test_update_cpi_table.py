"""Tests for the CPI table updater, against tables of its own.

The BLS download is network: each test hands the updater the flat file's text
through ``download_all_items``.
"""

# cspell:ignore CUSR  (BLS series ids: CUUR/CUSR + area + item)

from __future__ import annotations

import ast
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from comic_utils import cpi_table
from comic_utils import update_cpi_table as updater

if TYPE_CHECKING:
    from pathlib import Path

SERIES = updater.SERIES_ID
OTHER = "CUSR0000SA0"

# The BLS layout: a header row, tab-separated fields padded with spaces, CRLF endings.
HEADER = "series_id                   \tyear\tperiod\t       value\tfootnote_codes\r\n"


def _bls(*rows: tuple[str, int, str, str]) -> str:
    return HEADER + "".join(f"{s}   \t{y}\t{p}\t  {v}\t\r\n" for s, y, p, v in rows)


def _update(table: Path, text: str) -> updater.UpdateResult:
    with patch.object(updater, "download_all_items", return_value=text):
        return updater.update_cpi_table(table)


class TestAnnualAverages:
    def test_each_year_averages_all_its_values_of_the_one_series(self) -> None:
        text = _bls(
            (SERIES, 2024, "M01", "300.0"),
            (SERIES, 2024, "M02", "302.0"),
            (SERIES, 2024, "M13", "304.0"),  # BLS's annual average counts as a value
            (OTHER, 2024, "M01", "999.0"),  # another series: ignored
            (SERIES, 2025, "M01", "310.0"),  # a partial year: the months so far
        )
        assert updater.annual_averages(text) == {2024: 302.0, 2025: 310.0}

    def test_suppressed_and_short_rows_are_skipped(self) -> None:
        text = _bls((SERIES, 2024, "M01", "-"), (SERIES, 2024, "M02", "300.0")) + "short\trow\r\n"
        assert updater.annual_averages(text) == {2024: 300.0}


class TestTheTableFile:
    def test_the_shipped_table_is_what_the_renderer_writes(self) -> None:
        """So an update changes only the figures, never the file's shape."""
        shipped = updater.TABLE_PATH.read_text(encoding="utf-8")
        assert updater.render_table(dict(cpi_table.ANNUAL_CPI)) == shipped

    def test_a_rendered_table_reads_back(self, tmp_path: Path) -> None:
        table = {1913: 9.88, 1914: 10.01}
        path = tmp_path / "cpi_table.py"
        path.write_text(updater.render_table(table), encoding="utf-8")
        assert updater.read_table(path) == table
        ast.parse(path.read_text(encoding="utf-8"))  # valid Python

    def test_no_table_reads_empty(self, tmp_path: Path) -> None:
        assert updater.read_table(tmp_path / "absent.py") == {}


class TestUpdate:
    def test_a_newer_download_replaces_the_table(self, tmp_path: Path) -> None:
        path = tmp_path / "cpi_table.py"
        path.write_text(updater.render_table({2023: 304.7, 2024: 313.7}), encoding="utf-8")
        result = _update(path, _bls((SERIES, 2024, "M13", "313.7"), (SERIES, 2025, "M01", "317.6")))
        assert updater.read_table(path) == {2024: 313.7, 2025: 317.6}
        assert (result.years, result.previous_latest_year, result.latest_year) == (2, 2024, 2025)
        assert not path.with_suffix(".py.new").exists()

    def test_a_download_that_ends_earlier_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "cpi_table.py"
        before = updater.render_table({2024: 313.7, 2025: 321.9})
        path.write_text(before, encoding="utf-8")
        with pytest.raises(ValueError, match="ends 2024, before the table's 2025"):
            _update(path, _bls((SERIES, 2024, "M13", "313.7")))
        assert path.read_text(encoding="utf-8") == before

    def test_a_download_without_the_series_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "cpi_table.py"
        with pytest.raises(ValueError, match="no data for series"):
            _update(path, _bls((OTHER, 2025, "M01", "1.0")))
        assert not path.exists()


class TestDownload:
    def test_it_sends_a_descriptive_user_agent(self) -> None:
        """BLS answers 403 without one."""
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"text"
        with patch.object(updater.urllib.request, "urlopen", return_value=response) as urlopen:
            assert updater.download_all_items() == "text"
        request = urlopen.call_args.args[0]
        assert "gregg.kay@gmail.com" in request.get_header("User-agent")


class TestMain:
    def test_success_says_what_it_wrote(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "cpi_table.py"
        with patch.object(
            updater, "download_all_items", return_value=_bls((SERIES, 2025, "M01", "317.6"))
        ):
            assert updater.main(["--table", str(path)]) == 0
        assert "1 years, to 2025 (was None)" in capsys.readouterr().out

    def test_a_failure_exits_1_saying_why(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(updater, "download_all_items", side_effect=OSError("no network")):
            assert updater.main(["--table", str(tmp_path / "t.py")]) == 1
        assert "no network" in capsys.readouterr().err
