"""Color themes for the Barks Reader UI.

All theme colors were extracted from Barks' own art (see
docs/design-review-2026-07.md). The scrim values are neutral grey multiplies
applied to background-art images: a grey multiply darkens the art without
shifting its hue, so the art shows its true colors under a constant,
legibility-preserving dim — replacing the old per-navigation random tints.

The active theme is selected by the "Color Theme" setting and applied via
`set_active_theme` during app start-up, before any widgets are built. UI code
must therefore read colors lazily — `theme().text_title` at widget-construction
time — never bind them at module-import time.
"""

from dataclasses import dataclass

from .ports import PaletteId
from .reader_colors import Color

SCRIM_TOP_VIEW: Color = (0.65, 0.65, 0.65, 1.0)
SCRIM_TITLE: Color = (0.45, 0.45, 0.45, 1.0)
SCRIM_FUN: Color = (0.95, 0.95, 0.95, 1.0)

FIXED_SCRIMS: dict[PaletteId, Color] = {
    PaletteId.TOP_VIEW: SCRIM_TOP_VIEW,
    PaletteId.FUN: SCRIM_FUN,
    PaletteId.TITLE: SCRIM_TITLE,
}


@dataclass(frozen=True, slots=True)
class ReaderTheme:
    """A named UI color theme."""

    name: str
    accent_selection: Color  # tree/selection bar
    app_title: Color  # action-bar title (also the wiki top bar)
    text_title: Color  # story-title text in tree rows and search results
    text_secondary: Color  # issue/date lines and quiet info text
    row_stripe_even: Color
    row_stripe_odd: Color
    search_heading: Color  # "Title:"/"Tag:"/"Words:" labels and accent labels
    tag_chip_bg: Color
    focus_ring: Color
    danger: Color  # quit accents


MASTHEAD = ReaderTheme(
    name="Masthead",
    accent_selection=(0.65, 0.23, 0.16, 0.85),  # Scrooge-coat red
    app_title=(0.98, 0.82, 0.50, 1.0),  # coin gold
    text_title=(0.98, 0.82, 0.50, 1.0),
    text_secondary=(0.94, 0.90, 0.80, 1.0),  # newsprint cream
    row_stripe_even=(0.14, 0.08, 0.05, 0.45),
    row_stripe_odd=(0.26, 0.14, 0.10, 0.45),
    search_heading=(0.82, 0.71, 0.50, 1.0),  # old gold
    tag_chip_bg=(0.36, 0.14, 0.09, 0.6),
    focus_ring=(0.98, 0.82, 0.50, 1.0),
    danger=(0.75, 0.22, 0.17, 1.0),
)

DUCKBURG = ReaderTheme(
    name="Duckburg",
    accent_selection=(0.24, 0.42, 0.45, 0.85),  # slate teal
    app_title=(0.98, 0.82, 0.50, 1.0),  # coin gold
    text_title=(0.98, 0.82, 0.50, 1.0),  # coin gold — cream was too quiet for titles
    text_secondary=(0.78, 0.84, 0.90, 1.0),  # sky blue
    row_stripe_even=(0.05, 0.10, 0.13, 0.5),
    row_stripe_odd=(0.13, 0.20, 0.24, 0.5),
    search_heading=(0.56, 0.65, 0.66, 1.0),  # weathered slate
    tag_chip_bg=(0.12, 0.23, 0.25, 0.6),
    focus_ring=(0.98, 0.82, 0.50, 1.0),
    danger=(0.57, 0.24, 0.15, 1.0),  # brick
)

FOUR_COLOR = ReaderTheme(
    name="Four Color",
    accent_selection=(0.21, 0.38, 0.56, 0.85),  # print blue
    app_title=(0.97, 0.94, 0.89, 1.0),  # newsprint cream
    text_title=(0.91, 0.76, 0.44, 1.0),  # old gold
    text_secondary=(0.78, 0.84, 0.90, 1.0),  # sky blue
    row_stripe_even=(0.04, 0.07, 0.11, 0.55),
    row_stripe_odd=(0.09, 0.16, 0.22, 0.55),
    search_heading=(0.76, 0.89, 0.97, 1.0),  # pale sky
    tag_chip_bg=(0.12, 0.21, 0.31, 0.6),
    focus_ring=(0.98, 0.82, 0.50, 1.0),
    danger=(0.75, 0.22, 0.17, 1.0),
)

THEMES: dict[str, ReaderTheme] = {t.name: t for t in (MASTHEAD, DUCKBURG, FOUR_COLOR)}
THEME_NAMES: tuple[str, ...] = tuple(THEMES)
DEFAULT_THEME_NAME = MASTHEAD.name

_active_theme: ReaderTheme = MASTHEAD


def set_active_theme(name: str) -> None:
    """Set the active color theme, falling back to the default for unknown names.

    Args:
        name: A theme name from `THEME_NAMES`.

    """
    global _active_theme  # noqa: PLW0603
    _active_theme = THEMES.get(name, THEMES[DEFAULT_THEME_NAME])


def theme() -> ReaderTheme:
    """Return the active color theme."""
    return _active_theme


def color_to_markup_hex(color: Color) -> str:
    """Return the Kivy markup hex string ("#" + six hex digits) for an RGBA color.

    Args:
        color: RGBA components in [0.0, 1.0]; alpha is ignored.

    Returns:
        A hex string usable inside a Kivy ``[color=...]`` markup tag.

    """
    r, g, b = (round(c * 255) for c in color[:3])
    return f"#{r:02x}{g:02x}{b:02x}"
