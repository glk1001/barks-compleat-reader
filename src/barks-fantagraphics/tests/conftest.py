"""The real database, once, and this directory on ``sys.path``.

The tests run under ``--import-mode=importlib``, which puts no test directory on
``sys.path``, so a module beside the tests (``title_page_allowlists``,
``panel_factories``) is reached by putting the directory there, as ``scripts/tests``
does for the scripts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from barks_fantagraphics.comics_database import ComicsDatabase
from barks_fantagraphics.ocr_file_paths import OCR_PRELIM_DIR_ENV_VAR

# The prelim-dir override points tools at a work tree, and a shell that has it set would
# send these tests there too: two fail, or with a missing directory collection stops at
# test_ocr_json_files' import. Dropped here, at import, because a fixture runs after
# collection. The tests of the override set it themselves.
os.environ.pop(OCR_PRELIM_DIR_ENV_VAR, None)

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))


@pytest.fixture(scope="session")
def db() -> ComicsDatabase:
    """Read the story-titles ini files into the real ComicsDatabase; no comic dirs needed."""
    return ComicsDatabase(for_building_comics=False)
