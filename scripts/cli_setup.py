"""Script-specific CLI setup wrapping comic_utils.cli_setup."""

from pathlib import Path

import log_setup as _log_setup
from comic_utils.cli_setup import init_logging as _init_logging

_LOG_CONFIG = Path(__file__).parent / "log-config.yaml"


def init_logging(app_logging_name: str, log_filename: str, log_level_str: str) -> None:
    """Configure loguru logging for scripts."""
    _init_logging(_log_setup, _LOG_CONFIG, app_logging_name, log_filename, log_level_str)
