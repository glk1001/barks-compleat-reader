"""Tests for the Kivy import ordering guard in config_info."""

import sys
from types import ModuleType
from unittest.mock import patch

import pytest
from barks_reader.core import config_info

# noinspection PyProtectedMember
from barks_reader.core.config_info import _assert_kivy_not_yet_imported

_NOT_UNDER_PYTEST = patch.object(config_info, "_running_under_pytest", return_value=False)


class TestAssertKivyNotYetImported:
    def test_raises_when_kivy_in_sys_modules(self) -> None:
        fake_modules = {**sys.modules, "kivy": ModuleType("kivy")}
        with (
            _NOT_UNDER_PYTEST,
            patch.dict(sys.modules, fake_modules),
            pytest.raises(ImportError, match="Kivy was imported before"),
        ):
            _assert_kivy_not_yet_imported()

    def test_raises_when_kivy_submodule_in_sys_modules(self) -> None:
        clean = {k: v for k, v in sys.modules.items() if k != "kivy" and not k.startswith("kivy.")}
        clean["kivy.app"] = ModuleType("kivy.app")
        with (
            _NOT_UNDER_PYTEST,
            patch.dict(sys.modules, clean, clear=True),
            pytest.raises(ImportError, match=r"kivy\.app"),
        ):
            _assert_kivy_not_yet_imported()

    def test_passes_when_kivy_not_loaded(self) -> None:
        clean_modules = {
            k: v for k, v in sys.modules.items() if k != "kivy" and not k.startswith("kivy.")
        }
        with _NOT_UNDER_PYTEST, patch.dict(sys.modules, clean_modules, clear=True):
            _assert_kivy_not_yet_imported()  # Should not raise.

    def test_error_message_includes_fix_hint(self) -> None:
        fake_modules = {**sys.modules, "kivy": ModuleType("kivy")}
        with (
            _NOT_UNDER_PYTEST,
            patch.dict(sys.modules, fake_modules),
            pytest.raises(ImportError, match="ensure config_info is imported before"),
        ):
            _assert_kivy_not_yet_imported()

    def test_skipped_under_pytest(self) -> None:
        """Guard should be a no-op when running under pytest."""
        fake_modules = {**sys.modules, "kivy": ModuleType("kivy")}
        with patch.dict(sys.modules, fake_modules):
            _assert_kivy_not_yet_imported()  # Should not raise (pytest skip active).
