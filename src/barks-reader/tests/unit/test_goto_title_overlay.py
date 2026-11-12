# ruff: noqa: SLF001
"""The goto-title overlay: a title in italics beside the button that goes to it."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.ui import goto_title_overlay
from barks_reader.ui.goto_title_overlay import OVERLAY_BUTTON_WIDTH, GotoTitleOverlay
from barks_reader.ui.ui_helpers import TouchExpandedButton
from kivy.factory import Factory
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty  # ty: ignore[import-not-found]
from kivy.uix.label import Label

if TYPE_CHECKING:
    from collections.abc import Iterator


class _BgColorLabel(Label):
    """Stand in for the app's BgColorLabel, defined in main_screen.kv, which is not loaded here."""

    background_color = ListProperty([0, 0, 0, 0])
    sizing_factor_x = NumericProperty(1.0)


@pytest.fixture(autouse=True)
def _bg_color_label() -> Iterator[None]:
    if "BgColorLabel" in Factory.classes:
        yield
        return
    Factory.register("BgColorLabel", cls=_BgColorLabel)
    yield
    Factory.unregister("BgColorLabel")


def _overlay(**kwargs: object) -> GotoTitleOverlay:
    with patch.object(GotoTitleOverlay, "_get_button_source", return_value="book.png"):
        overlay = GotoTitleOverlay(size_hint=(None, None), **kwargs)
    overlay.pos = (100, 50)
    overlay.size = (400, 300)
    return overlay


def _label(overlay: GotoTitleOverlay) -> Label:
    # Not the button, which is a Label too.
    return next(child for child in overlay.children if child is not overlay.goto_button)


def test_a_title_is_set_in_italics() -> None:
    assert goto_title_overlay._italic("Lost in the Andes!") == "[i]Lost in the Andes![/i]"


def test_a_titles_own_brackets_and_ampersand_are_text_not_markup() -> None:
    assert goto_title_overlay._italic("Tom & [b]Jerry") == "[i]Tom &amp; &bl;b&br;Jerry[/i]"


class TestTheOverlay:
    def test_it_holds_a_label_and_the_button_it_names(self) -> None:
        overlay = _overlay(current_title_str="Lost in the Andes!")

        button = overlay.goto_button
        assert isinstance(button, TouchExpandedButton)
        assert button.source == "book.png"
        assert button.visual_size == OVERLAY_BUTTON_WIDTH
        assert _label(overlay).text == "[i]Lost in the Andes![/i]"
        # The button is added last: it is on top, and takes the press first.
        assert overlay.children[0] is button

    @pytest.mark.parametrize(
        ("position", "disc_bottom"),
        [
            ("bottom-right", 0.4 * OVERLAY_BUTTON_WIDTH),
            ("top-right", 300 - OVERLAY_BUTTON_WIDTH - dp(10)),
        ],
    )
    def test_the_button_sits_in_the_corner_the_position_names(
        self, position: str, disc_bottom: float
    ) -> None:
        overlay = _overlay(position=position)
        button = overlay.goto_button

        assert button.x == pytest.approx(
            100 + 400 - 1.4 * OVERLAY_BUTTON_WIDTH - button.touch_padding
        )
        assert button.y == pytest.approx(50 + disc_bottom - button.touch_padding)

    def test_the_label_stands_left_of_the_button_level_with_it(self) -> None:
        overlay = _overlay(current_title_str="Lost in the Andes!")
        button, label = overlay.goto_button, _label(overlay)
        label.size = (120, 20)

        assert label.x == pytest.approx(button.x - 120 - dp(2))
        assert label.y == pytest.approx(button.y + (button.height - 20) / 2)

    def test_the_label_follows_the_title_its_colours_and_whether_it_shows(self) -> None:
        overlay = _overlay(current_title_str="Lost in the Andes!")
        label = _label(overlay)

        overlay.current_title_str = "Voodoo [Hoodoo]"
        assert label.text == "[i]Voodoo &bl;Hoodoo&br;[/i]"

        overlay.label_color = (1, 0, 0, 1)
        overlay.label_bg_color = (0, 0, 1, 1)
        assert list(label.color) == [1, 0, 0, 1]
        assert list(label.background_color) == [0, 0, 1, 1]

        overlay.label_opacity = 0.5
        assert label.opacity == pytest.approx(0.5)
        overlay.show_title = False
        assert label.opacity == 0
        overlay.show_title = True
        assert label.opacity == pytest.approx(0.5)

    def test_a_label_colour_given_is_kept_and_none_given_is_the_themes(self) -> None:
        assert list(_overlay(label_color=(0, 1, 0, 1)).label_color) == [0, 1, 0, 1]
        themed = _overlay()
        assert list(themed.label_color) == list(goto_title_overlay.theme().text_title)

    def test_a_press_on_the_button_is_the_overlays_goto_press(self) -> None:
        overlay = _overlay()
        pressed = MagicMock()
        overlay.bind(on_goto_press=pressed)

        overlay.goto_button.dispatch("on_press")

        pressed.assert_called_once_with(overlay)

    def test_the_button_is_active_as_the_overlay_is(self) -> None:
        overlay = _overlay(is_active=False)
        assert overlay.goto_button.is_active is False
        overlay.is_active = True
        assert overlay.goto_button.is_active is True

    def test_the_buttons_image_is_the_apps_goto_title_file(self) -> None:
        app = MagicMock()
        app.reader_settings.sys_file_paths.get_goto_title_button_file.return_value = "goto.png"
        with patch.object(goto_title_overlay.App, "get_running_app", return_value=app):
            assert GotoTitleOverlay._get_button_source() == "goto.png"
