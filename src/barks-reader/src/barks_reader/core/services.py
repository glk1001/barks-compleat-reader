from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PlatformServices:
    """A collection of all UI/Platform specific functions.

    Default field values act as a synchronous null implementation, so
    ``PlatformServices()`` is still usable as a stand-alone test double:
    ``schedule_once`` runs the callback inline, cursor changes are no-ops,
    ``escape_markup`` is identity. The module-level singleton, however, is
    deliberately unset — see ``_current_services`` below.
    """

    # RETURNS: Any (Kivy returns an Event object, your test lambda returns None)
    schedule_once: Callable[[Callable[[float], Any], float], Any] = lambda cb, dt: cb(dt)

    set_busy_cursor: Callable[[], None] = lambda: None
    set_normal_cursor: Callable[[], None] = lambda: None

    escape_markup: Callable[[str], str] = lambda text: text


# The singleton starts unset so a missing ``register()`` call fails loudly.
# Previously this defaulted to ``PlatformServices()``, which silently ran
# worker-thread callbacks inline on the calling (non-GL) thread — invisible
# in tests, but produces black canvases / corrupted OpenGL state in real
# Kivy hosts that forgot to register. Hosts must call ``register()``; tests
# typically register an explicit null impl via a fixture.
_current_services: PlatformServices | None = None


def register(services: PlatformServices | None) -> None:
    """Swap in the active PlatformServices.

    Kivy hosts pass a Kivy-backed instance. Tests pass either a custom
    instance or ``PlatformServices()`` for the synchronous null impl. ``None``
    resets back to unregistered (used by tests to restore prior state).
    """
    global _current_services  # noqa: PLW0603
    _current_services = services


def _require_services() -> PlatformServices:
    if _current_services is None:
        msg = (
            "barks_reader.core.services.register() has not been called. "
            "Kivy hosts: register PlatformServices(schedule_once=Clock.schedule_once, ...). "
            "Tests: register PlatformServices() (null impl) in a fixture."
        )
        raise RuntimeError(msg)
    return _current_services


# --- Proxy Functions ---


def schedule_once(callback: Callable[[float], Any], timeout: float = 0) -> Any:  # noqa: ANN401
    # Note: Kivy's Clock.schedule_once takes (callback, timeout)
    # noinspection PyArgumentList
    return _require_services().schedule_once(callback, timeout)


def set_busy_cursor() -> None:
    _require_services().set_busy_cursor()


def set_normal_cursor() -> None:
    _require_services().set_normal_cursor()


def escape_markup(text: str) -> str:
    # noinspection PyArgumentList
    return _require_services().escape_markup(text)
