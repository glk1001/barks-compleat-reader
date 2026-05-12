"""Shared fixtures for unit and benchmark trees."""

from __future__ import annotations

import pytest
from barks_reader.core import services


@pytest.fixture(autouse=True)
def _register_null_services() -> None:
    """Register the synchronous null PlatformServices for every test.

    Production code calls ``services.register()`` during Kivy boot, but tests
    don't go through that path. The singleton is deliberately unset by default
    (fail-fast for unregistered Kivy hosts), so each test needs the null impl
    swapped in. This lives at the ``tests/`` root so the benchmark tree picks
    it up too — without it, ``comic_book_loader``'s worker-thread callbacks
    raise inside ``services.schedule_once`` and the load-complete events
    never fire.
    """
    services.register(services.PlatformServices())
