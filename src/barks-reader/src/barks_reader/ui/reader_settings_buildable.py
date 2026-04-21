from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any, override

from loguru import logger

from barks_reader.core.reader_file_paths import BarksPanelsExtType
from barks_reader.core.reader_settings import (
    _FIELDS,
    BARKS_READER_SECTION,
    PNG_BARKS_PANELS_DIR,
    USE_PNG_IMAGES,
    BuildableConfigParser,
    ReaderSettings,
    Settings,
    _get_reader_settings_json,
    _resolve_default,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def _always_true(_value: Any) -> bool:  # noqa: ANN401
    return True


class BuildableReaderSettings(ReaderSettings):
    def __init__(self) -> None:
        super().__init__()

        self._settings: Settings | None = None

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
        assert self._config
        settings.add_json_panel(
            BARKS_READER_SECTION, self._config, data=_get_reader_settings_json()
        )
        self._settings = settings

    def validate_settings(self) -> None:
        for key in self._VALIDATION_METHODS:
            self._VALIDATION_METHODS[key](self._GETTER_METHODS[key]())

    def on_changed_setting(self, section: str, key: str, value: Any) -> bool:  # noqa: ANN401
        if section != BARKS_READER_SECTION:
            return True

        assert key in self._VALIDATION_METHODS
        if not self._VALIDATION_METHODS[key](value):
            return False

        if key == PNG_BARKS_PANELS_DIR:
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

    @override
    def _save_settings(self) -> None:
        assert self._config
        self._config.write()
        self._update_settings_panel()

    def _update_settings_panel(self) -> None:
        if not self._settings:
            logger.debug("Panel settings not set. Skipping update.")
            return

        logger.info("Updating panel reader settings.")

        panels = self._settings.interface.content.panels

        # This module is used by non-GUI scripts but this import pops up a window.
        from kivy.uix.settings import SettingItem  # noqa: PLC0415

        for panel in panels.values():
            children = panel.children

            for child in children:
                if isinstance(child, SettingItem):
                    child.value = panel.get_value(child.section, child.key)
