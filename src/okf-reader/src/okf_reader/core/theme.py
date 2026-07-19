"""Kivy-free description of the viewer's color theme.

The embedding app's seam for recoloring the reader to match its own palette —
the Barks launcher fills it from the app's selected color theme so the wiki
screen's selection band, tree text, striping, focus ring, article headings and
search hits track the theme the rest of the app is wearing. Same port idiom as
`okf_reader.core.top_bar`: okf_reader knows nothing about any particular app's
palette; every field defaults to the viewer's standalone look, so an app that
passes no spec (or the CLI) is pixel-identical to before.

Two kinds of field: RGBA tuples drive widget colors (tree rows, focus ring,
selection band); hex strings (no leading '#') drive the Kivy *markup* colors the
core renderer bakes into text (headings, links, search-hit titles). Neutral
chrome that should not shift with the palette — the background-image darkening
tint, the dark search-input backing, the near-black section bands — stays
hardcoded in the UI layer and is deliberately absent here.
"""

from __future__ import annotations

from dataclasses import dataclass

# An RGBA color, components in [0, 1] — matching Kivy's color convention without
# importing kivy (this module stays in the pure core layer).
Rgba = tuple[float, float, float, float]


@dataclass(frozen=True)
class ViewerThemeSpec:
    """How the embedding app wants the viewer's colors themed.

    ``selection`` is the band behind the selected tree node and the active
    search-result row. ``title_text``/``dir_text`` color the concept-leaf and
    directory rows in the tree; ``secondary_text`` the quiet notes (search
    hint, "no matches", "Searching…"). ``row_stripe_even``/``row_stripe_odd``
    stripe the tree. ``focus_ring`` outlines the sidebar when it owns the keys.

    ``heading_hex`` recolors every article heading and table header (baked into
    markup by ``render_page``); ``link_hex`` the hyperlinks and footnote refs;
    ``title_hex``/``crumb_hex`` the search-hit title and breadcrumb. Hex
    strings carry no leading '#'.

    ``icon_tint`` multiplies the top-bar icon glyphs (Back/Contrast/page-action/
    Quit) so they wear the app's accent; the default white is a no-op, leaving
    the standalone bar's plain white glyphs untouched.

    Defaults reproduce the standalone reader exactly — an app themes only what
    it wants and inherits the rest.
    """

    selection: Rgba = (0.306, 0.631, 1.0, 0.35)
    title_text: Rgba = (1.0, 0.835, 0.29, 1.0)
    dir_text: Rgba = (1.0, 1.0, 1.0, 1.0)
    secondary_text: Rgba = (0.7, 0.7, 0.7, 1.0)
    row_stripe_even: Rgba = (1.0, 1.0, 1.0, 0.04)
    row_stripe_odd: Rgba = (0.0, 0.0, 0.0, 0.0)
    focus_ring: Rgba = (0.306, 0.631, 1.0, 0.9)
    heading_hex: str = "ffd54a"
    link_hex: str = "4ea1ff"
    title_hex: str = "ffd54a"
    crumb_hex: str = "999999"
    icon_tint: Rgba = (1.0, 1.0, 1.0, 1.0)
