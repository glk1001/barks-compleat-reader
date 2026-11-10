# ruff: noqa: SLF001
# cspell:ignore phen ation

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from barks_reader.core import log_markers
from barks_reader.core.hyphen_break_engine import REF_PREFIX, SOFT_HYPHEN
from barks_reader.core.log_markers import pattern
from barks_reader.ui import font_manager, hyphen_label
from barks_reader.ui.hyphen_label import HyphenatingLabel
from kivy.core.text.markup import MarkupLabel as CoreMarkupLabel

if TYPE_CHECKING:
    from collections.abc import Callable

    from barks_reader.core.hyphen_break_engine import Box

SHY = SOFT_HYPHEN


def _boxes(line: int) -> list[Box]:
    return [(0.0, line * 20.0, 9.0, line * 20.0 + 19.0)]


def _refs_from_markup(markup: str, breaking_refs: dict[str, int]) -> dict[str, list[Box]]:
    """Fake a render: every ref in the markup gets one box on its given line."""
    refs: dict[str, list[Box]] = {}
    for part in markup.split("[ref=")[1:]:
        name = part.split("]", 1)[0]
        refs[name] = _boxes(breaking_refs.get(name, 0))
    return refs


def _make_label(source_text: str = "", width: float = 300.0) -> HyphenatingLabel:
    label = HyphenatingLabel(markup=True)
    label.width = width
    label.source_text = source_text
    return label


class TestHyphenatingLabel:
    def test_break_at_gap_gets_visible_hyphen(self) -> None:
        label = _make_label(f"hy{SHY}phen")
        breaking = {f"{REF_PREFIX}1": 1}  # the second fragment landed on the next line

        def fake_texture_update(instance: HyphenatingLabel) -> None:
            instance.refs = _refs_from_markup(instance.text, breaking)

        with patch.object(
            HyphenatingLabel, "texture_update", autospec=True, side_effect=fake_texture_update
        ):
            label._refine()

        assert label.text == f"[ref={REF_PREFIX}0]hy-[/ref][ref={REF_PREFIX}1]phen[/ref]"

    def test_no_break_means_no_hyphen(self) -> None:
        label = _make_label(f"hy{SHY}phen")

        def fake_texture_update(instance: HyphenatingLabel) -> None:
            instance.refs = _refs_from_markup(instance.text, {})

        with patch.object(
            HyphenatingLabel, "texture_update", autospec=True, side_effect=fake_texture_update
        ):
            label._refine()

        # No break at the gap -> the final merge collapses the runs to plain text.
        assert label.text == "hyphen"

    def test_non_breaking_gap_is_merged_away(self) -> None:
        label = _make_label(f"hy{SHY}phen{SHY}ation")
        # Only the middle gap breaks; the first should not survive as a run boundary.
        breaking = {f"{REF_PREFIX}2": 1}

        def fake_texture_update(instance: HyphenatingLabel) -> None:
            instance.refs = _refs_from_markup(instance.text, breaking)

        with patch.object(
            HyphenatingLabel, "texture_update", autospec=True, side_effect=fake_texture_update
        ):
            label._refine()

        assert label.text == f"[ref={REF_PREFIX}0]hyphen-[/ref][ref={REF_PREFIX}2]ation[/ref]"

    def test_missing_refs_fall_back_to_hyphen_less_breaks_and_log(self) -> None:
        label = _make_label(f"hy{SHY}phen")

        def fake_texture_update(instance: HyphenatingLabel) -> None:
            instance.refs = {}

        with (
            patch.object(
                HyphenatingLabel, "texture_update", autospec=True, side_effect=fake_texture_update
            ),
            patch.object(hyphen_label, "logger") as mock_logger,
        ):
            label._refine()

        assert label.text == f"[ref={REF_PREFIX}0]hy[/ref][ref={REF_PREFIX}1]phen[/ref]"
        # A failed break is reported, not swallowed.
        mock_logger.error.assert_called_once()

    def test_successful_hyphenation_logs_nothing(self) -> None:
        label = _make_label(f"hy{SHY}phen")

        def fake_texture_update(instance: HyphenatingLabel) -> None:
            instance.refs = _refs_from_markup(instance.text, {f"{REF_PREFIX}1": 1})

        with (
            patch.object(
                HyphenatingLabel, "texture_update", autospec=True, side_effect=fake_texture_update
            ),
            patch.object(hyphen_label, "logger") as mock_logger,
        ):
            label._refine()

        mock_logger.error.assert_not_called()
        mock_logger.warning.assert_not_called()

    def test_text_without_markers_passes_through(self) -> None:
        label = _make_label("plain text only")

        with patch.object(HyphenatingLabel, "texture_update", autospec=True) as mock_update:
            label._refine()

        assert label.text == "plain text only"
        mock_update.assert_not_called()

    def test_unusable_width_strips_markers(self) -> None:
        label = _make_label(f"hy{SHY}phen", width=0.0)

        with patch.object(HyphenatingLabel, "texture_update", autospec=True) as mock_update:
            label._refine()

        assert label.text == "hyphen"
        mock_update.assert_not_called()

    def test_refinement_is_memoized_per_text_and_width(self) -> None:
        label = _make_label(f"hy{SHY}phen")

        def fake_texture_update(instance: HyphenatingLabel) -> None:
            instance.refs = _refs_from_markup(instance.text, {})

        with patch.object(
            HyphenatingLabel, "texture_update", autospec=True, side_effect=fake_texture_update
        ) as mock_update:
            label._refine()
            calls_after_first = mock_update.call_count
            label._refine()

        assert mock_update.call_count == calls_after_first

    def test_render_error_falls_back_to_plain_text(self) -> None:
        label = _make_label(f"hy{SHY}phen")

        with patch.object(
            HyphenatingLabel, "texture_update", autospec=True, side_effect=RuntimeError("boom")
        ):
            label._refine()

        assert label.text == "hyphen"

    def test_a_refine_asked_for_during_one_is_ignored(self) -> None:
        """Setting the text re-triggers a refine; the one running must not recurse."""
        label = _make_label(f"hy{SHY}phen")
        label.text = "in progress"
        label._refining = True

        with patch.object(HyphenatingLabel, "texture_update", autospec=True) as texture_update:
            label._refine()

        texture_update.assert_not_called()
        assert label.text == "in progress"

    def test_words_wrapped_without_a_hyphen_are_named(self, loguru_sink: list[str]) -> None:
        """Breaks found unstable, then the hyphen-less fallback wraps a word: say which."""
        label = _make_label(f"hy{SHY}phen")
        renders: list[str] = []

        def fake_texture_update(instance: HyphenatingLabel) -> None:
            renders.append(instance.text)
            # The first render loses its refs (refinement fails); the fallback's
            # render breaks the word at the gap.
            breaking = {f"{REF_PREFIX}1": 1}
            instance.refs = {} if len(renders) == 1 else _refs_from_markup(instance.text, breaking)

        with patch.object(
            HyphenatingLabel, "texture_update", autospec=True, side_effect=fake_texture_update
        ):
            label._refine()

        assert len(renders) == 2  # noqa: PLR2004
        assert label.text == f"[ref={REF_PREFIX}0]hy[/ref][ref={REF_PREFIX}1]phen[/ref]"
        assert (
            "Hyphenation did not stabilize for 'hyphen'...: 1 word(s) wrapped without a hyphen:"
            " ['hyphen']" in loguru_sink
        )


_SHOWN_LINES = 3
_FEWER_LINES = 2


def test_a_text_given_to_the_constructor_is_refined() -> None:
    """Set before the bindings were made, it asked for no refinement of its own."""
    with patch.object(HyphenatingLabel, "_request_refine", autospec=True) as request_refine:
        HyphenatingLabel(markup=True)
        request_refine.assert_not_called()

        label = HyphenatingLabel(source_text=f"hy{SHY}phen", markup=True)
        request_refine.assert_called_once_with(label)


class TestJustifiedLinesRepair:
    """A justified line's end is brought back after each layout, in the word's own font."""

    @staticmethod
    def _lay_out(label: HyphenatingLabel) -> MagicMock:
        core = label._label
        with patch.object(hyphen_label, "repair_justified_lines") as repair:
            core._pre_render()
        return repair

    def test_the_core_label_stays_the_class_kivy_hands_refs_to(self) -> None:
        assert type(_make_label()._label) is CoreMarkupLabel

    def test_a_justified_label_is_repaired_to_its_width_less_padding(self) -> None:
        label = HyphenatingLabel(markup=True, halign="justify", padding=[3, 0, 4, 0])
        label._label.text = "some words"
        label._label.text_size = (200, None)

        repair = self._lay_out(label)

        repair.assert_called_once()
        assert repair.call_args.args[1] == 200 - 3 - 4

    def test_a_label_with_no_width_or_another_alignment_is_not(self) -> None:
        unsized = HyphenatingLabel(markup=True, halign="justify")
        unsized._label.text = "some words"
        unsized._label.text_size = (None, None)
        left = HyphenatingLabel(markup=True, halign="left")
        left._label.text = "some words"
        left._label.text_size = (200, None)

        assert not self._lay_out(unsized).called
        assert not self._lay_out(left).called

    def test_measuring_a_word_leaves_the_label_on_its_own_options(self) -> None:
        label = HyphenatingLabel(markup=True, halign="justify")
        core = label._label
        core.text = "some words"
        core.text_size = (200, None)
        word_options = {**core.options, "italic": True}
        seen: list[bool] = []

        def get_extents(_text: str) -> tuple[int, int]:
            seen.append(core.options["italic"])
            return (12, 10)

        def fake_repair(_lines: object, _width: float, measure: Callable[..., float]) -> None:
            assert measure(SimpleNamespace(text="in", options=word_options)) == 12  # noqa: PLR2004

        with (
            patch.object(hyphen_label, "repair_justified_lines", side_effect=fake_repair),
            patch.object(core, "get_extents", side_effect=get_extents),
        ):
            core._pre_render()

        assert seen[-1] is True  # the word's font, while it was measured
        assert not core.options["italic"]


class TestJustifiedLinesInTheRealFont:
    """Real layouts, in the notes' real font, of lines mixing roman and italic.

    The first test catches the repair silently ceasing to work, should Kivy change how it
    lays out a line. The second is a tripwire for Kivy fixing its bug: when it fails, on an
    upgrade, the repair and these tests can go (docs/BACKLOG.md, "Kivy 3.0").
    """

    TEXT = (
        'Barks told Edward Summer: [i]"I liked stories that gave me a chance to draw water and'
        ' ships sailing into storms and big pictorial panels."[/i] His example, which could be'
        ' a page or two of this story, is [i]"a whole page in which I have a ship wallowing'
        " around in the waves. A hurricane is tearing the ship apart, and the villain turns on"
        ' his own helper."[/i] It made a story and [i]"it was just a gimmick"[/i] after that.'
    )
    WIDTHS = range(250, 500, 2)
    PADDING = (1, 0, 0, 0)
    FONT_SIZE = 17
    # Rounding can leave a line a pixel or two over; Kivy's bug leaves it tens of pixels over.
    ROUNDING = 4

    def _worst_overrun(self, core: CoreMarkupLabel) -> float:
        worst = 0.0
        core.text = self.TEXT
        for width in self.WIDTHS:
            core.text_size = (width, None)
            core.render()
            for line in core._cached_lines:
                run_start = sum(word.lw for word in line.words[:-1]) + self.PADDING[0]
                last = line.words[-1]
                options = core.options
                core.options = last.options
                worst = max(worst, run_start + core.get_extents(last.text)[0] - width)
                core.options = options
        return worst

    def test_the_label_keeps_every_line_inside_its_width(self) -> None:
        label = HyphenatingLabel(
            markup=True,
            font_name=font_manager.EXTRA_INFO_FONT,
            font_size=self.FONT_SIZE,
            halign="justify",
            padding=list(self.PADDING),
        )

        assert self._worst_overrun(label._label) < self.ROUNDING

    def test_kivy_on_its_own_still_runs_some_lines_past_their_width(self) -> None:
        core = CoreMarkupLabel(
            font_name=font_manager.EXTRA_INFO_FONT,
            font_size=self.FONT_SIZE,
            halign="justify",
            padding=list(self.PADDING),
        )

        assert self._worst_overrun(core) > self.ROUNDING


class TestLinesReport:
    """The lines a held-down label lays out, and any it cuts, reach the log at rest."""

    LAID_OUT = pattern(log_markers.TEXT_LAID_OUT)
    CUT = pattern(log_markers.TEXT_CUT_SHORT)

    @staticmethod
    def _laid_out(lines: int, shown: int, text: str = f"hy{SHY}phen") -> HyphenatingLabel:
        label = _make_label(text)
        label.shown_lines = shown

        def fake_texture_update(instance: HyphenatingLabel) -> None:
            instance.refs = _refs_from_markup(instance.text, {})
            instance._label._cached_lines = [object()] * lines

        with patch.object(
            HyphenatingLabel, "texture_update", autospec=True, side_effect=fake_texture_update
        ):
            label._refine()
        return label

    def _matching(self, sink: list[str], marker: str) -> list[str]:
        return [line for line in sink if re.search(marker, line)]

    def test_text_that_fits_is_laid_out_and_not_cut(self, loguru_sink: list[str]) -> None:
        label = self._laid_out(lines=_SHOWN_LINES, shown=_SHOWN_LINES)

        label._report_lines()

        assert len(self._matching(loguru_sink, self.LAID_OUT)) == 1
        assert self._matching(loguru_sink, self.CUT) == []

    def test_a_line_too_many_is_cut_and_says_which_text(self, loguru_sink: list[str]) -> None:
        label = self._laid_out(lines=_SHOWN_LINES + 1, shown=_SHOWN_LINES)

        label._report_lines()

        cut = self._matching(loguru_sink, self.CUT)
        assert len(cut) == 1
        assert f"{_SHOWN_LINES + 1} lines, {_SHOWN_LINES} shown" in cut[0]
        assert "hyphen" in cut[0]

    def test_the_same_layout_is_reported_once(self, loguru_sink: list[str]) -> None:
        label = self._laid_out(lines=_SHOWN_LINES, shown=_SHOWN_LINES)

        label._report_lines()
        label._report_lines()

        assert len(self._matching(loguru_sink, self.LAID_OUT)) == 1

    def test_fewer_lines_shown_at_rest_are_reported_again(self, loguru_sink: list[str]) -> None:
        label = self._laid_out(lines=_SHOWN_LINES, shown=_SHOWN_LINES)
        label._report_lines()

        label.shown_lines = _FEWER_LINES
        label._report_lines()

        assert len(self._matching(loguru_sink, self.LAID_OUT)) == 2  # noqa: PLR2004
        assert len(self._matching(loguru_sink, self.CUT)) == 1

    def test_a_label_not_held_to_a_number_of_lines_reports_nothing(
        self, loguru_sink: list[str]
    ) -> None:
        label = self._laid_out(lines=_SHOWN_LINES, shown=0)

        label._report_lines()

        assert self._matching(loguru_sink, self.LAID_OUT) == []

    def test_clearing_the_text_does_not_report_the_last_texts_lines(
        self, loguru_sink: list[str]
    ) -> None:
        """A title with no notes follows one with: its panel was reported as cut short."""
        label = self._laid_out(lines=_SHOWN_LINES, shown=_SHOWN_LINES)
        label._report_lines()
        loguru_sink.clear()

        label.source_text = ""
        label._refine()
        label.shown_lines = 1
        label._report_lines()

        assert loguru_sink == []

    def test_new_text_is_not_reported_until_it_is_counted(self, loguru_sink: list[str]) -> None:
        label = self._laid_out(lines=_SHOWN_LINES, shown=_SHOWN_LINES)
        loguru_sink.clear()

        label.source_text = "Another note, not yet refined"
        label._report_lines()

        assert loguru_sink == []

    def test_lines_first_held_after_the_refinement_are_counted_and_reported(
        self, loguru_sink: list[str]
    ) -> None:
        """Refined with every line shown, the text had no count: no report ever came."""
        label = self._laid_out(lines=_SHOWN_LINES, shown=0)

        def fake_texture_update(instance: HyphenatingLabel) -> None:
            instance.refs = _refs_from_markup(instance.text, {})
            instance._label._cached_lines = [object()] * _SHOWN_LINES

        with (
            patch.object(
                HyphenatingLabel, "texture_update", autospec=True, side_effect=fake_texture_update
            ),
            patch.object(label, "_refine_trigger", side_effect=label._refine) as refine,
        ):
            label.shown_lines = _FEWER_LINES
        label._report_lines()

        refine.assert_called_once_with()
        assert len(self._matching(loguru_sink, self.LAID_OUT)) == 1
        assert len(self._matching(loguru_sink, self.CUT)) == 1

    def test_lines_changed_for_a_counted_text_do_not_refine_it_again(self) -> None:
        label = self._laid_out(lines=_SHOWN_LINES, shown=_SHOWN_LINES)
        with patch.object(label, "_refine_trigger") as refine:
            label.shown_lines = _FEWER_LINES
        refine.assert_not_called()

    def test_the_report_waits_for_a_quiet_moment(self) -> None:
        label = _make_label("plain")
        with patch.object(label, "_lines_report_trigger") as trigger:
            label.shown_lines = _SHOWN_LINES
            label.shown_lines = _FEWER_LINES

        assert trigger.cancel.call_count == trigger.call_count == 2  # noqa: PLR2004


class TestShownLines:
    """The lines shown are cut only after the breaks are refined."""

    def test_the_refinement_renders_every_line_and_the_cut_comes_after(self) -> None:
        label = _make_label(f"hy{SHY}phen")
        label.shown_lines = _SHOWN_LINES
        label.max_lines = _SHOWN_LINES
        seen: list[int] = []

        def fake_texture_update(instance: HyphenatingLabel) -> None:
            seen.append(instance.max_lines)  # a dropped line renders no refs to read
            instance.refs = _refs_from_markup(instance.text, {f"{REF_PREFIX}1": 1})

        with patch.object(
            HyphenatingLabel, "texture_update", autospec=True, side_effect=fake_texture_update
        ):
            label._refine()

        assert seen
        assert set(seen) == {0}
        assert label.max_lines == _SHOWN_LINES
        assert label.text == f"[ref={REF_PREFIX}0]hy-[/ref][ref={REF_PREFIX}1]phen[/ref]"

    def test_the_lines_shown_change_at_rest(self) -> None:
        label = _make_label("plain")
        label.shown_lines = _FEWER_LINES
        assert label.max_lines == _FEWER_LINES
        label.shown_lines = 0
        assert label.max_lines == 0
