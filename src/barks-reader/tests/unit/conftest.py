"""Conftest that auto-skips Kivy-UI tests when no OpenGL context is available.

On headless CI runners (macOS, Windows) without a display server or GPU,
Kivy cannot create an OpenGL window. Tests that import from barks_reader.ui
or kivy are skipped when the environment variable KIVY_HEADLESS_CI is set.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_HEADLESS_CI = os.environ.get("KIVY_HEADLESS_CI", "") == "1"

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
        with Path(mod_file).open() as f:
            source = f.read()
    except OSError:
        return False
    return any(prefix in source for prefix in ("from barks_reader.ui", "from kivy"))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:  # noqa: ARG001
    """Skip UI tests on headless CI where Kivy cannot create an OpenGL context."""
    if not _HEADLESS_CI:
        return

    skip_marker = pytest.mark.skip(reason="Kivy UI tests skipped on headless CI (no OpenGL)")
    for item in items:
        if _test_imports_ui(item):
            item.add_marker(skip_marker)
