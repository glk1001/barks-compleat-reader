"""Tests for the remote-keys check over the GUI tests.

Each case is a shape the GUI tests actually use: literal keys, ``*["Down"] * n``,
a key chosen from a module constant, a tuple assignment through a conditional,
and the one desktop key with its waiver.
"""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from check_gui_keys import REMOTE_KEYS, Press, main, presses_in

if TYPE_CHECKING:
    from pathlib import Path


def _problems(source: str) -> list[str | None]:
    return [p.problem() for p in presses_in(dedent(source))]


class TestLiteralKeys:
    def test_the_six_remote_keys_pass(self) -> None:
        source = """
            def test_it(d):
                d.key("Escape", "Return")
                d.key_then_wait(PATTERN, "Up", "Down", timeout=5)
                d.move_focus("Left", "Right")
        """
        assert _problems(source) == [None] * 6

    def test_a_desktop_key_fails_and_names_itself(self) -> None:
        source = """
            def test_it(d):
                d.key_then_wait(PATTERN, "Delete")
        """
        (problem,) = _problems(source)
        assert problem is not None
        assert problem.startswith("'Delete' is not a remote key")
        assert "# desktop key: <why>" in problem

    def test_the_pattern_argument_of_key_then_wait_is_not_a_key(self) -> None:
        source = """
            def test_it(d):
                d.key_then_wait("Some log line", "Return")
        """
        assert _problems(source) == [None]

    def test_typed_text_is_not_a_key(self) -> None:
        source = """
            def test_it(d):
                d.type_slowly("hello Tab world")
                d.main_menu_button("quit")
        """
        assert presses_in(dedent(source)) == []


class TestWaiver:
    def test_a_desktop_key_passes_with_the_waiver_on_the_call(self) -> None:
        source = """
            def test_it(d):
                d.key_then_wait(
                    PATTERN,
                    "Delete",  # desktop key: no remote equivalent
                )
        """
        (press,) = presses_in(dedent(source))
        assert press.waived
        assert press.problem() is None

    def test_the_waiver_needs_a_reason(self) -> None:
        source = """
            def test_it(d):
                d.key("Delete")  # desktop key:
        """
        (press,) = presses_in(dedent(source))
        assert not press.waived
        assert press.problem() is not None

    def test_a_waiver_on_the_line_before_does_not_count(self) -> None:
        source = """
            def test_it(d):
                # desktop key: the reason
                d.key("Delete")
        """
        (press,) = presses_in(dedent(source))
        assert not press.waived


class TestTracedKeys:
    def test_a_repeated_list_is_its_element(self) -> None:
        source = """
            def test_it(d, n):
                d.move_focus(*["Down"] * n, *["Right"] * 2)
        """
        assert [p.keys for p in presses_in(dedent(source))] == [{"Down"}, {"Right"}]

    def test_a_key_chosen_from_a_module_constant_is_every_member(self) -> None:
        source = """
            KEYS = ("Escape", "Return", "Up", "Down", "Left", "Right")

            def test_it(d, rng):
                key = "Escape" if popup_open(d) else rng.choice(KEYS)
                d.key_then_wait(PATTERN, key)
        """
        (press,) = presses_in(dedent(source))
        assert press.keys == REMOTE_KEYS
        assert press.problem() is None

    def test_a_tuple_assigned_through_a_conditional_pairs_by_position(self) -> None:
        source = """
            def walk(self, forward, backward):
                step, presses = ("Right", forward) if forward <= backward else ("Left", backward)
                for _ in range(presses):
                    self.move_focus(step)
        """
        (press,) = presses_in(dedent(source))
        assert press.keys == {"Right", "Left"}

    def test_a_loop_variable_is_what_it_iterates(self) -> None:
        source = """
            def test_it(d):
                for key in ("Up", "Home"):
                    d.key(key)
        """
        (press,) = presses_in(dedent(source))
        assert press.keys == {"Up", "Home"}
        assert press.problem() is not None

    def test_a_key_nothing_can_be_found_for_fails(self) -> None:
        source = """
            def press(d, key):
                d.key(key)
        """
        (press,) = presses_in(dedent(source))
        assert press.keys == frozenset()
        problem = press.problem()
        assert problem is not None
        assert problem.startswith("cannot tell which key")

    def test_a_receiver_and_a_condition_are_not_followed(self) -> None:
        """The first draft walked every node and gathered the seed and the boot nodes."""
        source = """
            NODES = {"a-story": 1}

            def test_it(boot, start, rng):
                d = boot(NODES[start], cues="none")
                key = "Escape" if open_popup(d) else rng.choice(("Up",))
                d.key(key)
        """
        (press,) = presses_in(dedent(source))
        assert press.keys == {"Escape", "Up"}


class TestKeyMethodDefinitions:
    def test_a_key_method_passing_its_keys_on_is_not_checked(self) -> None:
        source = """
            class Driver:
                def key_then_wait(self, pattern, *keys, timeout=15):
                    with self.expect(pattern, timeout):
                        self.key(*keys)

                def move_focus(self, *keys, pattern=None):
                    for key in keys:
                        self.key_then_wait(pattern, key)

                def open_it(self):
                    self.key_then_wait(self.OPENED, "Return")
        """
        (press,) = presses_in(dedent(source))
        assert press.keys == {"Return"}


class TestMain:
    @pytest.fixture
    def gui_dir(self, tmp_path: Path) -> Path:
        (tmp_path / "test_ok.py").write_text('def test_it(d):\n    d.key("Return")\n')
        return tmp_path

    def test_passes_a_clean_tree(self, gui_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        assert main([str(gui_dir)]) == 0
        assert "All 1 key press(es) across 1 file(s)" in capsys.readouterr().out

    def test_fails_a_desktop_key_with_its_file_and_line(
        self, gui_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (gui_dir / "test_bad.py").write_text('def test_it(d):\n\n    d.key("Tab")\n')
        assert main([str(gui_dir)]) == 1
        out = capsys.readouterr().out
        assert "test_bad.py:3: 'Tab' is not a remote key" in out
        assert "1 of 2 key press(es) in 2 file(s)." in out

    def test_counts_the_waived_presses(
        self, gui_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (gui_dir / "test_waived.py").write_text(
            'def test_it(d):\n    d.key("Delete")  # desktop key: because\n'
        )
        assert main([str(gui_dir)]) == 0
        assert "(1 waived as desktop keys)" in capsys.readouterr().out


class TestPress:
    def test_a_waived_remote_key_is_just_a_remote_key(self) -> None:
        assert Press(1, frozenset({"Up"}), waived=True).problem() is None
