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
    from collections.abc import Callable
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
    the only close control. The ``contrast_*`` pair (both or neither) likewise
    turns the Contrast toggle into an icon button: the "on" icon shows while
    the toggle is up, the "off" icon while it is down — each depicts what
    pressing will do. (A page action's icon rides on ``PageAction`` instead;
    the bar only hosts that button.)

    ``on_close`` is what the Quit button does: the standalone app leaves it
    None (the viewer falls back to stopping the running app); an embedding
    app supplies its own leave-this-screen action instead.

    The style fields default to the bar's standalone look (mirroring the
    Barks Reader's kv action-bar idiom): a dark opaque band, thin grey
    separators, a fixed-width icon container, and a wide separator fencing
    the Quit button off from the working buttons (the 1dp line sits centered,
    leaving dead space on each side). ``icon_width``/``quit_fence_width`` are
    raw units like ``height``; the UI dp-scales them.
    """

    title_markup: str = "OKF Reader"
    title_color: tuple[float, float, float, float] = (1, 1, 1, 1)
    icon_path: Path | None = None
    back_icon_path: Path | None = None
    contrast_on_icon_path: Path | None = None
    contrast_off_icon_path: Path | None = None
    close_icon_path: Path | None = None
    height: int = 40
    on_close: Callable[[], None] | None = None
    bg_color: tuple[float, float, float, float] = (0.12, 0.12, 0.12, 1)
    separator_color: tuple[float, float, float, float] = (0.3, 0.3, 0.3, 1)
    icon_width: int = 70
    quit_fence_width: int = 17
