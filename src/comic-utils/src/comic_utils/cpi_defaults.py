from pathlib import Path

from comic_utils.comic_consts import IS_PYINSTALLER_BUNDLE, PYINSTALLER_BUNDLED_MAIN_DIR

CPI_DB_PATH = (
    PYINSTALLER_BUNDLED_MAIN_DIR / __package__.replace("_", "-") / "src" / __package__
    if IS_PYINSTALLER_BUNDLE
    else Path(__file__).parent
) / "cpi.db"

assert CPI_DB_PATH.is_file(), f'cpi.db file, "{CPI_DB_PATH}" does not exist.'

DEFAULT_SERIES_ID = "CUUR0000SA0"
DEFAULTS_SERIES_ATTRS = {
    "survey": "All urban consumers",
    "seasonally_adjusted": False,
    "periodicity": "Monthly",
    "area": "U.S. city average",
    "items": "All items",
}
