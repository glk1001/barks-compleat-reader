"""Answer a GUI test's memory census request: what is alive after a full collection.

The census and its request file are ``barks_reader.core.memory_census``; this
says what a widget and a texture are, and polls for requests on the clock.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from kivy.cache import Cache
from kivy.clock import Clock
from kivy.core.image import Texture
from kivy.uix.widget import Widget
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.memory_census import MEMORY_CENSUS_FILE_ENV_VAR, take_census, take_request

if TYPE_CHECKING:
    from collections.abc import Callable

# A test asks, then waits: four looks a second answer well inside its timeout.
POLL_SECS = 0.25

# The installed poll, held here because Kivy's clock only holds it weakly.
_SERVICE: list[Callable[[float], None]] = []

# Kivy's caches that keep an image or a text rendering for a minute after its
# last use, by design. A census empties them first: counted, they would pass for
# a leak in any test that loads something new each round in under a minute.
TIMED_CACHES = ("kv.texture", "kv.image", "textinput.label", "textinput.width")


# By the object's own type: isinstance asks a weak proxy (Kivy keeps one per
# widget) for its referent's class, and raises when the referent has gone.
def _is_widget(obj: object) -> bool:
    return issubclass(type(obj), Widget)


def _is_texture(obj: object) -> bool:
    return issubclass(type(obj), Texture)


def answer(request: str) -> None:
    """Empty Kivy's timed caches, take a census, and log it as the answer to `request`."""
    for category in TIMED_CACHES:
        Cache.remove(category)
    census = take_census(_is_widget, _is_texture)
    logger.debug(
        log_markers.MEMORY_CENSUS.format(
            request=request,
            widgets=census.widgets,
            textures=census.textures,
            objects=census.objects,
            rss_mib=census.rss_mib,
            took_ms=census.took_ms,
        )
    )


def install_memory_census_service() -> bool:
    """Answer memory census requests when the GUI probe asked for them; else do nothing.

    Returns:
        Whether the service is running (the request file's variable is set).

    """
    request_file = os.environ.get(MEMORY_CENSUS_FILE_ENV_VAR, "")
    if not request_file:
        return False
    path = Path(request_file)

    def poll(_dt: float) -> None:
        request = take_request(path)
        if request is not None:
            answer(request)

    _SERVICE.append(poll)
    Clock.schedule_interval(poll, POLL_SECS)
    logger.info(f"Memory census: answering requests in {request_file}.")
    return True
