"""The screen bundle's groups: which screens the keys and the bottom pane each mean."""

from __future__ import annotations

from dataclasses import fields
from unittest.mock import MagicMock

from barks_reader.ui.screen_bundle import ScreenBundle


def _bundle() -> ScreenBundle:
    return ScreenBundle(
        **{field.name: MagicMock(name=field.name) for field in fields(ScreenBundle)}
    )


def test_the_screens_that_take_the_keys_are_looked_for_indexes_first() -> None:
    bundle = _bundle()
    assert bundle.keyboard_nav_screens == (
        bundle.main_index,
        bundle.speech_index,
        bundle.names_index,
        bundle.locations_index,
        bundle.statistics,
        bundle.history,
        bundle.search,
    )


def test_the_bottom_pane_holds_the_two_views_and_every_screen_that_takes_the_keys() -> None:
    bundle = _bundle()
    assert set(map(id, bundle.bottom_screens)) == {
        id(bundle.bottom_title_view),
        id(bundle.fun_image_view),
        *map(id, bundle.keyboard_nav_screens),
    }
