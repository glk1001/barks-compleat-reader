# ruff: noqa: SLF001, ARG005

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import panel_image_loader as loader_module
from barks_reader.core.panel_image_loader import PanelImageLoader
from barks_reader.core.services import schedule_once
from PIL import Image


@pytest.fixture
def mock_callback() -> MagicMock:
    return MagicMock()


@pytest.fixture
def loader() -> PanelImageLoader:
    return PanelImageLoader()


def _patch_sync_worker(loader_ref: PanelImageLoader) -> tuple:  # noqa: ARG001
    """Return patchers that run the worker thread synchronously and execute schedule_once inline."""
    thread_patch = patch.object(loader_module, threading.Thread.__name__)
    schedule_patch = patch.object(loader_module, schedule_once.__name__)
    return thread_patch, schedule_patch


class TestPanelImageLoader:
    def test_init(self) -> None:
        loader = PanelImageLoader()
        assert loader._cancel is False
        assert loader._current_thread is None

    def test_cancel(self, loader: PanelImageLoader) -> None:
        loader.cancel()
        assert loader._cancel is True

    def test_load_pil_success_invokes_callback_with_rgba_image(
        self, loader: PanelImageLoader, mock_callback: MagicMock
    ) -> None:
        mock_path = MagicMock(spec=Path)
        raw_pil = MagicMock(spec=Image.Image)
        converted = MagicMock(spec=Image.Image)
        raw_pil.convert.return_value = converted

        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(loader_module, "load_pil", return_value=raw_pil) as mock_load_pil,
            patch.object(loader_module, "convert_mode", return_value=converted) as mock_convert,
            patch.object(loader_module, schedule_once.__name__) as mock_schedule,
        ):
            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: target(*args)
            )
            mock_schedule.side_effect = lambda func, dt: func(dt)

            loader.load_pil(mock_path, mock_callback)

            mock_load_pil.assert_called_once_with(mock_path, encrypted_zip=True)
            mock_convert.assert_called_once_with(raw_pil, "RGBA")
            mock_callback.assert_called_once_with(converted, None)

    def test_load_pil_error_path(self, loader: PanelImageLoader, mock_callback: MagicMock) -> None:
        mock_path = MagicMock(spec=Path)
        error = OSError("Read failed")

        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(loader_module, "load_pil", side_effect=error),
            patch.object(loader_module, schedule_once.__name__) as mock_schedule,
        ):
            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: target(*args)
            )
            mock_schedule.side_effect = lambda func, dt: func(dt)

            loader.load_pil(mock_path, mock_callback)

            mock_callback.assert_called_once_with(None, error)

    def test_worker_cancel_before_decode_skips_callback(
        self, loader: PanelImageLoader, mock_callback: MagicMock
    ) -> None:
        mock_path = MagicMock(spec=Path)

        def cancel_during_load(*_a: object, **_k: object) -> MagicMock:
            loader.cancel()
            return MagicMock(spec=Image.Image)

        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(loader_module, "load_pil", side_effect=cancel_during_load),
            patch.object(loader_module, "convert_mode") as mock_convert,
            patch.object(loader_module, schedule_once.__name__) as mock_schedule,
        ):
            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: target(*args)
            )

            loader.load_pil(mock_path, mock_callback)

            # Cancel happened right after load_pil; convert_mode should not run.
            mock_convert.assert_not_called()
            mock_schedule.assert_not_called()

    def test_worker_cancel_after_convert_skips_callback(
        self, loader: PanelImageLoader, mock_callback: MagicMock
    ) -> None:
        mock_path = MagicMock(spec=Path)
        raw_pil = MagicMock(spec=Image.Image)

        def cancel_during_convert(*_a: object, **_k: object) -> MagicMock:
            loader.cancel()
            return MagicMock(spec=Image.Image)

        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(loader_module, "load_pil", return_value=raw_pil),
            patch.object(loader_module, "convert_mode", side_effect=cancel_during_convert),
            patch.object(loader_module, schedule_once.__name__) as mock_schedule,
        ):
            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: target(*args)
            )

            loader.load_pil(mock_path, mock_callback)

            mock_schedule.assert_not_called()

    def test_start_worker_kills_previous_thread(
        self, loader: PanelImageLoader, mock_callback: MagicMock
    ) -> None:
        mock_path = MagicMock(spec=Path)

        with patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls:
            mock_thread_instance = MagicMock()
            mock_thread_cls.return_value = mock_thread_instance

            loader.load_pil(mock_path, mock_callback)
            assert loader._current_thread == mock_thread_instance

            loader.load_pil(mock_path, mock_callback)

            mock_thread_instance.join.assert_called_once()
            assert loader._cancel is False  # Reset to false
