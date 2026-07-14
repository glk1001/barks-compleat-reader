"""Kivy-free per-page contextual actions for the OKF reader.

The embedding app's seam for offering one action on the page being viewed —
e.g. the Barks launcher's "Read Comic" button on a story page, which the
future embedded reader will re-implement as an in-app screen switch. Same
port idiom as `okf_reader.core.backgrounds.ImageProvider`: okf_reader knows
nothing about any particular bundle's pages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@dataclass(frozen=True)
class PageAction:
    """One offered action: a button label and the callable it triggers.

    ``icon_path`` renders the bar button as an icon instead of the label
    (the label still names the action for non-visual uses).
    """

    label: str
    run: Callable[[], None]
    icon_path: Path | None = None


class PageActionProvider(Protocol):
    """Decides whether the current page gets a contextual action."""

    def action_for(self, frontmatter: dict[str, Any], page_path: Path) -> PageAction | None:
        """Return the page's action, or None for no button."""
        ...
