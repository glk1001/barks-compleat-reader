from __future__ import annotations

from dataclasses import dataclass, field

from barks_reader.core.justified_lines import JustifiedWord, repair_justified_lines

ROMAN: dict[str, object] = {"italic": False}
ITALIC: dict[str, object] = {"italic": True}
WIDTH = 100.0
MEASURED = {
    "  in": 18.0,
    " in": 14.0,
    "  in and": 40.0,
    "wal": 20.0,
    " I had": 43.0,
    "mer-": 33.0,
    "sum": 31.0,
    " how in the ": 40.0,
}


@dataclass(eq=False)
class Word:
    text: str
    lw: float
    options: dict[str, object] = field(default_factory=lambda: ROMAN)


@dataclass
class Line:
    words: list[Word]
    is_last_line: bool = False


def _measure_by_text(word: JustifiedWord) -> float:
    return MEASURED.get(word.text, 99.0)


def _repair(line: Line) -> None:
    repair_justified_lines([line], WIDTH, _measure_by_text)


class TestRepairJustifiedLines:
    def test_a_split_run_past_the_edge_comes_back_flush_with_it(self) -> None:
        left = Word('"a  whole  page', 60.0, ITALIC)
        right = Word("  in", 25.0, ITALIC)  # measured in the wrong font, so too wide
        line = Line([Word("view  places  ", 30.0), left, right])

        _repair(line)

        assert right.lw == 18.0  # noqa: PLR2004
        assert left.lw == 52.0  # noqa: PLR2004
        assert sum(word.lw for word in line.words) == WIDTH

    def test_the_left_half_may_be_narrower_than_it_was_measured(self) -> None:
        # The right half opens with a space, which the left half's last letter can sit on.
        left = Word("to see if I could", 90.0, ITALIC)
        right = Word(" in", 14.0, ITALIC)

        _repair(Line([left, right]))

        assert left.lw == 86.0  # noqa: PLR2004

    def test_runs_after_the_split_keep_their_widths(self) -> None:
        left = Word("a  ship", 40.0)
        right = Word("  in", 25.0)
        fragment = Word("wal", 20.0, ITALIC)

        _repair(Line([left, right, fragment]))

        assert fragment.lw == 20.0  # noqa: PLR2004
        assert right.lw == 18.0  # noqa: PLR2004
        assert left.lw == 62.0  # noqa: PLR2004

    def test_runs_of_different_styles_were_not_split(self) -> None:
        left = Word("a  ship", 60.0, ROMAN)
        right = Word("  in", 25.0, ITALIC)

        _repair(Line([left, right]))

        assert (left.lw, right.lw) == (60.0, 25.0)

    def test_a_last_run_with_no_leading_space_was_not_split(self) -> None:
        left = Word("a  ship", 60.0)
        right = Word("in  the", 25.0)

        _repair(Line([left, right]))

        assert (left.lw, right.lw) == (60.0, 25.0)

    def test_a_line_with_no_spaced_run_after_its_first_is_left_alone(self) -> None:
        first = Word("a  ship", 60.0)
        fragment = Word("wal", 25.0)

        _repair(Line([first, fragment]))

        assert (first.lw, fragment.lw) == (60.0, 25.0)

    def test_a_split_end_short_of_the_edge_goes_out_to_it(self) -> None:
        left = Word("a  ship", 40.0)
        right = Word("  in", 12.0)

        _repair(Line([left, right]))

        assert left.lw == 82.0  # noqa: PLR2004

    def test_a_line_past_the_edge_gives_way_at_the_space_starting_its_last_run(self) -> None:
        before = Word("cause", 60.0, ITALIC)
        last = Word(" I had", 42.0, ROMAN)

        _repair(Line([before, last]))

        assert before.lw == 57.0  # noqa: PLR2004

    def test_a_line_past_the_edge_gives_way_at_the_space_ending_its_last_spaced_run(self) -> None:
        spaced = Word(" how in the ", 40.0, ROMAN)
        fragment = Word("sum", 31.0, ITALIC)

        _repair(Line([spaced, fragment, Word("mer-", 33.0, ROMAN)]))

        assert spaced.lw == 36.0  # noqa: PLR2004

    def test_a_line_inside_the_edge_with_no_split_is_left_alone(self) -> None:
        before = Word("cause", 40.0, ITALIC)
        last = Word(" I had", 42.0, ROMAN)

        _repair(Line([before, last]))

        assert (before.lw, last.lw) == (40.0, 42.0)

    def test_the_last_line_is_not_justified(self) -> None:
        left = Word("a  ship", 60.0)
        right = Word("  in", 25.0)

        _repair(Line([left, right], is_last_line=True))

        assert (left.lw, right.lw) == (60.0, 25.0)

    def test_every_line_is_seen(self) -> None:
        first = Word("  in", 25.0)
        second = Word("  in", 26.0)
        lines = [Line([Word("a", 10.0), first]), Line([Word("b", 10.0), second])]

        repair_justified_lines(lines, WIDTH, _measure_by_text)

        assert (first.lw, second.lw) == (18.0, 18.0)

    def test_the_left_half_never_goes_negative(self) -> None:
        left = Word("a", 5.0)
        right = Word("  in and", 40.0)

        repair_justified_lines([Line([Word("b", 90.0), left, right])], WIDTH, _measure_by_text)

        assert left.lw == 0
