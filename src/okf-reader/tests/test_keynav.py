# ruff: noqa: PLR2004

"""Unit tests for the viewer's Kivy-free keyboard-navigation logic.

These pin the scroll-step math (including the pin-when-content-fits rule),
the link/list index cycling, and the focused-link markup rewrite against the
exact ref shapes the core renderer emits (``render._inline``).
"""

from __future__ import annotations

from okf_reader.ui.keynav import (
    enumerate_refs,
    highlight_ref_occurrence,
    hybrid_link_step,
    scroll_step,
    step_index,
)

LINK_COLOR = "4ea1ff"
FOCUS_COLOR = "ffd54a"

# The two ref shapes render._inline produces: a page link and a footnote marker.
PAGE_LINK = f"[ref=concepts/foo-bar.md][color={LINK_COLOR}][u]Foo Bar[/u][/color][/ref]"
QUOTED_LINK = (
    f"[ref=stories/lost%20in%20the%20andes.md][color={LINK_COLOR}][u]Andes[/u][/color][/ref]"
)
FOOTNOTE_REF = f"[ref=fn:2][color={LINK_COLOR}][sup][size=11]\\[2][/size][/sup][/color][/ref]"


class TestScrollStep:
    def test_content_fits_pins_to_top(self) -> None:
        assert scroll_step(0.4, viewport_h=500, content_h=300, delta_px=100) == 1.0
        assert scroll_step(0.0, viewport_h=500, content_h=500, delta_px=-100) == 1.0

    def test_moves_down_by_exact_fraction(self) -> None:
        # 1000px scrollable range; 100px down = 0.1 off the normalized offset.
        assert scroll_step(1.0, viewport_h=500, content_h=1500, delta_px=100) == 0.9

    def test_moves_up(self) -> None:
        assert scroll_step(0.5, viewport_h=500, content_h=1500, delta_px=-200) == 0.7

    def test_clamps_at_bottom(self) -> None:
        assert scroll_step(0.05, viewport_h=500, content_h=1500, delta_px=500) == 0.0

    def test_clamps_at_top(self) -> None:
        assert scroll_step(0.95, viewport_h=500, content_h=1500, delta_px=-500) == 1.0


class TestHybridLinkStep:
    """Viewport-relative geometry: y grows downward, viewport spans [0, 500)."""

    VIEWPORT = 500.0
    STEP = 60.0

    # Labels: one above the view, two inside it, one just below the bottom edge
    # (reachable within a step), one far below.
    LINKS = (
        (-300.0, -280.0),  # 0: scrolled off above
        (100.0, 120.0),  # 1: visible
        (300.0, 320.0),  # 2: visible
        (520.0, 540.0),  # 3: just below — within one step of the bottom edge
        (2000.0, 2020.0),  # 4: far below
    )

    def _step(self, focused: int | None, delta: int) -> tuple[str, int | None]:
        return hybrid_link_step(self.LINKS, focused, self.VIEWPORT, self.STEP, delta)

    def test_no_links_scrolls(self) -> None:
        assert hybrid_link_step([], None, self.VIEWPORT, self.STEP, 1) == ("scroll", None)

    def test_no_focus_down_picks_first_visible(self) -> None:
        assert self._step(None, 1) == ("focus", 1)

    def test_no_focus_up_picks_last_visible(self) -> None:
        assert self._step(None, -1) == ("focus", 2)

    def test_no_focus_nothing_visible_scrolls(self) -> None:
        far_links = [(2000.0, 2020.0)]
        assert hybrid_link_step(far_links, None, self.VIEWPORT, self.STEP, 1) == ("scroll", None)

    def test_down_focuses_next_visible_link(self) -> None:
        assert self._step(1, 1) == ("focus", 2)

    def test_down_focuses_link_within_a_step_below(self) -> None:
        assert self._step(2, 1) == ("focus", 3)

    def test_down_scrolls_when_next_link_is_far(self) -> None:
        assert self._step(3, 1) == ("scroll", None)

    def test_down_at_last_link_scrolls(self) -> None:
        assert self._step(4, 1) == ("scroll", None)

    def test_up_focuses_previous_visible_link(self) -> None:
        assert self._step(2, -1) == ("focus", 1)

    def test_up_scrolls_when_previous_link_is_far_above(self) -> None:
        # Link 0 sits 300px above the view — beyond one step's reach.
        assert self._step(1, -1) == ("scroll", None)

    def test_up_at_first_link_scrolls(self) -> None:
        assert self._step(0, -1) == ("scroll", None)

    def test_up_focuses_link_within_a_step_above(self) -> None:
        links = [(-40.0, -20.0), (100.0, 120.0)]
        assert hybrid_link_step(links, 1, self.VIEWPORT, self.STEP, -1) == ("focus", 0)

    def test_same_label_occurrences_walk_without_scrolling(self) -> None:
        # Two refs in one label share its geometry; both are one press apart.
        links = [(100.0, 140.0), (100.0, 140.0)]
        assert hybrid_link_step(links, 0, self.VIEWPORT, self.STEP, 1) == ("focus", 1)
        assert hybrid_link_step(links, 1, self.VIEWPORT, self.STEP, -1) == ("focus", 0)


class TestStepIndex:
    def test_steps_normally(self) -> None:
        assert step_index(2, 5, 1) == 3
        assert step_index(2, 5, -1) == 1

    def test_clamps_at_both_ends(self) -> None:
        assert step_index(4, 5, 1) == 4
        assert step_index(0, 5, -1) == 0


class TestEnumerateRefs:
    def test_document_order(self) -> None:
        markup = f"See {PAGE_LINK} and {FOOTNOTE_REF} then {QUOTED_LINK}."
        assert enumerate_refs(markup) == [
            "concepts/foo-bar.md",
            "fn:2",
            "stories/lost%20in%20the%20andes.md",
        ]

    def test_no_refs(self) -> None:
        assert enumerate_refs("plain [b]bold[/b] text") == []

    def test_quoted_href_returned_verbatim(self) -> None:
        assert enumerate_refs(QUOTED_LINK) == ["stories/lost%20in%20the%20andes.md"]


class TestHighlightRefOccurrence:
    def test_recolors_only_the_requested_span(self) -> None:
        markup = f"{PAGE_LINK} and {QUOTED_LINK}"

        result = highlight_ref_occurrence(markup, 1, LINK_COLOR, FOCUS_COLOR)

        assert result.count(f"[color={FOCUS_COLOR}]") == 1
        assert result.index(f"[color={FOCUS_COLOR}]") > result.index(f"[color={LINK_COLOR}]")
        # The first span keeps its link color; total span count is unchanged.
        assert result.count("[ref=") == 2

    def test_first_occurrence(self) -> None:
        markup = f"{PAGE_LINK} tail"

        result = highlight_ref_occurrence(markup, 0, LINK_COLOR, FOCUS_COLOR)

        assert f"[color={FOCUS_COLOR}][u]Foo Bar[/u]" in result
        assert LINK_COLOR not in result

    def test_footnote_shape(self) -> None:
        result = highlight_ref_occurrence(FOOTNOTE_REF, 0, LINK_COLOR, FOCUS_COLOR)

        assert f"[color={FOCUS_COLOR}][sup]" in result

    def test_out_of_range_returns_unchanged(self) -> None:
        assert highlight_ref_occurrence(PAGE_LINK, 5, LINK_COLOR, FOCUS_COLOR) == PAGE_LINK

    def test_no_reflow_markup_added(self) -> None:
        # Only a color value changes: same length, no new tags such as [b].
        result = highlight_ref_occurrence(PAGE_LINK, 0, LINK_COLOR, FOCUS_COLOR)

        assert len(result) == len(PAGE_LINK)
        assert "[b]" not in result

    def test_text_outside_spans_untouched(self) -> None:
        markup = f"before {PAGE_LINK} after"

        result = highlight_ref_occurrence(markup, 0, LINK_COLOR, FOCUS_COLOR)

        assert result.startswith("before ")
        assert result.endswith(" after")
