"""The real database, once, and this directory on ``sys.path``.

The tests run under ``--import-mode=importlib``, which puts no test directory on
``sys.path``, so a module beside the tests (``title_page_allowlists``,
``panel_factories``) is reached by putting the directory there, as ``scripts/tests``
does for the scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from barks_fantagraphics.comics_database import ComicsDatabase

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))


@pytest.fixture(scope="session")
def db() -> ComicsDatabase:
    """Read the story-titles ini files into the real ComicsDatabase; no comic dirs needed."""
    return ComicsDatabase(for_building_comics=False)
