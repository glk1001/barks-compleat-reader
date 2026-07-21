import sqlite3
from pathlib import Path

CPI_DATABASE_PATH = Path(__file__).parent / "cpi.db"

# CPI series used by default: All items in U.S. city average, all urban consumers.
DEFAULT_SERIES_ID = "CUUR0000SA0"


def _max_year(cursor: sqlite3.Cursor, series_id: str) -> int | None:
    """Return the most recent year present for ``series_id`` in ``indexes``.

    Args:
        cursor: An open cursor on the cpi.db database.
        series_id: The CPI series to inspect.

    Returns:
        The latest calendar year with data for ``series_id``, or ``None`` if the
        series has no rows.

    """
    cursor.execute("SELECT MAX(year) FROM indexes WHERE series = ?", (series_id,))
    result = cursor.fetchone()
    return result[0] if result is not None else None


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
    if not db_path.is_file():
        msg = f'Database not found at: "{db_path}"'
        raise FileNotFoundError(msg)

    conn = sqlite3.connect(db_path)
    try:
        latest = _max_year(conn.cursor(), series_id)
    finally:
        conn.close()

    if latest is None:
        msg = f"No CPI data found for series {series_id}"
        raise ValueError(msg)
    return latest


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
    if not db_path.is_file():
        msg = f'Database not found at: "{db_path}"'
        raise FileNotFoundError(msg)

    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    def get_avg_cpi_for_year(year: int) -> float:
        # We query the average value of all entries for the specific year and series.
        # This handles years with partial data (like the current year) automatically.
        query = """
            SELECT AVG(value)
            FROM indexes
            WHERE year = ?
            AND series = ?
        """
        cursor.execute(query, (year, series_id))
        result = cursor.fetchone()

        if result is None or result[0] is None:
            errmsg = f"No CPI data found for year {year} with series {series_id}"
            raise ValueError(errmsg)

        return result[0]

    try:
        # Resolve the target year lazily so it reflects the current database.
        if to_year is None:
            latest = _max_year(cursor, series_id)
            if latest is None:
                errmsg = f"No CPI data found for series {series_id}"
                raise ValueError(errmsg)
            to_year = latest

        # 1. Get CPI for base year
        cpi_start = get_avg_cpi_for_year(base_year)

        # 2. Get CPI for target year
        cpi_end = get_avg_cpi_for_year(to_year)

        # 3. Calculate adjusted value
        # Formula: (Target CPI / Start CPI) * Amount
        return (cpi_end / cpi_start) * amount

    finally:
        conn.close()


if __name__ == "__main__":
    # Example: convert $100 from 1945 into the latest year the database supports.
    try:
        latest_year = get_latest_year()
        value = get_adjusted_usd(100, 1945)
        print(f"$100 in 1945 is equivalent to ${value:.2f} in {latest_year}")  # noqa: T201
    except (FileNotFoundError, ValueError) as e:
        print(e)  # noqa: T201
