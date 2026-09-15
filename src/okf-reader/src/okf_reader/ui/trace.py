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

if TYPE_CHECKING:
    from pathlib import Path

PREFIX = "OKFViewer"


def _rel(bundle: Path, path: Path) -> str:
    try:
        return str(path.relative_to(bundle))
    except ValueError:
        return path.name


def page_shown(bundle: Path, path: Path, history_depth: int) -> None:
    """Log that a page has been rendered and is on show."""
    Logger.info(f"{PREFIX}: Showed page '{_rel(bundle, path)}' (history depth {history_depth}).")


def focus_region(name: str) -> None:
    """Log that the navigation keys now belong to `name` (PAGE, SIDEBAR or TOP_BAR)."""
    Logger.debug(f"{PREFIX}: Focus region {name}.")


def back_to(bundle: Path, path: Path) -> None:
    """Log that Back popped the history and is showing `path` again."""
    Logger.info(f"{PREFIX}: Back to '{_rel(bundle, path)}'.")


def back_exit() -> None:
    """Log that Back reached the history's root and is handing control to the host."""
    Logger.info(f"{PREFIX}: Back at history root; exiting.")


def tree_settled(node_text: str, frames: int) -> None:
    """Log that the sidebar tree settled and the selected node was scrolled into view."""
    Logger.debug(f"{PREFIX}: Tree settled on '{node_text}' after {frames} frames.")


def page_action(label: str) -> None:
    """Log that the page's contextual action was run."""
    Logger.info(f"{PREFIX}: Page action '{label}'.")
