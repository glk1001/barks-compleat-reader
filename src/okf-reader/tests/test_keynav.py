# ruff: noqa: PLR2004

"""Unit tests for the viewer's Kivy-free keyboard-navigation logic.

These pin the scroll-step math (including the pin-when-content-fits rule),
the link/list index cycling, and the focused-link markup rewrite against the
exact ref shapes the core renderer emits (``render._inline``).
"""

from __future__ import annotations

from okf_reader.ui.keynav import (
    advance_index,
    enumerate_refs,
    highlight_ref_occurrence,
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


class TestAdvanceIndex:
    def test_no_focus_forward_starts_at_first(self) -> None:
        assert advance_index(None, 5, 1) == 0

    def test_no_focus_backward_starts_at_last(self) -> None:
        assert advance_index(None, 5, -1) == 4

    def test_stops_at_last(self) -> None:
        assert advance_index(4, 5, 1) == 4

    def test_stops_at_first(self) -> None:
        assert advance_index(0, 5, -1) == 0

    def test_steps_normally(self) -> None:
        assert advance_index(2, 5, 1) == 3

    def test_empty_has_no_focus(self) -> None:
        assert advance_index(None, 0, 1) is None
        assert advance_index(3, 0, -1) is None


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
