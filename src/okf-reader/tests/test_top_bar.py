"""Unit tests for :mod:`okf_reader.core.top_bar`.

Pin the spec's style defaults: an embedding app overrides them, but the
standalone okf window renders from these values, so changing them changes
the standalone look.
"""

from __future__ import annotations

from okf_reader.core.top_bar import TopBarSpec


class TestTopBarSpecDefaults:
    def test_style_defaults_unchanged(self) -> None:
        """The standalone bar's look: dark band, grey separators, fixed widths."""
        spec = TopBarSpec()
        assert spec.bg_color == (0.12, 0.12, 0.12, 1)
        assert spec.separator_color == (0.3, 0.3, 0.3, 1)
        assert (spec.icon_width, spec.quit_fence_width, spec.height) == (70, 17, 40)

    def test_content_defaults(self) -> None:
        """Without an embedding app the bar is text-only and stops the app on Quit."""
        spec = TopBarSpec()
        assert spec.title_markup == "OKF Reader"
        assert spec.icon_path is None
        assert spec.back_icon_path is None
        assert spec.close_icon_path is None
        assert spec.on_close is None
