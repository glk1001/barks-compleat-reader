"""Answer a GUI test's memory census request: what is alive after a full collection.

The census and its request file are ``barks_reader.core.memory_census``; this
says what a widget and a texture are, and polls for requests on the clock.
"""

from __future__ import annotations

from kivy.cache import Cache
from kivy.core.image import Texture
from kivy.uix.widget import Widget
from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.memory_census import MEMORY_CENSUS_FILE_ENV_VAR, take_census

from .request_service import install_request_service

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
    return install_request_service(
        MEMORY_CENSUS_FILE_ENV_VAR,
        "Memory census",
        # Looked up at each request, not bound now.
        lambda request, _out_dir: answer(request),
    )
