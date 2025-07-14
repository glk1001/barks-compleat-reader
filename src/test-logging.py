import logging
import os

# os.environ["KIVY_LOG_MODE"] = "PYTHON"
os.environ["KIVY_LOG_MODE"] = "MIXED"

from barks_fantagraphics.comics_logging import setup_logging


setup_logging(log_level=logging.DEBUG)

logging.debug("Debug message.")
logging.info("Info message.")
logging.warning("Warning message.")
logging.error("Error message.")
logging.critical("Critical message.")
logging.fatal("Fatal message.")
