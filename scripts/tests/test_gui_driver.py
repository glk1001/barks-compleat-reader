"""Unit tests for the GUI driver's own logic and its log-driven waits.

Nothing here starts the app: the sequencing that would otherwise need a live
boot to check is exercised against a stub driver instead.
"""

from __future__ import annotations

import json
import re
import subprocess
from contextlib import contextmanager, nullcontext
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import gui_driver
import pytest
from barks_reader.core import log_markers
from gui_driver import Driver, DriverError, Pick, boot_app_at, probe
from okf_reader.core import log_markers as okf_log_markers
from script_test_helpers import keys_recorded

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Sequence
    from pathlib import Path

    KeysPressed = Callable[[MagicMock], list[str]]

EXPECTED_DOWNS = 2
THREE_TURNS, FOUR_RESTS = 3, 4


class TestPick:
    def test_defaults(self) -> None:
        pick = Pick("GOOD_DEEDS")
        assert (pick.pages, pick.dwell) == (2, 2.5)

    def test_per_story_overrides(self) -> None:
        pick = Pick("SILENT_NIGHT", pages=1, dwell=4.0)
        assert (pick.pages, pick.dwell) == (1, 4.0)


class TestSelectNode:
    def test_stops_as_soon_as_the_node_is_current(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "current_node", return_value="Themes"),
            patch.object(Driver, "key_then_wait") as down,
        ):
            stub_driver.select_node("Themes")
        down.assert_not_called()

    def test_each_down_waits_for_the_selection_line(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "current_node", side_effect=["Categories", "Search", "Themes"]),
            patch.object(Driver, "key_then_wait") as down,
            patch.object(Driver, "hold") as hold,
        ):
            stub_driver._paced = False  # noqa: SLF001
            stub_driver.select_node("Themes")
        assert [c.args for c in down.call_args_list] == [(Driver.NODE_SELECTED, "Down")] * 2
        hold.assert_not_called()

    def test_a_paced_walk_rests_after_each_down(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "current_node", side_effect=["Categories", "Themes"]),
            patch.object(Driver, "key_then_wait"),
            patch.object(Driver, "hold") as hold,
        ):
            stub_driver.select_node("Themes")
        hold.assert_called_once_with(gui_driver.WALK_PAUSE)

    def test_raises_when_a_down_moves_nothing(self, stub_driver: Driver) -> None:
        """A Down that logs no selection within its timeout is the bottom of the tree."""
        with (
            patch.object(Driver, "current_node", return_value="Bottom"),
            patch.object(Driver, "key_then_wait", side_effect=DriverError("no new line")),
            pytest.raises(DriverError, match='tree stopped at "Bottom"'),
        ):
            stub_driver.select_node("Nowhere")


class TestReadPages:
    """Every caller that reads a comic turns exactly `pages - 1` times."""

    @staticmethod
    def _turns_for(driver: Driver, pages: int) -> int:
        with (
            patch.object(Driver, "key_then_wait") as turn,
            patch.object(Driver, "hold"),
        ):
            driver.read_pages(Pick("X", pages=pages, dwell=0))
        return turn.call_count

    def test_one_page_never_turns(self, stub_driver: Driver) -> None:
        assert self._turns_for(stub_driver, 1) == 0

    def test_turns_one_less_than_the_page_count(self, stub_driver: Driver) -> None:
        assert self._turns_for(stub_driver, 4) == THREE_TURNS

    def test_rests_on_every_page(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "key_then_wait"),
            patch.object(Driver, "hold") as rest,
        ):
            stub_driver.read_pages(Pick("X", pages=4, dwell=1.5))
        assert rest.call_count == FOUR_RESTS


class TestPressMenuButton:
    """Menu focus is sticky, so a second press must account for the first."""

    @staticmethod
    def _presses(driver: Driver, name: str, keys_pressed: KeysPressed) -> list[str]:
        with keys_recorded() as (key, _):
            driver.press_menu_button(name)
        return keys_pressed(key)

    def test_walks_forward_from_the_default(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        """Close -> fullscreen -> double_page is two Rights on a fresh reader."""
        assert self._presses(stub_driver, "double_page", keys_pressed) == [
            "Escape",
            "Right",
            "Right",
            "Return",
        ]

    def test_takes_the_short_way_round(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        """goto_page is one Left back from close, not five Rights forward."""
        assert self._presses(stub_driver, "goto_page", keys_pressed) == ["Escape", "Left", "Return"]

    def test_a_second_press_starts_where_the_first_left_off(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        """Regression: after a goto-page, two Rights reach fullscreen, not double-page.

        Fullscreen resizes the window on the nested display, so this silently
        wrecked the rest of a recording rather than merely showing the wrong
        thing.
        """
        self._presses(stub_driver, "goto_page", keys_pressed)
        presses = self._presses(stub_driver, "double_page", keys_pressed)
        assert "Escape" in presses
        assert presses.count("Right") == THREE_TURNS
        assert "Left" not in presses

    def test_no_movement_when_already_there(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        assert self._presses(stub_driver, "close", keys_pressed) == ["Escape", "Return"]

    def test_an_unknown_button_raises(self, stub_driver: Driver, keys_pressed: KeysPressed) -> None:
        with pytest.raises(DriverError, match="no such menu button"):
            self._presses(stub_driver, "nope", keys_pressed)


class TestMainMenuButton:
    """The main screen's bar is sticky too, and opens on go_back."""

    @staticmethod
    def _presses(driver: Driver, name: str, keys_pressed: KeysPressed) -> list[str]:
        with keys_recorded() as (key, _):
            driver.main_menu_button(name)
        return keys_pressed(key)

    def test_go_back_is_the_default_focus(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        assert self._presses(stub_driver, "go_back", keys_pressed) == ["Escape", "Return"]

    def test_quit_is_the_short_way_round(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        """Quit is three Lefts back from go_back, not four Rights forward."""
        assert self._presses(stub_driver, "quit", keys_pressed) == [
            "Escape",
            "Left",
            "Left",
            "Left",
            "Return",
        ]

    def test_a_second_press_starts_where_the_first_left_off(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        self._presses(stub_driver, "menu", keys_pressed)  # three Rights from go_back
        assert self._presses(stub_driver, "collapse", keys_pressed) == [
            "Escape",
            "Left",
            "Left",
            "Return",
        ]

    def test_go_back_uses_it(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "main_menu_button") as press,
        ):
            stub_driver.go_back()
        press.assert_called_once_with("go_back")

    def test_an_unknown_button_raises(self, stub_driver: Driver, keys_pressed: KeysPressed) -> None:
        with pytest.raises(DriverError, match="no such menu button"):
            self._presses(stub_driver, "nope", keys_pressed)


class TestCloseReader:
    """close_reader shares press_menu_button's walk, so it starts from the same focus."""

    def test_walks_from_where_the_last_press_left_the_menu(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        """After a goto-page, close is one Right on, not a fresh count from the start."""
        stub_driver._menu_focus = "goto_page"  # noqa: SLF001
        with keys_recorded() as (key, wait):
            stub_driver.close_reader()
        assert keys_pressed(key) == ["Escape", "Right", "Return"]
        assert wait.call_args.args == ("Main screen is active", "Return")
        assert stub_driver._menu_focus == "close"  # noqa: SLF001


class TestGotoPage:
    """Steps through the page list are the difference between two page numbers."""

    @staticmethod
    def _steps(driver: Driver, target: int, current: int, keys_pressed: KeysPressed) -> list[str]:
        with (
            keys_recorded() as (key, _),
            patch.object(Driver, "expect", return_value=nullcontext()),
            patch.object(Driver, "current_page", return_value=current),
        ):
            driver.goto_page(target)
        pressed = keys_pressed(key)
        return pressed[2:]  # past the Escape and Left that walk to the goto button

    def test_steps_down_to_a_later_page(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        steps = self._steps(stub_driver, 18, 4, keys_pressed)
        assert steps == ["Return", *["Down"] * 14, "Return"]  # open, step, pick

    def test_waits_on_the_page_the_reader_shows_when_that_is_not_the_target(
        self, stub_driver: Driver
    ) -> None:
        """Two-up the reader renders the unit's left page, so that is the line to wait on."""
        with (
            keys_recorded(),
            patch.object(Driver, "expect", return_value=nullcontext()) as expect,
            patch.object(Driver, "current_page", return_value=0),
        ):
            stub_driver.goto_page(12, shows=11)
            waited_on = [c.args[0] for c in expect.call_args_list]
        assert "Showed page 11 in " in waited_on
        assert not any("Showed page 12" in w for w in waited_on)

    def test_steps_up_to_an_earlier_page(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        steps = self._steps(stub_driver, 2, 5, keys_pressed)
        assert steps == ["Return", *["Up"] * 3, "Return"]

    def test_no_steps_when_already_there(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        assert self._steps(stub_driver, 7, 7, keys_pressed) == ["Return", "Return"]  # open, pick

    def test_waits_for_the_page_it_asked_for(self, stub_driver: Driver) -> None:
        with (
            keys_recorded(),
            patch.object(Driver, "expect", return_value=nullcontext()) as expect,
            patch.object(Driver, "current_page", return_value=4),
        ):
            stub_driver.goto_page(18)
        waited_on = [c.args[0] for c in expect.call_args_list]
        # Anchored past the number: "Showed page 3" is a prefix of "Showed page 34".
        assert "Showed page 18 in " in waited_on
        # The pick's Return is held until the dropdown has let go of the keys.
        assert waited_on[-1] == Driver.DROPDOWN_DISMISSED

    def test_reads_where_it_is_rather_than_being_told(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        """The reader opens on whatever page the user cued, so it has to look."""
        with (
            keys_recorded() as (key, _),
            patch.object(Driver, "expect", return_value=nullcontext()),
            patch.object(Driver, "current_page", return_value=29) as where,
        ):
            stub_driver.goto_page(31)
        where.assert_called_once()
        assert keys_pressed(key)[2:] == ["Return", "Down", "Down", "Return"]


class TestExpect:
    """expect() is the one wait every *_then_wait move is built on."""

    def test_waits_for_a_new_match_not_an_old_one(self, stub_driver: Driver) -> None:
        """Regression: the marker fires once per comic, so an old match must not count.

        `gui-probe wait` greps the whole log and would return instantly on the
        previous story's line, carrying on before this one had drawn.
        """
        counts = iter([1, 1, 2])
        with (
            patch.object(Driver, "match_count", side_effect=lambda _p: next(counts)),
            patch.object(Driver, "key") as key,
            patch.object(gui_driver.time, "sleep"),
        ):
            stub_driver.key_then_wait("All images loaded", "Return", timeout=30)
        key.assert_called_once_with("Return")

    def test_raises_when_the_marker_never_arrives(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "match_count", return_value=3),
            patch.object(Driver, "key"),
            patch.object(gui_driver.time, "sleep"),
            pytest.raises(DriverError, match="beat stalled"),
        ):
            stub_driver.key_then_wait("Showed page", "Right", timeout=0)

    def test_wraps_any_block(self, stub_driver: Driver) -> None:
        """A composite move inside the block counts, not just a single key."""
        counts = iter([0, 1])
        ran: list[str] = []
        with (
            patch.object(Driver, "match_count", side_effect=lambda _p: next(counts)),
            patch.object(gui_driver.time, "sleep"),
            stub_driver.expect("Main screen is active", 5),
        ):
            ran.append("moved")
        assert ran == ["moved"]

    def test_the_block_is_not_blamed_for_an_old_match(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "match_count", return_value=1),
            patch.object(gui_driver.time, "sleep"),
            pytest.raises(DriverError, match="beat stalled"),
            stub_driver.expect("already there", 0),
        ):
            pass


class TestWaitTitleFade:
    """Waits until the latest fade to start has logged its finish."""

    @staticmethod
    def _with_log(driver: Driver, *lines: str) -> Driver:
        """Give the stub an app log holding `lines`, for the real predicate to read."""
        driver._log = MagicMock(read_text=lambda **_kw: "".join(f"{n}\n" for n in lines))  # noqa: SLF001
        return driver

    def test_returns_at_once_when_the_latest_fade_is_over(self, stub_driver: Driver) -> None:
        self._with_log(stub_driver, "Title view fade started: 2s.", "Title view fade finished.")
        with patch.object(gui_driver.time, "sleep") as sleep:
            stub_driver.wait_title_fade()
        sleep.assert_not_called()

    def test_an_empty_log_is_an_unfinished_fade(self, stub_driver: Driver) -> None:
        """A caller that has just triggered a fade may ask before its start line lands."""
        self._with_log(stub_driver)
        assert stub_driver._latest_fade_finished() is False  # noqa: SLF001

    def test_a_started_fade_is_unfinished(self, stub_driver: Driver) -> None:
        self._with_log(stub_driver, "Title view fade started: 2s.")
        assert stub_driver._latest_fade_finished() is False  # noqa: SLF001

    def test_an_earlier_finish_does_not_count_for_a_new_start(self, stub_driver: Driver) -> None:
        self._with_log(
            stub_driver,
            "Title view fade started: 1s.",
            "Title view fade finished.",
            "Title view fade started: 2s.",
        )
        assert stub_driver._latest_fade_finished() is False  # noqa: SLF001

    def test_superseded_fades_do_not_count(self, stub_driver: Driver) -> None:
        """Regression: walking several titles starts a fade each; only the last finishes."""
        self._with_log(
            stub_driver,
            "Title view fade started: 3s.",
            "Title view fade started: 1s.",
            "Title view fade started: 2s.",
            "Title view fade finished.",
        )
        assert stub_driver._latest_fade_finished() is True  # noqa: SLF001

    def test_waits_while_the_latest_fade_runs(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "_latest_fade_finished", side_effect=[False, False, True]),
            patch.object(gui_driver.time, "sleep") as sleep,
        ):
            stub_driver.wait_title_fade()
        assert sleep.call_count == 2  # noqa: PLR2004

    def test_raises_when_the_latest_fade_never_finishes(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "_latest_fade_finished", return_value=False),
            patch.object(gui_driver.time, "sleep"),
            patch.object(gui_driver.time, "monotonic", side_effect=[0.0, 20.0]),
            pytest.raises(DriverError, match="never finished"),
        ):
            stub_driver.wait_title_fade(timeout=10)


class TestProbe:
    """Every probe call goes through one helper, which refuses to hide a failure."""

    def test_returns_stdout_on_success(self) -> None:
        done = subprocess.CompletedProcess(["x"], 0, stdout="/run/user/1/app.log\n", stderr="")
        with patch.object(gui_driver.subprocess, "run", return_value=done):
            assert probe("log") == "/run/user/1/app.log\n"

    def test_raises_with_stderr_on_failure(self) -> None:
        """Regression: a failed `start` returned normally and the stale app was driven."""
        failed = subprocess.CompletedProcess(
            ["x"], 1, stdout="", stderr="gui-probe: already running (stop it first)\n"
        )
        with (
            patch.object(gui_driver.subprocess, "run", return_value=failed),
            pytest.raises(DriverError, match="already running"),
        ):
            probe("start")


class TestBootAppAt:
    """Each boot pins the node, the cues and the seed, then starts the app."""

    def test_writes_node_and_pinned_cues(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(gui_driver.RANDOM_SEED_ENV_VAR, raising=False)  # restored after
        config = tmp_path / "barks-reader.json"
        config.write_text(
            json.dumps({"AAA_Settings": {"x": 1}, "Voodoo Hoodoo": {"a": 1}}), encoding="utf-8"
        )
        cues: dict[str, dict[str, int | str] | None] = {
            "Lost in the Andes!": {"page_index": 34},
            "Voodoo Hoodoo": None,
        }
        with patch.object(gui_driver, "probe") as start:
            boot_app_at(["Reading", "root"], config=config, seed=7, cues=cues)
        written = json.loads(config.read_text(encoding="utf-8"))
        assert written["AAA_Settings"] == {"x": 1, "last_selected_node": ["Reading", "root"]}
        assert written["Lost in the Andes!"] == {"last_read_page": {"page_index": 34}}
        assert "Voodoo Hoodoo" not in written
        assert gui_driver.os.environ[gui_driver.RANDOM_SEED_ENV_VAR] == "7"
        start.assert_called_once_with("start")

    def test_reads_from_the_template_when_given(self, tmp_path: Path) -> None:
        config, template = tmp_path / "cfg.json", tmp_path / "pristine.json"
        config.write_text(json.dumps({"stale": True}), encoding="utf-8")
        template.write_text(json.dumps({"fresh": True}), encoding="utf-8")
        with patch.object(gui_driver, "probe"):
            boot_app_at(["root"], config=config, seed=None, template=template)
        written = json.loads(config.read_text(encoding="utf-8"))
        assert "fresh" in written
        assert "stale" not in written

    def test_no_seed_clears_the_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config = tmp_path / "cfg.json"
        config.write_text("{}", encoding="utf-8")
        monkeypatch.setenv(gui_driver.RANDOM_SEED_ENV_VAR, "5")
        with patch.object(gui_driver, "probe"):
            boot_app_at(["root"], config=config, seed=None)
        assert gui_driver.RANDOM_SEED_ENV_VAR not in gui_driver.os.environ


class TestExpectNoNew:
    """The one clock wait, for negatives: a new match within the window is a failure."""

    def test_passes_when_nothing_new_arrives(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "match_count", return_value=2),
            patch.object(gui_driver.time, "sleep"),
            patch.object(gui_driver.time, "monotonic", side_effect=[0.0, 0.5, 1.0, 3.0]),
        ):
            stub_driver.expect_no_new("Closing app", 2.0)

    def test_raises_on_a_new_match(self, stub_driver: Driver) -> None:
        counts = iter([2, 3])
        with (
            patch.object(Driver, "match_count", side_effect=lambda _p: next(counts)),
            patch.object(gui_driver.time, "sleep"),
            patch.object(gui_driver.time, "monotonic", return_value=0.0),
            pytest.raises(DriverError, match="unexpected new"),
        ):
            stub_driver.expect_no_new("Closing app", 2.0)


class TestWindowGeometry:
    def test_parses_the_probe_output(self, stub_driver: Driver) -> None:
        with patch.object(Driver, "_run", return_value="782x1224+59+10\n"):
            assert stub_driver.window_geometry() == (782, 1224, 59, 10)

    def test_rejects_anything_else(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "_run", return_value="gui-probe: not running\n"),
            pytest.raises(DriverError, match="not WxH"),
        ):
            stub_driver.window_geometry()


class TestBootFromConfigDir:
    def test_exports_the_dir_and_uses_its_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(gui_driver.CONFIG_DIR_ENV_VAR, raising=False)  # restored after
        (tmp_path / "barks-reader.json").write_text("{}", encoding="utf-8")
        with patch.object(gui_driver, "probe") as start:
            boot_app_at(["root"], config_dir=tmp_path)
        assert gui_driver.os.environ[gui_driver.CONFIG_DIR_ENV_VAR] == str(tmp_path)
        written = json.loads((tmp_path / "barks-reader.json").read_text(encoding="utf-8"))
        assert written["AAA_Settings"]["last_selected_node"] == ["root"]
        start.assert_called_once_with("start")

    def test_needs_one_of_config_or_config_dir(self) -> None:
        with pytest.raises(ValueError, match="config="):
            boot_app_at(["root"])


class TestOpenStory:
    """Opening a story waits for the fade and confirms the portal before pressing it."""

    def test_waits_then_confirms_each_step(self, stub_driver: Driver) -> None:
        order: list[str] = []
        with (
            patch.object(Driver, "wait_title_fade", side_effect=lambda: order.append("fade")),
            patch.object(
                Driver, "key_then_wait", side_effect=lambda p, *_k, **_kw: order.append(p)
            ),
            patch.object(Driver, "read_pages"),
            patch.object(Driver, "close_reader"),
            patch.object(Driver, "hold"),
            patch.object(Driver, "key"),
            patch.object(Driver, "settle"),
        ):
            stub_driver.open_story(Pick("X", pages=1, dwell=0))
        assert order == [
            "fade",
            Driver.ENTERED_AT_PORTAL,
            "All images loaded",
            "Exited bottom focus region.",
        ]


class TestMoveFocus:
    """Every step within a screen waits for the focus ring to land, not for the clock."""

    def test_each_key_waits_for_the_focus_line(self, stub_driver: Driver) -> None:
        with patch.object(Driver, "key_then_wait") as wait:
            stub_driver.move_focus("Right", "Right", "Down")
        assert [c.args for c in wait.call_args_list] == [
            (Driver.FOCUS_MOVED, "Right"),
            (Driver.FOCUS_MOVED, "Right"),
            (Driver.FOCUS_MOVED, "Down"),
        ]

    def test_the_wiki_has_its_own_focus_line(self, stub_driver: Driver) -> None:
        with patch.object(Driver, "key_then_wait") as wait:
            stub_driver.move_focus("Down", pattern=Driver.WIKI_FOCUS_MOVED, timeout=5)
        assert wait.call_args.args == (Driver.WIKI_FOCUS_MOVED, "Down")
        assert wait.call_args.kwargs == {"timeout": 5}


class TestPacing:
    """Camera gaps apply only to a paced driver; the tests' driver runs on the log alone."""

    def test_a_paced_driver_holds(self, stub_driver: Driver) -> None:
        with patch.object(Driver, "hold") as hold:
            stub_driver._pace(0.4)  # noqa: SLF001
        hold.assert_called_once_with(0.4)

    def test_a_driver_that_is_not_paced_does_not(self, stub_driver: Driver) -> None:
        stub_driver._paced = False  # noqa: SLF001
        with patch.object(Driver, "hold") as hold:
            stub_driver._pace(0.4)  # noqa: SLF001
        hold.assert_not_called()

    def test_a_menu_walk_waits_on_menu_mode_then_each_focus(self, stub_driver: Driver) -> None:
        stub_driver._paced = False  # noqa: SLF001
        with (
            patch.object(Driver, "key_then_wait") as wait,
            patch.object(Driver, "hold") as hold,
        ):
            stub_driver._walk_menu_to("double_page")  # noqa: SLF001
        assert [c.args for c in wait.call_args_list] == [
            (Driver.MENU_ENTERED, "Escape"),
            (Driver.FOCUS_MOVED, "Right"),
            (Driver.FOCUS_MOVED, "Right"),
        ]
        hold.assert_not_called()


class TestTypeSlowly:
    """Each character waits on its own results line where there is one, else on the clock."""

    def test_waits_on_the_marker_for_the_text_so_far(self, stub_driver: Driver) -> None:
        waited: list[str] = []

        @contextmanager
        def fake_expect(pattern: str, _timeout: float = 15) -> Generator[None]:
            waited.append(pattern)
            yield

        with (
            patch.object(Driver, "_run"),
            patch.object(Driver, "expect", side_effect=fake_expect),
            patch.object(Driver, "match_count", return_value=0),
            patch.object(gui_driver.time, "sleep") as sleep,
        ):
            stub_driver.type_slowly("abc", marker=lambda typed: typed if typed[1:] else None)
        assert waited == ["ab", "abc"]
        sleep.assert_called_once_with(gui_driver.TYPE_PAUSE)

    def test_no_marker_rests_after_every_character(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "_run") as run,
            patch.object(gui_driver.time, "sleep") as sleep,
        ):
            stub_driver.type_slowly("abc")
        assert run.call_count == THREE_TURNS
        assert sleep.call_count == THREE_TURNS


@contextmanager
def _stalls(_pattern: str, _timeout: float = 15) -> Generator[None]:
    """Stand in for a wait on a line that never comes."""
    yield
    msg = "beat stalled"
    raise gui_driver.DriverError(msg)


@contextmanager
def _answers(_pattern: str, _timeout: float = 15) -> Generator[None]:
    """Stand in for a wait whose line comes."""
    yield


class TestTypeSlowlyReady:
    """A box that has lost the keyboard stops the typing with the reason, not a stall."""

    def test_a_box_that_lost_the_keyboard_is_not_typed_into(self, stub_driver: Driver) -> None:
        reasons = iter([None, "the box lost the keyboard"])
        with (
            patch.object(Driver, "_run") as run,
            patch.object(gui_driver.time, "sleep"),
            pytest.raises(gui_driver.DriverError, match="stopped before 'b': the box lost"),
        ):
            stub_driver.type_slowly("ab", ready=lambda: next(reasons))
        run.assert_called_once_with(["type", "a"])

    def test_a_stall_names_the_reason_when_there_is_one(self, stub_driver: Driver) -> None:
        reasons = iter([None, "the box lost the keyboard"])
        with (
            patch.object(Driver, "_run"),
            patch.object(Driver, "expect", side_effect=_stalls),
            patch.object(Driver, "match_count", return_value=0),
            pytest.raises(gui_driver.DriverError, match="stalled at 'a': the box lost") as raised,
        ):
            stub_driver.type_slowly("a", marker=lambda typed: typed, ready=lambda: next(reasons))
        assert str(raised.value.__cause__) == "beat stalled"

    def test_a_stall_with_the_box_still_ready_is_the_stall(self, stub_driver: Driver) -> None:
        """The key reached the app (its key line was logged): the app did not answer it."""
        with (
            patch.object(Driver, "_run") as run,
            patch.object(Driver, "expect", side_effect=_stalls),
            patch.object(Driver, "match_count", side_effect=[0, 1]),
            pytest.raises(gui_driver.DriverError, match=r"^beat stalled$"),
        ):
            stub_driver.type_slowly("a", marker=lambda typed: typed, ready=lambda: None)
        run.assert_called_once_with(["type", "a"])


class TestTypeSlowlyLostKey:
    """A character the app never logged as given is typed once more (the macOS VM lost one)."""

    def test_a_key_the_app_never_got_is_typed_again(
        self, stub_driver: Driver, capsys: pytest.CaptureFixture[str]
    ) -> None:
        waits = iter([_stalls, _answers])
        with (
            patch.object(Driver, "_run") as run,
            patch.object(Driver, "expect", side_effect=lambda p, t=15: next(waits)(p, t)),
            patch.object(Driver, "match_count", return_value=0),
        ):
            stub_driver.type_slowly("d", marker=lambda typed: typed, ready=lambda: None)
        assert run.call_args_list == [call(["type", "d"]), call(["type", "d"])]
        assert "'d' never reached the app; typing it again" in capsys.readouterr().err

    def test_it_is_typed_again_only_once(self, stub_driver: Driver) -> None:
        with (
            patch.object(Driver, "_run") as run,
            patch.object(Driver, "expect", side_effect=_stalls),
            patch.object(Driver, "match_count", return_value=0),
            pytest.raises(gui_driver.DriverError, match=r"^beat stalled$"),
        ):
            stub_driver.type_slowly("d", marker=lambda typed: typed, ready=lambda: None)
        assert run.call_count == 2  # noqa: PLR2004

    def test_the_key_line_is_the_one_the_app_logs(self) -> None:
        logged = log_markers.KEY_PRESSED.format(key=ord("d"), name="d")
        expected = gui_driver.KEY_PRESSED_LINE.format(key=ord("d"))
        assert logged.startswith(expected)


class TestFrameCapture:
    """The app saves what its window draws; the driver copies the PNG its answer names."""

    def test_the_frame_the_app_names_is_copied_out(
        self, stub_driver: Driver, tmp_path: Path
    ) -> None:
        saved = tmp_path / "frame-final.png"
        saved.write_bytes(b"png")
        log = tmp_path / "app.log"
        log.write_text(
            log_markers.FRAME_CAPTURED.format(request="final", width=8, height=6, path=saved)
            + "\n",
            encoding="utf-8",
        )
        stub_driver._log = log  # noqa: SLF001
        out = tmp_path / "out.png"

        with (
            patch.object(Driver, "_run") as run,
            patch.object(Driver, "expect", return_value=nullcontext()) as expect,
        ):
            assert stub_driver.frame_capture(out, "final") == out

        run.assert_called_once_with(["frame-capture", "final"])
        assert re.search(expect.call_args.args[0], log.read_text(encoding="utf-8"))
        assert out.read_bytes() == b"png"

    def test_the_answer_pattern_reads_the_line_the_app_logs(self) -> None:
        line = log_markers.FRAME_CAPTURED.format(
            request="7", width=782, height=1225, path="/run/x/frame-7.png"
        )
        found = gui_driver.FRAME_CAPTURED_RE.search(line)
        assert found is not None
        assert (found[1], found[2]) == ("7", "/run/x/frame-7.png")


class TestTaps:
    def test_a_tap_goes_to_the_probe_in_window_pixels(self, stub_driver: Driver) -> None:
        with patch.object(Driver, "_run") as run:
            stub_driver.tap(12, 34)
        run.assert_called_once_with(["tap", "12", "34"])

    def test_a_tap_targets_request_names_its_id(self, stub_driver: Driver) -> None:
        with patch.object(Driver, "_run") as run:
            stub_driver.request_tap_targets("7")
        run.assert_called_once_with(["tap-targets", "7"])

    def test_tap_then_wait_taps_inside_the_wait(self, stub_driver: Driver) -> None:
        order: list[str] = []

        @contextmanager
        def fake_expect(pattern: str, _timeout: float = 15) -> Generator[None]:
            order.append(f"expect {pattern}")
            yield
            order.append("waited")

        with (
            patch.object(Driver, "expect", side_effect=fake_expect),
            patch.object(Driver, "tap", side_effect=lambda *_: order.append("tap")),
        ):
            stub_driver.tap_then_wait("Showed page", 1, 2)
        assert order == ["expect Showed page", "tap", "waited"]


class TestDriverMarkersMatchTheApp:
    """The driver is stdlib-only, so it carries its own copies of the app's marker text.

    Each copy must match the line the app actually logs, which is written once in
    ``barks_reader.core.log_markers``; this is the drift check between the two.
    """

    @pytest.mark.parametrize(
        ("driver_regex", "app_line"),
        [
            (Driver.FOCUS_MOVED, log_markers.NAV_FOCUS.format(widget='Button "Titles"')),
            (Driver.DROPDOWN_DISMISSED, log_markers.DROPDOWN_DISMISSED),
            (Driver.MENU_ENTERED, log_markers.MENU_ENTERED),
            (Driver.FADE_STARTED, log_markers.TITLE_FADE_STARTED.format(duration=2)),
            (Driver.FADE_FINISHED, log_markers.TITLE_FADE_FINISHED),
            (Driver.ENTERED_AT_PORTAL, log_markers.TITLE_VIEW_ENTERED_AT_PORTAL),
            (Driver.NODE_SELECTED, log_markers.NEW_SELECTED_NODE.format(name="A", previous="B")),
            (
                Driver.NODE_EXPANDED.format(name="Covers"),
                log_markers.NODE_EXPANDED.format(name="Covers"),
            ),
            (Driver.SHOWED_PAGE, log_markers.SHOWED_PAGE.format(index=3, elapsed="1ms")),
            (
                Driver.ALL_IMAGES_LOADED,
                log_markers.ALL_IMAGES_LOADED.format(elapsed="1s", index=0),
            ),
            (
                Driver.MAIN_SCREEN_ACTIVE,
                log_markers.MAIN_SCREEN_ACTIVE.format(origin=log_markers.FROM_COMIC_READER),
            ),
            (Driver.EXITED_BOTTOM_FOCUS, log_markers.EXITED_BOTTOM_FOCUS),
            (Driver.GOTO_PAGE_DROPDOWN_OPENED, log_markers.GOTO_PAGE_DROPDOWN_OPENED),
            (
                Driver.WIKI_FOCUS_MOVED,
                okf_log_markers.FOCUS_RING.format(widget="Back"),
            ),
            (
                Driver.WIKI_FOCUS_MOVED,
                okf_log_markers.TREE_FOCUS.format(node="Lost in the Andes!"),
            ),
        ],
    )
    def test_the_driver_regex_matches_the_app_line(self, driver_regex: str, app_line: str) -> None:
        assert re.search(driver_regex, app_line), f"/{driver_regex}/ does not match {app_line!r}"

    def test_the_node_and_page_parsers_read_the_app_lines(self) -> None:
        node_line = log_markers.NEW_SELECTED_NODE.format(name="FROZEN_GOLD", previous="root")
        page_line = log_markers.SHOWED_PAGE.format(index=34, elapsed="1ms")
        node = Driver._NODE_RE.search(node_line)  # noqa: SLF001
        page = Driver._PAGE_RE.search(page_line)  # noqa: SLF001
        assert node is not None
        assert node.group(1) == "FROZEN_GOLD"
        assert page is not None
        assert page.group(1) == "34"


class TestInMenuMode:
    """The driver reads whether the app is in a menu from its log, and walks accordingly."""

    @staticmethod
    def _log(driver: Driver, *lines: str) -> None:
        driver.log_path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")

    def test_more_entries_than_exits_means_in_a_menu(self, stub_driver: Driver) -> None:
        assert not stub_driver.in_menu_mode()
        self._log(stub_driver, Driver.MENU_ENTERED)
        assert stub_driver.in_menu_mode()
        self._log(stub_driver, Driver.MENU_ENTERED, Driver.MENU_EXITED)
        assert not stub_driver.in_menu_mode()

    def test_already_in_the_menu_the_walk_presses_no_escape(
        self, stub_driver: Driver, keys_pressed: KeysPressed
    ) -> None:
        """The settings closed by Escape leave the keys on the bar: an Escape would leave it."""
        self._log(stub_driver, Driver.MENU_ENTERED)
        with (
            patch.object(Driver, "key") as key,
            patch.object(Driver, "key_then_wait") as key_then_wait,
            patch.object(Driver, "move_focus") as move,
            patch.object(Driver, "_pace"),
        ):
            stub_driver.main_menu_button("menu")
        key_then_wait.assert_not_called()
        assert keys_pressed(key) == ["Return"]
        assert move.call_count >= 1


class FakeApp:
    """Stand in for the probe and the app behind it: a key writes the lines the app would log.

    The driver's waits read its log file, so with this in place of ``Driver._run`` they
    run for real: nothing of the driver's own is patched.
    """

    def __init__(self, driver: Driver, answers: dict[str, list[str]]) -> None:
        """Answer each command in `answers` (``key Down``, ``click 3 4``) with its lines.

        A command's lines are used up one per time it is sent, the last one staying.
        """
        self._log = driver.log_path
        self._answers = {command: list(lines) for command, lines in answers.items()}
        self.sent: list[str] = []

    def __call__(self, args: Sequence[str]) -> str:
        command = " ".join(args)
        self.sent.append(command)
        lines = self._answers.get(command)
        if lines:
            line = lines.pop(0) if len(lines) > 1 else lines[0]
            with self._log.open("a", encoding="utf-8") as log:
                log.write(line + "\n")
        return ""


@pytest.fixture
def not_paced(stub_driver: Driver) -> Driver:
    """Make a stub driver that keeps no camera gaps, as the GUI tests run it."""
    stub_driver._paced = False  # noqa: SLF001
    stub_driver._settle_quiet_ms = gui_driver.SETTLE_QUIET_MS  # noqa: SLF001
    return stub_driver


class TestWhatTheLogSays:
    """The reads every wait is built on, against a real log file."""

    LOG = (
        '10:00:01 | New selected node: "Themes"\n'
        "10:00:02 | Showed page 3 in 12 ms.\n"
        '10:00:03 | New selected node: "FROZEN_GOLD"\n'
        "10:00:04 | Showed page 34 in 9 ms.\n"
    )

    def test_before_the_app_has_logged_anything(self, stub_driver: Driver) -> None:
        assert stub_driver.current_node() == ""
        assert stub_driver.current_page() == 0
        assert stub_driver.last_line("Showed page") == ""
        assert stub_driver.match_count("Showed page") == 0

    def test_the_node_and_the_page_are_the_last_the_app_logged(self, stub_driver: Driver) -> None:
        stub_driver.log_path.write_text(self.LOG, encoding="utf-8")

        assert stub_driver.current_node() == "FROZEN_GOLD"
        assert stub_driver.current_page() == 34  # noqa: PLR2004
        assert stub_driver.match_count("Showed page") == 2  # noqa: PLR2004
        assert stub_driver.last_line("Showed page") == "10:00:04 | Showed page 34 in 9 ms."
        assert stub_driver.last_line("New selected node").endswith('"FROZEN_GOLD"')

    def test_bytes_that_are_not_text_do_not_stop_a_read(self, stub_driver: Driver) -> None:
        """A log caught mid-write can end inside a character."""
        stub_driver.log_path.write_bytes(self.LOG.encode() + b"\xe2\x94")

        assert stub_driver.current_page() == 34  # noqa: PLR2004


class TestWaitFor:
    def test_a_line_already_logged_is_enough(self, stub_driver: Driver) -> None:
        stub_driver.log_path.write_text("Main screen is active\n", encoding="utf-8")

        stub_driver.wait_for("Main screen is active", timeout=0)

    def test_a_line_that_never_comes_is_a_stalled_beat(self, stub_driver: Driver) -> None:
        with (
            patch.object(gui_driver.time, "monotonic", side_effect=[100.0, 100.5, 116.0]),
            patch.object(gui_driver.time, "sleep") as sleep,
            pytest.raises(DriverError, match=r"never saw /All images loaded/ in the app log"),
        ):
            stub_driver.wait_for("All images loaded")

        sleep.assert_called_once_with(0.25)


class TestAgainstAnAppThatAnswers:
    """Each composite move, with only the probe replaced: the waits are the real ones."""

    def test_a_click_waits_for_its_own_new_line(self, not_paced: Driver) -> None:
        not_paced.log_path.write_text("Showed page 3 in 12 ms.\n", encoding="utf-8")
        app = FakeApp(not_paced, {"click 40 60": ["Showed page 4 in 8 ms."]})

        with patch.object(Driver, "_run", side_effect=app):
            not_paced.click_then_wait(Driver.SHOWED_PAGE, 40, 60, timeout=0)

        assert app.sent == ["click 40 60"]
        assert not_paced.current_page() == 4  # noqa: PLR2004

    def test_a_click_the_app_ignores_is_a_stalled_beat(self, not_paced: Driver) -> None:
        """The page already shown is not the answer: only a new line is."""
        not_paced.log_path.write_text("Showed page 3 in 12 ms.\n", encoding="utf-8")
        app = FakeApp(not_paced, {})

        with (
            patch.object(Driver, "_run", side_effect=app),
            patch.object(gui_driver.time, "sleep"),
            pytest.raises(DriverError, match=r"no new /Showed page/ in the app log after 0s"),
        ):
            not_paced.click_then_wait(Driver.SHOWED_PAGE, 40, 60, timeout=0)

    def test_a_branch_is_walked_to_opened_and_left_to_lay_out(self, not_paced: Driver) -> None:
        selections = [f'New selected node: "{name}"' for name in ("Series", "Themes")]
        expanded = Driver.NODE_EXPANDED.format(name="Themes")
        app = FakeApp(not_paced, {"key Down": selections, "key Return": [expanded]})

        with patch.object(Driver, "_run", side_effect=app):
            not_paced.open_branch("Themes")

        settle = f"settle {gui_driver.SETTLE_QUIET_MS}"
        assert app.sent == ["key Down", "key Down", "key Return", settle]

    def test_a_tree_that_stops_moving_says_where_it_stopped(self, not_paced: Driver) -> None:
        app = FakeApp(not_paced, {})
        not_paced.log_path.write_text('New selected node: "Series"\n', encoding="utf-8")

        with (
            patch.object(Driver, "_run", side_effect=app),
            patch.object(gui_driver.time, "sleep"),
            pytest.raises(DriverError, match=r'tree stopped at "Series" before reaching "Themes"'),
        ):
            not_paced.select_node("Themes", step_timeout=0)

    def test_a_node_too_far_down_is_given_up_on(self, not_paced: Driver) -> None:
        selections = [f'New selected node: "Story {n}"' for n in range(5)]
        app = FakeApp(not_paced, {"key Down": selections})

        with (
            patch.object(Driver, "_run", side_effect=app),
            pytest.raises(DriverError, match=r'never reached node "Themes" in 3 steps'),
        ):
            not_paced.select_node("Themes", max_steps=3)

        assert app.sent == ["key Down"] * 3

    def test_a_main_bar_button_s_wait_counts_from_after_the_walk(self, not_paced: Driver) -> None:
        """The dots menu: the walk to it logs the very line its opening logs."""
        focus = Driver.FOCUS_MOVED
        answers = {
            "key Escape": [Driver.MENU_ENTERED],
            "key Right": [f"{focus} collapse", f"{focus} change_pics", f"{focus} menu"],
            "key Return": [f"{focus} the menu's first entry"],
        }
        app = FakeApp(not_paced, answers)

        with patch.object(Driver, "_run", side_effect=app):
            not_paced.main_menu_button_then_wait("menu", focus, timeout=0)

        assert app.sent == ["key Escape", "key Right", "key Right", "key Right", "key Return"]
        assert not_paced._main_menu_focus == "menu"  # noqa: SLF001

    def test_going_back_waits_for_a_new_line_not_the_one_from_the_way_in(
        self, not_paced: Driver
    ) -> None:
        not_paced.log_path.write_text("Main screen is active\n", encoding="utf-8")
        answers = {"key Escape": [Driver.MENU_ENTERED], "key Return": ["Main screen is active"]}
        app = FakeApp(not_paced, answers)

        with patch.object(Driver, "_run", side_effect=app):
            not_paced.go_back_then_wait(Driver.MAIN_SCREEN_ACTIVE, timeout=0)

        assert app.sent == ["key Escape", "key Return"]  # go_back is where the bar opens
        assert not_paced.match_count(Driver.MAIN_SCREEN_ACTIVE) == 2  # noqa: PLR2004

    def test_the_document_bar_is_walked_the_short_way_and_remembered(
        self, not_paced: Driver
    ) -> None:
        focus = Driver.FOCUS_MOVED
        answers = {
            "key Escape": [Driver.MENU_ENTERED],
            "key Right": [f"{focus} fullscreen"],
            "key Left": [f"{focus} goto_story"],
        }
        app = FakeApp(not_paced, answers)

        with patch.object(Driver, "_run", side_effect=app):
            not_paced.press_document_menu_button("fullscreen")  # from close: one Right, wrapping
            not_paced.log_path.write_text("", encoding="utf-8")  # the bar closed again
            not_paced.press_document_menu_button("goto_story")

        assert app.sent == [
            *("key Escape", "key Right", "key Return"),
            *("key Escape", "key Right", "key Return"),
        ]
        assert not_paced._document_menu_focus == "goto_story"  # noqa: SLF001

    def test_a_button_the_document_bar_does_not_have(self, not_paced: Driver) -> None:
        with pytest.raises(DriverError, match=r"no such menu button: quit \(have: fullscreen,"):
            not_paced.press_document_menu_button("quit")


class TestTheProbeCommands:
    """What each plain move sends the probe, and what attaching reads from it."""

    def test_attaching_asks_the_probe_for_the_app_s_log(self, tmp_path: Path) -> None:
        script = tmp_path / "gui_probe.py"
        with patch.object(gui_driver, "probe", return_value=f"{tmp_path / 'app.log'}\n") as run:
            driver = Driver(script, settle_quiet_ms=250, paced=False)

        run.assert_called_once_with("log", script=script)
        assert driver.log_path == tmp_path / "app.log"

    def test_each_move_is_one_probe_command(self, tmp_path: Path) -> None:
        with patch.object(gui_driver, "probe", return_value=f"{tmp_path / 'app.log'}\n") as run:
            driver = Driver(settle_quiet_ms=250)
            run.reset_mock()
            driver.key("Down", "Return")
            driver.click(40, 60)
            driver.tap(10, 20)
            driver.request_tap_targets("7")
            driver.request_memory_census("8")
            driver.settle()
            shot = driver.shot(tmp_path / "shot.png")

        assert shot == tmp_path / "shot.png"
        assert [c.args for c in run.call_args_list] == [
            ("key", "Down", "Return"),
            ("click", "40", "60"),
            ("tap", "10", "20"),
            ("tap-targets", "7"),
            ("memory-census", "8"),
            ("settle", "250"),
            ("shot", str(tmp_path / "shot.png")),
        ]
        assert all(c.kwargs == {"script": gui_driver.PROBE} for c in run.call_args_list)

    def test_a_hold_is_a_sleep_and_nothing_more(self) -> None:
        with patch.object(gui_driver.time, "sleep") as sleep:
            Driver.hold(1.5)

        sleep.assert_called_once_with(1.5)
