"""Color types and the fixed color source used for background-art scrims."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .ports import PaletteId

Color = tuple[float, float, float, float]


class FixedColorSource:
    """A `ColorSource` that returns one fixed color per palette.

    Replaces the old `RandomColorTint`: background art is shown in true color
    under a constant neutral scrim instead of a per-navigation random hue wash.
    """

    def __init__(self, colors: Mapping[PaletteId, Color]) -> None:
        """Store the fixed color for each palette.

        Args:
            colors: The color to return for each `PaletteId`.

        """
        self._colors = dict(colors)

    def next_color(self, palette: PaletteId) -> Color:
        """Return the fixed color for the given palette.

        Args:
            palette: Which palette to draw from.

        Returns:
            An RGBA color tuple with each component in [0.0, 1.0].

        """
        return self._colors[palette]
