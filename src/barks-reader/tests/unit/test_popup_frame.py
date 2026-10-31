"""The popup frame: its size classes, and the widget every popup is built on."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import popup_frame as core_frame
from barks_reader.core.keys import KEY_ENTER, KEY_ESCAPE, KEY_LEFT, KEY_RIGHT
from barks_reader.core.popup_frame import (
    MAX_WINDOW_WIDTH_FRACTION,
    SIZE_CLASSES,
    FrameButton,
    PopupSize,
    popup_size,
)
from barks_reader.ui import popup_frame
from barks_reader.ui.popup_frame import PopupFrame, message_body
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput


class TestPopupSize:
    @pytest.mark.parametrize("size", list(PopupSize))
    def test_the_single_page_and_the_spread_at_one_height_match(self, size: PopupSize) -> None:
        assert popup_size(size, 900, 1300) == popup_size(size, 1760, 1300)

    def test_the_width_is_in_pages_and_the_height_in_the_window(self) -> None:
        width, height = popup_size(PopupSize.MEDIUM, 1760, 1300, page_aspect_ratio=1.3)
        assert width == pytest.approx(0.85 * 1000)
        assert height == pytest.approx(0.42 * 1300)

    def test_a_narrow_window_still_shows_round_the_popup(self) -> None:
        width, _ = popup_size(PopupSize.LARGE, 400, 1300)
        assert width == pytest.approx(MAX_WINDOW_WIDTH_FRACTION * 400)

    def test_the_classes_grow_from_small_to_large(self) -> None:
        sizes = [popup_size(size, 1760, 1300) for size in PopupSize]
        assert sizes == sorted(sizes)
        assert set(SIZE_CLASSES) == set(PopupSize)

    def test_it_is_measured_in_comic_pages_by_default(self) -> None:
        width, _ = popup_size(PopupSize.SMALL, 5000, 1300)
        assert width == pytest.approx(0.70 * 1300 / core_frame.COMIC_PAGE_ASPECT_RATIO)


def _frame(buttons: tuple[FrameButton, ...] = (), **kwargs: object) -> PopupFrame:
    with patch.object(popup_frame, "Window") as window:
        window.width, window.height = 1760, 1300
        return PopupFrame(title="A Title", body=Label(), buttons=buttons, **kwargs)  # ty: ignore[invalid-argument-type]


def _press(frame: PopupFrame, key: int) -> bool:
    return frame._on_key_down(None, key, 0, "", [])  # noqa: SLF001


def _texts(widget: object) -> list[str]:
    return [w.text for w in widget.walk() if isinstance(w, Button)]  # ty: ignore[unresolved-attribute]


class TestPopupFrame:
    def test_it_is_sized_by_its_class_and_centred(self) -> None:
        frame = _frame(size=PopupSize.SMALL)
        assert tuple(frame.size) == pytest.approx(popup_size(PopupSize.SMALL, 1760, 1300))
        assert frame.pos_hint == {"center_x": 0.5, "center_y": 0.5}

    def test_buttons_and_no_close_x(self) -> None:
        frame = _frame((FrameButton("Quit", MagicMock()), FrameButton("Stay", MagicMock())))
        assert _texts(frame) == ["Quit", "Stay"]
        assert [b.text for b in frame.button_widgets] == ["Quit", "Stay"]

    def test_no_buttons_puts_a_close_x_in_the_title_bar(self) -> None:
        assert _texts(_frame()) == ["X"]

    def test_enter_presses_the_first_button_after_closing(self) -> None:
        quit_, stay = MagicMock(), MagicMock()
        frame = _frame((FrameButton("Quit", quit_), FrameButton("Stay", stay)))
        with patch.object(frame, "dismiss") as dismiss:
            assert _press(frame, KEY_ENTER) is True
        dismiss.assert_called_once_with()
        quit_.assert_called_once_with()
        stay.assert_not_called()

    def test_right_moves_the_focus_and_left_wraps_round(self) -> None:
        presses = [MagicMock(), MagicMock(), MagicMock()]
        frame = _frame(tuple(FrameButton(str(i), p) for i, p in enumerate(presses)))
        with patch.object(frame, "dismiss"), patch.object(popup_frame, "update_focus_in_list"):
            _press(frame, KEY_RIGHT)
            _press(frame, KEY_LEFT)
            _press(frame, KEY_LEFT)
            _press(frame, KEY_ENTER)
        presses[2].assert_called_once_with()

    def test_escape_presses_the_last_button_the_cancel(self) -> None:
        ok, cancel = MagicMock(), MagicMock()
        frame = _frame((FrameButton("Settings", ok), FrameButton("Close", cancel)))
        with patch.object(frame, "dismiss"):
            _press(frame, KEY_ESCAPE)
        cancel.assert_called_once_with()
        ok.assert_not_called()

    def test_with_no_buttons_return_closes_it(self) -> None:
        frame = _frame()
        with patch.object(frame, "dismiss") as dismiss:
            assert _press(frame, KEY_ENTER) is True
        dismiss.assert_called_once_with()

    def test_with_no_buttons_escape_lands_on_the_x_and_again_leaves_it(self) -> None:
        # As everywhere in the app: Escape to the close X, Return there closes.
        frame = _frame()
        with (
            patch.object(frame, "dismiss") as dismiss,
            patch.object(popup_frame, "draw_focus_highlight") as draw,
            patch.object(popup_frame, "clear_focus_highlight") as clear,
        ):
            assert _press(frame, KEY_ESCAPE) is True
            draw.assert_called_once()
            assert draw.call_args.args[0].text == "X"
            _press(frame, KEY_ESCAPE)
            clear.assert_called_once()
            _press(frame, KEY_ENTER)
        dismiss.assert_called_once_with()

    def test_a_button_can_leave_the_popup_up(self) -> None:
        save = MagicMock()
        frame = _frame((FrameButton("Save", save, closes=False), FrameButton("OK", MagicMock())))
        with patch.object(frame, "dismiss") as dismiss:
            _press(frame, KEY_ENTER)
        save.assert_called_once_with()
        dismiss.assert_not_called()

    def test_escape_presses_the_last_button_that_closes(self) -> None:
        ok, copy = MagicMock(), MagicMock()
        frame = _frame((FrameButton("OK", ok), FrameButton("Copy", copy, closes=False)))
        with patch.object(frame, "dismiss") as dismiss:
            _press(frame, KEY_ESCAPE)
        ok.assert_called_once_with()
        copy.assert_not_called()
        dismiss.assert_called_once_with()

    def test_escape_closes_a_popup_whose_buttons_all_leave_it_up(self) -> None:
        copy = MagicMock()
        frame = _frame((FrameButton("Copy", copy, closes=False),))
        with patch.object(frame, "dismiss") as dismiss:
            _press(frame, KEY_ESCAPE)
        copy.assert_not_called()
        dismiss.assert_called_once_with()

    def test_it_can_fill_its_window_whatever_the_window_does(self) -> None:
        frame = _frame(fill_window=True)
        assert tuple(frame.size_hint) == (1, 1)
        size = tuple(frame.size)
        with patch.object(popup_frame, "Window") as window:
            window.width, window.height = 400, 300
            frame.fit_to_window()
        assert tuple(frame.size) == size

    def test_every_key_is_kept_while_it_is_open(self) -> None:
        frame = _frame()
        with patch.object(frame, "dismiss") as dismiss:
            assert _press(frame, KEY_LEFT) is True
        dismiss.assert_not_called()

    def test_its_title_can_be_changed_to_show_news(self) -> None:
        frame = _frame()
        frame.title = "Copied to clipboard"
        titles = [w.text for w in frame.walk() if isinstance(w, Label)]
        assert "Copied to clipboard" in titles
        assert "A Title" not in titles

    def test_a_key_handler_is_asked_first_and_what_it_takes_the_frame_leaves(self) -> None:
        frame = _frame()
        frame.key_handler = MagicMock(side_effect=lambda key: key == KEY_ENTER)
        with patch.object(frame, "dismiss") as dismiss:
            assert _press(frame, KEY_ENTER) is True  # taken: the frame does not close
            dismiss.assert_not_called()
            frame.key_handler = MagicMock(return_value=False)
            _press(frame, KEY_ENTER)  # left: the frame's Return closes it
        dismiss.assert_called_once_with()

    def test_its_body_can_be_put_in_another_place(self) -> None:
        ok = FrameButton("OK", MagicMock())
        frame = _frame((ok,))
        old, new = frame.body, Label(text="new body")
        content = old.parent
        frame.set_body(new)
        assert frame.body is new
        assert old.parent is None
        assert content.children[-1] is new  # above the button row

    def test_only_a_frame_that_asks_closes_on_a_tap_outside(self) -> None:
        assert _frame().auto_dismiss is False
        assert _frame(close_on_outside_tap=True).auto_dismiss is True

    def test_the_title_can_carry_markup_a_font_and_a_new_size(self) -> None:
        frame = _frame(title_markup=True, title_font_name="Roboto")
        (title,) = [w for w in frame.walk() if isinstance(w, Label) and w.text == "A Title"]
        assert title.markup is True
        assert title.font_name == "Roboto"
        frame.title_font_size = 31
        assert title.font_size == 31  # noqa: PLR2004

    def test_the_focus_can_start_on_another_button(self) -> None:
        clear, cancel = MagicMock(), MagicMock()
        frame = _frame((FrameButton("Clear", clear), FrameButton("Cancel", cancel)), first_focus=1)
        with patch.object(frame, "dismiss"):
            _press(frame, KEY_ENTER)
        cancel.assert_called_once_with()
        clear.assert_not_called()

    def test_a_row_left_unfocused_presses_nothing_on_enter_and_escape_still_cancels(self) -> None:
        ok, cancel = MagicMock(), MagicMock()
        frame = _frame((FrameButton("OK", ok), FrameButton("Cancel", cancel)), first_focus=None)
        with patch.object(frame, "dismiss"):
            assert _press(frame, KEY_ENTER) is True  # kept, but no button has the focus
            ok.assert_not_called()
            _press(frame, KEY_ESCAPE)
        cancel.assert_called_once_with()

    @pytest.mark.parametrize(("key", "pressed"), [(KEY_RIGHT, "OK"), (KEY_LEFT, "Cancel")])
    def test_right_or_left_onto_an_unfocused_row_lands_on_its_near_end(
        self, key: int, pressed: str
    ) -> None:
        on_press = {"OK": MagicMock(), "Cancel": MagicMock()}
        frame = _frame(
            tuple(FrameButton(text, action) for text, action in on_press.items()), first_focus=None
        )
        _press(frame, key)
        with patch.object(frame, "dismiss"):
            _press(frame, KEY_ENTER)
        on_press[pressed].assert_called_once_with()

    def test_a_body_can_hand_the_focus_to_the_row_and_take_it_back(self) -> None:
        ok = MagicMock()
        frame = _frame(
            (FrameButton("OK", ok), FrameButton("Cancel", MagicMock())), first_focus=None
        )
        frame.focus_button(0)
        with patch.object(frame, "dismiss"):
            _press(frame, KEY_ENTER)
        ok.assert_called_once_with()
        frame.focus_button(None)
        with patch.object(frame, "dismiss"):
            _press(frame, KEY_ENTER)
        ok.assert_called_once_with()  # not again: the row has no focus

    def test_while_a_text_box_has_the_keyboard_only_escape_is_the_frames(self) -> None:
        box = TextInput()
        ok, cancel = MagicMock(), MagicMock()
        with patch.object(popup_frame, "Window") as window:
            window.width, window.height = 1760, 1300
            frame = PopupFrame(
                title="T", body=box, buttons=(FrameButton("OK", ok), FrameButton("Cancel", cancel))
            )
        box.focus = True
        with patch.object(frame, "dismiss"):
            assert _press(frame, KEY_ENTER) is False  # the box's own Enter
            assert _press(frame, KEY_LEFT) is False
            ok.assert_not_called()
            assert _press(frame, KEY_ESCAPE) is True
        cancel.assert_called_once_with()
        box.focus = False

    def test_closing_lets_a_focused_text_box_go(self) -> None:
        box = TextInput()
        with patch.object(popup_frame, "Window") as window:
            window.width, window.height = 1760, 1300
            frame = PopupFrame(title="T", body=box, buttons=(FrameButton("OK", MagicMock()),))
        box.focus = True
        with patch.object(popup_frame, "Window"):
            frame.dispatch("on_dismiss")
        assert box.focus is False

    def test_on_closed_runs_once_it_has_left_the_window(self) -> None:
        on_closed = MagicMock()
        frame = _frame(on_closed=on_closed)
        frame._on_parent(frame, MagicMock())  # noqa: SLF001
        on_closed.assert_not_called()
        frame._on_parent(frame, None)  # noqa: SLF001
        on_closed.assert_called_once_with()

    def test_the_keys_are_taken_before_the_fade_in(self) -> None:
        # The screen beneath yields keys to any modal on the window, fading in or not.
        frame = _frame()
        with patch.object(popup_frame, "Window") as window:
            frame.dispatch("on_pre_open")
        window.bind.assert_called_once()

    def test_the_window_bindings_go_with_the_dismissal(self) -> None:
        frame = _frame((FrameButton("OK", MagicMock()),))
        with (
            patch.object(popup_frame, "Window") as window,
            patch.object(popup_frame, "update_focus_in_list") as focus,
        ):
            frame._on_pre_open()  # noqa: SLF001
            frame._on_dismiss()  # noqa: SLF001
        assert window.bind.call_args.kwargs == window.unbind.call_args.kwargs
        focus.assert_called_once_with(frame.button_widgets, 0, popup_frame._FOCUS_GROUP)  # noqa: SLF001


class TestMessageBody:
    def test_prose_is_left_aligned_and_a_question_centred(self) -> None:
        assert message_body("Prose.", font_size=20).halign == "left"
        assert message_body("A question?", font_size=20, centred=True).halign == "center"

    def test_it_wraps_to_its_size(self) -> None:
        label = message_body("Prose.", font_size=20)
        label.size = (300, 100)
        assert tuple(label.text_size) == (300, 100)
