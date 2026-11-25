"""Unit tests for the Kivy-free BackHistory."""

from __future__ import annotations

import pytest
from barks_reader.core.navigation import BackHistory, TreeLocation, VisitKind
from barks_reader.core.navigation.back_history import DEFAULT_MAX_ENTRIES

A: TreeLocation = ("A", "root")
B: TreeLocation = ("B", "root")
C: TreeLocation = ("C", "root")
D: TreeLocation = ("D", "root")


def _jumped(*locations: TreeLocation | None, max_entries: int = DEFAULT_MAX_ENTRIES) -> BackHistory:
    history = BackHistory(max_entries)
    for location in locations:
        history.visit(location, VisitKind.JUMP)
    return history


class TestBackHistory:
    def test_starts_nowhere_with_nothing_to_go_back_to(self) -> None:
        history = BackHistory()

        assert history.current is None
        assert history.depth == 0
        assert history.back() is None

    def test_the_first_jump_leaves_nowhere_and_remembers_nothing(self) -> None:
        history = _jumped(A)

        assert history.current == A
        assert history.depth == 0

    def test_back_walks_the_jumps_newest_first(self) -> None:
        history = _jumped(A, B, C, D)

        assert [history.back(), history.back(), history.back()] == [C, B, A]
        assert history.current == A
        assert history.back() is None
        assert history.current is None

    def test_back_remembers_nothing(self) -> None:
        # The old single slot swapped between two nodes: Back twice came back.
        history = _jumped(A, B, C)

        assert history.back() == B
        assert history.depth == 1
        assert history.back() == A
        assert history.depth == 0

    def test_a_step_moves_without_remembering(self) -> None:
        history = _jumped(A)

        history.visit(B, VisitKind.STEP)
        history.visit(C, VisitKind.STEP)

        assert history.current == C
        assert history.depth == 0

    def test_a_jump_after_steps_remembers_where_the_steps_ended(self) -> None:
        history = _jumped(A)
        history.visit(B, VisitKind.STEP)
        history.visit(C, VisitKind.STEP)

        history.visit(D, VisitKind.JUMP)

        assert history.back() == C
        assert history.back() is None

    def test_a_step_from_nowhere_remembers_nothing(self) -> None:
        history = BackHistory()

        history.visit(A, VisitKind.STEP)

        assert history.current == A
        assert history.depth == 0

    def test_a_jump_to_where_the_tree_is_remembers_nothing(self) -> None:
        history = _jumped(A, B)

        history.visit(B, VisitKind.JUMP)

        assert history.depth == 1
        assert history.back() == A

    def test_a_jump_from_the_place_on_top_is_not_remembered_twice(self) -> None:
        history = _jumped(A, B)
        history.visit(A, VisitKind.STEP)

        history.visit(C, VisitKind.JUMP)

        assert history.depth == 1
        assert history.back() == A

    def test_a_collapse_is_a_jump_to_nowhere_that_back_undoes(self) -> None:
        history = _jumped(A, B)

        history.visit(None, VisitKind.JUMP)

        assert history.current is None
        assert history.back() == B
        assert history.back() == A

    def test_a_jump_from_nowhere_remembers_nothing(self) -> None:
        history = _jumped(A, None, B)

        assert history.depth == 1
        assert history.back() == A

    def test_going_back_then_arriving_there_remembers_nothing(self) -> None:
        # Going back selects the node, and the tree reports that selection.
        history = _jumped(A, B, C)

        gone_back_to = history.back()
        history.visit(gone_back_to, VisitKind.JUMP)

        assert history.depth == 1
        assert history.back() == A

    def test_the_oldest_place_is_dropped_at_the_cap(self) -> None:
        cap = 2
        history = _jumped(A, B, C, D, max_entries=cap)

        assert history.depth == cap
        assert [history.back(), history.back(), history.back()] == [C, B, None]

    def test_the_default_cap(self) -> None:
        history = BackHistory()
        extra = 10
        for number in range(DEFAULT_MAX_ENTRIES + extra):
            history.visit((str(number), "root"), VisitKind.JUMP)

        assert history.depth == DEFAULT_MAX_ENTRIES
        oldest = [history.back() for _ in range(DEFAULT_MAX_ENTRIES)][-1]
        assert oldest == (str(extra - 1), "root")
        assert history.back() is None

    @pytest.mark.parametrize("max_entries", [0, -1])
    def test_a_cap_below_one_is_refused(self, max_entries: int) -> None:
        with pytest.raises(ValueError, match="at least one entry"):
            BackHistory(max_entries)
