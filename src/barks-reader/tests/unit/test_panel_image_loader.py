# ruff: noqa: SLF001, ARG005

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from barks_reader.core import panel_image_loader as loader_module
from barks_reader.core.panel_image_loader import PanelImageLoader, load_panel_pil
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


class TestLoadPanelPil:
    def test_encrypted_by_default(self) -> None:
        """The sync entry point defaults to encrypted-zip handling, like the worker."""
        mock_path = MagicMock(spec=Path)
        pil = MagicMock(spec=Image.Image)

        with patch.object(loader_module, "load_pil", return_value=pil) as mock_load_pil:
            assert load_panel_pil(mock_path) is pil

        mock_load_pil.assert_called_once_with(mock_path, encrypted_zip=True)

    def test_encrypted_flag_passed_through(self) -> None:
        mock_path = MagicMock(spec=Path)

        with patch.object(loader_module, "load_pil") as mock_load_pil:
            load_panel_pil(mock_path, encrypted_zip=False)

        mock_load_pil.assert_called_once_with(mock_path, encrypted_zip=False)


class TestPanelImageLoader:
    def test_init(self, fake_scheduler: FakeScheduler) -> None:
        loader = PanelImageLoader(fake_scheduler)
        assert loader._generation == 0

    def test_cancel_bumps_generation(self, loader: PanelImageLoader) -> None:
        loader.cancel()
        assert loader._generation == 1

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

    def test_new_load_does_not_join_previous_thread(
        self, loader: PanelImageLoader, mock_callback: MagicMock
    ) -> None:
        """A new load must never block the UI thread waiting on the previous decode."""
        mock_path = MagicMock(spec=Path)

        with patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls:
            first_thread = MagicMock()
            mock_thread_cls.return_value = first_thread

            loader.load_pil(mock_path, mock_callback)
            loader.load_pil(mock_path, mock_callback)

            first_thread.join.assert_not_called()

    def test_stale_worker_result_dropped(
        self, loader: PanelImageLoader, fake_scheduler: FakeScheduler
    ) -> None:
        """A worker superseded by a newer load must not deliver its result."""
        mock_path = MagicMock(spec=Path)
        workers: list[tuple[Any, tuple[Any, ...]]] = []

        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(loader_module, "load_pil", return_value=MagicMock(spec=Image.Image)),
            patch.object(loader_module, "convert_mode", return_value=MagicMock(spec=Image.Image)),
        ):
            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: workers.append((target, args))
            )
            callback_a = MagicMock()
            callback_b = MagicMock()
            loader.load_pil(mock_path, callback_a)
            loader.load_pil(mock_path, callback_b)

            # Run the superseded worker A after B was requested.
            target_a, args_a = workers[0]
            target_a(*args_a)
            callback_a.assert_not_called()
            assert fake_scheduler.scheduled_once_count == 0

            target_b, args_b = workers[1]
            target_b(*args_b)
            callback_b.assert_called_once()

    def test_cancel_drops_in_flight_result(
        self, loader: PanelImageLoader, mock_callback: MagicMock, fake_scheduler: FakeScheduler
    ) -> None:
        mock_path = MagicMock(spec=Path)
        workers: list[tuple[Any, tuple[Any, ...]]] = []

        with (
            patch.object(loader_module, threading.Thread.__name__) as mock_thread_cls,
            patch.object(loader_module, "load_pil", return_value=MagicMock(spec=Image.Image)),
            patch.object(loader_module, "convert_mode", return_value=MagicMock(spec=Image.Image)),
        ):
            mock_thread_cls.side_effect = lambda target, args, daemon: MagicMock(
                start=lambda: workers.append((target, args))
            )
            loader.load_pil(mock_path, mock_callback)
            loader.cancel()

            target, args = workers[0]
            target(*args)

            mock_callback.assert_not_called()
            assert fake_scheduler.scheduled_once_count == 0

    def test_stale_scheduled_delivery_dropped_on_ui_thread(
        self, loader: PanelImageLoader, mock_callback: MagicMock
    ) -> None:
        """A delivery scheduled just before a newer load bumped the generation is dropped."""
        pil = MagicMock(spec=Image.Image)
        loader._generation = 2

        loader._deliver(1, mock_callback, pil, None)
        mock_callback.assert_not_called()

        loader._deliver(2, mock_callback, pil, None)
        mock_callback.assert_called_once_with(pil, None)
