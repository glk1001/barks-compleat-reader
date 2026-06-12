# ruff: noqa: SLF001, ARG005

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import panel_image_loader as loader_module
from barks_reader.core.panel_image_loader import PanelImageLoader
from barks_reader.core.testing import FakeScheduler
from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def _synchronous_worker_thread() -> Iterator[MagicMock]:
    """Patch the loader's Thread so the worker runs synchronously on start()."""
    with patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls:
        mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
            start=lambda: target(*args)
        )
        yield mock_thread_cls


@pytest.fixture
def mock_callback() -> MagicMock:
    return MagicMock()


@pytest.fixture
def fake_scheduler() -> FakeScheduler:
    return FakeScheduler()


@pytest.fixture
def loader(fake_scheduler: FakeScheduler) -> PanelImageLoader:
    return PanelImageLoader(fake_scheduler)


class TestPanelImageLoader:
    def test_init(self, fake_scheduler: FakeScheduler) -> None:
        loader = PanelImageLoader(fake_scheduler)
        assert loader._cancel is False
        assert loader._current_thread is None

    def test_cancel(self, loader: PanelImageLoader) -> None:
        loader.cancel()
        assert loader._cancel is True

    def test_load_pil_success_invokes_callback_with_rgba_image(
        self,
        loader: PanelImageLoader,
        mock_callback: MagicMock,
        fake_scheduler: FakeScheduler,
    ) -> None:
        mock_path = MagicMock(spec=Path)
        raw_pil = MagicMock(spec=Image.Image)
        converted = MagicMock(spec=Image.Image)
        raw_pil.convert.return_value = converted

        with (
            _synchronous_worker_thread(),
            patch.object(loader_module, "load_pil", return_value=raw_pil) as mock_load_pil,
            patch.object(loader_module, "convert_mode", return_value=converted) as mock_convert,
        ):
            loader.load_pil(mock_path, mock_callback)

            mock_load_pil.assert_called_once_with(mock_path, encrypted_zip=True)
            mock_convert.assert_called_once_with(raw_pil, "RGBA")
            mock_callback.assert_called_once_with(converted, None)
            assert fake_scheduler.scheduled_once_count == 1

    def test_load_pil_error_path(
        self,
        loader: PanelImageLoader,
        mock_callback: MagicMock,
        fake_scheduler: FakeScheduler,
    ) -> None:
        mock_path = MagicMock(spec=Path)
        error = OSError("Read failed")

        with (
            _synchronous_worker_thread(),
            patch.object(loader_module, "load_pil", side_effect=error),
        ):
            loader.load_pil(mock_path, mock_callback)

            mock_callback.assert_called_once_with(None, error)
            assert fake_scheduler.scheduled_once_count == 1

    def test_worker_cancel_before_decode_skips_callback(
        self,
        loader: PanelImageLoader,
        mock_callback: MagicMock,
        fake_scheduler: FakeScheduler,
    ) -> None:
        mock_path = MagicMock(spec=Path)

        def cancel_during_load(*_a: object, **_k: object) -> MagicMock:
            loader.cancel()
            return MagicMock(spec=Image.Image)

        with (
            _synchronous_worker_thread(),
            patch.object(loader_module, "load_pil", side_effect=cancel_during_load),
            patch.object(loader_module, "convert_mode") as mock_convert,
        ):
            loader.load_pil(mock_path, mock_callback)

            # Cancel happened right after load_pil; convert_mode should not run.
            mock_convert.assert_not_called()
            assert fake_scheduler.scheduled_once_count == 0

    def test_worker_cancel_after_convert_skips_callback(
        self,
        loader: PanelImageLoader,
        mock_callback: MagicMock,
        fake_scheduler: FakeScheduler,
    ) -> None:
        mock_path = MagicMock(spec=Path)
        raw_pil = MagicMock(spec=Image.Image)

        def cancel_during_convert(*_a: object, **_k: object) -> MagicMock:
            loader.cancel()
            return MagicMock(spec=Image.Image)

        with (
            _synchronous_worker_thread(),
            patch.object(loader_module, "load_pil", return_value=raw_pil),
            patch.object(loader_module, "convert_mode", side_effect=cancel_during_convert),
        ):
            loader.load_pil(mock_path, mock_callback)

            assert fake_scheduler.scheduled_once_count == 0

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
