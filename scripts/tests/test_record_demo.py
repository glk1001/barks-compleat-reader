"""Unit tests for the demo recorder's pure logic and its log-driven waits.

Nothing here starts the app: the sequencing that used to need a 90-second
recording to check is exercised against a stub driver instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import record_demo
from record_demo import (
    OUTPUTS,
    POSTER_BEAT,
    BeatError,
    Driver,
    Pick,
    beat_names,
    even,
    find_beat,
    missing_clips,
    parse_geometry,
    select_beats,
)

if TYPE_CHECKING:
    from pathlib import Path

EXPECTED_REGION = (782, 1224, 59, 10)
EXPECTED_DOWNS = 2
THREE_TURNS, FOUR_RESTS = 3, 4
ODD_HEIGHT, EVEN_HEIGHT = 1225, 1224
EVEN_WIDTH = 782

XWININFO = """xwininfo: Window id: 0x2e0 (the root window) (has no name)

  Root window id: 0x2e0 (the root window) (has no name)
     1 child:
     0x200007 "Compleat Barks Disney Reader": ("barks-reader" "barks-reader")  \
782x1225+59+10  +59+10
"""


class TestEven:
    def test_rounds_odd_down(self) -> None:
        assert even(ODD_HEIGHT) == EVEN_HEIGHT

    def test_leaves_even_alone(self) -> None:
        assert even(EVEN_WIDTH) == EVEN_WIDTH


class TestParseGeometry:
    def test_reads_the_window_line(self) -> None:
        assert parse_geometry(XWININFO, "Compleat Barks Disney Reader") == EXPECTED_REGION

    def test_raises_when_the_window_is_absent(self) -> None:
        with pytest.raises(BeatError, match="could not find the app window"):
            parse_geometry(XWININFO, "Some Other Window")


class TestSelectBeats:
    NAMES = ("one", "two", "three")

    def test_records_everything_by_default(self) -> None:
        assert select_beats(self.NAMES, None, None, stitch_only=False) == ["one", "two", "three"]

    def test_only_records_one(self) -> None:
        assert select_beats(self.NAMES, "two", None, stitch_only=False) == ["two"]

    def test_from_records_the_tail(self) -> None:
        assert select_beats(self.NAMES, None, "two", stitch_only=False) == ["two", "three"]

    def test_stitch_records_nothing(self) -> None:
        assert select_beats(self.NAMES, None, None, stitch_only=True) == []


class TestMissingClips:
    def test_reports_only_the_absent(self, tmp_path: Path) -> None:
        (tmp_path / "here.mp4").write_bytes(b"")
        assert missing_clips(["here", "gone"], tmp_path) == ["gone"]


class TestBeatRegistry:
    """Guards for the wiring that a typo would otherwise break silently."""

    def test_every_output_names_real_beats(self) -> None:
        known = set(beat_names())
        for output, beats in OUTPUTS.items():
            unknown = set(beats) - known
            assert not unknown, f"{output} names beats that do not exist: {sorted(unknown)}"

    def test_poster_beat_exists(self) -> None:
        assert POSTER_BEAT in beat_names()

    def test_beat_names_are_unique(self) -> None:
        names = beat_names()
        assert len(names) == len(set(names))

    def test_every_beat_has_a_node_ending_at_root(self) -> None:
        for name in beat_names():
            node = find_beat(name).node
            assert node, f"{name} has no start node"
            assert node[-1] == "root", f"{name} node is not leaf-to-root: {node}"

    def test_unknown_beat_raises(self) -> None:
        with pytest.raises(BeatError, match="no such beat: nope"):
            find_beat("nope")


class TestPick:
    def test_defaults(self) -> None:
        pick = Pick("GOOD_DEEDS")
        assert (pick.pages, pick.dwell) == (2, 2.5)

    def test_per_story_overrides(self) -> None:
        pick = Pick("SILENT_NIGHT", pages=1, dwell=4.0)
        assert (pick.pages, pick.dwell) == (1, 4.0)


def _stub_driver() -> Driver:
    """Return a Driver with no probe attached, for exercising its own logic."""
    with patch.object(Driver, "__init__", lambda _self, *_a, **_kw: None):
        return Driver()


class TestSelectNode:
    def test_stops_as_soon_as_the_node_is_current(self) -> None:
        driver = _stub_driver()
        with (
            patch.object(Driver, "current_node", return_value="Themes"),
            patch.object(Driver, "key") as key,
        ):
            driver.select_node("Themes")
        key.assert_not_called()

    def test_walks_down_until_it_arrives(self) -> None:
        driver = _stub_driver()
        reads = iter(["Categories", "Search", "Themes"])
        with (
            patch.object(Driver, "current_node", side_effect=lambda: next(reads)),
            patch.object(Driver, "key") as key,
            patch.object(record_demo.time, "sleep"),
        ):
            driver.select_node("Themes")
        assert key.call_count == EXPECTED_DOWNS

    def test_raises_when_the_tree_stops_moving(self) -> None:
        """Two identical reads in a row means the selection cannot go further down."""
        driver = _stub_driver()
        with (
            patch.object(Driver, "current_node", return_value="Bottom"),
            patch.object(Driver, "key"),
            patch.object(record_demo.time, "sleep"),
            pytest.raises(BeatError, match='tree stopped at "Bottom"'),
        ):
            driver.select_node("Nowhere")


class TestCutAlignment:
    """browse_tree and open_comic must land on the same story, or the cut jumps."""

    def test_open_comic_setup_walks_the_shared_number_of_steps(self) -> None:
        driver = _stub_driver()
        setup = find_beat("open_comic").setup
        assert setup is not None, "open_comic needs a setup to line its cut up"
        with patch.object(Driver, "key") as key, patch.object(Driver, "settle"):
            setup(driver)
        downs = [k for call in key.call_args_list for k in call.args]
        assert downs == ["Down"] * record_demo.BROWSE_TITLE_STEPS

    def test_open_comic_starts_in_the_range_browse_tree_opens(self) -> None:
        assert find_beat("open_comic").node[0] == record_demo.BROWSE_RANGE


class TestReadPages:
    """Every beat that reads a comic turns exactly `pages - 1` times."""

    @staticmethod
    def _turns_for(pages: int) -> int:
        driver = _stub_driver()
        with (
            patch.object(Driver, "key_then_wait") as turn,
            patch.object(Driver, "hold"),
        ):
            driver.read_pages(Pick("X", pages=pages, dwell=0))
        return turn.call_count

    def test_one_page_never_turns(self) -> None:
        assert self._turns_for(1) == 0

    def test_turns_one_less_than_the_page_count(self) -> None:
        assert self._turns_for(4) == THREE_TURNS

    def test_rests_on_every_page(self) -> None:
        driver = _stub_driver()
        with (
            patch.object(Driver, "key_then_wait"),
            patch.object(Driver, "hold") as rest,
        ):
            driver.read_pages(Pick("X", pages=4, dwell=1.5))
        assert rest.call_count == FOUR_RESTS


class TestGotoPage:
    """Steps through the page list are the difference between two page numbers."""

    @staticmethod
    def _steps(target: int, current: int) -> list[str]:
        driver = _stub_driver()
        with (
            patch.object(Driver, "key") as key,
            patch.object(Driver, "key_then_wait"),
            patch.object(Driver, "settle"),
            patch.object(Driver, "hold"),
        ):
            driver.goto_page(target, current)
        pressed = [k for call in key.call_args_list for k in call.args]
        return pressed[2:]  # past the Escape and Left that reach the button

    def test_steps_down_to_a_later_page(self) -> None:
        steps = self._steps(18, 4)
        assert steps == ["Return", *["Down"] * 14]

    def test_steps_up_to_an_earlier_page(self) -> None:
        steps = self._steps(2, 5)
        assert steps == ["Return", *["Up"] * 3]

    def test_no_steps_when_already_there(self) -> None:
        assert self._steps(7, 7) == ["Return"]

    def test_waits_for_the_page_it_asked_for(self) -> None:
        driver = _stub_driver()
        with (
            patch.object(Driver, "key"),
            patch.object(Driver, "key_then_wait") as wait,
            patch.object(Driver, "settle"),
            patch.object(Driver, "hold"),
        ):
            driver.goto_page(18, 4)
        assert wait.call_args.args[0] == "Showed page 18"


class TestKeyThenWait:
    def test_waits_for_a_new_match_not_an_old_one(self) -> None:
        """Regression: the marker fires once per comic, so an old match must not count.

        `gui-probe wait` greps the whole log and would return instantly on the
        previous story's line, cutting away before this one had drawn.
        """
        driver = _stub_driver()
        counts = iter([1, 1, 2])
        with (
            patch.object(Driver, "match_count", side_effect=lambda _p: next(counts)),
            patch.object(Driver, "key") as key,
            patch.object(record_demo.time, "sleep"),
        ):
            driver.key_then_wait("All images loaded", 30, "Return")
        key.assert_called_once_with("Return")

    def test_raises_when_the_marker_never_arrives(self) -> None:
        driver = _stub_driver()
        with (
            patch.object(Driver, "match_count", return_value=3),
            patch.object(Driver, "key"),
            patch.object(record_demo.time, "sleep"),
            pytest.raises(BeatError, match="beat stalled"),
        ):
            driver.key_then_wait("Showed page", 0, "Right")
