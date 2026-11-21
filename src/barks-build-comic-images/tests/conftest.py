"""What the page builder's tests share: the comics database, and ``build_test_helpers``."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from barks_fantagraphics.comics_database import ComicsDatabase

# The importlib import mode adds no path of its own.
_TESTS_DIR = str(Path(__file__).resolve().parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)


@pytest.fixture(scope="session")
def comics_database() -> ComicsDatabase:
    """Return the comics database, read once for every test that looks a comic up."""
    return ComicsDatabase(for_building_comics=False)
