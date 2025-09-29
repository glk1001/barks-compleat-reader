from comic_utils import cpi_defaults

from barks_fantagraphics.comics_consts import DATA_DIR

cpi_defaults.CUSTOM_CPI_DB_PATH = DATA_DIR / "cpi.db"

assert cpi_defaults.CUSTOM_CPI_DB_PATH.is_file()
