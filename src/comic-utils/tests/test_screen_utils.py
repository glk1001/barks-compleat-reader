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


class TestPrimaryMonitorOffset:
    def test_the_primary_monitors_origin(self) -> None:
        with patch.object(screeninfo, "get_monitors", return_value=[LEFT, RIGHT]):
            assert get_primary_monitor_offset() == (1920, 100)

    def test_with_no_primary_the_first_monitors_origin(self) -> None:
        with patch.object(
            screeninfo, "get_monitors", return_value=[RIGHT._replace(is_primary=False)]
        ):
            assert get_primary_monitor_offset() == (1920, 100)

    def test_with_no_monitors_the_desktop_origin(self) -> None:
        with patch.object(screeninfo, "get_monitors", return_value=[]):
            assert get_primary_monitor_offset() == (0, 0)

    def test_when_the_monitors_cannot_be_read_the_desktop_origin(self) -> None:
        with patch.object(screeninfo, "get_monitors", side_effect=screeninfo.ScreenInfoError):
            assert get_primary_monitor_offset() == (0, 0)


class TestCentredOnThePrimaryMonitor:
    def test_centred_on_the_primary_monitor(self) -> None:
        with patch.object(screeninfo, "get_monitors", return_value=[LEFT, RIGHT]):
            assert get_centred_position_on_primary_monitor(560, 440) == (
                1920 + (2560 - 560) // 2,
                100 + (1440 - 440) // 2,
            )

    def test_with_no_primary_centred_on_the_first_monitor(self) -> None:
        with patch.object(screeninfo, "get_monitors", return_value=[LEFT]):
            assert get_centred_position_on_primary_monitor(920, 80) == (500, 500)

    def test_with_no_monitors_a_fixed_position(self) -> None:
        with patch.object(screeninfo, "get_monitors", return_value=[]):
            assert get_centred_position_on_primary_monitor(560, 440) == (100, 100)

    def test_when_the_monitors_cannot_be_read_a_fixed_position(self) -> None:
        with patch.object(screeninfo, "get_monitors", side_effect=screeninfo.ScreenInfoError):
            assert get_centred_position_on_primary_monitor(560, 440) == (100, 100)


class TestWithoutScreeninfo:
    """A machine where screeninfo will not import still gets a position."""

    @pytest.fixture(autouse=True)
    def _no_screeninfo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # None in sys.modules makes the import statement raise ImportError.
        monkeypatch.setitem(sys.modules, "screeninfo", None)

    def test_the_offset_is_the_desktop_origin(self) -> None:
        assert get_primary_monitor_offset() == (0, 0)

    def test_the_centred_position_is_the_fixed_one(self) -> None:
        assert get_centred_position_on_primary_monitor(560, 440) == (100, 100)
