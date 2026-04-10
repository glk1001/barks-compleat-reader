from __future__ import annotations

from barks_reader.core.settings_notifier import SettingsNotifier


class TestSettingsNotifier:
    def test_notify_calls_registered_callback(self) -> None:
        notifier = SettingsNotifier()
        called = []
        notifier.register_callback("display", "theme", lambda: called.append("theme"))

        notifier.notify("display", "theme")

        assert called == ["theme"]

    def test_notify_with_no_registered_callbacks_is_noop(self) -> None:
        notifier = SettingsNotifier()
        # Should not raise.
        notifier.notify("display", "theme")

    def test_notify_does_not_fire_unrelated_callbacks(self) -> None:
        notifier = SettingsNotifier()
        called = []
        notifier.register_callback("display", "theme", lambda: called.append("theme"))

        notifier.notify("display", "font_size")

        assert called == []

    def test_multiple_callbacks_for_same_key(self) -> None:
        notifier = SettingsNotifier()
        called: list[str] = []
        notifier.register_callback("sec", "key", lambda: called.append("a"))
        notifier.register_callback("sec", "key", lambda: called.append("b"))

        notifier.notify("sec", "key")

        assert called == ["a", "b"]

    def test_callbacks_for_different_keys_are_independent(self) -> None:
        notifier = SettingsNotifier()
        called: list[str] = []
        notifier.register_callback("s1", "k1", lambda: called.append("first"))
        notifier.register_callback("s2", "k2", lambda: called.append("second"))

        notifier.notify("s1", "k1")

        assert called == ["first"]

    def test_notify_can_be_called_multiple_times(self) -> None:
        notifier = SettingsNotifier()
        call_count = 0

        def increment() -> None:
            nonlocal call_count
            call_count += 1

        notifier.register_callback("s", "k", increment)
        notifier.notify("s", "k")
        notifier.notify("s", "k")

        assert call_count == 2  # noqa: PLR2004
