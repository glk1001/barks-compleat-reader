"""Tests for the CPI database updater, against a small database of its own.

The real ``cpi.db`` is git-LFS (CI has only its pointer), and the BLS download is
network: each test builds a database in a temp dir and hands the updater the flat
file's text through ``download_all_items``.
"""

# cspell:ignore CUSR  (BLS series ids: CUUR/CUSR + area + item)

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from comic_utils import update_cpi_db as updater

if TYPE_CHECKING:
    from pathlib import Path

REF = updater.REFERENCE_SERIES
OTHER = "CUSR0000SA0"
UNTOUCHED = "CUUR0000SAF"

# The BLS layout: a header row, tab-separated fields padded with spaces, CRLF endings.
HEADER = "series_id                   \tyear\tperiod\t       value\tfootnote_codes\r\n"


def _bls(*rows: tuple[str, int, str, str]) -> str:
    return HEADER + "".join(f"{s}   \t{y}\t{p}\t  {v}\t\r\n" for s, y, p, v in rows)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    """Build a cpi.db: the reference series to 2024, and two other series."""
    path = tmp_path / "cpi.db"
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("CREATE TABLE indexes (series TEXT, year INTEGER, period TEXT, value REAL)")
        conn.executemany(
            "INSERT INTO indexes VALUES (?, ?, ?, ?)",
            [
                (REF, 2023, "M13", 304.7),
                (REF, 2024, "M13", 313.7),
                (OTHER, 2024, "M13", 1.0),
                (UNTOUCHED, 2024, "M13", 42.0),
            ],
        )
    return path


def _rows(path: Path, series: str) -> list[tuple[int, str, float]]:
    with closing(sqlite3.connect(path)) as conn, conn:
        return conn.execute(
            "SELECT year, period, value FROM indexes WHERE series = ? ORDER BY year, period",
            (series,),
        ).fetchall()


def _update(db: Path, text: str, **kwargs: object) -> updater.UpdateResult:
    with patch.object(updater, "download_all_items", return_value=text):
        return updater.update_cpi_db(db, **kwargs)  # ty: ignore[invalid-argument-type]


class TestParseIndexRows:
    def test_padded_crlf_rows_parse_and_the_header_is_skipped(self) -> None:
        text = _bls((REF, 2025, "M01", "317.671"), (REF, 2025, "M13", "321.9"))
        assert updater.parse_index_rows(text) == [
            (REF, 2025, "M01", 317.671),
            (REF, 2025, "M13", 321.9),
        ]

    def test_suppressed_values_and_short_rows_are_skipped(self) -> None:
        text = (
            HEADER + f"{REF}\t2025\tM02\t   -\t\r\n" + "garbage\r\n" + f"{REF}\t2025\tM03\t1.5\r\n"
        )
        assert updater.parse_index_rows(text) == [(REF, 2025, "M03", 1.5)]


class TestUpdateCpiDb:
    def test_the_downloaded_series_are_replaced_and_the_rest_kept(self, db: Path) -> None:
        result = _update(
            db,
            _bls(
                (REF, 2024, "M13", "313.689"),
                (REF, 2025, "M13", "321.9"),
                (OTHER, 2025, "M13", "2.0"),
            ),
        )
        assert _rows(db, REF) == [(2024, "M13", 313.689), (2025, "M13", 321.9)]
        assert _rows(db, OTHER) == [(2025, "M13", 2.0)]
        assert _rows(db, UNTOUCHED) == [(2024, "M13", 42.0)]
        assert result.series_updated == 2  # noqa: PLR2004
        assert result.rows_written == 3  # noqa: PLR2004
        assert result.previous_latest_year == 2024  # noqa: PLR2004
        assert result.latest_year == 2025  # noqa: PLR2004

    def test_the_old_database_is_kept_as_a_backup(self, db: Path) -> None:
        result = _update(db, _bls((REF, 2025, "M13", "321.9")))
        assert result.backup_path == db.with_name("cpi.db.bak")
        assert _rows(result.backup_path, REF) == [(2023, "M13", 304.7), (2024, "M13", 313.7)]

    def test_no_backup_when_asked(self, db: Path) -> None:
        result = _update(db, _bls((REF, 2025, "M13", "321.9")), keep_backup=False)
        assert result.backup_path is None
        assert not db.with_name("cpi.db.bak").exists()

    @pytest.mark.parametrize(
        ("text", "match"),
        [
            (HEADER, "no parseable CPI rows"),
            (_bls((REF, 2020, "M13", "258.8")), "older than existing 2024"),
        ],
        ids=["empty", "older-data"],
    )
    def test_a_bad_download_leaves_the_database_as_it_was(
        self, db: Path, text: str, match: str
    ) -> None:
        before = db.read_bytes()
        with pytest.raises(ValueError, match=match):
            _update(db, text)
        assert db.read_bytes() == before
        assert not list(db.parent.glob("*.cpi.tmp"))  # the temp copy is removed
        assert not db.with_name("cpi.db.bak").exists()

    def test_no_reference_series_anywhere_is_an_error(self, db: Path) -> None:
        """A download without it keeps the database's own rows; with none there either, it fails."""
        with closing(sqlite3.connect(db)) as conn, conn:
            conn.execute("DELETE FROM indexes WHERE series = ?", (REF,))
        before = db.read_bytes()
        with pytest.raises(ValueError, match="missing after update"):
            _update(db, _bls((OTHER, 2025, "M13", "2.0")))
        assert db.read_bytes() == before

    def test_a_download_without_the_reference_series_keeps_its_rows(self, db: Path) -> None:
        result = _update(db, _bls((OTHER, 2025, "M13", "2.0")))
        assert _rows(db, REF) == [(2023, "M13", 304.7), (2024, "M13", 313.7)]
        assert result.latest_year == 2024  # noqa: PLR2004

    def test_a_missing_database_is_an_error(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Database not found"):
            updater.update_cpi_db(tmp_path / "absent.db")


def test_the_download_sends_the_contact_user_agent() -> None:
    """BLS answers 403 to a request without one."""
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b"text"
    with patch.object(updater.urllib.request, "urlopen", return_value=response) as urlopen:
        assert updater.download_all_items("https://example.invalid/x", "Agent (a@b.c)", 5) == "text"
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://example.invalid/x"
    assert request.get_header("User-agent") == "Agent (a@b.c)"
    assert urlopen.call_args.kwargs == {"timeout": 5}


class TestMain:
    def test_success_reports_what_changed(
        self, db: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(
            updater, "download_all_items", return_value=_bls((REF, 2025, "M13", "1"))
        ):
            assert updater.main(["--db", str(db)]) == 0
        out = capsys.readouterr().out
        assert f"Latest {REF} year: 2024 -> 2025." in out
        assert "backed up to cpi.db.bak" in out

    def test_failure_is_exit_one_with_the_reason(
        self, db: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with patch.object(updater, "download_all_items", return_value=HEADER):
            assert updater.main(["--db", str(db), "--no-backup"]) == 1
        assert "CPI update failed: BLS download contained no parseable CPI rows" in (
            capsys.readouterr().err
        )
