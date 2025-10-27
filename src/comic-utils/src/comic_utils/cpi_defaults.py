from pathlib import Path

CPI_DB_PATH = Path(__file__).parent / "cpi.db"
assert CPI_DB_PATH.is_file(), f'cpi.db file, "{CPI_DB_PATH}" does not exist.'

DEFAULT_SERIES_ID = "CUUR0000SA0"
DEFAULTS_SERIES_ATTRS = {
    "survey": "All urban consumers",
    "seasonally_adjusted": False,
    "periodicity": "Monthly",
    "area": "U.S. city average",
    "items": "All items",
}
