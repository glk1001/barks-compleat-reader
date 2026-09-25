"""Tap targets: the record and its request file (core), and the widget walk (ui)."""

from __future__ import annotations

import gc
import re
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import log_markers
from barks_reader.core.log_markers import capture
from barks_reader.core.tap_targets import (
    TAP_TARGETS_FILE_ENV_VAR,
    TapTarget,
    TapTargetRequests,
    decode_targets,
    encode_targets,
    settling_began,
    settling_ended,
)
from barks_reader.ui import tap_targets as ui_tap_targets
from barks_reader.ui.tap_targets import install_tap_targets_service, snapshot
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.stencilview import StencilView
from kivy.uix.treeview import TreeViewLabel
from kivy.uix.widget import Widget

if TYPE_CHECKING:
    from pathlib import Path

WINDOW_W = 400
WINDOW_H = 300


def _target(text: str = "Go", **kwargs: object) -> TapTarget:
    fields: dict = {"kind": "Button", "text": text, "id": "", "left": 10, "top": 20}
    fields |= {"width": 100, "height": 50} | kwargs
    return TapTarget(**fields)


# ------------------------------------------------------------------- core --


def test_a_target_round_trips_through_its_json() -> None:
    targets = [_target("Mickey\u2019s \u201cTale\u201d"), _target("", kind="VKeyboard", id="kb")]
    encoded = encode_targets(targets)
    assert "\n" not in encoded
    assert "\u2019" in encoded, "non-ASCII text is kept as it is, as the log is UTF-8"
    assert decode_targets(encoded) == targets


def test_a_target_names_its_centre_and_itself() -> None:
    target = _target(id="menu_button")
    assert target.center == (60, 45)
    assert target.describe() == 'Button "Go" #menu_button'
    assert _target("").describe() == "Button"


def test_the_marker_carries_the_json_intact() -> None:
    encoded = encode_targets([_target("{braces} and [brackets]")])
    line = log_markers.TAP_TARGETS.format(request="7", width=400, height=300, targets=encoded)
    digits = re.compile(r"\d+")  # the size is digits, or `.*` would eat into the JSON
    regex = capture(log_markers.TAP_TARGETS, "targets", request=7, width=digits, height=digits)
    found = re.search(regex, line)
    assert found is not None
    assert decode_targets(found["targets"]) == [_target("{braces} and [brackets]")]


class TestTapTargetRequests:
    @pytest.fixture
    def request_file(self, tmp_path: Path) -> Path:
        return tmp_path / "tap-request"

    def test_no_request_no_snapshot(self, request_file: Path) -> None:
        shots = MagicMock(return_value=[_target()])
        assert TapTargetRequests(request_file).poll(shots) is None
        shots.assert_not_called()

    def test_an_empty_request_waits_for_its_id(self, request_file: Path) -> None:
        request_file.write_text("", encoding="utf-8")
        shots = MagicMock(return_value=[_target()])
        assert TapTargetRequests(request_file).poll(shots) is None
        shots.assert_not_called()

    def test_answers_once_the_same_list_is_taken_twice(self, request_file: Path) -> None:
        request_file.write_text("3\n", encoding="utf-8")
        requests = TapTargetRequests(request_file)
        shots = MagicMock(return_value=[_target()])
        assert requests.poll(shots) is None
        assert requests.poll(shots) == ("3", [_target()])
        assert not request_file.exists(), "an answered request is spent"
        assert requests.poll(shots) is None

    def test_a_moving_layout_is_not_answered(self, request_file: Path) -> None:
        request_file.write_text("4", encoding="utf-8")
        requests = TapTargetRequests(request_file)
        moving = MagicMock(side_effect=[[_target(top=20)], [_target(top=10)], [_target(top=10)]])
        assert requests.poll(moving) is None
        assert requests.poll(moving) is None, "still moving: not the same list twice"
        assert requests.poll(moving) == ("4", [_target(top=10)])

    def test_no_answer_while_the_layout_is_settling(self, request_file: Path) -> None:
        request_file.write_text("5", encoding="utf-8")
        requests = TapTargetRequests(request_file)
        shots = MagicMock(return_value=[_target()])
        owner = object()
        settling_began(owner)
        assert requests.poll(shots) is None
        assert requests.poll(shots) is None
        shots.assert_not_called()
        settling_ended(owner)
        assert requests.poll(shots) is None, "two polls once it has ended, not one"
        assert requests.poll(shots) == ("5", [_target()])

    def test_a_new_request_starts_afresh(self, request_file: Path) -> None:
        requests = TapTargetRequests(request_file)
        shots = MagicMock(return_value=[_target()])
        request_file.write_text("1", encoding="utf-8")
        requests.poll(shots)
        request_file.unlink()
        assert requests.poll(shots) is None  # withdrawn: the half-made answer is dropped
        request_file.write_text("2", encoding="utf-8")
        assert requests.poll(shots) is None, "a new request needs its own two polls"
        assert requests.poll(shots) == ("2", [_target()])


# --------------------------------------------------------------------- ui --


class _Window:
    """What `snapshot` reads of Kivy's window: its children and its size."""

    def __init__(self, *children: Widget) -> None:
        self.children = list(children)
        self.width = WINDOW_W
        self.height = WINDOW_H
        self.ids: dict = {}
        self.parent = self  # as Kivy's window is
        for child in children:
            child.parent = self

    def to_window(
        self, x: float, y: float, *, initial: bool = True, relative: bool = False
    ) -> tuple[float, float]:
        """Return window coordinates unchanged, as Kivy's window does."""
        del initial, relative
        return x, y


def _placed(widget: Widget, x: float, y: float, w: float, h: float) -> Widget:
    widget.size_hint = (None, None)
    widget.pos = (x, y)
    widget.size = (w, h)
    return widget


def _root(*children: Widget) -> Widget:
    root = _placed(Widget(), 0, 0, WINDOW_W, WINDOW_H)
    for child in children:
        root.add_widget(child)
    return root


def test_a_button_is_a_target_with_the_origin_top_left() -> None:
    button = _placed(Button(text="  Go\n on "), 10, 20, 100, 50)
    [target] = snapshot(_Window(_root(button)))
    assert target == TapTarget("Button", "Go on", "", 10, WINDOW_H - 70, 100, 50)
    assert target.whole


def test_plain_widgets_are_not_targets() -> None:
    assert snapshot(_Window(_root(_placed(Label(text="words"), 0, 0, 50, 50)))) == []


def test_hidden_and_disabled_widgets_are_left_out_with_their_children() -> None:
    hidden = _placed(BoxLayout(opacity=0), 0, 0, 100, 100)
    hidden.add_widget(Button(text="under a hidden bar"))
    disabled = _placed(Button(text="greyed", disabled=True), 200, 0, 50, 50)
    assert snapshot(_Window(_root(hidden, disabled))) == []


def test_a_scroll_view_clips_what_it_holds() -> None:
    viewport = _placed(StencilView(), 0, 0, 100, 100)
    viewport.add_widget(_placed(Button(text="half in"), 50, 50, 100, 100))
    viewport.add_widget(_placed(Button(text="scrolled away"), 0, 150, 50, 50))
    [target] = snapshot(_Window(_root(viewport)))
    assert (target.text, target.left, target.top, target.width, target.height) == (
        "half in",
        50,
        WINDOW_H - 100,
        50,
        50,
    )
    assert not target.whole, "a target the scroll view cuts off says so"


def test_the_window_clips_too() -> None:
    [target] = snapshot(_Window(_root(_placed(Button(text="edge"), 350, 0, 100, 10))))
    assert target.width == WINDOW_W - 350
    assert not target.whole


def test_an_open_popup_hides_everything_under_it() -> None:
    popup = ModalView()
    popup.add_widget(Button(text="OK"))
    popup.children[0].size_hint = (None, None)
    popup.children[0].size = (40, 20)
    under = _root(_placed(Button(text="under"), 0, 0, 50, 50))
    listed = [(t.kind, t.text) for t in snapshot(_Window(popup, under))]
    assert listed == [("ModalView", ""), ("Button", "OK")], "the panel, then what it holds"


def test_a_popup_is_named_by_its_title() -> None:
    popup = Popup(title="  Speech\n bubbles ", content=Label(), size_hint=(None, None))
    popup.size = (100, 80)
    [panel, *_] = snapshot(_Window(popup))
    assert (panel.kind, panel.text) == ("Popup", "Speech bubbles")


def test_a_kv_id_names_its_widget() -> None:
    button = _placed(Button(), 0, 0, 20, 20)
    root = _root(button)
    root.ids = {"menu_button": button.proxy_ref}
    [target] = snapshot(_Window(root))
    assert (target.text, target.id) == ("", "menu_button")


def test_a_widget_with_no_id_is_found_under_the_window_without_looping() -> None:
    # Kivy's window is its own parent: the id search must stop there, not spin.
    [target] = snapshot(_Window(_root(_placed(Button(text="no id"), 0, 0, 20, 20))))
    assert target.id == ""


def test_a_tree_node_is_named_as_the_tree_logs_it() -> None:
    class _Node(TreeViewLabel):
        def get_name(self) -> str:
            return "GHOST_OF_THE_GROTTO_THE"

    node = _placed(_Node(text="[b]The Ghost[/b]", markup=True), 0, 0, 100, 20)
    plain = _placed(Button(text="[i]FC 203[/i] &bl;1948&br; &amp;", markup=True), 0, 50, 100, 20)
    texts = {t.kind: t.text for t in snapshot(_Window(_root(node, plain)))}
    assert texts == {"_Node": "GHOST_OF_THE_GROTTO_THE", "Button": "FC 203 [1948] &"}


def test_a_widget_names_its_own_regions() -> None:
    class _Reader(Widget):
        def tap_target_regions(self) -> dict[str, tuple[float, float, float, float]]:
            return {"left margin": (0.0, 0.0, 30.0, 40.0), "off screen": (-50.0, 0.0, 20.0, 10.0)}

    [target] = snapshot(_Window(_root(_placed(_Reader(), 0, 0, 100, 100))))
    assert target == TapTarget("_Reader", "left margin", "", 0, WINDOW_H - 40, 30, 40)


def test_the_service_is_off_without_its_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TAP_TARGETS_FILE_ENV_VAR, raising=False)
    with patch.object(ui_tap_targets, "Clock") as clock:
        assert not install_tap_targets_service(_Window())
    clock.schedule_interval.assert_not_called()


def test_the_service_answers_a_request_in_the_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, loguru_sink: list[str]
) -> None:
    request_file = tmp_path / "tap-request"
    monkeypatch.setenv(TAP_TARGETS_FILE_ENV_VAR, str(request_file))
    window = _Window(_root(_placed(Button(text="Go"), 10, 20, 100, 50)))
    with patch.object(ui_tap_targets, "Clock") as clock:
        assert install_tap_targets_service(window)
    poll = clock.schedule_interval.call_args.args[0]
    request_file.write_text("9", encoding="utf-8")
    poll(0.1)
    poll(0.1)
    [line] = [m for m in loguru_sink if m.startswith("Tap targets #")]
    expected = encode_targets([TapTarget("Button", "Go", "", 10, WINDOW_H - 70, 100, 50)])
    assert line == log_markers.TAP_TARGETS.format(
        request="9", width=WINDOW_W, height=WINDOW_H, targets=expected
    )


def test_the_service_outlives_its_install_under_the_real_clock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Kivy's clock holds callbacks weakly: a poll nothing else holds would never run."""
    monkeypatch.setenv(TAP_TARGETS_FILE_ENV_VAR, str(tmp_path / "tap-request"))
    monkeypatch.setattr(ui_tap_targets, "_SERVICE", [])
    before = set(Clock.get_events())
    assert install_tap_targets_service(_Window())
    [event] = [e for e in Clock.get_events() if e not in before]
    try:
        gc.collect()
        assert event.get_callback() is not None
    finally:
        event.cancel()
