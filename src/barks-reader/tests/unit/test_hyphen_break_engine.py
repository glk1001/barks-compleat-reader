# ruff: noqa: PLR2004
# cspell:ignore phen ation
"""Tests for the pure hyphen-break refinement engine (no Kivy involved)."""

from __future__ import annotations

from barks_reader.core.hyphen_break_engine import (
    REF_PREFIX,
    SOFT_HYPHEN,
    Box,
    BreakRefinement,
    RefinementStatus,
    build_markup,
    compute_breaks,
    parse_marked_text,
)

SHY = SOFT_HYPHEN

EMPTY: frozenset[int] = frozenset()


def ref(fragment_id: int) -> str:
    return f"{REF_PREFIX}{fragment_id}"


def boxes_on_line(line: int, count: int = 1) -> list[Box]:
    """Make ref boxes whose y encodes the line number."""
    return [
        (float(i * 10), float(line * 20), float(i * 10 + 9), float(line * 20 + 19))
        for i in range(count)
    ]


class TestParseMarkedText:
    def test_plain_words_are_single_fragments(self) -> None:
        parsed = parse_marked_text("plain words here")
        assert [t.fragments for t in parsed.tokens] == [("plain",), ("words",), ("here",)]
        assert parsed.gaps == EMPTY

    def test_marked_word_splits_into_fragments_with_gaps(self) -> None:
        parsed = parse_marked_text(f"hy{SHY}phen{SHY}ation next")
        assert parsed.tokens[0].fragments == ("hy", "phen", "ation")
        assert parsed.tokens[0].first_fragment_id == 0
        assert parsed.tokens[1].fragments == ("next",)
        assert parsed.tokens[1].first_fragment_id == 3
        assert parsed.gaps == frozenset({0, 1})

    def test_fragment_ids_are_global(self) -> None:
        parsed = parse_marked_text(f"ab{SHY}cd ef{SHY}gh")
        assert parsed.tokens[1].first_fragment_id == 2
        assert parsed.gaps == frozenset({0, 2})

    def test_markup_tokens_are_kept_whole(self) -> None:
        parsed = parse_marked_text(f"[i]wo{SHY}rd[/i] pa\n\nra&amp;")
        assert parsed.tokens[0].fragments == ("[i]word[/i]",)
        assert parsed.tokens[1].fragments == ("pa\n\nra&amp;",)
        assert parsed.gaps == EMPTY

    def test_degenerate_markers_are_stripped(self) -> None:
        parsed = parse_marked_text(f"{SHY}word{SHY}")
        assert parsed.tokens[0].fragments == ("word",)
        assert parsed.gaps == EMPTY

    def test_empty_text_round_trips(self) -> None:
        parsed = parse_marked_text("")
        assert build_markup(parsed, EMPTY, EMPTY) == ""


class TestBuildMarkup:
    def test_no_hyphens_emits_ref_runs(self) -> None:
        parsed = parse_marked_text(f"hy{SHY}phen end")
        markup = build_markup(parsed, EMPTY, EMPTY)
        assert markup == f"[ref={ref(0)}]hy[/ref][ref={ref(1)}]phen[/ref] end"

    def test_hyphen_at_gap_is_inside_left_run(self) -> None:
        parsed = parse_marked_text(f"hy{SHY}phen")
        markup = build_markup(parsed, frozenset({0}), EMPTY)
        assert markup == f"[ref={ref(0)}]hy-[/ref][ref={ref(1)}]phen[/ref]"

    def test_disabled_gap_merges_fragments(self) -> None:
        parsed = parse_marked_text(f"hy{SHY}phen{SHY}ation")
        markup = build_markup(parsed, EMPTY, frozenset({0}))
        assert markup == f"[ref={ref(0)}]hyphen[/ref][ref={ref(2)}]ation[/ref]"

    def test_all_gaps_disabled_emits_plain_token(self) -> None:
        parsed = parse_marked_text(f"hy{SHY}phen")
        assert build_markup(parsed, EMPTY, frozenset({0})) == "hyphen"

    def test_single_fragment_tokens_have_no_refs(self) -> None:
        parsed = parse_marked_text("[i]word[/i] plain")
        assert build_markup(parsed, EMPTY, EMPTY) == "[i]word[/i] plain"

    def test_hyphen_not_doubled_after_existing_dash(self) -> None:
        # pyphen can mark a break right beside a literal hyphen, as in "e-mail".
        parsed = parse_marked_text(f"e-{SHY}mail")
        markup = build_markup(parsed, frozenset({0}), EMPTY)
        assert markup == f"[ref={ref(0)}]e-[/ref][ref={ref(1)}]mail[/ref]"


class TestComputeBreaks:
    def test_same_line_is_no_break(self) -> None:
        parsed = parse_marked_text(f"hy{SHY}phen")
        refs = {ref(0): boxes_on_line(0), ref(1): boxes_on_line(0)}
        assert compute_breaks(parsed, EMPTY, refs) == EMPTY

    def test_different_line_is_a_break(self) -> None:
        parsed = parse_marked_text(f"hy{SHY}phen")
        refs = {ref(0): boxes_on_line(0), ref(1): boxes_on_line(1)}
        assert compute_breaks(parsed, EMPTY, refs) == frozenset({0})

    def test_multi_box_ref_uses_last_and_first_boxes(self) -> None:
        # Justify's push-to-edge can split one ref into several boxes on one line.
        parsed = parse_marked_text(f"hy{SHY}phen")
        refs = {ref(0): boxes_on_line(0, count=2), ref(1): boxes_on_line(0, count=3)}
        assert compute_breaks(parsed, EMPTY, refs) == EMPTY

    def test_ref_spanning_lines_compares_adjacent_edges(self) -> None:
        # A force-split left fragment ends on line 1; the right fragment starts there too.
        parsed = parse_marked_text(f"hy{SHY}phen")
        refs = {
            ref(0): boxes_on_line(0) + boxes_on_line(1),
            ref(1): boxes_on_line(1),
        }
        assert compute_breaks(parsed, EMPTY, refs) == EMPTY

    def test_missing_ref_fails(self) -> None:
        parsed = parse_marked_text(f"hy{SHY}phen")
        assert compute_breaks(parsed, EMPTY, {ref(0): boxes_on_line(0)}) is None

    def test_empty_boxes_fail(self) -> None:
        parsed = parse_marked_text(f"hy{SHY}phen")
        refs: dict[str, list[Box]] = {ref(0): boxes_on_line(0), ref(1): []}
        assert compute_breaks(parsed, EMPTY, refs) is None

    def test_disabled_gaps_are_not_checked(self) -> None:
        parsed = parse_marked_text(f"hy{SHY}phen")
        # Gap 0 disabled: the merged run needs no partner ref, so nothing to detect.
        assert compute_breaks(parsed, frozenset({0}), {}) == EMPTY


class TestBreakRefinement:
    @staticmethod
    def refs_for(markup: str, breaking_refs: dict[str, int]) -> dict[str, list[Box]]:
        """Fake a render: every ref present in the markup gets a box on its given line."""
        refs: dict[str, list[Box]] = {}
        for part in markup.split("[ref="):
            if "]" not in part:
                continue
            name = part.split("]", 1)[0]
            refs[name] = boxes_on_line(breaking_refs.get(name, 0))
        return refs

    def test_no_gaps(self) -> None:
        refinement = BreakRefinement("no markers here")
        assert not refinement.has_gaps
        assert refinement.markup() == "no markers here"

    def test_converges_when_no_breaks_occur(self) -> None:
        refinement = BreakRefinement(f"hy{SHY}phen")
        status = refinement.observe(self.refs_for(refinement.markup(), {}))
        assert status is RefinementStatus.STABLE
        assert refinement.markup() == f"[ref={ref(0)}]hy[/ref][ref={ref(1)}]phen[/ref]"

    def test_converges_after_adding_hyphen(self) -> None:
        refinement = BreakRefinement(f"hy{SHY}phen")

        # Pass 1: the word broke at the gap -> hyphen wanted.
        status = refinement.observe(self.refs_for(refinement.markup(), {ref(1): 1}))
        assert status is RefinementStatus.CONTINUE
        assert refinement.markup() == f"[ref={ref(0)}]hy-[/ref][ref={ref(1)}]phen[/ref]"

        # Pass 2: hyphen fits, the break stayed put -> stable.
        status = refinement.observe(self.refs_for(refinement.markup(), {ref(1): 1}))
        assert status is RefinementStatus.STABLE

    def test_final_markup_merges_non_breaking_gaps(self) -> None:
        # A three-fragment word that only breaks at the middle gap: the first gap is
        # merged away in the final markup so no hairline gap shows mid-line.
        refinement = BreakRefinement(f"hy{SHY}phen{SHY}ation")
        status = refinement.observe(self.refs_for(refinement.markup(), {ref(2): 1}))
        assert status is RefinementStatus.CONTINUE
        status = refinement.observe(self.refs_for(refinement.markup(), {ref(2): 1}))
        assert status is RefinementStatus.STABLE
        # Gap 1 (before "ation") carries the hyphen; gap 0 is merged into one run.
        assert refinement.final_markup() == f"[ref={ref(0)}]hyphen-[/ref][ref={ref(2)}]ation[/ref]"

    def test_final_markup_no_hyphens_is_plain_text(self) -> None:
        refinement = BreakRefinement(f"hy{SHY}phen")
        assert refinement.observe(self.refs_for(refinement.markup(), {})) is RefinementStatus.STABLE
        assert refinement.final_markup() == "hyphen"

    def test_verify_final_true_when_break_holds(self) -> None:
        refinement = BreakRefinement(f"hy{SHY}phen{SHY}ation")
        refinement.observe(self.refs_for(refinement.markup(), {ref(2): 1}))
        refinement.observe(self.refs_for(refinement.markup(), {ref(2): 1}))
        # The merged final markup still breaks before "ation".
        assert refinement.verify_final(self.refs_for(refinement.final_markup(), {ref(2): 1}))

    def test_verify_final_false_when_break_moves(self) -> None:
        refinement = BreakRefinement(f"hy{SHY}phen{SHY}ation")
        refinement.observe(self.refs_for(refinement.markup(), {ref(2): 1}))
        refinement.observe(self.refs_for(refinement.markup(), {ref(2): 1}))
        # After merging, the narrower word no longer breaks -> verification fails.
        assert not refinement.verify_final(self.refs_for(refinement.final_markup(), {}))

    def test_oscillating_gap_is_disabled(self) -> None:
        refinement = BreakRefinement(f"hy{SHY}phen")

        # Pass 1: break at the gap -> hyphen added (toggle 1).
        assert (
            refinement.observe(self.refs_for(refinement.markup(), {ref(1): 1}))
            is RefinementStatus.CONTINUE
        )
        # Pass 2: hyphen didn't fit, the break moved away (toggle 2) -> gap disabled,
        # fragments merged for good.
        assert (
            refinement.observe(self.refs_for(refinement.markup(), {})) is RefinementStatus.CONTINUE
        )
        assert refinement.markup() == "hyphen"

        # Pass 3: nothing left to toggle -> stable.
        assert refinement.observe(self.refs_for(refinement.markup(), {})) is RefinementStatus.STABLE

    def test_missing_refs_fail(self) -> None:
        refinement = BreakRefinement(f"hy{SHY}phen")
        assert refinement.observe({}) is RefinementStatus.FAILED

    def test_iteration_cap_fails(self) -> None:
        # Adversarial oracle: each pass, the (sole) break moves to the next word's gap,
        # so the state never stabilizes and the iteration cap must end the loop.
        refinement = BreakRefinement(" ".join(f"a{SHY}b" for _ in range(10)))
        status = RefinementStatus.CONTINUE
        word = 0
        passes = 0
        while status is RefinementStatus.CONTINUE:
            markup = refinement.markup()
            status = refinement.observe(self.refs_for(markup, {ref(2 * word + 1): 1}))
            word += 1
            passes += 1
            assert passes <= 20, "refinement failed to terminate"
        assert status is RefinementStatus.FAILED
        assert "-" not in refinement.fallback_markup()

    def test_fallback_markup_has_break_points_but_no_hyphens(self) -> None:
        refinement = BreakRefinement(f"hy{SHY}phen")
        refinement.observe(self.refs_for(refinement.markup(), {ref(1): 1}))
        assert "-" not in refinement.fallback_markup()
        assert refinement.fallback_markup() == f"[ref={ref(0)}]hy[/ref][ref={ref(1)}]phen[/ref]"

    def test_fallback_broken_words_names_wrapped_words(self) -> None:
        refinement = BreakRefinement(f"hy{SHY}phen ab{SHY}cd")
        # In the fallback render "hyphen" wraps (gap 0 breaks) but "abcd" does not.
        refs = self.refs_for(refinement.fallback_markup(), {ref(1): 1})
        assert refinement.fallback_broken_words(refs) == ["hyphen"]

    def test_fallback_broken_words_empty_when_nothing_wraps(self) -> None:
        refinement = BreakRefinement(f"hy{SHY}phen")
        refs = self.refs_for(refinement.fallback_markup(), {})
        assert refinement.fallback_broken_words(refs) == []

    def test_fallback_broken_words_none_when_refs_missing(self) -> None:
        refinement = BreakRefinement(f"hy{SHY}phen")
        assert refinement.fallback_broken_words({}) is None
