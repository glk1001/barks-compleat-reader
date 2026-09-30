"""A row of chips of which one is picked, walked with the remote's arrows and Enter."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from barks_reader.ui.reader_keyboard_nav import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_RIGHT,
    KEY_TAB,
    KEY_UP,
)
from barks_reader.ui.search_chip_row import (
    CHIP_BORDER_NONE,
    ChipRow,
    RowKey,
    chip_bg_active,
    chip_bg_normal,
    chip_border_focused,
)

OPTIONS = [("", "All"), ("Donald", "Donald"), ("Scrooge", "Scrooge")]


def _chip(value: str, label: str) -> MagicMock:
    chip = MagicMock()
    chip.value = value
    chip.text = label
    return chip


def _press(chip: MagicMock) -> None:
    """Release a chip as a click does: run the handler the row bound to it."""
    chip.bind.call_args.kwargs["on_release"](chip)


@pytest.fixture
def on_select() -> MagicMock:
    return MagicMock()


@pytest.fixture
def row(on_select: MagicMock) -> ChipRow:
    chip_row = ChipRow(MagicMock(), _chip, on_select, selected="Donald")
    chip_row.set_options(OPTIONS)
    return chip_row


def _chips(row: ChipRow) -> list[MagicMock]:
    return cast("list[MagicMock]", row.chips)


def test_the_options_become_chips_in_the_layout_in_order(row: ChipRow) -> None:
    assert [(c.value, c.text) for c in _chips(row)] == [
        ("", "All"),
        ("Donald", "Donald"),
        ("Scrooge", "Scrooge"),
    ]
    layout = cast("MagicMock", row._layout)  # noqa: SLF001
    assert [c.args[0] for c in layout.add_widget.call_args_list] == row.chips


def test_new_options_replace_the_chips_and_the_focus(row: ChipRow) -> None:
    row.enter_focus()
    row.set_options([("x", "X")])
    assert [c.value for c in _chips(row)] == ["x"]
    assert row.focused is None
    cast("MagicMock", row._layout).clear_widgets.assert_called()  # noqa: SLF001
    row.set_options([])
    assert row.chips == []


def test_the_picked_chip_is_filled_and_the_focused_one_bordered(row: ChipRow) -> None:
    all_chip, donald, scrooge = _chips(row)
    assert donald.chip_bg_color == chip_bg_active()
    assert all_chip.chip_bg_color == scrooge.chip_bg_color == chip_bg_normal()
    assert {c.chip_border_color for c in _chips(row)} == {CHIP_BORDER_NONE}

    row.enter_focus()
    assert donald.chip_border_color == chip_border_focused()
    assert all_chip.chip_border_color == scrooge.chip_border_color == CHIP_BORDER_NONE


def test_a_click_picks_the_chip_then_tells_the_screen(row: ChipRow, on_select: MagicMock) -> None:
    scrooge = _chips(row)[2]
    on_select.side_effect = lambda _v: seen.append(row.selected)
    seen: list[str] = []
    _press(scrooge)
    on_select.assert_called_once_with("Scrooge")
    assert seen == ["Scrooge"]  # the row had marked it picked by then
    assert scrooge.chip_bg_color == chip_bg_active()


def test_set_selected_does_not_tell_the_screen(row: ChipRow, on_select: MagicMock) -> None:
    row.set_selected("")
    assert row.selected == ""
    assert _chips(row)[0].chip_bg_color == chip_bg_active()
    on_select.assert_not_called()


def test_focus_starts_on_the_picked_chip_and_is_logged(
    row: ChipRow, loguru_sink: list[str]
) -> None:
    row.enter_focus()
    assert row.focused == 1
    assert 'Nav focus on MagicMock "Donald".' in loguru_sink


def test_focus_starts_on_the_first_chip_when_none_is_picked(on_select: MagicMock) -> None:
    row = ChipRow(MagicMock(), _chip, on_select, selected="nobody")
    row.set_options(OPTIONS)
    row.enter_focus()
    assert row.focused == 0


def test_an_empty_row_takes_focus_without_a_chip_to_show_it(
    on_select: MagicMock, loguru_sink: list[str]
) -> None:
    row = ChipRow(MagicMock(), _chip, on_select)
    row.enter_focus()
    assert row.handle_key(KEY_ENTER) is RowKey.HANDLED
    assert not any("Nav focus" in line for line in loguru_sink)


def test_left_and_right_walk_and_the_ends_behave(row: ChipRow) -> None:
    row.enter_focus()
    assert row.handle_key(KEY_RIGHT) is RowKey.HANDLED
    assert row.focused == 2  # noqa: PLR2004
    assert row.handle_key(KEY_RIGHT) is RowKey.HANDLED  # the last chip: stays
    assert row.focused == 2  # noqa: PLR2004
    row.handle_key(KEY_LEFT)
    row.handle_key(KEY_LEFT)
    assert row.focused == 0
    assert row.handle_key(KEY_LEFT) is RowKey.EXIT_LEFT  # off the first: a way out
    assert row.focused == 0  # the screen decides whether it is taken


def test_enter_picks_the_focused_chip_and_keeps_the_focus(
    row: ChipRow, loguru_sink: list[str]
) -> None:
    row.enter_focus()
    row.handle_key(KEY_RIGHT)
    loguru_sink.clear()
    assert row.handle_key(KEY_ENTER) is RowKey.HANDLED
    _chips(row)[2].trigger_action.assert_called_once_with(duration=0)
    assert row.focused == 2  # noqa: PLR2004
    assert loguru_sink == ['Nav focus on MagicMock "Scrooge".']


@pytest.mark.parametrize(
    ("key", "outcome"),
    [
        (KEY_DOWN, RowKey.EXIT_DOWN),
        (KEY_TAB, RowKey.EXIT_DOWN),
        (KEY_UP, RowKey.EXIT_UP),
        (KEY_ESCAPE, RowKey.EXIT_ESCAPE),
        (ord("a"), RowKey.UNHANDLED),
    ],
)
def test_the_other_keys_are_ways_out_or_not_the_rows(
    row: ChipRow, key: int, outcome: RowKey
) -> None:
    row.enter_focus()
    assert row.handle_key(key) is outcome
    assert row.focused == 1


def test_clearing_the_focus_leaves_no_chip_bordered(row: ChipRow) -> None:
    row.enter_focus()
    row.clear_focus()
    assert row.focused is None
    assert {c.chip_border_color for c in _chips(row)} == {CHIP_BORDER_NONE}
