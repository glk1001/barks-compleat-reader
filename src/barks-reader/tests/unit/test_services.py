# ruff: noqa: SLF001

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from barks_reader.core import services as services_module
from barks_reader.core.services import PlatformServices, register


class TestPlatformServicesDefaults:
    def test_default_schedule_once_calls_callback(self) -> None:
        defaults = PlatformServices()
        mock_cb = MagicMock()
        defaults.schedule_once(mock_cb, 0.5)
        mock_cb.assert_called_once_with(0.5)

    def test_default_escape_markup_returns_text_unchanged(self) -> None:
        defaults = PlatformServices()
        assert defaults.escape_markup("hello & <world>") == "hello & <world>"

    def test_default_cursor_functions_are_noop(self) -> None:
        defaults = PlatformServices()
        # Should not raise.
        defaults.set_busy_cursor()
        defaults.set_normal_cursor()


class TestRegisterAndProxy:
    def test_register_swaps_implementation(self) -> None:
        original = services_module._current_services

        mock_escape = MagicMock(return_value="escaped")
        custom = PlatformServices(escape_markup=mock_escape)

        try:
            register(custom)
            result = services_module.escape_markup("test")
            assert result == "escaped"
            mock_escape.assert_called_once_with("test")
        finally:
            register(original)

    def test_proxy_schedule_once_delegates(self) -> None:
        original = services_module._current_services

        mock_sched = MagicMock(return_value="event")
        custom = PlatformServices(schedule_once=mock_sched)

        try:
            register(custom)
            result = services_module.schedule_once(lambda _dt: None, 1.0)
            assert result == "event"
        finally:
            register(original)

    def test_proxy_cursor_functions_delegate(self) -> None:
        original = services_module._current_services

        mock_busy = MagicMock()
        mock_normal = MagicMock()
        custom = PlatformServices(set_busy_cursor=mock_busy, set_normal_cursor=mock_normal)

        try:
            register(custom)
            services_module.set_busy_cursor()
            services_module.set_normal_cursor()
            mock_busy.assert_called_once()
            mock_normal.assert_called_once()
        finally:
            register(original)


class TestUnregistered:
    """Proxies must fail loudly when no services have been registered.

    Hosts that forget to call ``register()`` previously silently used a
    synchronous default — invisible in tests, but corrupting OpenGL state in
    real Kivy hosts. The proxies now raise to surface the missing wiring.
    """

    def test_schedule_once_raises_when_unregistered(self) -> None:
        original = services_module._current_services
        try:
            register(None)
            with pytest.raises(RuntimeError, match="register"):
                services_module.schedule_once(lambda _dt: None)
        finally:
            register(original)

    def test_set_busy_cursor_raises_when_unregistered(self) -> None:
        original = services_module._current_services
        try:
            register(None)
            with pytest.raises(RuntimeError, match="register"):
                services_module.set_busy_cursor()
        finally:
            register(original)

    def test_set_normal_cursor_raises_when_unregistered(self) -> None:
        original = services_module._current_services
        try:
            register(None)
            with pytest.raises(RuntimeError, match="register"):
                services_module.set_normal_cursor()
        finally:
            register(original)

    def test_escape_markup_raises_when_unregistered(self) -> None:
        original = services_module._current_services
        try:
            register(None)
            with pytest.raises(RuntimeError, match="register"):
                services_module.escape_markup("text")
        finally:
            register(original)

    def test_error_message_mentions_register_and_test_fixture_hint(self) -> None:
        original = services_module._current_services
        try:
            register(None)
            with pytest.raises(RuntimeError) as exc_info:
                services_module.escape_markup("text")
            assert "register()" in str(exc_info.value)
            assert "PlatformServices" in str(exc_info.value)
        finally:
            register(original)

    def test_register_none_then_register_restores_proxy(self) -> None:
        original = services_module._current_services
        try:
            register(None)
            register(PlatformServices(escape_markup=lambda _t: "restored"))
            assert services_module.escape_markup("anything") == "restored"
        finally:
            register(original)
