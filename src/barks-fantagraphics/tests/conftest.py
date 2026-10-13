"""Make this directory importable, for the data the ini checks share.

The tests run under ``--import-mode=importlib``, which puts no test directory on
``sys.path``, so a module beside the tests (``title_page_allowlists``) is reached by
putting the directory there, as ``scripts/tests`` does for the scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
