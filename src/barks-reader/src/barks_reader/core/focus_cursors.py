"""Where keyboard focus goes next: along a list, round a ring, or about a grid. Kivy-free.

The screens keep their widgets and draw the ring; the arithmetic of the move is here,
so a wrong step is a unit test's find and not a remote's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


def clamped(index: int, count: int) -> int:
    """Return `index` held within a list of `count` items; 0 for an empty list."""
    return max(0, min(count - 1, index))


def wrapped(index: int, delta: int, count: int) -> int:
    """Return `index` moved by `delta` round a ring of `count` items."""
    return (index + delta) % count


def next_index_toward(count: int, selected: int | None, delta: int) -> int:
    """Return the item a step of `delta` lands on, in a list of `count` items.

    With nothing selected, a step forward lands on the first item and a step back on
    the last; otherwise the step is held within the list.
    """
    if selected is None:
        return 0 if delta > 0 else count - 1
    return clamped(selected + delta, count)


def deal_into_columns[T](items: list[T], num_columns: int) -> list[list[T]]:
    """Deal `items` into `num_columns` columns, filling each with its share of what is left.

    Taking ``ceil(remaining / columns_left)`` each time reproduces the original
    per-column-count formulas exactly, without branching on the column count.
    """
    columns: list[list[T]] = []
    start = 0
    for col_idx in range(num_columns):
        columns_left = num_columns - col_idx
        take = -(-(len(items) - start) // columns_left)  # ceil
        columns.append(items[start : start + take])
        start += take
    return columns


def stripe_indexes(groups: Iterable[object]) -> list[int]:
    """Return each row's stripe index, restarting at 0 whenever its group changes."""
    indexes: list[int] = []
    group: object = None
    row_index = 0
    for row_group in groups:
        if row_group != group or not indexes:
            group, row_index = row_group, 0
        indexes.append(row_index)
        row_index += 1
    return indexes


@dataclass(frozen=True, slots=True)
class GridCursor:
    """The focused item of a grid of columns, by column and row; the columns may differ in length.

    Attributes:
        col: The column.
        idx: The row within the column.

    """

    col: int = 0
    idx: int = 0

    def up(self, col_len: Callable[[int], int]) -> GridCursor | None:
        """Return the cursor a row up: from the top of a column, the bottom of the one before.

        Args:
            col_len: How many items a column holds.

        Returns:
            The cursor moved; this one when its column is empty; None when it is at the
            top of the first column, or the column before is empty, so the move leaves
            the grid upwards.

        """
        if self.idx > 0:
            return self if col_len(self.col) == 0 else GridCursor(self.col, self.idx - 1)
        if self.col > 0 and col_len(self.col - 1) > 0:
            return GridCursor(self.col - 1, col_len(self.col - 1) - 1)
        return None

    def down(self, num_columns: int, col_len: Callable[[int], int]) -> GridCursor | None:
        """Return the cursor a row down: from the bottom of a column, the top of the next.

        Returns:
            The cursor moved, or None when there is nowhere to go: an empty column, or
            the bottom of the last column (or of one followed by an empty column).

        """
        count = col_len(self.col)
        if count == 0:
            return None
        if self.idx + 1 < count:
            return GridCursor(self.col, self.idx + 1)
        next_col = self.col + 1
        if next_col < num_columns and col_len(next_col) > 0:
            return GridCursor(next_col, 0)
        return None

    def sideways(
        self, delta: int, num_columns: int, col_len: Callable[[int], int]
    ) -> GridCursor | None:
        """Return the cursor `delta` columns over, at the same row or the column's last.

        Returns:
            The cursor moved, or None when the column is off the grid or empty.

        """
        new_col = self.col + delta
        if new_col < 0 or new_col >= num_columns:
            return None
        count = col_len(new_col)
        if count == 0:
            return None
        return GridCursor(new_col, min(self.idx, count - 1))

    def resync(self, btn_idx: int | None, old_count: int, new_count: int) -> GridCursor:
        """Return the cursor after the column's rows changed under a pressed button.

        Args:
            btn_idx: Where the pressed button is now, or None if it is gone.
            old_count: The column's rows before the press.
            new_count: The column's rows now.

        Returns:
            On the first row opened under the button when rows were added; else on the
            button itself (or where the cursor was, held within the column).

        """
        base = clamped(self.idx, new_count) if btn_idx is None else btn_idx
        if new_count > old_count:
            return GridCursor(self.col, min(base + 1, new_count - 1))
        return GridCursor(self.col, base)
