from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from barks_reader.core.reader_palette import (
    DEFAULT_THEME_NAME,
    THEME_NAMES,
    THEMES,
    color_to_markup_hex,
    set_active_theme,
    theme,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from barks_reader.core.reader_colors import Color


@pytest.fixture(autouse=True)
def _restore_active_theme() -> Iterator[None]:
    """Leave the module-level active theme as this test found it."""
    original = theme().name
    yield
    set_active_theme(original)


class TestColorToMarkupHex:
    @pytest.mark.parametrize(
        ("color", "expected"),
        [
            ((0.0, 0.0, 0.0, 1.0), "#000000"),
            ((1.0, 1.0, 1.0, 1.0), "#ffffff"),
            ((1.0, 0.0, 0.0, 1.0), "#ff0000"),
            ((0.0, 1.0, 0.0, 1.0), "#00ff00"),
            ((0.0, 0.0, 1.0, 1.0), "#0000ff"),
            # 0.5 * 255 = 127.5, and `round` breaks the tie to even.
            ((0.5, 0.5, 0.5, 1.0), "#808080"),
            # coin gold, the app_title colour of every theme
            ((0.98, 0.82, 0.50, 1.0), "#fad180"),
        ],
    )
    def test_scales_each_channel_to_a_byte(self, color: Color, expected: str) -> None:
        assert color_to_markup_hex(color) == expected

    def test_alpha_is_ignored(self) -> None:
        assert color_to_markup_hex((1.0, 0.0, 0.0, 0.25)) == color_to_markup_hex(
            (1.0, 0.0, 0.0, 1.0)
        )


class TestActiveTheme:
    def test_every_named_theme_can_be_selected(self) -> None:
        for name in THEME_NAMES:
            set_active_theme(name)
            assert theme().name == name

    def test_unknown_name_falls_back_to_the_default(self) -> None:
        set_active_theme("Not A Theme")

        assert theme() is THEMES[DEFAULT_THEME_NAME]
