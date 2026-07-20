# ruff: noqa: SLF001
# cspell:ignore phen ation

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from barks_reader.core.hyphen_break_engine import REF_PREFIX, SOFT_HYPHEN
from barks_reader.ui import hyphen_label
from barks_reader.ui.hyphen_label import HyphenatingLabel

if TYPE_CHECKING:
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
