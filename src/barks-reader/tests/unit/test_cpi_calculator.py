import sqlite3
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
from comic_utils import cpi_calculator
from comic_utils.cpi_calculator import (
    CpiDatabaseUnavailableError,
    get_adjusted_usd,
    get_latest_year,
)

# The two years the two_year_cpi_db fixture inserts.
_LATEST_YEAR = 2025


@pytest.fixture
def two_year_cpi_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_cpi.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE indexes (
            year INTEGER,
            series TEXT,
            value REAL
        )
    """)
    # Insert test data: CPI of 100 in 1945, 200 in 2025 -> 2x multiplier
    test_data = [
        (1945, "CUUR0000SA0", 100.0),
        (2025, "CUUR0000SA0", 200.0),
    ]
    cursor.executemany("INSERT INTO indexes VALUES (?, ?, ?)", test_data)
    conn.commit()
    conn.close()
    return db_path


class TestGetAdjustedUsd:
    def test_correct_inflation_adjustment(self, two_year_cpi_db: Path) -> None:
        result = get_adjusted_usd(100.0, 1945, 2025, two_year_cpi_db)
        assert result == pytest.approx(200.0)

    def test_same_year_returns_same_amount(self, two_year_cpi_db: Path) -> None:
        result = get_adjusted_usd(50.0, 1945, 1945, two_year_cpi_db)
        assert result == pytest.approx(50.0)

    def test_missing_year_raises_value_error(self, two_year_cpi_db: Path) -> None:
        with pytest.raises(ValueError, match="No CPI data found for year 1900"):
            get_adjusted_usd(100.0, 1900, 2025, two_year_cpi_db)

    def test_missing_db_file_raises_file_not_found(self) -> None:
        bogus = Path("/nonexistent/path/cpi.db")
        with pytest.raises(FileNotFoundError):
            get_adjusted_usd(100.0, 1945, 2025, bogus)

    def test_target_year_defaults_to_the_latest_available(self, two_year_cpi_db: Path) -> None:
        assert get_adjusted_usd(100.0, 1945, None, two_year_cpi_db) == pytest.approx(200.0)


class TestGetLatestYear:
    def test_returns_the_newest_year_in_the_series(self, two_year_cpi_db: Path) -> None:
        assert get_latest_year(two_year_cpi_db) == _LATEST_YEAR

    def test_missing_db_file_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            get_latest_year(Path("/nonexistent/path/cpi.db"))

    def test_unknown_series_raises_value_error(self, two_year_cpi_db: Path) -> None:
        with pytest.raises(ValueError, match="No CPI data found for series NOPE"):
            get_latest_year(two_year_cpi_db, "NOPE")


class TestNotADatabase:
    """cpi.db is a git-lfs object; a bare checkout has a pointer file at its path."""

    _LFS_POINTER = (
        b"version https://git-lfs.github.com/spec/v1\n"
        b"oid sha256:d6c0ca57225d0d82920b9183fce7cb765e1a1b6fdb47552a23d729fefcecd0cf\n"
        b"size 65073152\n"
    )

    def test_an_lfs_pointer_names_the_fix(self, tmp_path: Path) -> None:
        pointer = tmp_path / "cpi.db"
        pointer.write_bytes(self._LFS_POINTER)

        with pytest.raises(CpiDatabaseUnavailableError, match="git lfs pull"):
            get_latest_year(pointer)

    def test_the_error_is_still_a_file_not_found(self, tmp_path: Path) -> None:
        # Callers that already handle a missing database keep working unchanged.
        pointer = tmp_path / "cpi.db"
        pointer.write_bytes(self._LFS_POINTER)

        with pytest.raises(FileNotFoundError):
            get_adjusted_usd(100.0, 1945, 2025, pointer)

    def test_some_other_file_is_rejected_too(self, tmp_path: Path) -> None:
        junk = tmp_path / "cpi.db"
        junk.write_text("not a database")

        with pytest.raises(CpiDatabaseUnavailableError, match="not a SQLite database"):
            get_latest_year(junk)

    def test_an_empty_file_is_rejected(self, tmp_path: Path) -> None:
        empty = tmp_path / "cpi.db"
        empty.write_bytes(b"")

        with pytest.raises(CpiDatabaseUnavailableError):
            get_latest_year(empty)

    def test_the_failure_is_not_cached(self, tmp_path: Path, two_year_cpi_db: Path) -> None:
        # After `git lfs pull` puts the real file in place, the next lookup must
        # see it - a cached failure would make the fix look as if it had not worked.
        path = tmp_path / "cpi.db"
        path.write_bytes(self._LFS_POINTER)
        with pytest.raises(CpiDatabaseUnavailableError):
            get_latest_year(path)

        path.write_bytes(two_year_cpi_db.read_bytes())
        assert get_latest_year(path) == get_latest_year(two_year_cpi_db)


class TestYearTableCaching:
    """The 1.7M-row table is unindexed, so it is read once per series, not per lookup."""

    def test_repeated_lookups_hit_the_database_once(self, two_year_cpi_db: Path) -> None:
        cpi_calculator._avg_cpi_by_year.cache_clear()  # noqa: SLF001

        with patch.object(cpi_calculator, "sqlite3", wraps=sqlite3) as spy:
            for _ in range(50):
                get_adjusted_usd(100.0, 1945, 2025, two_year_cpi_db)

        assert spy.connect.call_count == 1

    def test_each_series_is_cached_separately(self, two_year_cpi_db: Path) -> None:
        cpi_calculator._avg_cpi_by_year.cache_clear()  # noqa: SLF001

        assert cpi_calculator._avg_cpi_by_year(two_year_cpi_db, "CUUR0000SA0")  # noqa: SLF001
        assert cpi_calculator._avg_cpi_by_year(two_year_cpi_db, "NOPE") == {}  # noqa: SLF001

        # Two separate reads: neither series was served from the other's entry.
        info = cpi_calculator._avg_cpi_by_year.cache_info()  # noqa: SLF001
        assert (info.misses, info.hits) == (2, 0)

        cpi_calculator._avg_cpi_by_year(two_year_cpi_db, "CUUR0000SA0")  # noqa: SLF001
        assert cpi_calculator._avg_cpi_by_year.cache_info().hits == 1  # noqa: SLF001

    def test_the_shared_table_cannot_be_mutated_by_a_caller(self, two_year_cpi_db: Path) -> None:
        """Every caller gets the one cached object, so it must be read-only."""
        cpi_calculator._avg_cpi_by_year.cache_clear()  # noqa: SLF001

        table = cpi_calculator._avg_cpi_by_year(two_year_cpi_db, "CUUR0000SA0")  # noqa: SLF001

        with pytest.raises(TypeError):
            cast("dict[int, float]", table)[1900] = 1.0

    def test_a_year_average_spans_its_monthly_rows(self, tmp_path: Path) -> None:
        db_path = tmp_path / "monthly.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE indexes (year INTEGER, series TEXT, value REAL)")
        conn.executemany(
            "INSERT INTO indexes VALUES (?, ?, ?)",
            [(1950, "S", 90.0), (1950, "S", 110.0), (2000, "S", 200.0)],
        )
        conn.commit()
        conn.close()

        cpi_calculator._avg_cpi_by_year.cache_clear()  # noqa: SLF001
        assert cpi_calculator._avg_cpi_by_year(db_path, "S") == {  # noqa: SLF001
            1950: pytest.approx(100.0),
            2000: pytest.approx(200.0),
        }
