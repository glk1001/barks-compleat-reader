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


def search_results(count: int, text: str) -> None:
    """Log that the sidebar shows `count` results (0 is the no-match note) for `text`."""
    Logger.debug(log_markers.SEARCH_RESULTS.format(count=count, text=text))


def search_focused() -> None:
    """Log that the search box took the keyboard (Up off the sidebar's top, or Ctrl+F)."""
    Logger.debug(log_markers.SEARCH_FOCUSED)


def search_left() -> None:
    """Log that Down left the search box for the sidebar."""
    Logger.debug(log_markers.SEARCH_LEFT)


def search_cleared() -> None:
    """Log that the search was cleared and the sidebar shows the tree again."""
    Logger.debug(log_markers.SEARCH_CLEARED)


def link_focus(ref: str) -> None:
    """Log that Up/Down moved the page's link highlight to the link to `ref`.

    A step that only scrolls logs nothing; a test steps until this line names
    the link it wants.
    """
    Logger.debug(log_markers.LINK_FOCUS.format(ref=ref))


def footnote_opened(ref: str) -> None:
    """Log that footnote `ref` (``fn:<label>``) is showing in its popup, which now owns the keys."""
    Logger.debug(log_markers.FOOTNOTE_OPENED.format(ref=ref))


def footnote_closed() -> None:
    """Log that the footnote popup was dismissed and the keys are the page's again."""
    Logger.debug(log_markers.FOOTNOTE_CLOSED)


def tree_branch_opened(node_text: str) -> None:
    """Log that the sidebar tree's directory `node_text` opened, its children listed."""
    Logger.debug(log_markers.TREE_BRANCH_OPENED.format(node=node_text))


def tree_branch_closed(node_text: str) -> None:
    """Log that the sidebar tree's directory `node_text` closed.

    Opening one branch closes every other (one open path at a time), so an
    open can be followed by closes of branches the key never touched.
    """
    Logger.debug(log_markers.TREE_BRANCH_CLOSED.format(node=node_text))


def contrast(on: bool) -> None:
    """Log that the Contrast toggle turned the page's text bands up (on) or back down (off)."""
    Logger.debug(log_markers.CONTRAST.format(state="on" if on else "off"))
