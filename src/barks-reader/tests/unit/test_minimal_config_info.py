"""Unit tests for :mod:`barks_reader.core.minimal_config_info`.

The minimal-config loader reads just enough of the INI file to create
the splash window before the rest of the reader is initialized. If any
step fails, it must fall back to the default :class:`MinimalConfigOptions`
rather than propagating the error.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from barks_reader.core.minimal_config_info import (
    MinimalConfigOptions,
    get_minimal_config_options,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write_ini(
    ini_path: Path,
    *,
    win_height: int = 800,
    win_left: int = 100,
    win_top: int = 50,
    log_level: str = "DEBUG",
) -> None:
    ini_path.write_text(
        "[Barks Reader]\n"
        f"main_window_height = {win_height}\n"
        f"main_window_left = {win_left}\n"
        f"main_window_top = {win_top}\n"
        f"log_level = {log_level}\n"
    )


def _make_reader_files_tree(app_data_dir: Path) -> Path:
    """Create the ``Reader Files/Various`` tree with the two required PNGs."""
    various = app_data_dir / "Reader Files" / "Various"
    various.mkdir(parents=True)
    (various / "error-background.png").touch()
    (various / "success-background.png").touch()
    return various


def _make_cfg_info(app_data_dir: Path, ini_path: Path) -> MagicMock:
    cfg = MagicMock()
    cfg.app_config_path = ini_path
    cfg.app_data_dir = app_data_dir
    return cfg


class TestMinimalConfigOptionsDefaults:
    def test_default_values(self) -> None:
        opts = MinimalConfigOptions()
        assert opts.error_background_path is None
        assert opts.success_background_path is None
        assert opts.win_height == 0
        assert opts.win_left == -1
        assert opts.win_top == -1
        assert opts.log_level == logging.getLevelName(logging.INFO)


class TestGetMinimalConfigOptions:
    def test_reads_values_from_ini_and_resolves_backgrounds(self, tmp_path: Path) -> None:
        various = _make_reader_files_tree(tmp_path)
        ini = tmp_path / "app.ini"
        _write_ini(ini, win_height=1024, win_left=5, win_top=7, log_level="DEBUG")

        opts = get_minimal_config_options(_make_cfg_info(tmp_path, ini))

        assert opts.win_height == 1024  # noqa: PLR2004
        assert opts.win_left == 5  # noqa: PLR2004
        assert opts.win_top == 7  # noqa: PLR2004
        assert opts.log_level == "DEBUG"
        assert opts.error_background_path == various / "error-background.png"
        assert opts.success_background_path == various / "success-background.png"

    def test_returns_defaults_when_ini_missing(self, tmp_path: Path) -> None:
        # No INI file and no reader-files tree; loader must not raise.
        missing_ini = tmp_path / "does_not_exist.ini"
        opts = get_minimal_config_options(_make_cfg_info(tmp_path, missing_ini))

        assert opts == MinimalConfigOptions()

    def test_returns_defaults_when_required_background_missing(self, tmp_path: Path) -> None:
        # Reader files tree exists but the required PNGs are absent → check_files raises
        # → function must swallow the error and return defaults.
        (tmp_path / "Reader Files" / "Various").mkdir(parents=True)
        ini = tmp_path / "app.ini"
        _write_ini(ini)

        opts = get_minimal_config_options(_make_cfg_info(tmp_path, ini))

        assert opts == MinimalConfigOptions()

    def test_returns_defaults_when_ini_has_wrong_type(self, tmp_path: Path) -> None:
        _make_reader_files_tree(tmp_path)
        ini = tmp_path / "app.ini"
        # main_window_height must parse as an int; "banana" should trigger the fallback.
        ini.write_text(
            "[Barks Reader]\n"
            "main_window_height = banana\n"
            "main_window_left = 0\n"
            "main_window_top = 0\n"
            "log_level = INFO\n"
        )

        opts = get_minimal_config_options(_make_cfg_info(tmp_path, ini))

        assert opts == MinimalConfigOptions()
