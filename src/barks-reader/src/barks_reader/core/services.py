from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class PlatformServices:
    """A collection of all UI/Platform specific functions.

    Default values act as the 'Test Implementation' (Null Pattern).
    """

    # RETURNS: Any (Kivy returns an Event object, your test lambda returns None)
    schedule_once: Callable[[Callable[[float], Any], float], Any] = lambda cb, dt: cb(dt)

    set_busy_cursor: Callable[[], None] = lambda: None
    set_normal_cursor: Callable[[], None] = lambda: None

    escape_markup: Callable[[str], str] = lambda text: text


# --- The Singleton Instance ---
_current_services = PlatformServices()


# --- Registration ---
def register(services: PlatformServices) -> None:
    """Call this from main.py to swap in the real Kivy implementation."""
    global _current_services  # noqa: PLW0603
    _current_services = services


# --- Proxy Functions ---


def schedule_once(callback: Callable[[float], Any], timeout: float = 0) -> Any:  # noqa: ANN401
    # Note: Kivy's Clock.schedule_once takes (callback, timeout)
    # noinspection PyArgumentList
    return _current_services.schedule_once(callback, timeout)


def set_busy_cursor() -> None:
    _current_services.set_busy_cursor()


def set_normal_cursor() -> None:
    _current_services.set_normal_cursor()


def escape_markup(text: str) -> str:
    # noinspection PyArgumentList
    return _current_services.escape_markup(text)
