"""What a key does to a popup frame, and where its focus goes (``core.popup_frame``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from barks_reader.core.keys import (
    KEY_DOWN,
    KEY_ENTER,
    KEY_ESCAPE,
    KEY_LEFT,
    KEY_NUMPAD_ENTER,
    KEY_RIGHT,
    KEY_UP,
    set_alt_escape_key,
)
from barks_reader.core.popup_frame import (
    FrameButton,
    FrameKeyAction,
    cancel_button,
    focus_after_step,
    frame_key_action,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

_ALT_ESCAPE = ord("r")


@pytest.fixture
def alt_escape() -> Iterator[int]:
    set_alt_escape_key(_ALT_ESCAPE)
    yield _ALT_ESCAPE
    set_alt_escape_key(0)


def _action(
    key: int,
    codepoint: str | None = None,
    *,
    typing: bool = False,
    has_buttons: bool = True,
    closable: bool = True,
) -> FrameKeyAction:
    return frame_key_action(
        key, codepoint, typing=typing, has_buttons=has_buttons, closable=closable
    )


class TestAFrameWithButtons:
    @pytest.mark.parametrize(
        ("key", "action"),
        [
            (KEY_LEFT, FrameKeyAction.FOCUS_LEFT),
            (KEY_RIGHT, FrameKeyAction.FOCUS_RIGHT),
            (KEY_ENTER, FrameKeyAction.PRESS_FOCUSED),
            (KEY_NUMPAD_ENTER, FrameKeyAction.PRESS_FOCUSED),
            (KEY_ESCAPE, FrameKeyAction.CANCEL),
            (KEY_UP, FrameKeyAction.NOTHING),
            (KEY_DOWN, FrameKeyAction.NOTHING),
            (ord("a"), FrameKeyAction.NOTHING),
        ],
    )
    def test_the_remote_s_keys_work_the_row(self, key: int, action: FrameKeyAction) -> None:
        assert _action(key) is action

    def test_the_alternate_escape_cancels_too(self, alt_escape: int) -> None:
        assert _action(alt_escape) is FrameKeyAction.CANCEL

    def test_whether_it_could_be_closed_with_no_buttons_makes_no_difference(self) -> None:
        assert _action(KEY_ESCAPE, closable=False) is FrameKeyAction.CANCEL
        assert _action(KEY_ENTER, closable=False) is FrameKeyAction.PRESS_FOCUSED


class TestAFrameWithNoButtons:
    @pytest.mark.parametrize(
        ("key", "action"),
        [
            (KEY_ESCAPE, FrameKeyAction.TOGGLE_CLOSE_FOCUS),
            (KEY_ENTER, FrameKeyAction.CLOSE),
            (KEY_NUMPAD_ENTER, FrameKeyAction.CLOSE),
            (KEY_LEFT, FrameKeyAction.NOTHING),
            (KEY_RIGHT, FrameKeyAction.NOTHING),
            (ord("a"), FrameKeyAction.NOTHING),
        ],
    )
    def test_escape_lands_on_its_x_and_return_closes_it(
        self, key: int, action: FrameKeyAction
    ) -> None:
        assert _action(key, has_buttons=False) is action

    def test_the_alternate_escape_lands_on_its_x_too(self, alt_escape: int) -> None:
        assert _action(alt_escape, has_buttons=False) is FrameKeyAction.TOGGLE_CLOSE_FOCUS

    @pytest.mark.parametrize("key", [KEY_ESCAPE, KEY_ENTER, KEY_NUMPAD_ENTER, KEY_LEFT])
    def test_one_that_cannot_be_closed_takes_every_key_and_does_nothing(self, key: int) -> None:
        assert _action(key, has_buttons=False, closable=False) is FrameKeyAction.NOTHING


class TestWhileATextBoxHasTheKeyboard:
    @pytest.mark.parametrize("has_buttons", [True, False])
    @pytest.mark.parametrize("key", [KEY_LEFT, KEY_RIGHT, KEY_ENTER, KEY_NUMPAD_ENTER, ord("a")])
    def test_every_key_but_escape_is_the_box_s(self, key: int, has_buttons: bool) -> None:
        action = _action(key, typing=True, has_buttons=has_buttons)
        assert action is FrameKeyAction.LEFT_TO_THE_TEXT_BOX

    def test_escape_is_still_the_frame_s(self) -> None:
        assert _action(KEY_ESCAPE, typing=True) is FrameKeyAction.CANCEL
        assert (
            _action(KEY_ESCAPE, typing=True, has_buttons=False) is FrameKeyAction.TOGGLE_CLOSE_FOCUS
        )

    def test_the_alternate_escape_typed_as_a_letter_is_the_box_s(self, alt_escape: int) -> None:
        typed = _action(alt_escape, chr(alt_escape), typing=True)
        assert typed is FrameKeyAction.LEFT_TO_THE_TEXT_BOX
        assert _action(alt_escape, None, typing=True) is FrameKeyAction.CANCEL

    def test_not_typing_the_same_letter_cancels(self, alt_escape: int) -> None:
        assert _action(alt_escape, chr(alt_escape)) is FrameKeyAction.CANCEL


class TestTheFocusAlongTheRow:
    @pytest.mark.parametrize(
        ("focused", "step", "landed"), [(0, 1, 1), (1, 1, 2), (2, 1, 0), (0, -1, 2), (2, -1, 1)]
    )
    def test_a_row_that_wraps_goes_round(self, focused: int, step: int, landed: int) -> None:
        assert focus_after_step(focused, step, 3, wrap=True) == landed

    @pytest.mark.parametrize(
        ("focused", "step", "landed"), [(0, 1, 1), (2, 1, 2), (0, -1, 0), (2, -1, 1)]
    )
    def test_a_row_that_does_not_stops_at_its_ends(
        self, focused: int, step: int, landed: int
    ) -> None:
        assert focus_after_step(focused, step, 3, wrap=False) == landed

    @pytest.mark.parametrize("wrap", [True, False])
    def test_onto_the_row_from_outside_it_lands_at_its_near_end(self, wrap: bool) -> None:
        assert focus_after_step(None, 1, 3, wrap=wrap) == 0
        assert focus_after_step(None, -1, 3, wrap=wrap) == 2  # noqa: PLR2004


class TestTheCancelButton:
    @staticmethod
    def _button(text: str, *, closes: bool = True) -> FrameButton:
        return FrameButton(text, lambda: None, closes=closes)

    def test_it_is_the_last_button_that_closes(self) -> None:
        ok, later = self._button("OK"), self._button("Later")
        assert cancel_button((ok, later)) is later

    def test_a_button_that_leaves_the_popup_up_is_passed_over(self) -> None:
        close, copy = self._button("Close"), self._button("Copy", closes=False)
        assert cancel_button((close, copy)) is close

    def test_there_is_none_where_no_button_closes_or_there_are_no_buttons(self) -> None:
        assert cancel_button((self._button("Copy", closes=False),)) is None
        assert cancel_button(()) is None
