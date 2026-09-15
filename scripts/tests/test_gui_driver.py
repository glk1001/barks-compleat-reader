"""Unit tests for the GUI driver's own logic and its log-driven waits.

Nothing here starts the app: the sequencing that would otherwise need a live
boot to check is exercised against a stub driver instead.
"""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import patch

import gui_driver
import pytest
from gui_driver import Driver, DriverError, Pick, boot_app_at, probe

if TYPE_CHECKING:
    from pathlib import Path

EXPECTED_DOWNS = 2
THREE_TURNS, FOUR_RESTS = 3, 4


def _stub_driver() -> Driver:
    """Return a Driver with no probe attached, for exercising its own logic."""
    with patch.object(Driver, "__init__", lambda _self, *_a, **_kw: None):
        return Driver()


class TestPick:
    def test_defaults(self) -> None:
        pick = Pick("GOOD_DEEDS")
        assert (pick.pages, pick.dwell) == (2, 2.5)

    def test_per_story_overrides(self) -> None:
        pick = Pick("SILENT_NIGHT", pages=1, dwell=4.0)
        assert (pick.pages, pick.dwell) == (1, 4.0)


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
            patch.object(gui_driver.time, "sleep"),
        ):
            driver.select_node("Themes")
        assert key.call_count == EXPECTED_DOWNS

    def test_raises_when_the_tree_stops_moving(self) -> None:
        """Two identical reads in a row means the selection cannot go further down."""
        driver = _stub_driver()
        with (
            patch.object(Driver, "current_node", return_value="Bottom"),
            patch.object(Driver, "key"),
            patch.object(gui_driver.time, "sleep"),
            pytest.raises(DriverError, match='tree stopped at "Bottom"'),
        ):
            driver.select_node("Nowhere")


class TestReadPages:
    """Every caller that reads a comic turns exactly `pages - 1` times."""

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
        wrecked the rest of a recording rather than merely showing the wrong
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
        with pytest.raises(DriverError, match="no such menu button"):
            self._presses(driver, "nope")


class TestMainMenuButton:
    """The main screen's bar is sticky too, and opens on go_back."""

    @staticmethod
    def _presses(driver: Driver, name: str) -> list[str]:
        with (
            patch.object(Driver, "key") as key,
            patch.object(Driver, "hold"),
        ):
            driver.main_menu_button(name)
        return [k for call in key.call_args_list for k in call.args]

    def test_go_back_is_the_default_focus(self) -> None:
        driver = _stub_driver()
        assert self._presses(driver, "go_back") == ["Escape", "Return"]

    def test_quit_is_the_short_way_round(self) -> None:
        """Quit is three Lefts back from go_back, not four Rights forward."""
        driver = _stub_driver()
        assert self._presses(driver, "quit") == ["Escape", "Left", "Left", "Left", "Return"]

    def test_a_second_press_starts_where_the_first_left_off(self) -> None:
        driver = _stub_driver()
        self._presses(driver, "menu")  # three Rights from go_back
        assert self._presses(driver, "collapse") == ["Escape", "Left", "Left", "Return"]

    def test_go_back_uses_it(self) -> None:
        driver = _stub_driver()
        with (
            patch.object(Driver, "main_menu_button") as press,
        ):
            driver.go_back()
        press.assert_called_once_with("go_back")

    def test_an_unknown_button_raises(self) -> None:
        driver = _stub_driver()
        with pytest.raises(DriverError, match="no such menu button"):
            self._presses(driver, "nope")


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


class TestExpect:
    """expect() is the one wait every *_then_wait move is built on."""

    def test_waits_for_a_new_match_not_an_old_one(self) -> None:
        """Regression: the marker fires once per comic, so an old match must not count.

        `gui-probe wait` greps the whole log and would return instantly on the
        previous story's line, carrying on before this one had drawn.
        """
        driver = _stub_driver()
        counts = iter([1, 1, 2])
        with (
            patch.object(Driver, "match_count", side_effect=lambda _p: next(counts)),
            patch.object(Driver, "key") as key,
            patch.object(gui_driver.time, "sleep"),
        ):
            driver.key_then_wait("All images loaded", 30, "Return")
        key.assert_called_once_with("Return")

    def test_raises_when_the_marker_never_arrives(self) -> None:
        driver = _stub_driver()
        with (
            patch.object(Driver, "match_count", return_value=3),
            patch.object(Driver, "key"),
            patch.object(gui_driver.time, "sleep"),
            pytest.raises(DriverError, match="beat stalled"),
        ):
            driver.key_then_wait("Showed page", 0, "Right")

    def test_wraps_any_block(self) -> None:
        """A composite move inside the block counts, not just a single key."""
        driver = _stub_driver()
        counts = iter([0, 1])
        ran: list[str] = []
        with (
            patch.object(Driver, "match_count", side_effect=lambda _p: next(counts)),
            patch.object(gui_driver.time, "sleep"),
            driver.expect("Main screen is active", 5),
        ):
            ran.append("moved")
        assert ran == ["moved"]

    def test_the_block_is_not_blamed_for_an_old_match(self) -> None:
        driver = _stub_driver()
        with (
            patch.object(Driver, "match_count", return_value=1),
            patch.object(gui_driver.time, "sleep"),
            pytest.raises(DriverError, match="beat stalled"),
            driver.expect("already there", 0),
        ):
            pass


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

    def test_writes_node_and_pinned_cues(self, tmp_path: Path) -> None:
        config = tmp_path / "barks-reader.json"
        config.write_text(json.dumps({"AAA_Settings": {"x": 1}, "Voodoo Hoodoo": {"a": 1}}))
        cues: dict[str, dict[str, int | str] | None] = {
            "Lost in the Andes!": {"page_index": 34},
            "Voodoo Hoodoo": None,
        }
        with patch.object(gui_driver, "probe") as start:
            boot_app_at(["Reading", "root"], config=config, seed=7, cues=cues)
        written = json.loads(config.read_text())
        assert written["AAA_Settings"] == {"x": 1, "last_selected_node": ["Reading", "root"]}
        assert written["Lost in the Andes!"] == {"last_read_page": {"page_index": 34}}
        assert "Voodoo Hoodoo" not in written
        assert gui_driver.os.environ[gui_driver.RANDOM_SEED_ENV_VAR] == "7"
        start.assert_called_once_with("start")

    def test_reads_from_the_template_when_given(self, tmp_path: Path) -> None:
        config, template = tmp_path / "cfg.json", tmp_path / "pristine.json"
        config.write_text(json.dumps({"stale": True}))
        template.write_text(json.dumps({"fresh": True}))
        with patch.object(gui_driver, "probe"):
            boot_app_at(["root"], config=config, seed=None, template=template)
        written = json.loads(config.read_text())
        assert "fresh" in written
        assert "stale" not in written

    def test_no_seed_clears_the_env_var(self, tmp_path: Path) -> None:
        config = tmp_path / "cfg.json"
        config.write_text("{}")
        gui_driver.os.environ[gui_driver.RANDOM_SEED_ENV_VAR] = "5"
        with patch.object(gui_driver, "probe"):
            boot_app_at(["root"], config=config, seed=None)
        assert gui_driver.RANDOM_SEED_ENV_VAR not in gui_driver.os.environ


class TestExpectNoNew:
    """The one clock wait, for negatives: a new match within the window is a failure."""

    def test_passes_when_nothing_new_arrives(self) -> None:
        driver = _stub_driver()
        with (
            patch.object(Driver, "match_count", return_value=2),
            patch.object(gui_driver.time, "sleep"),
            patch.object(gui_driver.time, "monotonic", side_effect=[0.0, 0.5, 1.0, 3.0]),
        ):
            driver.expect_no_new("Closing app", 2.0)

    def test_raises_on_a_new_match(self) -> None:
        driver = _stub_driver()
        counts = iter([2, 3])
        with (
            patch.object(Driver, "match_count", side_effect=lambda _p: next(counts)),
            patch.object(gui_driver.time, "sleep"),
            patch.object(gui_driver.time, "monotonic", return_value=0.0),
            pytest.raises(DriverError, match="unexpected new"),
        ):
            driver.expect_no_new("Closing app", 2.0)


class TestWindowGeometry:
    def test_parses_the_probe_output(self) -> None:
        driver = _stub_driver()
        with patch.object(Driver, "_run", return_value="782x1224+59+10\n"):
            assert driver.window_geometry() == (782, 1224, 59, 10)

    def test_rejects_anything_else(self) -> None:
        driver = _stub_driver()
        with (
            patch.object(Driver, "_run", return_value="gui-probe: not running\n"),
            pytest.raises(DriverError, match="not WxH"),
        ):
            driver.window_geometry()


class TestBootFromConfigDir:
    def test_exports_the_dir_and_uses_its_json(self, tmp_path: Path) -> None:
        (tmp_path / "barks-reader.json").write_text("{}")
        with patch.object(gui_driver, "probe") as start:
            boot_app_at(["root"], config_dir=tmp_path)
        assert gui_driver.os.environ[gui_driver.CONFIG_DIR_ENV_VAR] == str(tmp_path)
        written = json.loads((tmp_path / "barks-reader.json").read_text())
        assert written["AAA_Settings"]["last_selected_node"] == ["root"]
        start.assert_called_once_with("start")
        gui_driver.os.environ.pop(gui_driver.CONFIG_DIR_ENV_VAR)

    def test_needs_one_of_config_or_config_dir(self) -> None:
        with pytest.raises(ValueError, match="config="):
            boot_app_at(["root"])
