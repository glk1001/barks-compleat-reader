"""Unit tests for :mod:`okf_reader.core.theme`.

Pin the spec's scrollbar defaults: an embedding app overrides them, but the
standalone okf window renders from these values, so changing them changes
the standalone look.
"""

from __future__ import annotations

from okf_reader.core.theme import ViewerThemeSpec


class TestViewerThemeSpecDefaults:
    def test_scrollbar_defaults_unchanged(self) -> None:
        """The standalone viewer's bar: blue-white while scrolling, grey at rest."""
        spec = ViewerThemeSpec()
        assert spec.scrollbar == (0.7, 0.7, 1.0, 1.0)
        assert spec.scrollbar_inactive == (0.7, 0.7, 0.7, 0.9)
