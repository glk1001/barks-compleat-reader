"""Central palette for the Barks Reader UI.

Colors here are derived from Barks' own art (see docs/design-review-2026-07.md).
The scrim values are neutral grey multiplies applied to background-art images:
a grey multiply darkens the art without shifting its hue, so the art shows its
true colors under a constant, legibility-preserving dim — replacing the old
per-navigation random tints.
"""

from .ports import PaletteId
from .reader_colors import Color

SCRIM_TOP_VIEW: Color = (0.33, 0.33, 0.33, 1.0)
SCRIM_TITLE: Color = (0.45, 0.45, 0.45, 1.0)
SCRIM_FUN: Color = (0.95, 0.95, 0.95, 1.0)

FIXED_SCRIMS: dict[PaletteId, Color] = {
    PaletteId.TOP_VIEW: SCRIM_TOP_VIEW,
    PaletteId.FUN: SCRIM_FUN,
    PaletteId.TITLE: SCRIM_TITLE,
}
