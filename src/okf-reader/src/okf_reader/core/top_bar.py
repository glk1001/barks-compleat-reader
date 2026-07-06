"""Kivy-free description of the viewer's action bar.

The embedding app's seam for dressing the bar across the top of the reader —
the Barks launcher fills it with the app icon, the Carl Barks-font title
markup, and the stock go-back icon, so the standalone okf window matches the
Barks Reader's action-bar look. Same port idiom as `okf_reader.core.actions`:
okf_reader knows nothing about any particular app's icons or fonts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class TopBarSpec:
    """How the embedding app wants the viewer's action bar dressed.

    ``title_markup`` may carry kivy markup (font/size tags). ``height`` is in
    raw units; the UI dp-scales it. A click on the ``icon_path`` image shows
    the bundle's home page. ``back_icon_path``/``close_icon_path`` turn the
    Back and Quit buttons into icon buttons; without them they stay text
    buttons. Quit matters because the standalone app replaces the OS window
    titlebar with this bar (the Barks Reader convention), so the bar carries
    the only close control.
    """

    title_markup: str = "OKF Reader"
    title_color: tuple[float, float, float, float] = (1, 1, 1, 1)
    icon_path: Path | None = None
    back_icon_path: Path | None = None
    close_icon_path: Path | None = None
    height: int = 40
