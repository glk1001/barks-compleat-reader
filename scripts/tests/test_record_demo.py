"""Unit tests for the demo recorder's pure logic and its beat wiring.

Nothing here starts the app: the sequencing that used to need a 90-second
recording to check is exercised against a stub driver instead. The driver's own
logic is covered in test_gui_driver.py.
"""

from __future__ import annotations

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
    Recorder,
    beat_names,
    check_same_encode,
    even,
    find_beat,
    missing_clips,
    parse_args,
    parse_geometry,
    select_beats,
    validate,
)

EXPECTED_REGION = (782, 1224, 59, 10)
ODD_HEIGHT, EVEN_HEIGHT = 1225, 1224
EVEN_WIDTH = 782

XWININFO = """xwininfo: Window id: 0x2e0 (the root window) (has no name)

  Root window id: 0x2e0 (the root window) (has no name)
     1 child:
     0x200007 "Compleat Barks Disney Reader": ("barks-reader" "barks-reader")  \
782x1225+59+10  +59+10
"""


def _stub_driver() -> Driver:
    """Return a Driver with no probe attached, for exercising beat logic against."""
    with patch.object(Driver, "__init__", lambda _self, *_a, **_kw: None):
        return Driver()


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

    def test_fullscreen_is_never_pressed_by_a_beat(self) -> None:
        """It resizes the window, and the recorder grabs a fixed region."""
        source = Path(record_demo.__file__).read_text()
        assert 'press_menu_button("fullscreen")' not in source

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
