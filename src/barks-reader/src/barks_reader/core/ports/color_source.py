"""Color-source port — abstracts the three `RandomColorTint`s used for view tinting."""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from barks_reader.core.reader_colors import Color


class PaletteId(Enum):
    """Identifies which tint palette a caller wants a color from."""

    TOP_VIEW = auto()
    FUN = auto()
    TITLE = auto()


@runtime_checkable
class ColorSource(Protocol):
    """Generates a tint color for one of the named palettes.

    Production wraps three `RandomColorTint` instances configured to match the
    historical behavior of `BackgroundViews`. Test adapter
    (`core.testing.fakes.ScriptedColorSource`) cycles through a fixed palette.
    """

    def next_color(self, palette: PaletteId) -> Color:
        """Return the next color for the given palette.

        Args:
            palette: Which tint palette to draw from.

        Returns:
            An RGBA color tuple with each component in [0.0, 1.0].

        """
        ...
