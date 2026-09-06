import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from comic_utils import cpi_calculator
from comic_utils.cpi_calculator import get_adjusted_usd, get_latest_year

# The two years the cpi_db fixture inserts.
_LATEST_YEAR = 2025


@pytest.fixture
def cpi_db(tmp_path: Path) -> Path:
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
    def test_correct_inflation_adjustment(self, cpi_db: Path) -> None:
        result = get_adjusted_usd(100.0, 1945, 2025, cpi_db)
        assert result == pytest.approx(200.0)

    def test_same_year_returns_same_amount(self, cpi_db: Path) -> None:
        result = get_adjusted_usd(50.0, 1945, 1945, cpi_db)
        assert result == pytest.approx(50.0)

    def test_missing_year_raises_value_error(self, cpi_db: Path) -> None:
        with pytest.raises(ValueError, match="No CPI data found for year 1900"):
            get_adjusted_usd(100.0, 1900, 2025, cpi_db)

    def test_missing_db_file_raises_file_not_found(self) -> None:
        bogus = Path("/nonexistent/path/cpi.db")
        with pytest.raises(FileNotFoundError):
            get_adjusted_usd(100.0, 1945, 2025, bogus)

    def test_target_year_defaults_to_the_latest_available(self, cpi_db: Path) -> None:
        assert get_adjusted_usd(100.0, 1945, None, cpi_db) == pytest.approx(200.0)


class TestGetLatestYear:
    def test_returns_the_newest_year_in_the_series(self, cpi_db: Path) -> None:
        assert get_latest_year(cpi_db) == _LATEST_YEAR

    def test_missing_db_file_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            get_latest_year(Path("/nonexistent/path/cpi.db"))

    def test_unknown_series_raises_value_error(self, cpi_db: Path) -> None:
        with pytest.raises(ValueError, match="No CPI data found for series NOPE"):
            get_latest_year(cpi_db, "NOPE")


class TestYearTableCaching:
    """The 1.7M-row table is unindexed, so it is read once per series, not per lookup."""

    def test_repeated_lookups_hit_the_database_once(self, cpi_db: Path) -> None:
        cpi_calculator._avg_cpi_by_year.cache_clear()  # noqa: SLF001

        with patch.object(cpi_calculator, "sqlite3", wraps=sqlite3) as spy:
            for _ in range(50):
                get_adjusted_usd(100.0, 1945, 2025, cpi_db)

        assert spy.connect.call_count == 1

    def test_each_series_is_cached_separately(self, cpi_db: Path) -> None:
        cpi_calculator._avg_cpi_by_year.cache_clear()  # noqa: SLF001

        assert cpi_calculator._avg_cpi_by_year(cpi_db, "CUUR0000SA0")  # noqa: SLF001
        assert cpi_calculator._avg_cpi_by_year(cpi_db, "NOPE") == {}  # noqa: SLF001

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
