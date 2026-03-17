import sqlite3
from pathlib import Path

import pytest
from comic_utils.cpi_calculator import get_adjusted_usd


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

    def test_is_file_bug_never_raises_file_not_found(self) -> None:
        """Line 30 has `db_path.is_file` (missing parens) — always truthy.

        FileNotFoundError is never raised even for a nonexistent path.
        """
        bogus = Path("/nonexistent/path/cpi.db")
        # This should raise FileNotFoundError but doesn't due to the bug.
        # Instead, it raises an OperationalError from sqlite3 trying to open the file.
        with pytest.raises(sqlite3.OperationalError):
            get_adjusted_usd(100.0, 1945, 2025, bogus)
