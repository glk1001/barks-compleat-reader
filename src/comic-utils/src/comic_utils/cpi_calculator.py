import sqlite3
from pathlib import Path

CPI_DATABASE_PATH = Path(__file__).parent / "cpi.db"
CURRENT_YEAR = 2025


def get_adjusted_usd(
    amount: float,
    base_year: int,
    to_year: int = CURRENT_YEAR,
    db_path: Path = CPI_DATABASE_PATH,
    series_id: str = "CUUR0000SA0",
) -> float:
    """Convert USD from a historical year to a target year using a provided cpi.db file.

    Args:
        amount (float): The amount of money to convert.
        base_year (int): The year the amount originates from.
        to_year (int): The target year to convert to.
        db_path (str): File path to the 'cpi.db' SQLite database.
        series_id (str): The CPI series to use.
                         Default is 'CUUR0000SA0' (All items in U.S. city average,
                         all urban consumers).

    Returns:
        float: The adjusted dollar amount.

    """
    if not db_path.is_file:
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
            msg = f"No CPI data found for year {year} with series {series_id}"
            raise ValueError(msg)

        return result[0]

    try:
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
    path_to_db = CPI_DATABASE_PATH

    # Example: Convert $100 from 1980 to current value
    try:
        value = get_adjusted_usd(100, 1945, CURRENT_YEAR, path_to_db)
        print(f"$100 in 1980 is equivalent to ${value:.2f} in 2023")  # noqa: T201
    except Exception as e:  # noqa: BLE001
        print(e)  # noqa: T201
