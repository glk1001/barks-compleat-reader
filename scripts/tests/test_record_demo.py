"""Unit tests for the demo recorder's pure logic and its log-driven waits.

Nothing here starts the app: the sequencing that used to need a 90-second
recording to check is exercised against a stub driver instead.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import record_demo
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from record_demo import (
    OUTPUTS,
    POSTER_BEAT,
    Beat,
    BeatError,
    Driver,
    Pick,
    Recorder,
    beat_names,
    boot_app_at,
    check_same_encode,
    even,
    find_beat,
    missing_clips,
    parse_args,
    parse_geometry,
    probe,
    select_beats,
    validate,
)

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

    def test_open_comic_setup_replays_the_same_keys_as_browse_tree(self) -> None:
        """Same keys in the same order, or the tree ends up scrolled differently.

        browse_tree does its collapse in its setup and the rest in its body;
        open_comic does both in its setup, so the two are compared end to end.
        """
        browse, opener = find_beat("browse_tree"), find_beat("open_comic")
        assert browse.setup is not None
        assert opener.setup is not None, "open_comic needs a setup to line its cut up"
        browse_keys = self._keys_of(browse.setup) + self._keys_of(browse.body)
        assert self._keys_of(opener.setup) == browse_keys

    def test_both_beats_start_from_the_same_node(self) -> None:
        assert find_beat("open_comic").node == find_beat("browse_tree").node

    def test_the_replay_walks_the_shared_number_of_steps(self) -> None:
        setup = find_beat("open_comic").setup
        assert setup is not None
        downs = [k for k in self._keys_of(setup) if k == "Down"]
        assert len(downs) == record_demo.BROWSE_TITLE_STEPS

    @staticmethod
    def _keys_of(run: object) -> list[str]:
        """Every key a beat or setup presses, in order."""
        driver = _stub_driver()
        moves = iter(["Chronological", record_demo.BROWSE_RANGE])
        with (
            patch.object(Driver, "key") as key,
            patch.object(Driver, "settle"),
            patch.object(Driver, "hold"),
            patch.object(Driver, "select_node", side_effect=lambda _n: next(moves, None)),
        ):
            run(driver)  # ty: ignore[call-non-callable]
        return [k for call in key.call_args_list for k in call.args]


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


class TestPressMenuButton:
    """Menu focus is sticky, so a second press must account for the first."""

    @staticmethod
    def _presses(driver: Driver, name: str) -> list[str]:
        with (
            patch.object(Driver, "key") as key,
            patch.object(Driver, "hold"),
        ):
            driver.press_menu_button(name)
        return [k for call in key.call_args_list for k in call.args]

    def test_walks_forward_from_the_default(self) -> None:
        """Close -> fullscreen -> double_page is two Rights on a fresh reader."""
        driver = _stub_driver()
        driver._menu_focus = "close"  # noqa: SLF001
        assert self._presses(driver, "double_page") == ["Escape", "Right", "Right", "Return"]

    def test_takes_the_short_way_round(self) -> None:
        """goto_page is one Left back from close, not five Rights forward."""
        driver = _stub_driver()
        driver._menu_focus = "close"  # noqa: SLF001
        assert self._presses(driver, "goto_page") == ["Escape", "Left", "Return"]

    def test_a_second_press_starts_where_the_first_left_off(self) -> None:
        """Regression: after a goto-page, two Rights reach fullscreen, not double-page.

        Fullscreen resizes the window on the nested display, so this silently
        wrecked the rest of the recording rather than merely showing the wrong
        thing.
        """
        driver = _stub_driver()
        driver._menu_focus = "close"  # noqa: SLF001
        self._presses(driver, "goto_page")
        presses = self._presses(driver, "double_page")
        assert "Escape" in presses
        assert presses.count("Right") == THREE_TURNS
        assert "Left" not in presses

    def test_no_movement_when_already_there(self) -> None:
        driver = _stub_driver()
        driver._menu_focus = "close"  # noqa: SLF001
        assert self._presses(driver, "close") == ["Escape", "Return"]

    def test_an_unknown_button_raises(self) -> None:
        driver = _stub_driver()
        driver._menu_focus = "close"  # noqa: SLF001
        with pytest.raises(BeatError, match="no such menu button"):
            self._presses(driver, "nope")

    def test_fullscreen_is_never_pressed_by_a_beat(self) -> None:
        """It resizes the window, and the recorder grabs a fixed region."""
        source = Path(record_demo.__file__).read_text()
        assert 'press_menu_button("fullscreen")' not in source


class TestCloseReader:
    """close_reader shares press_menu_button's walk, so it starts from the same focus."""

    def test_walks_from_where_the_last_press_left_the_menu(self) -> None:
        """After a goto-page, close is one Right on, not a fresh count from the start."""
        driver = _stub_driver()
        driver._menu_focus = "goto_page"  # noqa: SLF001
        with (
            patch.object(Driver, "key") as key,
            patch.object(Driver, "key_then_wait") as wait,
            patch.object(Driver, "hold"),
        ):
            driver.close_reader()
        assert [k for call in key.call_args_list for k in call.args] == ["Escape", "Right"]
        assert wait.call_args.args == ("Main screen is active", 15, "Return")
        assert driver._menu_focus == "close"  # noqa: SLF001


class TestGotoPage:
    """Steps through the page list are the difference between two page numbers."""

    @staticmethod
    def _steps(target: int, current: int) -> list[str]:
        driver = _stub_driver()
        driver._menu_focus = "close"  # noqa: SLF001
        with (
            patch.object(Driver, "key") as key,
            patch.object(Driver, "key_then_wait"),
            patch.object(Driver, "settle"),
            patch.object(Driver, "hold"),
            patch.object(Driver, "current_page", return_value=current),
        ):
            driver.goto_page(target)
        pressed = [k for call in key.call_args_list for k in call.args]
        return pressed[2:]  # past the Escape and Left that open the page list

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
            patch.object(Driver, "current_page", return_value=4),
        ):
            driver._menu_focus = "close"  # noqa: SLF001
            driver.goto_page(18)
        # Anchored past the number: "Showed page 3" is a prefix of "Showed page 34".
        assert wait.call_args.args[0] == "Showed page 18 in "

    def test_reads_where_it_is_rather_than_being_told(self) -> None:
        """The reader opens on whatever page the user cued, so it has to look."""
        driver = _stub_driver()
        with (
            patch.object(Driver, "key") as key,
            patch.object(Driver, "key_then_wait"),
            patch.object(Driver, "settle"),
            patch.object(Driver, "hold"),
            patch.object(Driver, "current_page", return_value=29) as where,
        ):
            driver._menu_focus = "close"  # noqa: SLF001
            driver.goto_page(31)
        where.assert_called_once()
        assert [k for call in key.call_args_list for k in call.args][2:] == [
            "Return",
            "Down",
            "Down",
        ]


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


class TestProbe:
    """Every probe call goes through one helper, which refuses to hide a failure."""

    def test_returns_stdout_on_success(self) -> None:
        done = subprocess.CompletedProcess(["x"], 0, stdout="/run/user/1/app.log\n", stderr="")
        with patch.object(record_demo.subprocess, "run", return_value=done):
            assert probe("log") == "/run/user/1/app.log\n"

    def test_raises_with_stderr_on_failure(self) -> None:
        """Regression: a failed `start` returned normally and the stale app was driven."""
        failed = subprocess.CompletedProcess(
            ["x"], 1, stdout="", stderr="gui-probe: already running (stop it first)\n"
        )
        with (
            patch.object(record_demo.subprocess, "run", return_value=failed),
            pytest.raises(BeatError, match="already running"),
        ):
            probe("start")


class TestBootAppAt:
    """Each boot pins the node, the cues and the seed, then starts the app."""

    def test_writes_node_and_pinned_cues(self, tmp_path: Path) -> None:
        config = tmp_path / "barks-reader.json"
        config.write_text(json.dumps({"AAA_Settings": {"x": 1}, "Voodoo Hoodoo": {"a": 1}}))
        cues: dict[str, dict[str, int | str] | None] = {
            "Lost in the Andes!": {"page_index": 34},
            "Voodoo Hoodoo": None,
        }
        with patch.object(record_demo, "probe") as start:
            boot_app_at(["Reading", "root"], config=config, seed=7, cues=cues)
        written = json.loads(config.read_text())
        assert written["AAA_Settings"] == {"x": 1, "last_selected_node": ["Reading", "root"]}
        assert written["Lost in the Andes!"] == {"last_read_page": {"page_index": 34}}
        assert "Voodoo Hoodoo" not in written
        assert record_demo.os.environ[record_demo.RANDOM_SEED_ENV_VAR] == "7"
        start.assert_called_once_with("start")

    def test_reads_from_the_template_when_given(self, tmp_path: Path) -> None:
        config, template = tmp_path / "cfg.json", tmp_path / "pristine.json"
        config.write_text(json.dumps({"stale": True}))
        template.write_text(json.dumps({"fresh": True}))
        with patch.object(record_demo, "probe"):
            boot_app_at(["root"], config=config, seed=None, template=template, cues={})
        written = json.loads(config.read_text())
        assert "fresh" in written
        assert "stale" not in written

    def test_every_named_pick_has_a_pinned_cue(self) -> None:
        """A story a beat opens by name must be pinned, or the demo depends on the machine."""
        named = [
            record_demo.READ_STORY_PICK.title,
            record_demo.SERIES_PICK.title,
            record_demo.SEARCH_TITLE_PICK.title,
            record_demo.WIKI_SIDEBAR_PICK,
            *(p.title for p in record_demo.CENSORED_PICKS),
        ]
        for enum_name in named:
            display = ENUM_TO_STR_TITLE[Titles[enum_name]]
            assert display in record_demo.PINNED_CUES, f"{enum_name} ({display}) is not pinned"
        assert record_demo.SEARCH_WORD_PICK in record_demo.PINNED_CUES


class TestRecordClipHandling:
    """A clip only gets its final name once the beat ran and ffmpeg stopped cleanly."""

    @staticmethod
    def _recorder(tmp_path: Path) -> Recorder:
        recorder = Recorder.__new__(Recorder)
        recorder.work_dir = tmp_path
        recorder._ffmpeg = None  # noqa: SLF001
        return recorder

    def _record(self, tmp_path: Path, body: object, failure: str | None = None) -> Path | None:
        recorder = self._recorder(tmp_path)
        item = Beat(name="b", node=["root"], body=body)  # ty: ignore[invalid-argument-type]

        def fake_start(partial: Path, *_a: object) -> None:
            partial.write_bytes(b"mp4")

        with (
            patch.object(Recorder, "boot_at"),
            patch.object(Recorder, "app_region", return_value=(10, 10, 0, 0)),
            patch.object(Recorder, "_start_ffmpeg", side_effect=fake_start),
            patch.object(Recorder, "_check_ffmpeg_running"),
            patch.object(Recorder, "_stop_ffmpeg", return_value=failure),
            patch.object(record_demo, "Driver"),
            patch.object(record_demo, "probe"),
            patch.object(record_demo.time, "sleep"),
        ):
            return recorder.record(item)

    def test_a_finished_beat_takes_the_final_name(self, tmp_path: Path) -> None:
        clip = self._record(tmp_path, lambda _d: None)
        assert clip == tmp_path / "b.mp4"
        assert clip.is_file()
        assert not (tmp_path / "b.partial.mp4").exists()

    def test_a_failed_beat_leaves_no_cached_clip(self, tmp_path: Path) -> None:
        """Regression: a truncated clip was cached and stitched by the next --stitch."""

        def body(_d: Driver) -> None:
            msg = "beat stalled"
            raise BeatError(msg)

        with pytest.raises(BeatError, match="beat stalled"):
            self._record(tmp_path, body)
        assert missing_clips(["b"], tmp_path) == ["b"]
        assert (tmp_path / "b.partial.mp4").is_file(), "the partial stays for inspection"

    def test_a_failed_recorder_is_an_error_not_a_clip(self, tmp_path: Path) -> None:
        with pytest.raises(BeatError, match=r"\[b\] ffmpeg died"):
            self._record(tmp_path, lambda _d: None, failure="ffmpeg died")
        assert missing_clips(["b"], tmp_path) == ["b"]


class TestCheckSameEncode:
    """A stream-copy concat of mismatched clips succeeds silently, so check first."""

    def test_passes_when_every_clip_matches(self, tmp_path: Path) -> None:
        with patch.object(record_demo, "stream_signature", return_value="h264,782,1224,yuv420p"):
            check_same_encode(["a", "b"], tmp_path)

    def test_names_the_odd_one_out(self, tmp_path: Path) -> None:
        sizes = {"a": "h264,782,1224,yuv420p", "b": "h264,640,1000,yuv420p"}
        with (
            patch.object(record_demo, "stream_signature", side_effect=lambda p: sizes[p.stem]),
            pytest.raises(BeatError, match=r"b: h264,640,1000"),
        ):
            check_same_encode(["a", "b"], tmp_path)


class TestValidate:
    """Flag combinations that could only fail after the recording had been done."""

    @staticmethod
    def _validate(*argv: str) -> None:
        validate(parse_args(list(argv)))

    def test_plain_runs_pass(self) -> None:
        self._validate()
        self._validate("--clean")
        self._validate("--only", "browse_tree", "--output", "demo.mp4")

    @pytest.mark.parametrize(
        "argv",
        [
            ("--clean", "--only", "browse_tree"),
            ("--clean", "--from", "reading"),
            ("--clean", "--stitch"),
        ],
    )
    def test_clean_cannot_go_with_a_selector(self, argv: tuple[str, ...]) -> None:
        with pytest.raises(BeatError, match="--clean"):
            self._validate(*argv)

    def test_only_must_be_in_the_requested_output(self) -> None:
        with pytest.raises(BeatError, match="does not contain reading"):
            self._validate("--only", "reading", "--output", "demo.mp4")
