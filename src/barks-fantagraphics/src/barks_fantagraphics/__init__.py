from comic_utils import cpi_wrapper

from barks_fantagraphics.comics_consts import DATA_DIR

cpi_wrapper.CUSTOM_CPI_DB_PATH = DATA_DIR / "cpi.db"

assert cpi_wrapper.CUSTOM_CPI_DB_PATH.is_file()
