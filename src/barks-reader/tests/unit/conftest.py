"""Conftest that auto-skips Kivy-UI tests when no OpenGL context is available.

On headless CI runners (macOS, Windows) without a display server or GPU,
Kivy cannot create an OpenGL window. Tests that import from barks_reader.ui
or kivy are skipped when the environment variable KIVY_HEADLESS_CI is set.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from itertools import pairwise
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_HEADLESS_CI = os.environ.get("KIVY_HEADLESS_CI", "") == "1"


@pytest.fixture
def mock_font_manager() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_user_error_handler() -> MagicMock:
    return MagicMock()


# The shipped cpi.db is a 65 MB git-lfs object. A bare checkout - CI's, or a clone
# without `git lfs install` - gets the pointer file instead, so no test may depend
# on the real database. This stand-in is shaped like the real table at the years the
# payment ledger spans (values read off the real one), and covers the same year
# range, so the figures built on it behave like the shipped ones: the same
# "in 2026 dollars" labels, and inflation multiples of the same order.
_CPI_ANCHORS: tuple[tuple[int, float], ...] = (
    (1913, 9.88),
    (1942, 16.33),
    (1950, 24.07),
    (1966, 32.45),
    (1973, 44.40),
    (2026, 330.72),
)


def _interpolated_cpi(year: int) -> float:
    """Interpolate the CPI linearly between the two anchor years around ``year``."""
    for (y0, v0), (y1, v1) in pairwise(_CPI_ANCHORS):
        if y0 <= year <= y1:
            return v0 + (v1 - v0) * (year - y0) / (y1 - y0)
    msg = f"year {year} is outside the fixture's range"
    raise ValueError(msg)


@pytest.fixture(scope="session")
def cpi_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a small CPI database to stand in for the git-lfs one, one row per year."""
    db_path = tmp_path_factory.mktemp("cpi") / "cpi.db"
    first_year, last_year = _CPI_ANCHORS[0][0], _CPI_ANCHORS[-1][0]

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE indexes (year INTEGER, series TEXT, value REAL)")
        conn.executemany(
            "INSERT INTO indexes VALUES (?, ?, ?)",
            [
                (year, "CUUR0000SA0", _interpolated_cpi(year))
                for year in range(first_year, last_year + 1)
            ],
        )
        conn.commit()
    finally:
        conn.close()

    return db_path


_UI_IMPORT_PREFIXES = ("barks_reader.ui", "kivy.uix", "kivy.core.window")


def _test_imports_ui(item: pytest.Item) -> bool:
    """Return True if the test's module imports Kivy UI code."""
    module = getattr(item, "module", None)
    if module is None:
        return False
    # Check the module's direct imports (already loaded into sys.modules).
    for name in list(sys.modules):
        if any(name.startswith(prefix) for prefix in _UI_IMPORT_PREFIXES):
            # The module itself might not be the one importing UI code,
            # but checking the test file's source is more reliable.
            break
    else:
        return False

    # More precise: check the test file's own imports.
    mod_file = getattr(module, "__file__", "") or ""
    try:
        with Path(mod_file).open(encoding="utf-8") as f:
            source = f.read()
    except OSError:
        return False
    return any(prefix in source for prefix in ("from barks_reader.ui", "from kivy"))


# noinspection PyUnusedLocal
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:  # noqa: ARG001
    """Skip UI tests on headless CI where Kivy cannot create an OpenGL context."""
    if not _HEADLESS_CI:
        return

    skip_marker = pytest.mark.skip(reason="Kivy UI tests skipped on headless CI (no OpenGL)")
    for item in items:
        if _test_imports_ui(item):
            item.add_marker(skip_marker)
