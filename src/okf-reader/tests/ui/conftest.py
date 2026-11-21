"""What the viewer's tests share: a small bundle, a viewer over it, and no index thread."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

# The importlib import mode adds no path of its own.
_TESTS_DIR = str(Path(__file__).parent)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from okf_reader.ui import viewer as viewer_module  # noqa: E402
from okf_reader.ui.viewer import OKFViewer  # noqa: E402
from viewer_test_helpers import A_PAGE, HOME_PAGE, remove_popups_left_open  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    """Make a two-page bundle: a home page with a link and a footnote, and the linked page."""
    root = tmp_path / "bundle"
    (root / "concept").mkdir(parents=True)
    (root / "index.md").write_text(HOME_PAGE, encoding="utf-8")
    (root / "concept" / "a.md").write_text(A_PAGE, encoding="utf-8")
    return root


@pytest.fixture(autouse=True)
def index_worker() -> Iterator[MagicMock]:
    """Keep every test's viewer from starting the thread that builds the search index.

    A real one outlives its test, and what it logs then lands in another's log.
    """
    with patch.object(viewer_module.threading, "Thread") as thread:
        yield thread


@pytest.fixture
def viewer(bundle: Path) -> Iterator[OKFViewer]:
    okf_viewer = OKFViewer(bundle)
    yield okf_viewer
    # A focused box holds the window's one keyboard until it lets go, and the main
    # screen leaves every key to a focused text input: its key tests then fail (a
    # random-order run found it, after focus_search's test).
    okf_viewer.search_field.focus = False
    remove_popups_left_open()


@pytest.fixture
def deep_bundle(bundle: Path) -> Path:
    """Add a second folder, with a folder inside it, to the bundle."""
    (bundle / "other" / "deep").mkdir(parents=True)
    (bundle / "other" / "b.md").write_text("# B\n", encoding="utf-8")
    (bundle / "other" / "deep" / "c.md").write_text("# C\n", encoding="utf-8")
    return bundle
