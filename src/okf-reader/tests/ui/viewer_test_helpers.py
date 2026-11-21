# ruff: noqa: SLF001
# cspell:ignore ffcc pytestmark
"""What the viewer's tests share that is not a fixture: pages, patchers and look-ups.

A viewer needs a Kivy window, so each test file here carries ``NEEDS_A_WINDOW`` as its
``pytestmark``: skipped where there is none (KIVY_HEADLESS_CI). Every CI runner draws
one now (macOS on Apple's software renderer, Windows through ANGLE) and runs them.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.treeview import TreeViewLabel
from okf_reader.core.search import SearchHit
from okf_reader.ui import viewer as viewer_module
from okf_reader.ui.viewer import LAZY_TABLE_MIN_ROWS
from okf_reader.ui.widgets import TABLE_FONT_NAME

if TYPE_CHECKING:
    from pathlib import Path

    from okf_reader.ui.viewer import OKFViewer

NEEDS_A_WINDOW = pytest.mark.skipif(
    os.environ.get("KIVY_HEADLESS_CI", "") == "1",
    reason="a viewer needs a Kivy window, and headless CI has none",
)

HOME_PAGE = """# Home

See [the page](concept/a.md).[^note]

[^note]: A note that links to [the page](concept/a.md).
"""


A_PAGE = """---
title: A
---
# A

Body.
"""


def window_patched() -> Any:  # noqa: ANN401 — a patcher, as patch.object returns it
    """Patch the realized window the viewer imports where it needs it."""
    import kivy.core.window as window_module  # noqa: PLC0415 — importing it makes the window

    return patch.object(window_module, "Window")


def remove_popups_left_open() -> None:
    """Take any popup a test opened off the window, at once.

    A dismissed popup animates out, and a unit test never ticks the clock, so it
    would stay on the window for every test after; the main screen hands an open
    popup every key, and its key tests then fail (a random-order run found it).
    """
    from kivy.core.window import Window  # noqa: PLC0415 — the realized window

    for widget in list(Window.children):
        if isinstance(widget, ModalView):
            Window.remove_widget(widget)


def open_footnote(viewer: OKFViewer) -> None:
    """Press the home page's footnote marker, as a tap or Enter on it does."""
    note_label = next(lbl for lbl, ref, _ in viewer._page_links if ref == "fn:note")
    viewer._on_ref(note_label, "fn:note")


def page_of(viewer: OKFViewer) -> str:
    return viewer.history[-1].path.relative_to(viewer.bundle).as_posix()


# A long table's rows, as the core pads them: a colored header, one- and two-line rows.
LONG_TABLE_ROWS = [
    "[color=ffcc00]Title             Year[/color]",
    *(
        f"Story {i:<12}{1940 + i % 30}" if i % 7 else f"Story {i:<12}{1940 + i % 30}\n  (cont.)"
        for i in range(1, LAZY_TABLE_MIN_ROWS + 150)
    ),
]


def eager_heights(rows: list[str], font_size: int) -> list[int]:
    """Each row's height as the eager table's own row Labels take it."""
    heights = []
    for row in rows:
        lbl = Label(text=row, markup=True, font_name=TABLE_FONT_NAME, font_size=font_size)
        lbl.texture_update()
        heights.append(lbl.texture_size[1])
    return heights


def concept_node(viewer: OKFViewer) -> Any:  # noqa: ANN401
    """Return the tree's one directory node, the bundle's ``concept`` folder."""
    return next(n for n in viewer.tree.iterate_open_nodes() if n.text == "Concept")


def left_texts(viewer: OKFViewer) -> list[str]:
    return [w.text for w in viewer._left_body.walk(restrict=True) if isinstance(w, Label)]


class Hits:
    """A ready search provider with fixed hits."""

    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits

    def search(self, query: str) -> list[SearchHit]:  # noqa: ARG002
        return self.hits


def hit(path: Path, title: str) -> SearchHit:
    return SearchHit(path=path, title=title, breadcrumb="", matched_on="title", score=1)


def clock_patched() -> Any:  # noqa: ANN401 — a patcher, as patch.object returns it
    """Hold what the viewer schedules for the next frame, for a test to run by hand."""
    return patch.object(viewer_module, "Clock")


def run_scheduled(clock: MagicMock) -> None:
    """Run each callback scheduled so far, once: one frame."""
    calls = list(clock.schedule_once.call_args_list)
    clock.schedule_once.reset_mock()
    for call in calls:
        call.args[0](0)


def tree_node(viewer: OKFViewer, text: str) -> Any:  # noqa: ANN401
    return next(n for n in viewer.tree.iterate_open_nodes() if n.text == text)


def node_at(top: float) -> TreeViewLabel:
    """Return a tree node whose top edge is at `top`."""
    node = TreeViewLabel(text="A")
    node.top = top
    return node
