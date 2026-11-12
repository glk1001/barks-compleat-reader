from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any, cast, override

from loguru import logger

from barks_reader.core import log_markers
from barks_reader.core.reader_file_paths import BarksPanelsExtType
from barks_reader.core.reader_settings import (
    _FIELDS,
    BARKS_READER_SECTION,
    PNG_BARKS_PANELS_DIR,
    USE_PNG_IMAGES,
    BuildableConfigParser,
    ReaderSettings,
    SavableConfig,
    Settings,
    _get_reader_settings_json,
    _resolve_default,
    setting_value_from_panel,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# The settings window's title bar; the ini section stays BARKS_READER_SECTION.
SETTINGS_PANEL_TITLE = "Settings"


def _always_true(_value: Any) -> bool:  # noqa: ANN401
    return True


class BuildableReaderSettings(ReaderSettings):
    def __init__(self) -> None:
        super().__init__()

        self._settings: Settings | None = None
        # Each setting's value as the ini last held it on purpose: what a refused
        # change is put back to. Kivy's panel writes a change before it is checked.
        self._accepted_values: dict[str, str] = {}

        self._GETTER_METHODS: dict[str, Callable[[], Any]] = {
            spec.key: partial(self._read, spec.key) for spec in _FIELDS
        }
        self._VALIDATION_METHODS: dict[str, Callable[..., bool]] = {
            spec.key: partial(spec.validator, self) if spec.validator else _always_true
            for spec in _FIELDS
        }

    @staticmethod
    def build_config(config: BuildableConfigParser) -> None:
        # NOTE: For some reason we need to use 0/1 instead of False/True.
        #       Not sure why.
        config.setdefaults(
            BARKS_READER_SECTION,
            {spec.key: _resolve_default(spec) for spec in _FIELDS},
        )

    def build_settings(self, settings: Settings) -> None:
        settings.add_json_panel(
            SETTINGS_PANEL_TITLE, self._kivy_config(), data=_get_reader_settings_json()
        )
        self._settings = settings
        self._remember_accepted_values()

    def _remember_accepted_values(self) -> None:
        config = self._kivy_config()
        self._accepted_values = {
            spec.key: str(config.get(BARKS_READER_SECTION, spec.key)) for spec in _FIELDS
        }

    def _kivy_config(self) -> SavableConfig:
        # The settings panel and saving need Kivy's parser: the stdlib's write takes a
        # file. Only the app builds the panel or saves, and it sets Kivy's.
        assert self._config
        return cast("SavableConfig", self._config)

    def validate_settings(self) -> None:
        """Check each setting as the ini holds it, and log each one that will not do.

        At boot: a bad setting is named now, not left to show as a load failing later
        (some validators, such as the wiki bundle's index.md check, log nothing).
        """
        for key, is_valid in self._VALIDATION_METHODS.items():
            value = self._GETTER_METHODS[key]()
            if not is_valid(value):
                logger.warning(log_markers.SETTING_NOT_VALID_AT_BOOT.format(key=key, value=value))

    def on_changed_setting(self, section: str, key: str, value: Any) -> bool:  # noqa: ANN401
        if section != BARKS_READER_SECTION:
            return True

        assert key in self._VALIDATION_METHODS
        panel_text = str(value)
        value = setting_value_from_panel(key, value)  # the panel's text, typed
        if not self._VALIDATION_METHODS[key](value):
            self._put_back_refused(key, panel_text)
            return False
        self._accepted_values[key] = panel_text

        if key == PNG_BARKS_PANELS_DIR:
            # Only PNG mode reads this dir. In JPG mode its validator lets any path
            # through, and switching to it would read JPGs from the PNG dir - or raise,
            # if it does not exist yet. It is read when PNG images are turned on.
            if self._read(USE_PNG_IMAGES):
                self._reader_file_paths.set_barks_panels_source(
                    value, self._get_barks_panels_ext_type()
                )
        elif key == USE_PNG_IMAGES:
            if value:
                self._reader_file_paths.set_barks_panels_source(
                    self._read(PNG_BARKS_PANELS_DIR), BarksPanelsExtType.MOSTLY_PNG
                )
            else:
                self._reader_file_paths.set_barks_panels_source(
                    self._get_jpg_barks_panels_source(), BarksPanelsExtType.JPG
                )

        return True

    def _put_back_refused(self, key: str, refused: str) -> None:
        """Put the ini and the panel back to the value ``key`` had before Kivy wrote ``refused``."""
        kept = self._accepted_values.get(key)
        if kept is None:  # no panel was built, so nothing wrote the change
            return
        logger.warning(log_markers.SETTING_REFUSED.format(key=key, value=refused, kept=kept))
        self._kivy_config().set(BARKS_READER_SECTION, key, kept)
        # The panel's item is set back to the ini's value: its panel.set_value then
        # finds nothing changed, so no second on_config_change is sent.
        self._save_settings()

    @override
    def _save_settings(self) -> None:
        self._kivy_config().write()
        self._update_settings_panel()
        if self._settings:
            self._remember_accepted_values()  # a setting the app itself saved

    def _update_settings_panel(self) -> None:
        if not self._settings:
            logger.debug("Panel settings not set. Skipping update.")
            return

        logger.info("Updating panel reader settings.")

        # Kivy's menu interfaces and PinnedTitleSettingsInterface hold the ContentPanel
        # in `.content`; a bare ContentPanel used as the interface is itself.
        interface = self._settings.interface
        content = getattr(interface, "content", None) or interface
        panels = content.panels

        # This module is used by non-GUI scripts but this import pops up a window.
        from kivy.uix.settings import SettingItem  # noqa: PLC0415

        for panel in panels.values():
            children = panel.children

            for child in children:
                if isinstance(child, SettingItem):
                    child.value = panel.get_value(child.section, child.key)
