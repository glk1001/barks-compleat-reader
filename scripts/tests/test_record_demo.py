"""Unit tests for the demo recorder's pure logic and its beat wiring.

Nothing here starts the app: the sequencing that used to need a 90-second
recording to check is exercised against a stub driver instead. The driver's own
logic is covered in test_gui_driver.py.
"""

# cspell:ignore windowmove windowsize
from __future__ import annotations

import json
import os
import re
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import record_demo
from barks_fantagraphics.barks_titles import ENUM_TO_STR_TITLE, Titles
from barks_reader.core import log_markers
from barks_reader.core.main_layout import MATCH_THE_SCREEN, MainLayoutMode, choose_main_layout
from record_demo import (
    OUTPUTS,
    POSTER_BEAT,
    Beat,
    BeatError,
    Driver,
    Grab,
    Recorder,
    beat_names,
    check_same_encode,
    crop_to_aspect,
    even,
    find_beat,
    missing_clips,
    parse_args,
    parse_geometry,
    parse_root_size,
    parse_window_id,
    select_beats,
    validate,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    KeysPressed = Callable[[MagicMock], list[str]]

EXPECTED_REGION = (782, 1224, 59, 10)
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


class TestWholeScreenGrab:
    """The fullscreen beat films the screen and is fitted to the other clips' size."""

    ROOT = "xwininfo: Window id: 0x2e0 (the root window)\n\n  Width: 900\n  Height: 1300\n"

    def test_reads_the_window_id(self) -> None:
        assert parse_window_id(XWININFO, "Compleat Barks Disney Reader") == "0x200007"

    def test_raises_without_the_window(self) -> None:
        with pytest.raises(BeatError, match="could not find the app window"):
            parse_window_id(XWININFO, "Some Other Window")

    def test_reads_the_screen_size(self) -> None:
        assert parse_root_size(self.ROOT) == (900, 1300)

    def test_raises_without_a_size(self) -> None:
        with pytest.raises(BeatError, match="screen size"):
            parse_root_size("nothing here")

    def test_a_taller_clip_shape_trims_the_sides(self) -> None:
        """900x1300 to the clips' 782x1224: full height, 35 pixels off each side."""
        assert crop_to_aspect(900, 1300, 782, 1224) == (830, 1300, 35, 0)

    def test_a_wider_clip_shape_trims_top_and_bottom(self) -> None:
        assert crop_to_aspect(1000, 1000, 1600, 900) == (1000, 562, 0, 219)

    def test_the_same_shape_keeps_the_whole_screen(self) -> None:
        assert crop_to_aspect(1564, 2448, 782, 1224) == (1564, 2448, 0, 0)

    def test_the_crop_is_even_sized(self) -> None:
        width, height, _, _ = crop_to_aspect(901, 1301, 782, 1224)
        assert width % 2 == 0
        assert height % 2 == 0

    @staticmethod
    def _recorder() -> Recorder:
        recorder = Recorder.__new__(Recorder)
        recorder._ffmpeg = None  # noqa: SLF001
        return recorder

    def test_a_window_beat_grabs_the_window(self) -> None:
        with patch.object(Recorder, "app_region", return_value=(782, 1224, 59, 10)):
            grab = self._recorder().grab_for(Beat(name="b", node=["root"]))
        assert grab == Grab(782, 1224, 59, 10)

    def test_a_whole_screen_beat_grabs_the_screen_fitted_to_the_window(self) -> None:
        with (
            patch.object(Recorder, "app_region", return_value=(782, 1224, 59, 10)),
            patch.object(Recorder, "root_size", return_value=(900, 1300)),
        ):
            grab = self._recorder().grab_for(Beat(name="b", node=["root"], whole_screen=True))
        assert grab == Grab(900, 1300, 0, 0, crop=(830, 1300, 35, 0), out_size=(782, 1224))

    @staticmethod
    def _ffmpeg_argv(grab: Grab) -> list[str]:
        with patch.object(record_demo.subprocess, "Popen") as popen:
            TestWholeScreenGrab._recorder()._start_ffmpeg(Path("x.mp4"), grab, Path("cap.txt"))  # noqa: SLF001
        return popen.call_args.args[0]

    def test_the_screen_is_cropped_and_scaled_before_the_caption(self) -> None:
        argv = self._ffmpeg_argv(
            Grab(900, 1300, 0, 0, crop=(830, 1300, 35, 0), out_size=(782, 1224))
        )
        assert argv[argv.index("-video_size") + 1] == "900x1300"
        assert argv[argv.index("-i") + 1].endswith("+0,0")
        filters = argv[argv.index("-vf") + 1].split(",")
        assert filters[0] == "crop=830:1300:35:0"
        assert filters[1].startswith("scale=782:1224")
        assert filters[2].startswith("drawtext=")

    def test_a_window_grab_has_only_the_caption(self) -> None:
        argv = self._ffmpeg_argv(Grab(782, 1224, 59, 10))
        assert argv[argv.index("-video_size") + 1] == "782x1224"
        assert argv[argv.index("-i") + 1].endswith("+59,10")
        assert argv[argv.index("-vf") + 1].startswith("drawtext=")

    def test_fitting_the_window_moves_it_to_the_whole_screen(self) -> None:
        calls: list[list[str]] = []

        def fake_run(argv: list[str], **_kw: object) -> MagicMock:
            calls.append(list(argv))
            result = MagicMock()
            result.returncode = 0
            result.stdout = self.ROOT if argv[1:] == ["-root"] else XWININFO
            return result

        with (
            patch.object(record_demo.shutil, "which", return_value="/usr/bin/xdotool"),
            patch.object(record_demo.subprocess, "run", side_effect=fake_run),
        ):
            record_demo.fit_app_window_to_screen()
        assert calls[-1] == [
            "/usr/bin/xdotool",
            "windowmove",
            "0x200007",
            "0",
            "0",
            "windowsize",
            "0x200007",
            "900",
            "1300",
        ]

    def test_fitting_the_window_needs_xdotool(self) -> None:
        with (
            patch.object(record_demo.shutil, "which", return_value=None),
            pytest.raises(BeatError, match="xdotool"),
        ):
            record_demo.fit_app_window_to_screen()


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

    def test_only_the_fullscreen_beat_films_the_whole_screen(self) -> None:
        """Fullscreen outgrows the window region, so that beat alone grabs the screen."""
        whole = [b.name for b in record_demo.BEATS if b.whole_screen]
        assert whole == ["fullscreen"]

    def test_the_fullscreen_beat_follows_read_story_in_the_tour(self) -> None:
        tour = OUTPUTS["walkthrough.mp4"]
        assert tour.index("fullscreen") == tour.index("read_story") + 1

    def test_every_named_pick_has_a_pinned_cue(self) -> None:
        """A story a beat opens by name must be pinned, or the demo depends on the machine."""
        named = [
            record_demo.READ_STORY_PICK.title,
            record_demo.SERIES_PICK.title,
            record_demo.SEARCH_TITLE_PICK.title,
            record_demo.FULLSCREEN_PICK.title,
            record_demo.WIKI_SIDEBAR_PICK,
            *(p.title for p in record_demo.CENSORED_PICKS),
        ]
        for enum_name in named:
            display = ENUM_TO_STR_TITLE[Titles[enum_name]]
            assert display in record_demo.PINNED_CUES, f"{enum_name} ({display}) is not pinned"
        assert record_demo.SEARCH_WORD_PICK in record_demo.PINNED_CUES


@pytest.fixture
def keys_of(
    new_stub_driver: Callable[[], Driver], keys_pressed: KeysPressed
) -> Callable[[object], list[str]]:
    """Every key a beat or setup presses, in order, each run on a fresh driver."""

    def _keys_of(run: object) -> list[str]:
        driver = new_stub_driver()
        moves = iter(["Chronological", record_demo.BROWSE_RANGE])
        with (
            patch.object(Driver, "key") as key,
            patch.object(Driver, "key_then_wait", side_effect=lambda _p, *k, **_kw: key(*k)),
            patch.object(Driver, "expect", return_value=nullcontext()),
            patch.object(Driver, "settle"),
            patch.object(Driver, "hold"),
            patch.object(Driver, "wait_title_fade"),
            patch.object(Driver, "select_node", side_effect=lambda _n: next(moves, None)),
        ):
            run(driver)  # ty: ignore[call-non-callable]
        return keys_pressed(key)

    return _keys_of


class TestCutAlignment:
    """browse_tree and open_comic must land on the same story, or the cut jumps."""

    def test_open_comic_setup_replays_the_same_keys_as_browse_tree(
        self, keys_of: Callable[[object], list[str]]
    ) -> None:
        """Same keys in the same order, or the tree ends up scrolled differently.

        browse_tree does its collapse in its setup and the rest in its body;
        open_comic does both in its setup, so the two are compared end to end.
        """
        browse, opener = find_beat("browse_tree"), find_beat("open_comic")
        assert browse.setup is not None
        assert opener.setup is not None, "open_comic needs a setup to line its cut up"
        assert keys_of(opener.setup) == keys_of(browse.setup) + keys_of(browse.body)

    def test_both_beats_start_from_the_same_node(self) -> None:
        assert find_beat("open_comic").node == find_beat("browse_tree").node

    def test_the_replay_walks_the_shared_number_of_steps(
        self, keys_of: Callable[[object], list[str]]
    ) -> None:
        setup = find_beat("open_comic").setup
        assert setup is not None
        downs = [k for k in keys_of(setup) if k == "Down"]
        assert len(downs) == record_demo.BROWSE_TITLE_STEPS


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
    def _validate(*argv: str, xdotool: str | None = "/usr/bin/xdotool") -> None:
        with patch.object(record_demo.shutil, "which", return_value=xdotool):
            validate(parse_args(list(argv)))

    def test_plain_runs_pass(self) -> None:
        self._validate()
        self._validate("--clean")
        self._validate("--only", "browse_tree", "--output", "demo.mp4")

    def test_recording_the_fullscreen_beat_needs_xdotool(self) -> None:
        with pytest.raises(BeatError, match="xdotool"):
            self._validate(xdotool=None)
        with pytest.raises(BeatError, match="xdotool"):
            self._validate("--only", "fullscreen", xdotool=None)

    def test_a_run_without_the_fullscreen_beat_needs_no_xdotool(self) -> None:
        """CI's runners have no xdotool, and neither does a stitch need one."""
        self._validate("--stitch", xdotool=None)
        self._validate("--only", "browse_tree", xdotool=None)

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


class TestBeatMarkersMatchTheApp:
    """The recorder is stdlib-only, so it carries copies of the app's marker text.

    Each copy must match the line the app actually logs, which is written once in
    ``barks_reader.core.log_markers``.
    """

    @pytest.mark.parametrize(
        ("recorder_regex", "app_line"),
        [
            (
                record_demo.ALL_IMAGES_LOADED,
                log_markers.ALL_IMAGES_LOADED.format(elapsed="1s", index=0),
            ),
            (
                record_demo.GOTO_TITLE.format(name="VACATION_TIME"),
                log_markers.GOTO_TITLE.format(name="VACATION_TIME", filename="x.png"),
            ),
            (record_demo.WORD_CHIP_SELECTED, log_markers.WORD_SELECTED_CHIP.format(word="airline")),
            (
                record_demo.SHOW_BUBBLES_FOR.format(title="Adventure Down Under"),
                log_markers.SHOW_BUBBLES_FOR_SEARCH.format(title="Adventure Down Under", text="a"),
            ),
            (
                record_demo.BUBBLE_PRESS.format(title="Adventure Down Under"),
                log_markers.WORD_BUBBLE_PRESS.format(title="Adventure Down Under", page=3),
            ),
            (record_demo.BUBBLES_POPUP_OPENED, log_markers.BUBBLES_POPUP_OPENED),
            (
                re.escape(record_demo.HISTORY_VIEW_SELECTED.format(view="titles")),
                log_markers.HISTORY_SELECTED_VIEW.format(view="titles"),
            ),
            (record_demo.BUBBLES_POPUP_DISMISSED, log_markers.BUBBLES_POPUP_DISMISSED),
            (
                record_demo.SEARCH_MODE_SET.format(mode="Word"),
                log_markers.SEARCH_MODE_SET.format(mode="Word"),
            ),
            (record_demo.WIKI_ACTIVE, log_markers.WIKI_READER_ACTIVE),
            (
                record_demo.ENTERED_FULLSCREEN,
                log_markers.ENTERED_FULLSCREEN.format(screen="ComicBookReaderScreen"),
            ),
            (
                record_demo.NODE_SELECTED.format(name="VOODOO_HOODOO"),
                log_markers.NEW_SELECTED_NODE.format(name="VOODOO_HOODOO", previous="X"),
            ),
            (
                record_demo.LETTER_POPULATED,
                log_markers.INDEX_LETTER_POPULATED.format(letter="B", elapsed="1ms"),
            ),
            (
                record_demo.MAIN_LAYOUT_SPREAD,
                log_markers.MAIN_LAYOUT_MODE.format(
                    mode="spread", reason="boot", screen=record_demo.DEMO_SCREEN
                ),
            ),
        ],
    )
    def test_the_recorder_regex_matches_the_app_line(
        self, recorder_regex: str, app_line: str
    ) -> None:
        assert re.search(recorder_regex, app_line), f"/{recorder_regex}/ vs {app_line!r}"

    def test_a_filled_field_does_not_match_another_title(self) -> None:
        other = log_markers.GOTO_TITLE.format(name="VACATION_MISERY", filename="x.png")
        assert not re.search(record_demo.GOTO_TITLE.format(name="VACATION_TIME"), other)


class TestCannedHistory:
    """The Reading beat films this journal, so it must be one the app reads whole."""

    def test_every_title_is_a_real_display_title(self) -> None:
        display_titles = set(ENUM_TO_STR_TITLE)
        for read in record_demo.CANNED_HISTORY:
            assert read.title in display_titles, read.title

    def test_the_file_reads_back_as_the_app_reads_it(self) -> None:
        from barks_reader.core.reading_history import ReadEvent  # noqa: PLC0415

        events = [ReadEvent.from_json(e) for e in record_demo.canned_history_events()]
        assert len(events) == len(record_demo.CANNED_HISTORY)
        for event in events:
            assert event.closed_at is not None
            assert event.closed_at > event.opened_at
        assert len({e.event_id for e in events}) == len(events), "ids must be unique"
        assert events == sorted(events, key=lambda e: e.opened_at), (
            "oldest first, as the app keeps it"
        )

    def test_the_file_is_the_same_on_every_run(self) -> None:
        assert record_demo.canned_history_json() == record_demo.canned_history_json()

    @staticmethod
    def _recorder_for(tmp_path: Path) -> Recorder:
        config = tmp_path / "barks-reader.json"
        config.write_text("{}", encoding="utf-8")
        _write_ini(tmp_path, "DEBUG")
        with patch.object(record_demo, "probe", return_value=str(config)):
            return Recorder(tmp_path, work_dir=tmp_path)

    def test_a_boot_writes_the_canned_history_and_close_puts_the_users_back(
        self, tmp_path: Path
    ) -> None:
        history = tmp_path / record_demo.HISTORY_FILE_NAME
        history.write_text('{"version": 1, "events": ["mine"]}', encoding="utf-8")
        recorder = self._recorder_for(tmp_path)
        with patch.object(record_demo, "boot_app_at"):
            recorder.boot_at(["root"])
        assert "mine" not in history.read_text(encoding="utf-8")
        assert json.loads(history.read_text(encoding="utf-8")) == record_demo.canned_history_json()
        with patch.object(record_demo, "probe"):
            recorder.close()
        assert history.read_text(encoding="utf-8") == '{"version": 1, "events": ["mine"]}'

    def test_a_profile_with_no_history_gets_none_back(self, tmp_path: Path) -> None:
        history = tmp_path / record_demo.HISTORY_FILE_NAME
        recorder = self._recorder_for(tmp_path)
        with patch.object(record_demo, "boot_app_at"):
            recorder.boot_at(["root"])
        assert history.is_file()
        with patch.object(record_demo, "probe"):
            recorder.close()
        assert not history.exists()


class TestChapteredOutputs:
    """A manifest is written for the outputs the page reads chapters from, and no other."""

    WEBSITE = Path(record_demo.__file__).resolve().parent.parent / "website"

    def test_chaptered_outputs_are_outputs(self) -> None:
        assert set(OUTPUTS) >= record_demo.CHAPTERED_OUTPUTS

    def test_the_page_reads_exactly_the_chaptered_manifests(self) -> None:
        page = (self.WEBSITE / "app.html").read_text(encoding="utf-8")
        fetched = set(re.findall(r"fetch\('([\w-]+-chapters\.json)'\)", page))
        wanted = {f"{Path(name).stem}-chapters.json" for name in record_demo.CHAPTERED_OUTPUTS}
        assert fetched == wanted

    def test_no_manifest_is_left_for_an_output_without_chapters(self) -> None:
        for name in set(OUTPUTS) - record_demo.CHAPTERED_OUTPUTS:
            assert not (self.WEBSITE / f"{Path(name).stem}-chapters.json").exists(), name

    def test_stitch_writes_a_manifest_only_when_chaptered(self, tmp_path: Path) -> None:
        for beat in ("a", "b"):
            (tmp_path / f"{beat}.mp4").write_bytes(b"")
        with (
            patch.object(record_demo, "check_same_encode"),
            patch.object(record_demo, "_run_ffmpeg"),
            patch.object(record_demo, "duration_of", return_value=1.0),
            patch.object(record_demo, "_human_size", return_value="1K"),
            patch.object(record_demo, "write_chapters", return_value=tmp_path / "x") as writer,
            patch.object(record_demo, "CHAPTERED_OUTPUTS", frozenset({"tour.mp4"})),
        ):
            record_demo.stitch("tour.mp4", ("a", "b"), tmp_path, tmp_path)
            record_demo.stitch("hero.mp4", ("a", "b"), tmp_path, tmp_path)
        assert [c.args[0].name for c in writer.call_args_list] == ["tour.mp4"]


class TestTheSpread:
    """The demo is filmed on the two-page spread, and the recorder makes sure of it."""

    def test_the_demo_screen_gives_the_spread_by_matching_it(self) -> None:
        """A profile left on the default setting comes up as the spread on DEMO_SCREEN.

        Whatever the action bar's height comes to in pixels, the pair of pages fits.
        """
        width, height = (int(n) for n in record_demo.DEMO_SCREEN.split("x"))
        for chrome in (0, 45, 90):
            layout = choose_main_layout(MATCH_THE_SCREEN, width, height, chrome)
            assert layout is MainLayoutMode.SPREAD, chrome

    def test_the_demo_screen_keeps_nearly_all_of_a_spread_clip(self) -> None:
        """The fullscreen beat's crop to a spread clip's shape trims a few pixels a side."""
        width, height = (int(n) for n in record_demo.DEMO_SCREEN.split("x"))
        crop_width, crop_height, x, y = crop_to_aspect(width, height, 1592, 1224)
        assert (crop_height, y) == (height, 0)
        assert width - crop_width <= 80  # noqa: PLR2004
        assert x == (width - crop_width) // 2

    def test_a_boot_on_the_single_page_is_refused(
        self, new_stub_driver: Callable[[], Driver]
    ) -> None:
        driver = new_stub_driver()
        driver.log_path.write_text(
            log_markers.MAIN_LAYOUT_MODE.format(mode="single", reason="boot", screen="900x1300")
            + "\n",
            encoding="utf-8",
        )
        with pytest.raises(BeatError, match="set 'Layout'"):
            Recorder.require_spread(driver, "browse_tree")

    def test_a_boot_on_the_spread_is_filmed(self, new_stub_driver: Callable[[], Driver]) -> None:
        driver = new_stub_driver()
        driver.log_path.write_text(
            log_markers.MAIN_LAYOUT_MODE.format(mode="spread", reason="boot", screen="1700x1300")
            + "\n",
            encoding="utf-8",
        )
        Recorder.require_spread(driver, "browse_tree")

    def test_recording_films_on_the_demo_screen_unless_told_otherwise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("BARKS_PROBE_SCREEN", raising=False)
        with patch.object(record_demo, "Recorder", side_effect=BeatError("stop here")):
            with pytest.raises(BeatError, match="stop here"):
                record_demo.record_all(["browse_tree"], Path("/nonexistent"))
            assert os.environ["BARKS_PROBE_SCREEN"] == record_demo.DEMO_SCREEN
            monkeypatch.setenv("BARKS_PROBE_SCREEN", "900x1300")
            with pytest.raises(BeatError, match="stop here"):
                record_demo.record_all(["browse_tree"], Path("/nonexistent"))
            assert os.environ["BARKS_PROBE_SCREEN"] == "900x1300"


def _write_ini(config_dir: Path, log_level: str) -> Path:
    ini = config_dir / record_demo.INI_FILE_NAME
    ini.write_text(f"[barks_reader]\nlog_level = {log_level}\n", encoding="utf-8")
    return ini


class TestTheLogLevel:
    """The beats wait on DEBUG lines, so a profile logging at INFO is refused up front."""

    @pytest.mark.parametrize("level", ["DEBUG", "TRACE", "debug"])
    def test_a_debug_profile_records(self, tmp_path: Path, level: str) -> None:
        record_demo.require_debug_log(_write_ini(tmp_path, level))

    @pytest.mark.parametrize("level", ["INFO", "WARNING"])
    def test_a_quieter_profile_is_refused(self, tmp_path: Path, level: str) -> None:
        with pytest.raises(BeatError, match=f"log_level is {level}"):
            record_demo.require_debug_log(_write_ini(tmp_path, level))

    def test_a_profile_without_an_ini_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(BeatError, match=r"no barks-reader\.ini"):
            record_demo.require_debug_log(tmp_path / record_demo.INI_FILE_NAME)

    def test_the_recorder_checks_before_its_first_boot(self, tmp_path: Path) -> None:
        config = tmp_path / "barks-reader.json"
        config.write_text("{}", encoding="utf-8")
        _write_ini(tmp_path, "INFO")
        with (
            patch.object(record_demo, "probe", return_value=str(config)),
            pytest.raises(BeatError, match="log_level is INFO"),
        ):
            Recorder(tmp_path, work_dir=tmp_path)
