"""Log lines marking the viewer's user-visible transitions, for tests and diagnosis.

The viewer logs through Kivy's own logger so that ``okf_reader`` takes on no new
dependency: a host that routes Kivy's log records into its own log (the Barks
Reader does) sees these lines there, prefixed ``OKFViewer:``; the standalone
reader sees them on Kivy's console. Each fires once per user action, so a test
can count occurrences and wait for a new one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kivy.logger import Logger

from okf_reader.core import log_markers

if TYPE_CHECKING:
    from pathlib import Path

PREFIX = log_markers.PREFIX


def _rel(bundle: Path, path: Path) -> str:
    try:
        return path.relative_to(bundle).as_posix()  # the same line on Windows
    except ValueError:
        return path.name


def page_shown(bundle: Path, path: Path, history_depth: int) -> None:
    """Log that a page has been rendered and is on show."""
    Logger.info(log_markers.PAGE_SHOWN.format(page=_rel(bundle, path), depth=history_depth))


def focus_region(name: str) -> None:
    """Log that the navigation keys now belong to `name` (PAGE, SIDEBAR or TOP_BAR)."""
    Logger.debug(log_markers.FOCUS_REGION.format(name=name))


def focus_ring(widget_name: str) -> None:
    """Log that the keyboard focus ring has been drawn on `widget_name`.

    Fires once per focus move within a region (a top-bar button, a sidebar
    result row), so a test can step the focus and wait on each step.
    """
    Logger.debug(log_markers.FOCUS_RING.format(widget=widget_name))


def tree_focus(node_text: str) -> None:
    """Log that the sidebar tree's selection band moved to `node_text`.

    The tree shows keyboard focus as its selection band, not a drawn ring, so
    this is the sidebar's counterpart to `focus_ring` while the tree is showing.
    """
    Logger.debug(log_markers.TREE_FOCUS.format(node=node_text))


def back_to(bundle: Path, path: Path) -> None:
    """Log that Back popped the history and is showing `path` again."""
    Logger.info(log_markers.BACK_TO.format(page=_rel(bundle, path)))


def back_exit() -> None:
    """Log that Back reached the history's root and is handing control to the host."""
    Logger.info(log_markers.BACK_EXIT)


def tree_settled(node_text: str, frames: int) -> None:
    """Log that the sidebar tree settled and the selected node was scrolled into view."""
    Logger.debug(log_markers.TREE_SETTLED.format(node=node_text, frames=frames))


def page_action(label: str) -> None:
    """Log that the page's contextual action was run."""
    Logger.info(log_markers.PAGE_ACTION.format(label=label))
