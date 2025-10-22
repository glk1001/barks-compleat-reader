from collections import defaultdict
from collections.abc import Callable


class SettingsNotifier:
    """A class to manage and notify about settings changes."""

    def __init__(self) -> None:
        self._callbacks: dict[tuple[str, str], list[Callable[[], None]]] = defaultdict(list)
        self._on_change: Callable[[], None] | None = None

    def register_callback(
        self,
        section_name: str,
        section_key: str,
        callback_func: Callable[[], None],
    ) -> None:
        """Register a callback for a specific setting.

        Args:
            section_name: The name of the settings section.
            section_key: The key of the setting within the section.
            callback_func: The function to call when the setting changes.

        """
        self._callbacks[(section_name, section_key)].append(callback_func)

    def notify(self, section_name: str, section_key: str) -> None:
        """Notify all registered callbacks about a setting change.

        This method is intended to be called by the settings management system
        when a setting's value is updated.

        Args:
            section_name: The name of the section of the changed setting.
            section_key: The key of the changed setting.

        """
        callbacks_to_run = self._callbacks.get((section_name, section_key), [])
        for callback in callbacks_to_run:
            callback()


settings_notifier = SettingsNotifier()
