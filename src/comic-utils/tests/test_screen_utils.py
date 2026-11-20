"""Tests for the primary-monitor helpers, over a stand-in monitor list."""

from __future__ import annotations

import sys
from typing import NamedTuple
from unittest.mock import patch

import pytest
import screeninfo
from comic_utils.screen_utils import (
    get_centred_position_on_primary_monitor,
    get_primary_monitor_offset,
)


class _Monitor(NamedTuple):
    x: int
    y: int
    width: int
    height: int
    is_primary: bool


LEFT = _Monitor(x=0, y=0, width=1920, height=1080, is_primary=False)
RIGHT = _Monitor(x=1920, y=100, width=2560, height=1440, is_primary=True)

WINDOW = (560, 440)
CENTRED_ON_RIGHT = (1920 + (2560 - 560) // 2, 100 + (1440 - 440) // 2)
NO_MONITOR_OFFSET = (0, 0)
NO_MONITOR_POSITION = (100, 100)


# What screeninfo gives (a list, or the error it raises), then each helper's answer.
@pytest.mark.parametrize(
    ("monitors", "offset", "centred"),
    [
        pytest.param([LEFT, RIGHT], (1920, 100), CENTRED_ON_RIGHT, id="the primary monitor"),
        pytest.param(
            # The first is the right-hand one, so neither the last monitor nor the
            # no-monitor fallback gives its answer.
            [RIGHT._replace(is_primary=False), LEFT],
            (1920, 100),
            CENTRED_ON_RIGHT,
            id="no primary: the first monitor",
        ),
        pytest.param([], NO_MONITOR_OFFSET, NO_MONITOR_POSITION, id="no monitors"),
        pytest.param(
            screeninfo.ScreenInfoError,
            NO_MONITOR_OFFSET,
            NO_MONITOR_POSITION,
            id="the monitors cannot be read",
        ),
    ],
)
def test_the_offset_and_the_centred_position(
    monitors: list[_Monitor] | type[Exception], offset: tuple[int, int], centred: tuple[int, int]
) -> None:
    if isinstance(monitors, type):
        get_monitors = patch.object(screeninfo, "get_monitors", side_effect=monitors)
    else:
        get_monitors = patch.object(screeninfo, "get_monitors", return_value=monitors)
    with get_monitors:
        assert get_primary_monitor_offset() == offset
        assert get_centred_position_on_primary_monitor(*WINDOW) == centred


def test_a_screeninfo_that_will_not_import_gives_the_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # None in sys.modules makes the import statement raise ImportError.
    monkeypatch.setitem(sys.modules, "screeninfo", None)

    assert get_primary_monitor_offset() == NO_MONITOR_OFFSET
    assert get_centred_position_on_primary_monitor(*WINDOW) == NO_MONITOR_POSITION
