import sqlite3
from functools import lru_cache
from pathlib import Path

CPI_DATABASE_PATH = Path(__file__).parent / "cpi.db"

# CPI series used by default: All items in U.S. city average, all urban consumers.
DEFAULT_SERIES_ID = "CUUR0000SA0"


@lru_cache(maxsize=8)
def _avg_cpi_by_year(db_path: Path, series_id: str) -> dict[int, float]:
    """Return the average CPI for every year of a series, in one query.

    ``indexes`` holds 1.7M unindexed rows, so a per-year lookup costs a full
    table scan. Adjusting a few hundred payments one at a time therefore took
    about a minute; reading the whole series once takes under a tenth of a
    second. The result is cached per ``(db_path, series_id)`` - CPI figures for
    a year do not change under a running process.

    Args:
        db_path: File path to the 'cpi.db' SQLite database.
        series_id: The CPI series to read.

    Returns:
        Year to average index value. Empty if the series has no rows.

    Raises:
        FileNotFoundError: If ``db_path`` does not exist.

    """
    if not db_path.is_file():
        msg = f'Database not found at: "{db_path}"'
        raise FileNotFoundError(msg)

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT year, AVG(value) FROM indexes WHERE series = ? GROUP BY year",
            (series_id,),
        ).fetchall()
    finally:
        conn.close()

    return {year: value for year, value in rows if value is not None}


def get_latest_year(
    db_path: Path = CPI_DATABASE_PATH,
    series_id: str = DEFAULT_SERIES_ID,
) -> int:
    """Return the most recent year available for a CPI series in the database.

    Use this to discover the newest year the data supports; it tracks each
    ``cpi.db`` update automatically, so nothing needs to be hardcoded.

    Args:
        db_path: File path to the 'cpi.db' SQLite database.
        series_id: The CPI series to inspect. Default is 'CUUR0000SA0'.

    Returns:
        The latest calendar year with data for ``series_id``.

    Raises:
        FileNotFoundError: If ``db_path`` does not exist.
        ValueError: If no data exists for ``series_id``.

    """
    cpi_by_year = _avg_cpi_by_year(db_path, series_id)
    if not cpi_by_year:
        msg = f"No CPI data found for series {series_id}"
        raise ValueError(msg)
    return max(cpi_by_year)


def get_adjusted_usd(
    amount: float,
    base_year: int,
    to_year: int | None = None,
    db_path: Path = CPI_DATABASE_PATH,
    series_id: str = DEFAULT_SERIES_ID,
) -> float:
    """Convert USD from a historical year to a target year using a provided cpi.db file.

    Args:
        amount (float): The amount of money to convert.
        base_year (int): The year the amount originates from.
        to_year (int | None): The target year to convert to. If ``None`` (the
            default), the most recent year available for ``series_id`` in the
            database is used, so the result tracks each cpi.db update
            automatically instead of relying on a hardcoded year.
        db_path (Path): File path to the 'cpi.db' SQLite database.
        series_id (str): The CPI series to use.
                         Default is 'CUUR0000SA0' (All items in U.S. city average,
                         all urban consumers).

    Returns:
        float: The adjusted dollar amount.

    Raises:
        FileNotFoundError: If ``db_path`` does not exist.
        ValueError: If no CPI data exists for ``series_id`` or a requested year.

    """
    cpi_by_year = _avg_cpi_by_year(db_path, series_id)
    if not cpi_by_year:
        errmsg = f"No CPI data found for series {series_id}"
        raise ValueError(errmsg)

    # Resolve the target year lazily so it reflects the current database.
    if to_year is None:
        to_year = max(cpi_by_year)

    def get_avg_cpi_for_year(year: int) -> float:
        value = cpi_by_year.get(year)
        if value is None:
            errmsg = f"No CPI data found for year {year} with series {series_id}"
            raise ValueError(errmsg)
        return value

    # Formula: (Target CPI / Start CPI) * Amount
    return (get_avg_cpi_for_year(to_year) / get_avg_cpi_for_year(base_year)) * amount


if __name__ == "__main__":
    # Example: convert $100 from 1945 into the latest year the database supports.
    try:
        latest_year = get_latest_year()
        value = get_adjusted_usd(100, 1945)
        print(f"$100 in 1945 is equivalent to ${value:.2f} in {latest_year}")  # noqa: T201
    except (FileNotFoundError, ValueError) as e:
        print(e)  # noqa: T201
