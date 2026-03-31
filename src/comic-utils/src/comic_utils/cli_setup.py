"""Shared CLI setup helpers to eliminate boilerplate across entry points."""

from pathlib import Path
from types import ModuleType

from loguru_config import LoguruConfig


def init_logging(
    log_setup: ModuleType,
    log_config_yaml: Path,
    app_logging_name: str,
    log_filename: str,
    log_level_str: str,
) -> None:
    """Configure loguru logging for a CLI entry point."""
    log_setup.log_level = log_level_str  # ty: ignore[unresolved-attribute]
    log_setup.log_filename = log_filename  # ty: ignore[unresolved-attribute]
    log_setup.APP_LOGGING_NAME = app_logging_name  # ty: ignore[unresolved-attribute]
    LoguruConfig.load(log_config_yaml)
