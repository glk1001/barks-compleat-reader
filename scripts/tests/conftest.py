"""Make the scripts directory importable, and share the stub driver the script tests drive.

The scripts are standalone files rather than a package - they are run directly,
not imported by the app - so there is no installed module path to import them by.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from gui_driver import Driver  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable
    from unittest.mock import MagicMock


@pytest.fixture
def new_stub_driver() -> Callable[[], Driver]:
    """Make a Driver with no probe attached, for exercising its own logic against.

    A factory, for a helper that needs a fresh driver per call: menu focus is
    sticky on a driver, so two runs on one would see each other's moves. The
    class-level defaults stand in for what ``__init__`` would set.
    """

    def _make() -> Driver:
        with patch.object(Driver, "__init__", lambda _self, *_a, **_kw: None):
            return Driver()

    return _make


@pytest.fixture
def stub_driver(new_stub_driver: Callable[[], Driver]) -> Driver:
    """One stub driver for the test."""
    return new_stub_driver()


@pytest.fixture
def keys_pressed() -> Callable[[MagicMock], list[str]]:
    """Every key a patched ``Driver.key`` was given, in order."""

    def _keys(key: MagicMock) -> list[str]:
        return [k for call in key.call_args_list for k in call.args]

    return _keys
