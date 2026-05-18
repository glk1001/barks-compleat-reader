"""Production `ColorSource` adapter — wraps three `RandomColorTint`s.

The defaults reproduce the historical configuration used by `BackgroundViews`:
distinct tint distributions per palette and a custom alpha range for the title
palette.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from barks_reader.core.ports import PaletteId
from barks_reader.core.reader_colors import RandomColorTint

if TYPE_CHECKING:
    from barks_reader.core.reader_colors import Color


def _make_default_tints() -> dict[PaletteId, RandomColorTint]:
    top_view = RandomColorTint(30, 50)
    fun = RandomColorTint(80, 50)

    title = RandomColorTint(30, 70)
    title.set_full_color_alpha_range(100, 150)
    title.set_alpha_range(150, 200)

    return {
        PaletteId.TOP_VIEW: top_view,
        PaletteId.FUN: fun,
        PaletteId.TITLE: title,
    }


class TintColorSource:
    """A `ColorSource` backed by `RandomColorTint` instances."""

    def __init__(self, tints: dict[PaletteId, RandomColorTint] | None = None) -> None:
        self._tints = tints if tints is not None else _make_default_tints()

    def next_color(self, palette: PaletteId) -> Color:
        """Return a random color from the tint configured for *palette*."""
        return self._tints[palette].get_random_color()
