"""Memory census: the count after a full collection (core), and its answer (ui)."""

from __future__ import annotations

import gc
import re
import weakref
from typing import TYPE_CHECKING

import pytest
from barks_reader.core import log_markers
from barks_reader.core.log_markers import pattern
from barks_reader.core.memory_census import (
    MEMORY_CENSUS_FILE_ENV_VAR,
    take_census,
    take_request,
)
from barks_reader.ui import memory_census as ui_memory_census
from kivy.cache import Cache
from kivy.uix.widget import Widget

if TYPE_CHECKING:
    from pathlib import Path


class _Thing:
    """A stand-in for what a census counts."""


class _Cycle:
    """Garbage the collector must reach: a cycle, so reference counting alone never frees it."""

    def __init__(self) -> None:
        self.me = self


def _is_thing(obj: object) -> bool:
    return type(obj) is _Thing


class TestTakeCensus:
    def test_counts_what_is_alive(self) -> None:
        kept = [_Thing() for _ in range(3)]
        census = take_census(_is_thing, lambda _obj: False)
        assert census.widgets >= len(kept)
        assert census.textures == 0
        assert census.objects > 0
        assert census.rss_mib > 0

    def test_garbage_is_collected_before_the_count(self) -> None:
        gc.disable()  # else a collection could come at any allocation, and prove nothing
        try:
            _Cycle()
            census = take_census(lambda obj: type(obj) is _Cycle, lambda _obj: False)
        finally:
            gc.enable()
        assert census.widgets == 0


class TestTakeRequest:
    def test_a_request_is_read_and_removed(self, tmp_path: Path) -> None:
        request = tmp_path / "census-request"
        request.write_text("7\n", encoding="utf-8")
        assert take_request(request) == "7"
        assert not request.exists()

    def test_no_file_is_no_request(self, tmp_path: Path) -> None:
        assert take_request(tmp_path / "census-request") is None

    def test_an_empty_file_is_left_for_the_next_look(self, tmp_path: Path) -> None:
        request = tmp_path / "census-request"
        request.write_text("", encoding="utf-8")
        assert take_request(request) is None
        assert request.exists()


class TestAnswer:
    def test_the_answer_is_the_marker(self, loguru_sink: list[str]) -> None:
        ui_memory_census.answer("4")
        [line] = [m for m in loguru_sink if m.startswith("Memory census #4:")]
        assert re.fullmatch(pattern(log_markers.MEMORY_CENSUS, request=4), line)

    def test_a_dead_weak_proxy_is_not_asked_its_class(self) -> None:
        """Kivy keeps a weak proxy per widget; isinstance on a dead one raises ReferenceError."""
        widget = Widget()
        proxy = weakref.proxy(widget)
        del widget
        gc.collect()
        with pytest.raises(ReferenceError):
            isinstance(proxy, Widget)
        assert ui_memory_census._is_widget(proxy) is False  # noqa: SLF001

    def test_the_timed_caches_are_emptied_first(self) -> None:
        Cache.append("kv.texture", "planted", object())
        ui_memory_census.answer("5")
        assert Cache.get("kv.texture", "planted") is None


class TestInstall:
    def test_nothing_runs_without_the_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(MEMORY_CENSUS_FILE_ENV_VAR, raising=False)
        assert ui_memory_census.install_memory_census_service() is False
